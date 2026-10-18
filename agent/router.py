from __future__ import annotations

from core.database import get_db
from core.connectivity import network_available
from core.downloader import download_track
from core.library import find_local, normalize_track_for_client, is_local_file
from core.player_bridge import play as smart_play, queue as smart_queue
from core.recommender import home_recommendations, similar_to, prepare_for_playback
from tools.ranker import find_best_exact_song, rank_tracks
from tools.youtube import (
    find_song,
    discover_music,
    discover_podcasts,
    discover_current,
    prepare_tracks,
)
from tools.playback import player


class AgentRouter:
    def __init__(self, brain):
        self.brain = brain
        self.last_intent = {}
        self.last_tracks = []

    @staticmethod
    def _playable_local(track):
        return bool(track and track.get("local_path") and is_local_file(track["local_path"]))

    def _search_local_first(self, query, artist=None):
        rows = find_local(query, limit=20)
        if artist:
            target = f"{query} {artist}".strip()
            rows = sorted(rows, key=lambda t: (artist.lower() not in str(t.get("artist") or "").lower(), -int(t.get("is_favorite") or 0)))
        return [normalize_track_for_client(x) for x in rows]

    def _resolve(self, intent):
        action = intent.get("action")
        media = intent.get("media_type", "MUSIC")
        query = (intent.get("query") or "").strip()
        count = max(1, min(int(intent.get("count") or 1), 20))

        # Keep natural-language agent requests subject to the same connection
        # mode as buttons and search. The old router could bypass Offline mode.
        offline = get_db().get_setting("playback_mode", "auto") == "offline" or not network_available()
        if offline:
            if action in {"PLAY", "QUEUE", "SEARCH"}:
                rows = find_local(query, limit=max(20, count * 4)) if query else get_db().downloaded_tracks(100)
                return rank_tracks(rows, query=query, limit=count, media_type=media, artist=intent.get("artist"), variant=intent.get("variant"), prefer_tracks=True)
            if action in {"RECOMMEND", "TRENDING"}:
                rows = [x for x in get_db().downloaded_tracks(300) if self._playable_local(x)]
                if action == "TRENDING" and query:
                    terms = [term for term in query.casefold().split() if len(term) > 2]
                    rows = [
                        track for track in rows
                        if any(term in " ".join(str(track.get(key) or "") for key in ("title", "artist", "channel")).casefold() for term in terms)
                    ]
                return rank_tracks(rows, query=query, limit=count, prefer_tracks=bool(query))
            if action == "SIMILAR":
                current = self.brain.memory.current_song or {}
                rows = [x for x in get_db().downloaded_tracks(300) if self._playable_local(x) and str(x.get("id")) != str(current.get("id"))]
                return rank_tracks(rows, query=str(current.get("artist") or current.get("title") or query), limit=count)

        if action == "TRENDING":
            return discover_current(query, count, media)

        if action == "SIMILAR":
            current = self.brain.memory.current_song
            if not current:
                return []
            return similar_to(current, count)

        if action == "RECOMMEND":
            data = home_recommendations()
            candidates = data.get("for_you") or data.get("discover") or []
            if query:
                # A mood/activity phrase is used as an extra search/relevance signal.
                candidates = discover_music(
                    query,
                    count=max(count * 2, 8),
                    mood=intent.get("mood"),
                    genre=intent.get("genre"),
                    language=intent.get("language"),
                ) + candidates
                return rank_tracks(candidates, query=query, limit=count, prefer_tracks=True)
            return candidates[:count]

        if action in {"FAVORITES", "HISTORY", "LIBRARY"}:
            if action == "FAVORITES":
                return get_db().list_tracks(limit=max(count, 20), favorites_only=True)[:count]
            if action == "HISTORY":
                return get_db().history(limit=max(count, 20))[:count]
            return get_db().list_tracks(limit=max(count, 20), downloaded_only=True)[:count]

        if action in {"PLAYLIST", "QUEUE_PLAYLIST"}:
            name = intent.get("playlist_name") or ""
            playlists = get_db().playlists()
            target = next((p for p in playlists if p["name"].casefold() == name.casefold()), None)
            if not target:
                target = next((p for p in playlists if name.casefold() in p["name"].casefold()), None)
            if not target:
                return []
            return get_db().playlist_get(target["id"])["tracks"][:]

        # Local-first exact playback. If it exists, don't burn a YouTube search.
        if action in {"PLAY", "QUEUE"} and query and media == "MUSIC":
            local = self._search_local_first(query, intent.get("artist"))
            exact_local = find_best_exact_song(local, query, intent.get("artist"), intent.get("variant"), media_type=media)
            if exact_local:
                return [exact_local]

        if media == "PODCAST":
            return discover_podcasts(query, count)

        artist = intent.get("artist")
        variant = intent.get("variant")
        if count == 1 and action in {"PLAY", "QUEUE"} and intent.get("reason") == "fast music parser" and not intent.get("mood"):
            track = find_song(query, artist, variant)
            return [track] if track else []

        return discover_music(
            query or "music",
            count,
            mood=intent.get("mood"),
            genre=intent.get("genre"),
            artist=artist,
            language=intent.get("language"),
            variant=variant,
        )

    def _save_track(self, track):
        try:
            get_db().upsert_track(track)
        except Exception as exc:
            print("[router] track persistence failed:", repr(exc))

    def _current(self):
        return player.current_track

    def process(self, user_text):
        print(f"\n[agent] USER: {user_text}")
        intent = self.brain.understand(user_text)
        self.last_intent = intent
        print("[agent] INTENT:", intent)
        action = intent.get("action", "PLAY")
        self.last_tracks = []
        reply = ""

        if action == "PAUSE":
            player.pause(); reply = "Paused."
        elif action == "RESUME":
            player.resume(); reply = "Resumed."
        elif action == "NEXT":
            moved = player.next(); reply = "Skipped to the next track." if moved else "There is no next track in the queue."
        elif action == "PREVIOUS":
            moved = player.previous(); reply = "Going back to the previous track." if moved else "There is no previous track available."
        elif action == "CLEAR_FILTER":
            self.brain.clear_filters(); reply = "Session filter cleared."
        elif action == "CLEAR_QUEUE":
            player.clear_queue(); reply = "Queue cleared."
        elif action == "SHUFFLE":
            tracks = list(player._upcoming_tracks)
            player.shuffle_queue()
            reply = "Queue shuffled." if tracks else "There is nothing to shuffle."
        elif action == "CLOSE":
            reply = "Closing Viora."
        elif action in {"FAVORITE_CURRENT", "UNFAVORITE_CURRENT", "DOWNLOAD_CURRENT", "ADD_CURRENT_PLAYLIST"}:
            current = self._current()
            if not current:
                reply = "Nothing is playing right now."
            elif action in {"FAVORITE_CURRENT", "UNFAVORITE_CURRENT"}:
                value = action == "FAVORITE_CURRENT"
                get_db().set_favorite(current, value)
                reply = "Added to your favorites." if value else "Removed from your favorites."
            elif action == "DOWNLOAD_CURRENT":
                try:
                    result = download_track(current)
                    reply = f"Downloaded {current.get('title','this track')} for offline listening." if result.get("status") == "downloaded" else "Download started."
                except Exception as exc:
                    reply = f"I couldn't download that track: {exc}"
            else:
                name = intent.get("playlist_name")
                target = next((p for p in get_db().playlists() if p["name"].casefold() == str(name).casefold()), None)
                if not target:
                    try:
                        pid = get_db().playlist_create(name)
                    except Exception as exc:
                        reply = f"I couldn't create that playlist: {exc}"
                    else:
                        target = get_db().playlist_get(pid)
                if target:
                    get_db().playlist_add(target["id"], current)
                    reply = f"Added {current.get('title','the song')} to {target['name']}."
        else:
            tracks = self._resolve(intent)
            self.last_tracks = list(tracks or [])
            if not tracks:
                if action == "SIMILAR" and intent.get("reason") == "similar request without current":
                    reply = "Play a song first, and I'll find something that fits it."
                elif action in {"FAVORITES", "HISTORY", "LIBRARY"}:
                    reply = "There is nothing here yet. Start listening and I’ll build this up for you."
                else:
                    reply = f"I couldn't find a suitable result for '{intent.get('query', user_text)}'."
            elif action == "SEARCH":
                for track in tracks:
                    self._save_track(track)
                reply = "Found: " + "; ".join(t.get("title", "Unknown") for t in tracks[:5])
            elif action in {"QUEUE_PLAYLIST", "QUEUE"}:
                prepared = [t for t in tracks if self._playable_local(t)]
                online = [t for t in tracks if not self._playable_local(t)]
                if online:
                    prepared.extend(prepare_tracks(online, workers=min(6, len(online))))
                queued = player.queue(prepared)
                for t in prepared: self._save_track(t)
                reply = "Queued: " + "; ".join(t.get("title", "Unknown") for t in prepared)
                if not queued: reply = "I found the tracks, but could not add them to the queue."
            elif action in {"PLAYLIST", "FAVORITES", "HISTORY", "LIBRARY", "RECOMMEND", "SIMILAR", "TRENDING", "PLAY"}:
                prepared = []
                local = [t for t in tracks if self._playable_local(t)]
                online = [t for t in tracks if not self._playable_local(t)]
                prepared.extend(local)
                if online:
                    prepared.extend(prepare_tracks(online, workers=min(6, len(online))))
                if not prepared:
                    reply = "Those tracks aren't playable right now."
                else:
                    self.last_tracks = list(prepared)
                    first, rest = prepared[0], prepared[1:]
                    for t in prepared: self._save_track(t)
                    player_ok = smart_play(first, preserve_queue=True)
                    if rest:
                        smart_queue(rest)
                    self.brain.remember_song(first)
                    reply = f"Now playing: {first.get('title','Unknown')}"
            else:
                reply = "Done."

        self.brain.remember(user_text, {**intent, "reply": reply})
        return reply
