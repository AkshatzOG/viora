from __future__ import annotations

import json
import re

from agent.memory import MusicMemory


CONTROL_EXACT = {
    "pause": "PAUSE", "pause music": "PAUSE",
    "resume": "RESUME", "resume music": "RESUME", "continue": "RESUME",
    "next": "NEXT", "skip": "NEXT", "skip song": "NEXT", "next song": "NEXT", "play next": "NEXT",
    "previous": "PREVIOUS", "prev": "PREVIOUS", "back": "PREVIOUS", "go back": "PREVIOUS", "previous song": "PREVIOUS",
    "clear filter": "CLEAR_FILTER", "clear filters": "CLEAR_FILTER", "reset filter": "CLEAR_FILTER",
    "clear queue": "CLEAR_QUEUE", "clear the queue": "CLEAR_QUEUE", "empty queue": "CLEAR_QUEUE",
    "shuffle": "SHUFFLE", "shuffle queue": "SHUFFLE",
    "close": "CLOSE", "close agent": "CLOSE", "quit": "CLOSE", "quit agent": "CLOSE", "exit": "CLOSE", "exit agent": "CLOSE", "stop agent": "CLOSE",
}

MOODS = ("chill", "relaxing", "relax", "sad", "hype", "energetic", "workout", "calm", "focus", "happy", "romantic", "party", "late night", "feel good", "rainy")
MEDIA_PODCAST = re.compile(r"\b(podcast|podcasts|episode|episodes|talk show|interview)\b", re.I)


def _base(text: str, action="PLAY", **extra):
    return {
        "action": action,
        "media_type": "PODCAST" if MEDIA_PODCAST.search(text) else "MUSIC",
        "query": text,
        "count": 1,
        "scope": "once",
        "genre": None,
        "artist": None,
        "language": None,
        "mood": None,
        "variant": None,
        "playlist_name": None,
        "needs_current_info": False,
        "reason": "local parser",
        **extra,
    }


def _extract_count(text: str) -> int:
    m = re.search(r"\b(\d{1,2})\b", text)
    return max(1, min(int(m.group(1)), 20)) if m else 1


