from tools.youtube import (
    find_song,
    discover_music,
    discover_podcasts,
    discover_current,
    prepare_tracks,
)
from tools.discovery import recommend_similar
from tools.playback import player


class AgentRouter:
    def __init__(self, brain):
        self.brain = brain

    def _resolve(self, intent):
        media = intent.get("media_type", "MUSIC")
        query = intent.get("query") or "music"
        count = intent.get("count", 1)

        if intent.get("needs_current_info"):
            return discover_current(query, count, media)

        if intent.get("reason") == "similar request":
            current = self.brain.memory.current_song or {}
            current_title = current.get("title") or query
            current_artist = self.brain.memory.current_artist

            return recommend_similar(
                current_title,
                current_artist,
                count,
                query,
            )

        if media == "PODCAST":
            return discover_podcasts(query, count)

        artist = intent.get("artist")
        variant = intent.get("variant")

        # Only exact song requests use the targeted single-song resolver.
        # Mood/genre/discovery requests must use a candidate pool.
        if (
            count == 1
            and intent.get("reason") in {
                "fast music parser",
                "fallback parser",
            }
            and not intent.get("mood")
            and not intent.get("genre")
            and not intent.get("language")
        ):
            track = find_song(
                query,
                artist,
                variant,
            )
            return [track] if track else []

        return discover_music(
            query,
            count,
            mood=intent.get("mood"),
            genre=intent.get("genre"),
            artist=artist,
            language=intent.get("language"),
            variant=variant,
        )

    def process(self, user_text):
        print(f"\n[agent] USER: {user_text}")

        intent = self.brain.understand(user_text)

        print("[agent] INTENT:", intent)
        self.last_intent = intent

        action = intent.get("action", "PLAY")

        if action == "PAUSE":
            player.pause()
            reply = "Paused."

        elif action == "RESUME":
            player.resume()
            reply = "Resumed."

        elif action == "NEXT":
            moved = player.next()
            reply = "Skipped to the next track." if moved else "There is no next track in the queue."

        elif action == "PREVIOUS":
            moved = player.previous()
            reply = "Going back to the previous track." if moved else "There is no previous track available."

        elif action == "CLEAR_FILTER":
            self.brain.clear_filters()
            reply = "Session filter cleared."

        elif action == "CLEAR_QUEUE":
            player.clear_queue()
            reply = "Queue cleared."

        elif action == "CLOSE":
            reply = "Closing Local Music Agent."

        else:
            tracks = self._resolve(intent)

            if not tracks:
                reply = (
                    f"I couldn't find a suitable result for "
                    f"'{intent.get('query', user_text)}'."
                )

            elif action == "SEARCH":
                reply = (
                    "I found: "
                    + "; ".join(track["title"] for track in tracks)
                )

            elif action == "QUEUE":
                # Resolve the audio streams NOW, while the current song is
                # still playing. This prevents a long yt-dlp delay at EOF.
                tracks = prepare_tracks(tracks, workers=min(6, max(1, len(tracks))))
                queued = player.queue(tracks)
                reply = (
                    "Queued: "
                    + "; ".join(track["title"] for track in tracks)
                ) if queued else "I found the tracks, but could not add them to the queue."

            else:
                tracks = prepare_tracks(tracks, workers=4)

                first = tracks[0]
                player.play(first, preserve_queue=True)

                if len(tracks) > 1:
                    player.queue(tracks[1:])

                self.brain.remember_song(first)
                reply = f"Now playing: {first['title']}"

        self.brain.remember(
            user_text,
            {
                **intent,
                "reply": reply,
            },
        )

        return reply
