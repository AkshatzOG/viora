"""Short-lived browser connectivity signal for local-first playback."""
from __future__ import annotations

import threading

_lock = threading.RLock()
_browser_online: bool | None = None


def set_browser_online(value: bool | None) -> None:
    global _browser_online
    with _lock:
        _browser_online = None if value is None else bool(value)


def browser_online() -> bool | None:
    with _lock:
        return _browser_online


def network_available() -> bool:
    """Assume online until the active browser reports otherwise."""
    return browser_online() is not False