def _strip_command(text: str) -> str:
    s = text.strip()
    patterns = [
        r"^(please\s+)?(play|queue|add|search|find|look up|show|list)\s+",
        r"^(please\s+)?(give me|give us|suggest|recommend)\s+",
    ]
    for p in patterns:
        s = re.sub(p, "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip(" .")


def _strip_trend_words(text: str) -> str:
    """Keep the requested music subject; discard the command and time window."""
    value = str(text or "").strip()
    value = re.sub(r"^(?:please\s+)?(?:play|queue|find|search|show|recommend|suggest)\s+", "", value, flags=re.I)
    value = re.sub(r"\b(?:top|trending|popular|viral|chart(?:s)?|latest|new|this|week|month|today|tonight|currently|the|of|in|for|me|music|songs?|tracks?)\b", " ", value, flags=re.I)
    value = re.sub(r"\b(?:today|tonight|right now|currently|this week|this month|last week)\b", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip(" .,!?:;")


class MusicBrain:
    def __init__(self):
        self.memory = MusicMemory()

    def _local_control(self, text: str):
        lower = re.sub(r"\s+", " ", text.strip().lower())
        if lower in CONTROL_EXACT:
            return _base(text, action=CONTROL_EXACT[lower], reason="local control")
        # Conversational controls.
        if re.fullmatch(r"(please )?skip( this)?( song|track)?", lower):
            return _base(text, action="NEXT", reason="local control")
        if re.fullmatch(r"(go )?back( one( song|track))?", lower):
            return _base(text, action="PREVIOUS", reason="local control")
        return None

    def _fast_parse(self, text: str):
        control = self._local_control(text)
        if control:
            return control
        lower = text.lower().strip()
        count = _extract_count(lower)

        # Explicit playlist/library commands.
        m = re.match(r"^(?:play|open|show)\s+(?:my\s+)?playlist\s+(.+)$", lower)
        if m:
            return _base(text, action="PLAYLIST", playlist_name=m.group(1).strip(), reason="playlist command")
        m = re.match(r"^(?:queue|add)\s+(?:my\s+)?playlist\s+(.+)$", lower)
        if m:
            return _base(text, action="QUEUE_PLAYLIST", playlist_name=m.group(1).strip(), reason="playlist command")
        if re.fullmatch(r"(?:play|open)\s+(?:my\s+)?favorites", lower):
            return _base(text, action="FAVORITES", count=count, reason="favorites command")
        if re.fullmatch(r"(?:play|show)\s+(?:my\s+)?history|(?:show)\s+recent(?:ly played)?", lower):
            return _base(text, action="HISTORY", count=count, reason="history command")
        if re.fullmatch(r"(?:play|search)\s+(?:my\s+)?downloads|(?:show|open)\s+(?:my\s+)?library", lower):
            return _base(text, action="LIBRARY", count=count, reason="library command")

        # Explicit favorite/download actions for the current track.
        if re.fullmatch(r"(?:favorite|favourite|like)\s+(?:this|current|song|track)", lower):
            return _base(text, action="FAVORITE_CURRENT", reason="favorite current")
        if re.fullmatch(r"un(?:favorite|favourite|like)\s+(?:this|current|song|track)", lower):
            return _base(text, action="UNFAVORITE_CURRENT", reason="favorite current")
        if re.fullmatch(r"download\s+(?:this|current|song|track)", lower):
            return _base(text, action="DOWNLOAD_CURRENT", reason="download current")
        m = re.match(r"^(?:add|save)\s+(?:this|current|song|track)\s+to\s+(?:my\s+)?(?:playlist\s+)?(.+)$", lower)
        if m:
            return _base(text, action="ADD_CURRENT_PLAYLIST", playlist_name=m.group(1).strip(), reason="playlist current")

        # Similar/recommendation requests must be their own action, never a YouTube query literal.
        similar = any(x in lower for x in (
            "similar to this", "something similar", "play something similar", "more like this",
            "like this", "similar to it", "something like this", "songs like this", "songs similar to this",
        ))
        if similar:
            current = self.memory.current_song
            if current:
                return _base(text, action="SIMILAR", query=str(current.get("title") or ""), count=max(1, count), reason="similar request")
            return _base(text, action="SIMILAR", query="", count=max(1, count), reason="similar request without current")

        rec = any(x in lower for x in (
            "recommend", "suggest", "something i would like", "something i'll like", "for me", "for you",
            "surprise me", "what should i listen", "give me something", "play something",
        ))
        current_request = any(x in lower for x in ("trending", "this week", "this month", "right now", "latest", "popular now", "currently", "new releases"))
        if current_request:
            topic = _strip_trend_words(text)
            explicit_count = bool(re.search(r"\b\d{1,2}\b", lower))
            return _base(
                text,
                action="TRENDING",
                query=topic,
                count=count if explicit_count else 10,
                needs_current_info=True,
                reason="current discovery",
            )
        if rec:
            mood = next((m for m in MOODS if m in lower), None)
            cleaned = _strip_command(text)
            if cleaned.lower() in {"something", "something new", "music", "some music", "songs", "what should i listen to", "what should i listen to?", "what should i play", "for you"}:
                cleaned = ""
            return _base(text, action="RECOMMEND", query=cleaned, count=count, mood=mood, reason="recommendation request")

        # Search intent should remain search, not playback.
        if re.match(r"^(search|find|look up|show me|list)\b", lower):
            media = "PODCAST" if MEDIA_PODCAST.search(lower) else "MUSIC"
            query = _strip_command(text)
            return _base(text, action="SEARCH", query=query or ("podcasts" if media == "PODCAST" else "music"), count=count, media_type=media, reason="search request")

        if re.search(r"\b(queue|add)\b", lower):
            action = "QUEUE"
        else:
            action = "PLAY"

        media = "PODCAST" if MEDIA_PODCAST.search(lower) else "MUSIC"
        query = _strip_command(text)
        query = re.sub(r"\b(\d{1,2})\b", " ", query)
        query = re.sub(r"\s+", " ", query).strip(" .")

        mood = next((m for m in MOODS if re.search(rf"\b{re.escape(m)}\b", lower)), None)
        if query in {"", "something", "some", "music", "songs"} and mood:
            query = f"{mood} music"
        if not query:
            return None

        # Pull common variant words into a structured field while keeping the query intact enough for search.
        variant = None
        for v in ("slowed", "reverb", "sped up", "nightcore", "remix", "acoustic", "8d", "live"):
            if re.search(rf"\b{re.escape(v)}\b", lower):
                variant = v
                break

        # Simple artist extraction: "song by artist".
        artist = None
        m = re.match(r"(.+?)\s+by\s+(.+)$", query, flags=re.I)
        if m and m.group(2).strip():
            query = m.group(1).strip()
            artist = m.group(2).strip()

        return _base(
            text,
            action=action,
            query=query,
            count=count,
            media_type=media,
            mood=mood,
            artist=artist,
            variant=variant,
            reason="fast music parser" if media == "MUSIC" else "fast podcast parser",
        )

    def understand(self, user_text):
        text = (user_text or "").strip()
        if not text:
            return _base("", action="SEARCH", query="music", reason="empty request")
        parsed = self._fast_parse(text)
        if parsed:
            return parsed
        # Deliberately do not call a remote/local text model in v15.0.
        # Unknown natural-language requests are still routed as best-effort searches.
        return _base(text, action="SEARCH", query=text, reason="safe fallback")

    def remember_song(self, track):
        self.memory.remember_song(track)

    def set_filters(self, **filters):
        self.memory.set_filters(**filters)

    def clear_filters(self):
        self.memory.clear_filters()

    def remember(self, user_text, result):
        self.memory.add_message("user", user_text)
        self.memory.add_message("assistant", json.dumps(result, ensure_ascii=False))
