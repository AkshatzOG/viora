"""Regional Apple Music charts used as an attributed discovery source."""
from __future__ import annotations

import threading
import time

import requests

from core.connectivity import network_available


STOREFRONTS = {
    "IN": "India", "US": "United States", "GB": "United Kingdom",
    "CA": "Canada", "AU": "Australia", "JP": "Japan", "KR": "South Korea",
    "BR": "Brazil", "MX": "Mexico", "NG": "Nigeria", "ZA": "South Africa",
    "FR": "France", "DE": "Germany", "ES": "Spain", "ID": "Indonesia",
    "PH": "Philippines", "AE": "United Arab Emirates",
}
_lock = threading.RLock()
_cache: dict[str, tuple[float, dict]] = {}


def regional_top_songs(storefront="IN", limit=100, force_refresh=False):
    code = str(storefront or "IN").upper()
    if code not in STOREFRONTS:
        raise ValueError("Choose a supported chart region.")
    limit = max(10, min(int(limit), 100))
    with _lock:
        cached = _cache.get(code)
        if cached and not force_refresh and time.monotonic() - cached[0] < 86400:
            return {**cached[1], "results": [dict(row) for row in cached[1]["results"][:limit]]}
    if not network_available():
        with _lock:
            cached = _cache.get(code)
        if cached:
            return {**cached[1], "results": [dict(row) for row in cached[1]["results"][:limit]], "stale": True}
        return {"region": STOREFRONTS[code], "storefront": code, "results": [], "stale": False, "offline": True}

    # Keep the full regional snapshot in cache so a Top 50 view followed by a
    # larger view cannot inherit a truncated result set.
    url = f"https://rss.marketingtools.apple.com/api/v2/{code.lower()}/music/most-played/100/songs.json"
    response = requests.get(url, headers={"Accept": "application/json", "User-Agent": "Viora/15.6"}, timeout=4.0)
    response.raise_for_status()
    feed = response.json().get("feed", {})
    results = []
    for position, item in enumerate(feed.get("results", []), 1):
        results.append({
            "id": str(item.get("id") or f"{code}-{position}"),
            "position": position,
            "title": item.get("name") or "Unknown track",
            "artist": item.get("artistName") or "Unknown artist",
            "album": item.get("albumName") or "",
            "artwork": item.get("artworkUrl100") or "",
            "apple_url": item.get("url") or "https://music.apple.com/",
            "genres": [x.get("name", "") for x in item.get("genres", []) if x.get("name")],
            "release_date": item.get("releaseDate") or "",
            "source": "Apple Music Charts",
        })
    data = {"region": STOREFRONTS[code], "storefront": code, "results": results, "source_url": f"https://music.apple.com/{code.lower()}/charts", "updated_at": feed.get("updated") or "", "stale": False, "offline": False}
    with _lock:
        _cache[code] = (time.monotonic(), data)
    return {**data, "results": [dict(row) for row in data["results"][:limit]]}
