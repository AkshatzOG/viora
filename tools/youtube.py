import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import yt_dlp

from tools.ranker import (
    find_best_exact_song,
    rank_tracks,
    remove_duplicates,
)

_SEARCH_CACHE = {}
_SEARCH_CACHE_LOCK = threading.RLock()
_SEARCH_CACHE_TTL = 45.0

SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "extract_flat": True,
    "skip_download": True,
}

STREAM_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "format": "bestaudio/best",
    "noplaylist": True,
    "skip_download": True,
}


def search_youtube(query, limit=10):
    # Keep every caller, including natural-language commands, inside offline mode.
    from core.database import get_db
    from core.connectivity import network_available
    if get_db().get_setting("playback_mode", "auto") == "offline" or not network_available():
        return []
    key = (
        re.sub(r"\s+", " ", str(query or "").strip().lower()),
        int(limit),
    )

    now = time.monotonic()

    with _SEARCH_CACHE_LOCK:
        cached = _SEARCH_CACHE.get(key)

        if cached and now - cached[0] < _SEARCH_CACHE_TTL:
            return [dict(item) for item in cached[1]]

    print(f"[youtube] Searching: {query}")

    try:
        with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
            info = ydl.extract_info(
                f"ytsearch{limit}:{query}",
                download=False,
            )

    except Exception as exc:
        print("[youtube] Search failed:", repr(exc))
        return []

    results = []

    for entry in (info or {}).get("entries") or []:
        if not entry or not entry.get("id"):
            continue

        results.append(
            {
                "id": entry["id"],
                "title": entry.get("title") or "Unknown",
                "artist": entry.get("channel")
                or entry.get("uploader"),
                "channel": entry.get("channel")
                or entry.get("uploader"),
                "channel_is_verified": bool(entry.get("channel_is_verified") or entry.get("uploader_is_verified")),
                "channel_id": entry.get("channel_id") or entry.get("uploader_id"),
                "duration": entry.get("duration"),
                "thumbnail": f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg",
                "watch_url": (
                    f"https://www.youtube.com/watch?v={entry['id']}"
                ),
            }
        )

    with _SEARCH_CACHE_LOCK:
        _SEARCH_CACHE[key] = (
            time.monotonic(),
            [dict(item) for item in results],
        )

    return results


def search_parallel(queries, limit_each=12, workers=5):
    queries = [
        q.strip()
        for q in queries
        if str(q or "").strip()
    ]

    if not queries:
        return []

    results = []

    with ThreadPoolExecutor(
        max_workers=min(workers, len(queries))
    ) as executor:

        jobs = {
            executor.submit(
                search_youtube,
                query,
                limit_each,
            ): query
            for query in queries
        }

        for future in as_completed(jobs):
            try:
                results.extend(future.result())
            except Exception as exc:
                print(
                    "[youtube] parallel search failed:",
                    repr(exc),
                )

    return remove_duplicates(results)


# Backwards-compatible name used by older modules.
search_many = search_parallel


def find_song(
    song_name,
    artist=None,
    variant=None,
    media_type="MUSIC",
):
    clean_song = str(song_name or "").strip()

    if artist:
        clean_song = re.sub(
            rf"\s+by\s+{re.escape(str(artist).strip())}\s*$",
            "",
            clean_song,
            flags=re.I,
        ).strip()

    base = " ".join(
        x for x in (clean_song, artist) if x
    )

    suffix = f" {variant}" if variant else ""

    queries = [
        f'"{base}"{suffix} official audio',
        f"{base}{suffix} official audio",
        f"{base}{suffix}",
    ]

    if variant:
        queries.append(
            f"{base} {variant} version"
        )

    candidates = search_parallel(
        queries,
        limit_each=10,
        workers=3,
    )

    return find_best_exact_song(
        candidates,
        clean_song,
        artist,
        variant=variant,
        media_type=media_type,
    )


def search_ranked(
    query,
    limit=5,
    pool=None,
    media_type="MUSIC",
    variant=None,
    artist=None,
):
    pool = pool or max(limit * 5, 20)

    candidates = search_youtube(
        query,
        limit=pool,
    )

    return rank_tracks(
        candidates,
        query=query,
        limit=limit,
        media_type=media_type,
        variant=variant,
        artist=artist,
    )


