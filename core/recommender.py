from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from config import MAX_SEARCH_RESULTS
from core.database import get_db
from core.connectivity import network_available
from core.library import is_local_file
from core.taste import profile, score
from tools.ranker import rank_tracks, remove_duplicates, normalize_text, is_bad_result, attach_source_category
from tools.youtube import search_parallel, prepare_tracks


def _attach_source_query(tracks, query):
    result = []
    for track in tracks or []:
        t = dict(track)
        t["source_query"] = query
        result.append(t)
    return result


def _search_queries(queries, limit_each=10):
    queries = [q.strip() for q in queries if str(q or "").strip()]
    if not queries:
        return []
    buckets = []
    with ThreadPoolExecutor(max_workers=min(5, len(queries))) as ex:
        jobs = {ex.submit(search_parallel, [q], limit_each, 1): q for q in queries}
        for fut in as_completed(jobs):
            q = jobs[fut]
            try:
                buckets.extend(_attach_source_query(fut.result(), q))
            except Exception as exc:
                print("[recommend] search failed", q, repr(exc))
    return remove_duplicates(buckets)


def _rank(candidates, count, section, current_id=None, p=None):
    p = p or profile()
    recent = {str(x.get("id")) for x in get_db().recent_tracks(20)}
    db = get_db()
    hide_heard = bool(db.get_setting("hide_heard", True))
    heard_ids = db.heard_track_ids() if hide_heard else set()
    heard_signatures = db.heard_track_signatures() if hide_heard else set()
    behavior = db.engagement([str(t.get("id")) for t in candidates or []])
    out = []
    for t in remove_duplicates(candidates):
        t = attach_source_category(t)
        if current_id and str(t.get("id")) == str(current_id):
            continue
        signature = db._history_signature(t.get("title"), t.get("artist") or t.get("channel"))
        if hide_heard and (str(t.get("id")) in heard_ids or signature in heard_signatures):
            continue
        if is_bad_result(t.get("title", "")):
            continue
        t.update(behavior.get(str(t.get("id")), {}))
        t["recommendation_score"] = round(score(t, p, recent, t.get("source_query", ""), section), 3)
        out.append(t)
    # Preserve confidence tiers: metadata-verified signals, likely artist/label
    # signals, then community posts. Relevance only decides order within a tier.
    source_priority = {"official": 2, "likely_official": 1, "community": 0}
    out.sort(key=lambda t: (source_priority.get(t.get("source_category"), 0), t.get("recommendation_score", 0)), reverse=True)
    # Artist diversity: do not fill a row with the same artist unless there are no alternatives.
    selected, seen_artists = [], set()
    for t in out:
        artist = normalize_text(t.get("artist") or t.get("channel") or "")
        if artist and artist in seen_artists and len(selected) < max(1, count // 2):
            continue
        selected.append(t)
        if artist:
            seen_artists.add(artist)
        if len(selected) >= count:
            break
    if len(selected) < count:
        for t in out:
            if t not in selected:
                selected.append(t)
                if len(selected) >= count:
                    break
    return selected[:count]


def home_recommendations():
    db = get_db()
    p = profile()
    recent = db.recent_tracks(8)
    favorites = db.list_tracks(12, favorites_only=True)
    local = [track for track in db.downloaded_tracks(1000) if is_local_file(track.get("local_path"))][:20]

    if db.get_setting("playback_mode", "auto") == "offline" or not network_available():
        offline_picks = _rank(local, 10, "discover", p=p)
        return {
            "continue_listening": [x for x in recent if x.get("is_downloaded")],
            "favorites": [x for x in favorites if x.get("is_downloaded")],
            "for_you": offline_picks,
            "for_you_official": [],
            "for_you_community": [],
            "because": [],
            "discover": offline_picks,
            "discover_official": [],
            "discover_community": [],
            "offline_recommendations": offline_picks,
            "offline_mode": True,
            "local": local,
            "playlists": db.playlists(),
            "taste": p,
            "stats": db.stats(),
        }

    queries = []
    for artist in (p.get("favorite_artists") or [])[:4]:
        queries.append(f"{artist} songs official audio")
    taste_terms = " ".join((p.get("genres") or [])[:3] + (p.get("moods") or [])[:2] + (p.get("languages") or [])[:2])
    if taste_terms:
        queries.append(f"{taste_terms} songs official audio")
    for item in recent[:2]:
        if item.get("artist"):
            queries.append(f"{item['artist']} similar artists songs official audio")
    queries.append("new music this week official audio")

    online_candidates = _search_queries(queries, limit_each=16) if queries else []
    for t in online_candidates:
        db.upsert_track(t)

    because = _rank(online_candidates, 8, "because", p=p)
    for_you = _rank(online_candidates + favorites, 10, "for_you", p=p)
    discover = _rank(online_candidates, 8, "discover", p=p)
    official = [track for track in for_you if track.get("source_category") != "community"]
    community = [track for track in for_you if track.get("source_category") == "community"]
    official_discover = [track for track in discover if track.get("source_category") != "community"]
    community_discover = [track for track in discover if track.get("source_category") == "community"]

    return {
        "continue_listening": recent,
        "favorites": favorites,
        "for_you": for_you,
        "for_you_official": official,
        "for_you_community": community if db.get_setting("show_community", True) else [],
        "because": because,
        "discover": discover,
        "discover_official": official_discover,
        "discover_community": community_discover if db.get_setting("show_community", True) else [],
        "offline_recommendations": [],
        "offline_mode": False,
        "local": local,
        "playlists": db.playlists(),
        "taste": p,
        "stats": db.stats(),
    }


def similar_to(track: dict, count=10):
    title = str(track.get("title") or "")
    artist = str(track.get("artist") or track.get("channel") or "")
    current_id = track.get("id")
    queries = [
        f"{artist} similar artists songs official audio" if artist else "songs similar to this official audio",
        f"songs like {title} official audio",
        f"{title} related songs official audio",
    ]
    candidates = _search_queries(queries, limit_each=max(10, count * 2))
    # Prefer different artists for similarity unless the user clearly wants more by the same artist.
    result = _rank(candidates, max(count * 2, count), "discover", current_id=current_id)
    different = [x for x in result if normalize_text(x.get("artist")) != normalize_text(artist)]
    same = [x for x in result if x not in different]
    return (different + same)[:count]


def prepare_for_playback(tracks):
    tracks = prepare_tracks(tracks, workers=min(6, max(1, len(tracks))))
    for track in tracks:
        try:
            get_db().upsert_track(track)
        except Exception:
            pass
    return tracks
