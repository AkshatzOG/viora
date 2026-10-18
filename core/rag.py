"""Small, local retrieval layer for Viora's grounded music assistant.

This intentionally uses the existing SQLite catalog and behavior signals. It
does not call a hosted model or fabricate catalog entries; responses are
assembled from retrieved tracks, taste settings and listening history.
"""
from __future__ import annotations

import re

from core.database import get_db
from tools.ranker import normalize_text


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", normalize_text(text)))


def retrieve_context(query: str, db=None, limit: int = 8) -> dict:
    db = db or get_db()
    query_tokens = _tokens(query)
    pool: dict[str, tuple[dict, set[str]]] = {}

    def add(rows, source):
        for row in rows or []:
            track = dict(row)
            identity = str(track.get("id") or track.get("track_key") or track.get("track_id") or "")
            if not identity:
                continue
            track["id"] = identity
            current, reasons = pool.get(identity, (track, set()))
            # History rows include aliases; regular track fields remain the
            # canonical source of metadata for the assistant.
            for key in ("title", "artist", "channel", "duration", "thumbnail", "watch_url", "local_path", "is_downloaded", "is_favorite", "play_count", "skip_count", "completion_rate", "skip_rate"):
                if current.get(key) is None and track.get(key) is not None:
                    current[key] = track[key]
            reasons.add(source)
            pool[identity] = (current, reasons)

    if query.strip():
        add(db.search_tracks(query, limit=40), "catalog match")
    add(db.list_tracks(limit=30, favorites_only=True), "favorite")
    add(db.recent_tracks(30), "recent listen")
    add(db.downloaded_tracks(limit=40), "offline library")

    ranked = []
    for track, reasons in pool.values():
        text = " ".join(str(track.get(k) or "") for k in ("title", "artist", "channel"))
        words = _tokens(text)
        overlap = len(query_tokens & words) / max(1, len(query_tokens))
        score = overlap * 5
        if track.get("is_favorite"):
            score += 1.4
        if track.get("local_path"):
            score += 0.6
        score += min(1, int(track.get("play_count") or 0) / 10) * 0.5
        if "catalog match" in reasons:
            score += 0.8
        ranked.append((score, track, reasons))
    ranked.sort(key=lambda item: (item[0], float(item[1].get("last_played_at") or 0)), reverse=True)

    taste = db.get_onboarding()
    history = db.recent_tracks(8)
    favorites = db.list_tracks(limit=8, favorites_only=True)
    playlists = db.playlists()
    artists = db.frequent_artists(8)
    tracks = []
    for score, track, reasons in ranked[:max(1, min(int(limit), 20))]:
        track = dict(track)
        track["retrieval_score"] = round(score, 3)
        track["retrieval_reasons"] = sorted(reasons)
        tracks.append(track)
    return {
        "tracks": tracks,
        "favorite_artists": taste.get("favorite_artists") or [],
        "genres": taste.get("genres") or [],
        "moods": taste.get("moods") or [],
        "discovery_level": taste.get("discovery_level") or "balanced",
        "recent_tracks": history,
        "favorites": favorites,
        "playlists": playlists,
        "top_artists": artists,
    }


def grounded_insight(query: str, context: dict) -> str | None:
    text = normalize_text(query)
    artists = context.get("favorite_artists") or []
    genres = context.get("genres") or []
    moods = context.get("moods") or []
    recent = context.get("recent_tracks") or []
    favorites = context.get("favorites") or []
    top_artists = context.get("top_artists") or []

    if any(term in text for term in ("what do i like", "my taste", "my music taste", "what have i been listening")):
        parts = []
        if artists:
            parts.append("Your profile names " + ", ".join(artists[:5]) + " as favorite artists")
        if genres:
            parts.append("and " + ", ".join(genres[:4]) + " as genres")
        if moods:
            parts.append("with " + ", ".join(moods[:4]) + " moods")
        if top_artists:
            parts.append("Your most-played artists in local history include " + ", ".join(x.get("artist", "") for x in top_artists[:4] if x.get("artist")))
        if recent:
            parts.append("Recent listens include " + ", ".join(x.get("title", "Unknown") for x in recent[:3]))
        return ". ".join(parts).strip(". ") + ("." if parts else "I don't have enough saved listening data yet. Play or favorite a few tracks and I can summarize your taste.")

    if any(term in text for term in ("why this", "why did you", "why do you recommend", "why recommend", "how do you recommend", "how are recommendations")):
        signals = []
        if artists:
            signals.append("your favorite artists: " + ", ".join(artists[:4]))
        if genres:
            signals.append("genres: " + ", ".join(genres[:4]))
        if favorites:
            signals.append(f"{len(favorites)} saved favorites")
        signals.append("local play, skip and completion history" if recent else "the taste profile you entered")
        return "I rank retrieved tracks using " + "; ".join(signals) + ". I only describe tracks found in your catalog or returned by music search."

    return None
