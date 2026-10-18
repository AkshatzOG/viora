"""Background importer for user-supplied playlist exports."""
from __future__ import annotations

import csv
import io
import json
import re
import threading
import uuid
from core.connectivity import network_available
from core.database import get_db
from tools.ranker import find_best_exact_song
from tools.youtube import search_youtube


_jobs: dict[str, dict] = {}
_lock = threading.RLock()
_MAX_TRACKS = 100


def _clean_pair(title, artist=""):
    title = re.sub(r"\s+", " ", str(title or "")).strip()
    artist = re.sub(r"\s+", " ", str(artist or "")).strip()
    if not artist and " - " in title:
        artist, title = title.split(" - ", 1)
    return title[:220], artist[:180]


def parse_playlist_file(filename: str, text: str) -> list[dict[str, str]]:
    ext = str(filename or "").lower().rsplit(".", 1)[-1] if "." in str(filename or "") else "txt"
    rows: list[dict[str, str]] = []
    if ext == "json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("tracks") or data.get("items") or data.get("songs") or []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    title, artist = _clean_pair(item.get("title") or item.get("name"), item.get("artist") or item.get("artistName"))
                    if title:
                        rows.append({"title": title, "artist": artist})
    elif ext == "csv":
        reader = csv.DictReader(io.StringIO(text))
        for item in reader:
            keys = {str(k or "").strip().casefold(): v for k, v in item.items()}
            title, artist = _clean_pair(keys.get("track name") or keys.get("track") or keys.get("title") or keys.get("name"), keys.get("artist name") or keys.get("artist") or keys.get("artists"))
            if title:
                rows.append({"title": title, "artist": artist})
    else:
        pending_title = ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.upper().startswith("#EXTINF:"):
                pending_title = line.split(",", 1)[-1].strip()
                continue
            if line.startswith("#"):
                continue
            if re.match(r"https?://", line, re.I):
                if pending_title:
                    title, artist = _clean_pair(pending_title)
                    if title:
                        rows.append({"title": title, "artist": artist})
                    pending_title = ""
                continue
            # M3U entries commonly pair an EXTINF title with a local path or URL.
            # Keep the human-readable title and ignore the media locator.
            if pending_title:
                title, artist = _clean_pair(pending_title)
                if title:
                    rows.append({"title": title, "artist": artist})
                pending_title = ""
                continue
            value = line
            title, artist = _clean_pair(value or pending_title)
            if title:
                rows.append({"title": title, "artist": artist})
    unique = []
    seen = set()
    for row in rows:
        key = (row["title"].casefold(), row["artist"].casefold())
        if key not in seen:
            unique.append(row)
            seen.add(key)
        if len(unique) >= _MAX_TRACKS:
            break
    if not unique:
        if re.search(r"(?:spotify\.com|music\.apple\.com|youtube\.com|music\.youtube\.com|music\.amazon\.)/.*playlist", text, re.I):
            raise ValueError("A service playlist can be saved or previewed in Viora, but its player does not share the track list. Paste copied song names or import a CSV, M3U, JSON, or text list to build a Viora playlist.")
        raise ValueError("No song rows were found. Use a CSV, M3U/M3U8, JSON, or text list with one title per line (Artist - Title also works).")
    return unique


def start_playlist_import(filename: str, playlist_name: str, tracks: list[dict[str, str]]) -> str:
    if not network_available() or get_db().get_setting("playback_mode", "auto") == "offline":
        raise ValueError("Playlist matching needs an internet connection. Switch to Auto or Online mode, then retry.")
    if len(tracks) > _MAX_TRACKS:
        raise ValueError(f"A playlist import can contain up to {_MAX_TRACKS} songs.")
    name = re.sub(r"\s+", " ", str(playlist_name or "")).strip()[:80]
    if not name:
        name = re.sub(r"\.[^.]+$", "", str(filename or "Imported playlist"))[:80].strip() or "Imported playlist"
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {"id": job_id, "status": "running", "total": len(tracks), "completed": 0, "matched": 0, "missed": [], "playlist_name": name, "message": "Matching songs to Viora's playable catalog…"}
    threading.Thread(target=_run_import, args=(job_id, name, list(tracks)), daemon=True, name="viora-playlist-import").start()
    return job_id


def _run_import(job_id: str, name: str, tracks: list[dict[str, str]]) -> None:
    try:
        playlist_id = get_db().playlist_create(name)
        with _lock:
            _jobs[job_id]["playlist_id"] = playlist_id
        for item in tracks:
            query = " ".join(x for x in (item.get("title"), item.get("artist")) if x)
            candidates = search_youtube(f'"{query}" official audio', limit=14)
            match = find_best_exact_song(candidates, item.get("title"), item.get("artist"))
            if match:
                get_db().playlist_add(playlist_id, match)
                with _lock:
                    _jobs[job_id]["matched"] += 1
            else:
                with _lock:
                    _jobs[job_id]["missed"].append(item)
            with _lock:
                _jobs[job_id]["completed"] += 1
                _jobs[job_id]["message"] = f"Matched {_jobs[job_id]['matched']} of {_jobs[job_id]['completed']} songs."
        with _lock:
            job = _jobs[job_id]
            job["status"] = "complete"
            job["playlist"] = get_db().playlist_get(playlist_id)
            job["message"] = f"Imported {job['matched']} of {job['total']} songs into {name}."
    except Exception as exc:
        with _lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["message"] = "The import stopped before all songs were matched."
            _jobs[job_id]["error"] = str(exc)[:240]


def playlist_import_status(job_id: str):
    with _lock:
        job = _jobs.get(str(job_id))
        if not job:
            return None
        result = dict(job)
        result["missed"] = list(job.get("missed", []))[:100]
        return result
