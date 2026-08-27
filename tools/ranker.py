import re
from difflib import SequenceMatcher


CONTAINER_PHRASES = (
    "playlist", "mix", "radio", "compilation", "collection", "nonstop",
    "best of", "top 10", "top 20", "top 50", "top 100",
    "1 hour", "2 hour", "3 hour", "hours of", "study session",
    "continuous", "megamix",
)

BAD_MUSIC_PHRASES = (
    "lyrics", "lyric video", "live", "concert", "reaction", "react",
    "cover", "karaoke", "behind the scenes", "commercial",
    "advertisement", "interview", "shorts", "tiktok experience",
    "slowed", "reverb", "sped up", "nightcore", "loop", "edit audio",
    "amv", "fan made", "fanmade",
    # Educational / non-music false positives that frequently appear for
    # searches containing words such as "similar", "attention", etc.
    "similar words", "similar meaning", "similar song", "similar songs",
    "difference between", "same meaning",
    "english grammar", "grammar", "meaning words", "learn english",
    "lesson", "tutorial", "class", "worksheet", "workbook",
    "mathematics", "maths", "math", "algebra", "geometry",
    "congruent figures", "theorem", "formula", "science lesson",
    "question answer", "questions and answers", "explained",
    "explanation", "lecture", "study material", "educational",
    # Common non-English educational/search-title traps.
    "비슷한 노래", "비슷한", "노래", "歌", "似た曲", "ähnliche songs",
    "canciones similares", "chansons similaires", "canções semelhantes",
)

GOOD_PHRASES = (
    "official audio",
    "official music video",
    "official video",
    "audio",
)


def normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_title(title):
    text = normalize_text(title)

    for label in (
        "official music video",
        "official video",
        "official audio",
        "music video",
        "audio",
        "hd",
    ):
        text = text.replace(label, " ")

    return re.sub(r"\s+", " ", text).strip()


def content_type(title):
    text = normalize_text(title)

    if any(x in text for x in CONTAINER_PHRASES):
        return "CONTAINER"

    if any(
        x in text
        for x in (
            "podcast",
            "episode",
            "interview",
            "talk show",
        )
    ):
        return "PODCAST"

    if "acoustic" in text:
        return "ACOUSTIC"

    if "remix" in text:
        return "REMIX"

    if "live" in text or "concert" in text:
        return "LIVE"

    if "karaoke" in text:
        return "KARAOKE"

    if "cover" in text:
        return "COVER"

    if "amv" in text:
        return "AMV"

    return "TRACK"


def is_bad_result(title):
    text = normalize_text(title)

    return (
        content_type(title) == "CONTAINER"
        or any(phrase in text for phrase in BAD_MUSIC_PHRASES)
    )


def _token_score(expected, actual):
    e = set(normalize_text(expected).split())
    a = set(normalize_text(actual).split())

    return len(e & a) / len(e) if e else 0.0


