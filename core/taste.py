from __future__ import annotations

import math
import re
import time
from collections import Counter
from typing import Any

from core.database import get_db
from tools.ranker import normalize_text

MOOD_WORDS = {
    "chill": {"chill", "relax", "relaxing", "calm", "lofi", "acoustic", "soft"},
    "sad": {"sad", "emotional", "heartbreak", "melancholy", "alone", "cry"},
    "hype": {"hype", "energetic", "energy", "workout", "gym", "bass", "phonk"},
    "focus": {"focus", "study", "instrumental", "ambient", "concentration"},
    "romantic": {"romantic", "love", "couple", "date", "valentine"},
    "happy": {"happy", "feel good", "good vibes", "summer", "fun"},
    "party": {"party", "dance", "club", "edm", "dj"},
    "late night": {"night", "midnight", "after dark", "late night", "rain"},
}


def _tokens(value: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_text(value or "")))


def profile():
    return get_db().get_onboarding()


def update_from_event(track: dict[str, Any], event: str = "play"):
    # Taste is derived from actual behavior through track counts/skips and
    # onboarding; this helper is intentionally lightweight and data-local.
    return None


def _profile_tokens(p: dict[str, Any]) -> set[str]:
    values = []
    for key in ("favorite_artists", "genres", "languages", "moods"):
        values.extend(p.get(key) or [])
    return _tokens(" ".join(values))


def _track_tokens(track: dict[str, Any]) -> set[str]:
    return _tokens(" ".join(str(track.get(k) or "") for k in ("title", "artist", "channel")))


def _mood_score(track: dict[str, Any], moods: list[str]) -> float:
    text = normalize_text(" ".join(str(track.get(k) or "") for k in ("title", "artist", "channel")))
    if not moods:
        return 0.0
    score = 0.0
    for mood in moods:
        words = MOOD_WORDS.get(normalize_text(mood), {normalize_text(mood)})
        score = max(score, min(1.0, sum(1 for w in words if w in text) / max(1, len(words) / 4)))
    return score


def score(track: dict[str, Any], p: dict[str, Any], recent_ids: set[str] | None = None, source_query: str = "", section="for_you") -> float:
    recent_ids = recent_ids or set()
    text_tokens = _track_tokens(track)
    score = 0.0

    fav_artists = [normalize_text(x) for x in p.get("favorite_artists") or []]
    genres = [normalize_text(x) for x in p.get("genres") or []]
    languages = [normalize_text(x) for x in p.get("languages") or []]
    moods = [normalize_text(x) for x in p.get("moods") or []]
    text = normalize_text(" ".join(str(track.get(k) or "") for k in ("title", "artist", "channel", "source_query")))

    for artist in fav_artists:
        if artist and artist in text:
            score += 55
    for genre in genres:
        if genre and genre in text or (_tokens(genre) & text_tokens):
            score += 16
    for lang in languages:
        if lang and lang in text:
            score += 8

    score += 22 * _mood_score(track, moods)

    if source_query:
        q = _tokens(source_query)
        overlap = len(q & text_tokens) / max(1, len(q))
        score += overlap * 18

    plays = float(track.get("play_count") or 0)
    skips = float(track.get("skip_count") or 0)
    score += min(20, math.log1p(plays) * 7)
    score -= min(18, math.log1p(skips) * 8)

    if recent_ids and str(track.get("id")) in recent_ids:
        score -= 34

    if track.get("is_favorite"):
        score += 35

    score += max(0.0, min(1.0, float(track.get("completion_rate") or 0))) * 18
    score -= max(0.0, min(1.0, float(track.get("skip_rate") or 0))) * 20

    if section == "discover":
        score += 22 if not track.get("play_count") else -12
    elif section == "because":
        score += 18 if track.get("artist") else 0

    level = p.get("discovery_level", "balanced")
    if level == "familiar":
        score += min(15, plays * 2)
        score -= 10 if not plays else 0
    elif level == "explorer":
        score += 14 if not plays else 0
        score -= min(12, plays * 0.5)

    return score


def infer_taste_summary():
    db = get_db()
    p = profile()
    return {
        "onboarding": p,
        "top_artists": db.frequent_artists(12),
        "stats": db.stats(),
    }
