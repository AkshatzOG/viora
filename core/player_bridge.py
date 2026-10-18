from __future__ import annotations

import time
from typing import Any

from core.database import get_db
from tools.playback import player

_current_history_id: int | None = None
_current_track_id: str | None = None
_current_duration: float | None = None
_current_played_seconds = 0.0
_last_sync_at: float | None = None


def _record_start(track: dict[str, Any]):
    global _current_history_id, _current_track_id, _current_duration, _current_played_seconds
    db = get_db()
    _current_history_id = db.record_play_start(track)
    _current_track_id = str(track.get("id"))
    try:
        _current_duration = float(track.get("duration")) if track.get("duration") else None
    except (TypeError, ValueError):
        _current_duration = None
    _current_played_seconds = 0.0


def _record_end(action: str | None = None):
    global _current_history_id, _current_played_seconds
    if _current_history_id is None:
        return
    if action is None:
        ratio = _current_played_seconds / max(_current_duration or 1, 1)
        action = "complete" if _current_duration and ratio >= 0.8 else "skip"
    get_db().record_play_end(_current_history_id, _current_duration, _current_played_seconds, action)
    _current_history_id = None
    _current_played_seconds = 0.0


def play(track, preserve_queue=True):
    ok = player.play(track, preserve_queue=preserve_queue)
    if ok:
        _record_end()
        _record_start(track)
    return ok


def queue(tracks):
    return player.queue(tracks)


def sync_history_from_player():
    global _current_history_id, _current_track_id, _last_sync_at, _current_played_seconds
    now = time.monotonic()
    if getattr(player, "_is_preview", False):
        _last_sync_at = now
        return False
    if _last_sync_at is not None and _current_history_id is not None and player._playing and not player._paused:
        _current_played_seconds += min(3.0, max(0.0, now - _last_sync_at))
    _last_sync_at = now
    current = player.current_track
    changed = False
    if not current:
        changed = _current_history_id is not None
        _record_end()
        return changed
    cid = str(current.get("id"))
    if cid != _current_track_id:
        _record_end()
        _record_start(current)
        changed = True
    elif _current_history_id is None and player._playing:
        _record_start(current)
        changed = True
    elif not player._playing and not player._paused:
        _record_end("complete")
        changed = True
    return changed
