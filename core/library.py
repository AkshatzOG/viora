from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config import DOWNLOAD_DIR
from core.database import get_db
from tools.ranker import normalize_text

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".webm", ".opus", ".aac", ".wav", ".flac", ".ogg"}


def get_download_dir() -> Path:
    configured = get_db().get_setting("download_dir")
    try:
        path = Path(configured).expanduser().resolve() if configured else DOWNLOAD_DIR.resolve()
    except (OSError, TypeError, ValueError):
        path = DOWNLOAD_DIR.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def storage_info() -> dict[str, Any]:
    directory = get_download_dir()
    try:
        usage = __import__("shutil").disk_usage(directory)
        files = [p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
        used = sum(p.stat().st_size for p in files)
        return {
            "path": str(directory),
            "files": len(files),
            "used_bytes": used,
            "free_bytes": usage.free,
            "total_bytes": usage.total,
        }
    except OSError:
        return {"path": str(directory), "files": 0, "used_bytes": 0, "free_bytes": 0, "total_bytes": 0}


def safe_filename(title: str, artist: str | None = None) -> str:
    name = " - ".join(x for x in (artist, title) if x)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:180] or "track"


def is_local_file(path: str | Path | None) -> bool:
    return bool(path and Path(path).is_file())


def local_track_from_file(path: Path) -> dict[str, Any]:
    title = path.stem
    return {
        "id": f"local:{path.resolve()}",
        "source": "local",
        "youtube_id": None,
        "title": title,
        "artist": None,
        "channel": "Local file",
        "duration": None,
        "thumbnail": None,
        "watch_url": None,
        "media_type": "MUSIC",
        "local_path": str(path.resolve()),
        "is_downloaded": True,
    }


def scan_downloads() -> int:
    """Reconcile user-visible local downloads into SQLite without reading audio bytes."""
    db = get_db()
    directory = get_download_dir()
    count = 0
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if not db.track_by_local_path(str(path.resolve())):
            db.upsert_track(local_track_from_file(path), source="local")
        count += 1
    return count


def mark_downloaded(track: dict[str, Any], local_path: Path):
    data = dict(track)
    data["local_path"] = str(local_path.resolve())
    data["is_downloaded"] = True
    data["source"] = data.get("source") or "youtube"
    get_db().upsert_track(data, source=data["source"])
    return get_db().get_track(str(data["id"]))


def find_local(query: str, limit: int = 20):
    return [t for t in get_db().search_tracks(query, limit=limit, downloaded_only=True) if is_local_file(t.get("local_path"))]


def library_items(limit=100):
    tracks = get_db().downloaded_tracks(limit=limit)
    for track in tracks:
        track["missing_file"] = bool(track.get("local_path") and not is_local_file(track.get("local_path")))
    return tracks


def normalize_track_for_client(track: dict[str, Any]) -> dict[str, Any]:
    result = dict(track)
    if result.get("local_path") and not is_local_file(result["local_path"]):
        result["is_downloaded"] = False
    if "is_favorite" in result:
        result["is_favorite"] = bool(result["is_favorite"])
    if "is_downloaded" in result:
        result["is_downloaded"] = bool(result["is_downloaded"])
    return result