def exact_song_score(
    track,
    song_name,
    artist=None,
    position=0,
    variant=None,
    media_type="MUSIC",
):
    title = track.get("title", "")
    normalized = normalize_text(title)
    cleaned = clean_title(title)
    channel = normalize_text(
        track.get("channel") or track.get("artist") or track.get("uploader") or ""
    )

    song = normalize_text(song_name)
    artist_text = normalize_text(artist) if artist else ""

    if not song:
        return -1000

    song_tokens = set(song.split())
    title_tokens = set(cleaned.split())

    # Exact token overlap is preferred, but allow small spelling/transliteration
    # differences (for example "valom avo ne" -> "Valam Aavo Ne").
    exact_hits = len(song_tokens & title_tokens)
    overlap = exact_hits / max(1, len(song_tokens))

    fuzzy_hits = 0
    for expected in song_tokens:
        if expected in title_tokens:
            fuzzy_hits += 1
            continue
        if any(SequenceMatcher(None, expected, actual).ratio() >= 0.78
               for actual in title_tokens):
            fuzzy_hits += 1

    fuzzy_overlap = fuzzy_hits / max(1, len(song_tokens))

    # Require strong token agreement. For 3+ word titles, two exact/fuzzy
    # matches plus a close transliteration is enough; unrelated results are
    # still rejected before scoring.
    if overlap < 0.75 and fuzzy_overlap < 0.75:
        return -1000

    score = 80 + 70 * max(overlap, fuzzy_overlap)

    if artist_text:
        if artist_text in normalized or artist_text in channel:
            score += 65
        else:
            score -= 120

    if media_type == "PODCAST":
        score += 20 if content_type(title) == "PODCAST" else -80
        return score

    # Prefer a clean music release over user-generated derivatives.
    if content_type(title) == "CONTAINER":
        score -= 300

    if content_type(title) in {
        "LIVE", "COVER", "KARAOKE", "AMV", "PODCAST"
    }:
        score -= 180

    if "official audio" in normalized:
        score += 55
    elif "official music video" in normalized:
        score += 48
    elif "official video" in normalized:
        score += 42
    elif "audio" in normalized:
        score += 18

    # Strong penalties. A lyrics/mashup result can contain every requested
    # token, but it is still not the clean recording the user asked for.
    if "lyrics" in normalized or "lyric video" in normalized:
        score -= 160
    if "reaction" in normalized or "react" in normalized:
        score -= 220
    if "behind the scenes" in normalized or "commercial" in normalized:
        score -= 220
    if any(x in normalized for x in ("shorts", "tiktok experience", "fan made", "fanmade")):
        score -= 220
    if is_bad_result(title):
        score -= 120

    if variant:
        v = normalize_text(variant)
        if v in normalized:
            score += 100
        else:
            score -= 65
    elif content_type(title) in {"ACOUSTIC", "REMIX"}:
        score -= 50

    # Earlier YouTube results get only a tiny tie-break bonus; relevance
    # should dominate search position.
    score += max(0, 10 - position) * 0.2
    return score


def find_best_exact_song(
    tracks,
    song_name,
    artist=None,
    variant=None,
    media_type="MUSIC",
):
    candidates = []

    for i, track in enumerate(tracks or []):
        score = exact_song_score(
            track,
            song_name,
            artist,
            i,
            variant,
            media_type,
        )

        if score > -500:
            candidates.append((score, track))

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return candidates[0][1] if candidates else None


def remove_duplicates(tracks):
    seen_ids = set()
    seen_titles = set()
    result = []

    for track in tracks or []:
        vid = track.get("id")
        title = clean_title(track.get("title", ""))

        if vid and vid in seen_ids:
            continue

        if title and title in seen_titles:
            continue

        if vid:
            seen_ids.add(vid)

        if title:
            seen_titles.add(title)

        result.append(track)

    return result


def rank_tracks(
    tracks,
    query="",
    limit=5,
    media_type="MUSIC",
    variant=None,
    artist=None,
    prefer_tracks=False,
):
    tracks = remove_duplicates(tracks)

    scored = []
    q = normalize_text(query)
    artist_norm = normalize_text(artist) if artist else ""

    for index, track in enumerate(tracks):
        title = track.get("title", "")
        text = normalize_text(title)
        ctype = content_type(title)

        score = max(0, 10 - index)

        if media_type == "PODCAST":
            score += 90 if ctype == "PODCAST" else -100

        else:
            if ctype == "CONTAINER":
                score -= 180

            if ctype in {
                "AMV",
                "LIVE",
                "COVER",
                "KARAOKE",
                "PODCAST",
            }:
                score -= 70

            if prefer_tracks and is_bad_result(title):
                score -= 120

            if any(p in text for p in GOOD_PHRASES):
                score += 12

        if variant:
            v = normalize_text(variant)
            score += 80 if v in text else -35

        if artist_norm:
            if artist_norm in text:
                score += 35
            else:
                score -= 20

        if q:
            score += SequenceMatcher(
                None,
                q,
                clean_title(title),
            ).ratio() * 8

        scored.append((score, track))

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        track
        for _, track in scored[:limit]
    ]
