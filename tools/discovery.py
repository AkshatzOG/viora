import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
)
from tools.ranker import rank_tracks, normalize_text
from tools.youtube import find_song, search_parallel


SIMILAR_RESULT_BLACKLIST = (
    "similar words", "similar meaning", "similar song", "similar songs",
    "difference between", "same meaning",
    "english grammar", "grammar", "meaning words", "learn english",
    "lesson", "tutorial", "class", "worksheet", "workbook",
    "mathematics", "maths", "math", "algebra", "geometry",
    "congruent figures", "theorem", "formula", "science lesson",
    "question answer", "questions and answers", "lecture",
    "study material", "educational", "explained", "explanation",
    "how to",
    "비슷한 노래", "비슷한", "ähnliche songs",
    "canciones similares", "chansons similaires", "canções semelhantes",
)

def _usable_similar_track(track, current_key):
    title = normalize_text(track.get("title", ""))
    if not title or normalize_text(title) == current_key:
        return False
    return not any(phrase in title for phrase in SIMILAR_RESULT_BLACKLIST)


PROMPT = """
You are the recommendation planner for a music agent.

Return ONLY JSON:
{
  "songs": [
    {"title": "real song title", "artist": "real artist"}
  ]
}

Rules:
- Return distinct real songs.
- Never return the current song.
- Never return playlists, mixes, radio, compilations, reactions,
  AMVs, interviews, karaoke, loops, or "top songs" videos.
- Match the current song's genre, era, energy, mood and style.
- Do not invent artists or titles.
"""


def _ollama(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "system": PROMPT,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": 0.15,
                "num_predict": OLLAMA_NUM_PREDICT,
                "num_ctx": OLLAMA_NUM_CTX,
            },
        },
        timeout=OLLAMA_TIMEOUT,
    )
    response.raise_for_status()

    return json.loads(
        response.json().get("response", "{}")
    )


def recommend_similar(current_song, current_artist, count, user_text):
    context = str(current_song or "unknown")

    if current_artist:
        context += f" by {current_artist}"

    requested = max(count + 5, 8)

    try:
        data = _ollama(
            f"Current song: {context}\n"
            f"User request: {user_text}\n"
            f"Return {requested} candidate songs."
        )

        songs = data.get("songs", []) if isinstance(data, dict) else []

    except Exception as exc:
        print("[discovery] Ollama recommendation failed:", repr(exc))
        songs = []

    pairs = []
    seen = set()

    current_key = normalize_text(current_song)

    for item in songs:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip()
        artist = str(item.get("artist", "")).strip()

        if not title or not artist:
            continue

        key = (
            normalize_text(title),
            normalize_text(artist),
        )

        if key in seen:
            continue

        # Don't let the LLM recommend the exact current track.
        if normalize_text(title) == current_key:
            continue

        seen.add(key)
        pairs.append((title, artist))

    tracks = []
    used_ids = set()

    def resolve(pair):
        return find_song(pair[0], pair[1])

    if pairs:
        with ThreadPoolExecutor(
            max_workers=min(6, len(pairs))
        ) as executor:

            jobs = [
                executor.submit(resolve, pair)
                for pair in pairs
            ]

            for future in as_completed(jobs):
                try:
                    track = future.result()
                except Exception as exc:
                    print(
                        "[discovery] similar resolve failed:",
                        repr(exc),
                    )
                    track = None

                if not track:
                    continue

                if not _usable_similar_track(track, current_key):
                    continue

                if track.get("id") in used_ids:
                    continue

                used_ids.add(track["id"])
                tracks.append(track)

                if len(tracks) >= count:
                    break

    # If the LLM didn't give enough usable candidates, fall back to
    # multiple YouTube searches.
    if len(tracks) < count:
        fallback = search_parallel(
            [
                f"{current_artist or ''} songs similar to {current_song} official audio",
                f"{current_artist or ''} best songs official audio",
                f"{current_song} similar artists songs official audio",
            ],
            limit_each=max(12, count * 4),
            workers=4,
        )

        ranked = rank_tracks(
            fallback,
            query="official music audio song",
            artist=current_artist,
            limit=max(count * 5, count),
            prefer_tracks=True,
        )

        for track in ranked:
            if not _usable_similar_track(track, current_key):
                continue

            if track.get("id") in used_ids:
                continue

            used_ids.add(track["id"])
            tracks.append(track)

            if len(tracks) >= count:
                break

    return tracks[:count]


def discover_current(query, count=5):
    queries = [
        "trending music this week",
        "most popular songs this week",
        "new hit songs this week",
        query,
    ]

    candidates = search_parallel(
        queries,
        limit_each=max(15, count * 5),
        workers=4,
    )

    return rank_tracks(
        candidates,
        query="trending music this week",
        limit=count,
        prefer_tracks=True,
    )