def discover_music(
    query,
    count=5,
    mood=None,
    genre=None,
    artist=None,
    language=None,
    variant=None,
):
    base = " ".join(
        x
        for x in (
            artist,
            genre,
            language,
            mood,
            query,
        )
        if x
    ).strip()

    # Keep broad discovery parallel but reduce redundant searches.
    queries = [
        base,
        f"{base} songs",
        f"{base} official audio",
    ]

    if mood or genre or language:
        queries.append(f"popular {base}")

    candidates = search_parallel(
        queries,
        limit_each=max(10, count * 3),
        workers=min(5, len(queries)),
    )

    return rank_tracks(
        candidates,
        query=base,
        limit=count,
        variant=variant,
        artist=artist,
        prefer_tracks=True,
    )


def discover_podcasts(query, count=5):
    base = query.strip() or "podcast"

    queries = [
        f"{base} podcast",
        f"{base} podcast episode",
        f"{base} interview",
    ]

    candidates = search_parallel(
        queries,
        limit_each=max(10, count * 3),
        workers=3,
    )

    return rank_tracks(
        candidates,
        query=base,
        limit=count,
        media_type="PODCAST",
    )


def discover_current(
    query,
    count=5,
    media_type="MUSIC",
):
    topic = re.sub(r"\s+", " ", str(query or "")).strip()
    if media_type == "PODCAST":
        queries = ([
            f"{topic} trending podcast this week" if topic else "trending podcasts this week",
            f"{topic} popular podcast this week" if topic else "popular podcasts this week",
        ])
    else:
        queries = ([
            f"{topic} trending songs this week official audio" if topic else "trending music this week official audio",
            f"{topic} top songs this week" if topic else "most popular songs this week",
            f"{topic} latest popular songs" if topic else "new hit songs this week",
        ])

    candidates = search_parallel(
        queries,
        limit_each=max(12, count * 4),
        workers=4,
    )

    # A narrow request such as "trending phonk" must not silently become a
    # general chart query. Keep topic-matching results only; an honest empty
    # result is safer than playing an unrelated song.
    if topic:
        topic_terms = [word for word in re.findall(r"[\w'-]+", topic.casefold()) if len(word) > 2]
        if topic_terms:
            candidates = [
                track for track in candidates
                if any(term in " ".join(str(track.get(key) or "") for key in ("title", "artist", "channel")).casefold() for term in topic_terms)
            ]

    return rank_tracks(
        candidates,
        query=topic or ("trending podcasts this week" if media_type == "PODCAST" else "trending music this week"),
        limit=count,
        media_type=media_type,
        prefer_tracks=True,
    )


def _resolve_stream_url(track):
    """
    Resolve a YouTube watch URL to a direct audio stream URL.

    This is deliberately done before a queued track is handed to MPV.
    That means MPV does not have to wait for yt-dlp when the previous
    track finishes.

    The watch URL remains on the track as a refresh/fallback source.
    """
    if not track or not track.get("watch_url"):
        return track

    try:
        with yt_dlp.YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(
                track["watch_url"],
                download=False,
            )

        direct = info.get("url")

        if direct:
            result = dict(track)
            result["stream_url"] = direct
            result["stream_expires_at"] = (
                time.time() + 5 * 60 * 60
            )
            return result

    except Exception as exc:
        print(
            "[youtube] Stream prefetch failed:",
            track.get("title"),
            repr(exc),
        )

    return dict(track)


def prepare_tracks(tracks, workers=4):
    tracks = list(tracks or [])

    if not tracks:
        return []

    prepared = [None] * len(tracks)

    with ThreadPoolExecutor(
        max_workers=min(workers, len(tracks))
    ) as executor:

        jobs = {
            executor.submit(
                _resolve_stream_url,
                track,
            ): index
            for index, track in enumerate(tracks)
        }

        for future in as_completed(jobs):
            index = jobs[future]

            try:
                prepared[index] = future.result()
            except Exception as exc:
                print(
                    "[youtube] Track preparation failed:",
                    repr(exc),
                )
                prepared[index] = dict(tracks[index])

    return [
        track
        for track in prepared
        if track
    ]
