import json
import re
import requests

from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT
from agent.memory import MusicMemory


SYSTEM_PROMPT = """
You are Local Music Agent, a conversational music and podcast assistant.

Return ONLY valid JSON:
{
  "action": "PLAY|QUEUE|SEARCH|PAUSE|RESUME|NEXT|PREVIOUS|CLEAR_FILTER|CLOSE",
  "media_type": "MUSIC|PODCAST",
  "query": "string",
  "count": 1,
  "scope": "once|session",
  "genre": null,
  "artist": null,
  "language": null,
  "mood": null,
  "variant": null,
  "needs_current_info": false,
  "reason": "short explanation"
}

Rules:
- Explicit podcast/episode/talk/interview => PODCAST.
- queue/add/up next => QUEUE, never PLAY.
- play => PLAY.
- search/find/list/show => SEARCH, never playback.
- close/quit/exit/stop agent => CLOSE.
- pause/resume/next/previous => control actions.
- similar/like this/more like this uses the current playing song as context.
- trending/latest/current/this week/right now => needs_current_info=true.
- Japanese/Korean/Hindi/etc. are languages, not genres.
- "play something chill" => mood="chill", query="chill music".
- Do not invent current chart facts.
- count must be 1..20.
"""


class MusicBrain:
    def __init__(self):
        self.memory = MusicMemory()

    def _base(self, text, action="PLAY", **extra):
        return {
            "action": action,
            "media_type": "MUSIC",
            "query": text,
            "count": 1,
            "scope": "once",
            "genre": None,
            "artist": None,
            "language": None,
            "mood": None,
            "variant": None,
            "needs_current_info": False,
            "reason": "fast parser",
            **extra,
        }

    def _local_control(self, text):
        lower = text.strip().lower()

        mapping = {
            "pause": "PAUSE",
            "pause music": "PAUSE",
            "resume": "RESUME",
            "resume music": "RESUME",
            "continue": "RESUME",
            "next": "NEXT",
            "skip": "NEXT",
            "next song": "NEXT",
            "skip song": "NEXT",
            "previous": "PREVIOUS",
            "back": "PREVIOUS",
            "go back": "PREVIOUS",
            "previous song": "PREVIOUS",
            "clear filter": "CLEAR_FILTER",
            "clear queue": "CLEAR_QUEUE",
            "clear the queue": "CLEAR_QUEUE",
            "empty queue": "CLEAR_QUEUE",
            "empty the queue": "CLEAR_QUEUE",
            "clear filters": "CLEAR_FILTER",
            "reset filter": "CLEAR_FILTER",
            "remove filter": "CLEAR_FILTER",
            "close": "CLOSE",
            "close agent": "CLOSE",
            "quit": "CLOSE",
            "quit agent": "CLOSE",
            "exit": "CLOSE",
            "exit agent": "CLOSE",
            "stop agent": "CLOSE",
        }

        action = mapping.get(lower)
        if action:
            return self._base(text, action=action, reason="local control")

        return None

    def _fast_parse(self, text):
        control = self._local_control(text)
        if control:
            return control

        lower = text.lower().strip()

        count_match = re.search(r"\b(\d+)\b", lower)
        count = max(1, min(int(count_match.group(1)), 20)) if count_match else 1

        if re.search(r"\b(queue|add|up next)\b", lower):
            action = "QUEUE"
        elif re.search(r"\b(search|find|look up|show me|list)\b", lower):
            action = "SEARCH"
        else:
            action = "PLAY"

        media_type = (
            "PODCAST"
            if re.search(
                r"\b(podcast|podcasts|episode|episodes|talk show|interview)\b",
                lower,
            )
            else "MUSIC"
        )

        current = self.memory.current_song
        current_title = current.get("title") if current else None
        current_artist = self.memory.current_artist

        similar = any(
            phrase in lower
            for phrase in (
                "similar to this",
                "something similar",
                "play something similar",
                "similar",
                "like this",
                "more like this",
                "similar to it",
                "something like this",
                "songs similar to this",
                "songs like this",
            )
        )

        if similar and current_title:
            return self._base(
                text,
                action=action,
                query=f"similar songs to {current_title}",
                count=count,
                artist=current_artist,
                reason="similar request",
            )

        current_request = any(
            phrase in lower
            for phrase in (
                "trending",
                "this week",
                "this month",
                "right now",
                "latest",
                "popular now",
                "currently",
            )
        )

        if current_request:
            return self._base(
                text,
                action=action,
                query=(
                    "trending podcasts this week"
                    if media_type == "PODCAST"
                    else "trending music this week"
                ),
                count=count,
                media_type=media_type,
                needs_current_info=True,
                reason="current discovery request",
            )

        if media_type == "PODCAST":
            cleaned = lower
            cleaned = re.sub(
                r"\b(play|queue|add|search|find|podcast|podcasts|episode|episodes|talk show|interview)\b",
                " ",
                cleaned,
            )
            cleaned = re.sub(r"\b\d+\b", " ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

            cleaned = re.sub(r"^(a|an|the)\s+", "", cleaned).strip()
            if cleaned.startswith("by "):
                cleaned = cleaned[3:].strip()

            return self._base(
                text,
                action=action,
                query=cleaned or "podcast",
                count=count,
                media_type="PODCAST",
                reason="fast podcast parser",
            )

        mood = None
        for candidate in (
            "chill",
            "relaxing",
            "sad",
            "hype",
            "energetic",
            "workout",
            "calm",
            "focus",
            "happy",
            "romantic",
        ):
            if re.search(rf"\b{re.escape(candidate)}\b", lower):
                mood = candidate
                break

        cleaned = re.sub(
            r"\b(play|queue|add|search|find|some|something|songs?|music|tracks?)\b",
            " ",
            lower,
        )
        cleaned = re.sub(r"\b\d+\b", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if mood and (not cleaned or cleaned == mood):
            query = f"{mood} music"
        elif cleaned:
            query = cleaned
        else:
            return None

        # Preserve ordinary song/title requests on the fast path.
        if action in {"PLAY", "QUEUE"} and (" by " in lower or not mood):
            return self._base(
                text,
                action=action,
                query=query,
                count=count,
                mood=mood,
                reason="fast music parser",
            )

        if mood:
            return self._base(
                text,
                action=action,
                query=query,
                count=count,
                mood=mood,
                reason="fast mood parser",
            )

        return None

    def _fallback(self, text):
        fast = self._fast_parse(text)
        if fast:
            return fast

        lower = text.lower()
        current = self.memory.current_song
        current_title = current.get("title") if current else None

        query = text
        if current_title and any(
            p in lower for p in ("similar", "like this", "more like")
        ):
            query = f"similar songs to {current_title}"

        action = (
            "QUEUE"
            if any(w in lower for w in ("queue", "add", "up next"))
            else "PLAY"
        )

        if any(w in lower for w in ("search", "find", "look up")):
            action = "SEARCH"

        return self._base(
            text,
            action=action,
            query=query,
            reason="fallback parser",
        )

    def _call_ollama(self, user_text):
        prompt = (
            f"Current context:\n"
            f"{json.dumps(self.memory.context(), ensure_ascii=False)}\n\n"
            f"Recent conversation:\n"
            f"{json.dumps(self.memory.conversation[-10:], ensure_ascii=False)}\n\n"
            f"User:\n{user_text}"
        )

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 220,
                    "num_ctx": 2048,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()

        return json.loads(response.json().get("response", "{}"))

    def understand(self, user_text):
        text = user_text.strip()

        if not text:
            return self._fallback(text)

        fast = self._fast_parse(text)

        if fast:
            # Fast parser owns deterministic commands and obvious requests.
            # Ollama remains available for genuinely ambiguous conversation.
            result = fast
        else:
            try:
                result = self._call_ollama(text)
            except Exception as exc:
                print("[brain] Ollama unavailable/failed:", repr(exc))
                result = self._fallback(text)

        defaults = self._fallback(text)
        merged = {**defaults, **(result if isinstance(result, dict) else {})}

        merged["action"] = str(merged.get("action", "PLAY")).upper()

        allowed = {
            "PLAY",
            "QUEUE",
            "SEARCH",
            "PAUSE",
            "RESUME",
            "NEXT",
            "PREVIOUS",
            "CLEAR_FILTER",
            "CLEAR_QUEUE",
            "CLOSE",
        }

        if merged["action"] not in allowed:
            merged["action"] = defaults["action"]

        merged["media_type"] = str(
            merged.get("media_type", "MUSIC")
        ).upper()

        if merged["media_type"] not in {"MUSIC", "PODCAST"}:
            merged["media_type"] = "MUSIC"

        merged["scope"] = str(merged.get("scope", "once")).lower()

        if merged["scope"] not in {"once", "session"}:
            merged["scope"] = "once"

        try:
            merged["count"] = max(
                1,
                min(int(merged.get("count", 1)), 20),
            )
        except (TypeError, ValueError):
            merged["count"] = 1

        merged["needs_current_info"] = bool(
            merged.get("needs_current_info", False)
        )

        return merged

    def remember_song(self, track):
        self.memory.remember_song(track)

    def set_filters(self, **filters):
        self.memory.set_filters(**filters)

    def clear_filters(self):
        self.memory.clear_filters()

    def remember(self, user_text, result):
        self.memory.add_message("user", user_text)
        self.memory.add_message(
            "assistant",
            json.dumps(result, ensure_ascii=False),
        )
