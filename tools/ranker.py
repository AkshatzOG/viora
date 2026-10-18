import re
from difflib import SequenceMatcher


OFFICIAL_TITLE_MARKERS = (
    "official audio", "official music video", "official video",
    "provided to youtube by", "licensed to youtube by",
)


def source_category(track):
    """Prefer platform-level verification; title/channel text alone stays lower confidence."""
    track = track or {}
    if track.get("channel_is_verified") or track.get("uploader_is_verified") or track.get("verified"):
        return "official"
    channel = normalize_text(track.get("channel") or track.get("artist") or track.get("uploader") or "")
    # YouTube's generated Topic channels and widely recognizable label/Vevo
    # channels are stronger signals than a title that merely says “official”.
    trusted_channels = (
        "vevo", "t series", "zee music company", "sony music india",
        "saregama music", "tips official", "universal music group",
        "warner records", "atlantic records", "republic records",
        "sony music entertainment", "warner music", "universal music",
    )
    if channel.endswith(" topic") or any(name in channel for name in trusted_channels):
        return "likely_official"
    title = normalize_text(track.get("title") or "")
    if any(marker in title for marker in ("provided to youtube by", "licensed to youtube by")):
        return "official"
    if any(marker in title for marker in ("official audio", "official music video", "official video")) or channel.endswith(" official") or channel.startswith("official "):
        return "likely_official"
    return "community"


def attach_source_category(track):
    result = dict(track or {})
    result["source_category"] = source_category(result)
    result["source_badge"] = {
        "official": "Verified source metadata",
        "likely_official": "Artist / label source signal",
        "community": "Community upload",
    }[result["source_category"]]
    return result


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

UNREQUESTED_DERIVATIVES = (
    "remix", "mashup", "slowed", "slowed + reverb", "sped up",
    "nightcore", "fan edit", "edit audio", "8d audio", "bass boosted",
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

    category = source_category(track)
    score += 45 if category == "official" else 12 if category == "likely_official" else 0

    requested_variant = normalize_text(f"{song_name} {variant or ''}")
    if not any(term in requested_variant for term in UNREQUESTED_DERIVATIVES):
        if any(term in normalized for term in UNREQUESTED_DERIVATIVES):
            score -= 95

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
    seen_performances = set()
    result = []

    for track in tracks or []:
        vid = track.get("id")
        title = clean_title(track.get("title", ""))
        artist = normalize_text(track.get("artist") or track.get("channel") or track.get("uploader") or "")

        if vid and vid in seen_ids:
            continue

        # Keep same-title recordings from different performers/channels. A
        # title-only dedupe used to discard the canonical source before source
        # ranking even ran, which hid the better result from later searches.
        performance = (title, artist) if title and artist else None
        if performance and performance in seen_performances:
            continue

        if vid:
            seen_ids.add(vid)

        if performance:
            seen_performances.add(performance)

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
    query_tokens = set(q.split()) - {
        "official", "audio", "video", "music", "song", "songs", "track", "tracks",
        "the", "by", "play", "find", "search", "recommend", "recommendation",
        "recommendations", "me", "some", "please", "for", "a", "an", "this",
        "week", "today", "current", "trending", "popular", "new", "best", "top",
        "listen", "show", "want", "i", "like", "of", "from", "in", "my", "your", "on", "to",
    }

    for index, track in enumerate(tracks):
        track = attach_source_category(track)
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
            # Keep the canonical recording ahead of user-made variants unless
            # the query explicitly asks for that treatment.
            if prefer_tracks and not any(term in q for term in UNREQUESTED_DERIVATIVES):
                if any(term in text for term in UNREQUESTED_DERIVATIVES):
                    score -= 95

            if any(p in text for p in GOOD_PHRASES):
                score += 12

        if variant:
            v = normalize_text(variant)
            score += 80 if v in text else -35

        creator_text = normalize_text(" ".join(str(track.get(k) or "") for k in ("artist", "channel", "uploader")))
        if artist_norm:
            if artist_norm in creator_text or artist_norm in text:
                score += 35
            else:
                score -= 110

        if q:
            cleaned = clean_title(title)
            searchable = normalize_text(cleaned + " " + creator_text)
            score += SequenceMatcher(None, q, cleaned).ratio() * 8
            if prefer_tracks and query_tokens:
                title_tokens = set(cleaned.split())
                source_tokens = set(creator_text.split())
                title_coverage = len(query_tokens & title_tokens) / len(query_tokens)
                source_coverage = len(query_tokens & source_tokens) / len(query_tokens)
                combined_coverage = len(query_tokens & set(searchable.split())) / len(query_tokens)
                score += title_coverage * 48 + source_coverage * 30 + combined_coverage * 20
                if combined_coverage < 0.35:
                    score -= 95

        # Keep the requested sound/song relevant ahead of channel-level
        # confidence. A verified channel is useful evidence, but it cannot
        # make an unrelated result a good match.
        category = track.get("source_category")
        score += 16 if category == "official" else 8 if category == "likely_official" else 0

        scored.append((score, track))

    source_priority = {"official": 2, "likely_official": 1, "community": 0}
    scored.sort(key=lambda item: (item[0], source_priority.get(item[1].get("source_category"), 0)), reverse=True)

    return [
        track
        for _, track in scored[:limit]
    ]
