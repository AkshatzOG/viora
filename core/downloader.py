from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import yt_dlp

from config import DOWNLOAD_FORMAT, YTDLP_PATH
from core.library import get_download_dir, mark_downloaded, safe_filename

_download_lock = threading.RLock()
_active: dict[str, dict[str, Any]] = {}


def _find_output(download_info: dict[str, Any], requested_stem: str, download_dir: Path) -> Path | None:
    candidates = list(download_dir.glob(f"{requested_stem}.*"))
    candidates = [p for p in candidates if p.is_file()]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return None


def download_track(track: dict[str, Any]) -> dict[str, Any]:
    """Download an explicitly requested track; streaming remains the default elsewhere."""
    track = dict(track or {})
    source_url = track.get("watch_url") or track.get("url")
    if not source_url:
        raise ValueError("This track has no downloadable source URL.")

    key = str(track.get("id") or source_url)
    with _download_lock:
        active = _active.get(key)
        if active and active.get("status") == "downloading":
            return active
        _active[key] = {"status": "downloading", "progress": 0, "title": track.get("title")}

    download_dir = get_download_dir()
    stem = safe_filename(track.get("title") or "track", track.get("artist"))
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": DOWNLOAD_FORMAT,
        "noplaylist": True,
        "outtmpl": str(download_dir / f"{stem}.%(ext)s"),
        "paths": {"home": str(download_dir)},
        "overwrites": False,
        "writethumbnail": False,
        "writeinfojson": False,
        "writedescription": False,
        "progress_hooks": [
            lambda info: _update_progress(key, info),
        ],
    }
    # Prefer the explicit executable configuration when yt-dlp can use it as a path.
    if YTDLP_PATH:
        opts["paths"] = {"home": str(download_dir)}

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source_url, download=True)
            requested_downloads = info.get("requested_downloads") or []
            downloaded = None
            if requested_downloads:
                downloaded = requested_downloads[0].get("filepath")
            if not downloaded:
                prepared = Path(ydl.prepare_filename(info))
                downloaded = str(prepared)
            path = Path(downloaded)
            if not path.exists():
                found = _find_output(info, stem, download_dir)
                path = found or path
            if not path.exists():
                raise FileNotFoundError("yt-dlp completed but the local file was not found.")

        result = mark_downloaded(track, path)
        payload = {"status": "downloaded", "progress": 100, "title": track.get("title"), "local_path": str(path), "track": result}
        with _download_lock:
            _active[key] = payload
        return payload
    except Exception as exc:
        payload = {"status": "error", "progress": 0, "title": track.get("title"), "error": str(exc)}
        with _download_lock:
            _active[key] = payload
        raise


def download_status(track_id: str):
    with _download_lock:
        return dict(_active.get(str(track_id), {"status": "idle", "progress": 0}))


def _update_progress(key: str, info: dict[str, Any]):
    if info.get("status") == "finished":
        progress = 99
    elif info.get("status") == "downloading":
        try:
            total = float(info.get("total_bytes") or info.get("total_bytes_estimate") or 0)
            downloaded = float(info.get("downloaded_bytes") or 0)
            progress = int(min(99, max(0, downloaded * 100 / total))) if total else 0
        except (TypeError, ValueError, ZeroDivisionError):
            progress = 0
    else:
        return
    with _download_lock:
        current = dict(_active.get(key) or {})
        current.update({"status": "downloading", "progress": progress})
        _active[key] = current
