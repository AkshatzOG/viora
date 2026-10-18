"""Starter artists for taste onboarding; user listening remains first-party."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time

import requests

from core.connectivity import network_available


# A geographically varied starter set, not a claim that this is Spotify's
# changing global ranking. Listening history continuously adds user artists.
POPULAR_ARTISTS = [
    ("Arijit Singh", "South Asia"), ("Taylor Swift", "North America"),
    ("Bad Bunny", "Latin America"), ("Burna Boy", "West Africa"),
    ("BTS", "South Korea"), ("BLACKPINK", "South Korea"),
    ("The Weeknd", "North America"), ("Drake", "North America"),
    ("Dua Lipa", "Europe"), ("Billie Eilish", "North America"),
    ("Ed Sheeran", "Europe"), ("Olivia Rodrigo", "North America"),
    ("Sabrina Carpenter", "North America"), ("Karol G", "Latin America"),
    ("Rauw Alejandro", "Latin America"), ("Shakira", "Latin America"),
    ("J Balvin", "Latin America"), ("Anitta", "Latin America"),
    ("ROSALÍA", "Europe"), ("Peso Pluma", "Latin America"),
    ("A. R. Rahman", "South Asia"), ("Diljit Dosanjh", "South Asia"),
    ("Shreya Ghoshal", "South Asia"), ("Sid Sriram", "South Asia"),
    ("Atif Aslam", "South Asia"), ("AP Dhillon", "South Asia"),
    ("Karan Aujla", "South Asia"), ("Rema", "West Africa"),
    ("Tems", "West Africa"), ("Wizkid", "West Africa"),
    ("Tyla", "Southern Africa"), ("Davido", "West Africa"),
    ("Asake", "West Africa"), ("SZA", "North America"),
    ("Kendrick Lamar", "North America"), ("Travis Scott", "North America"),
    ("Doja Cat", "North America"), ("Ariana Grande", "North America"),
    ("Beyoncé", "North America"), ("Rihanna", "Caribbean"),
    ("Eminem", "North America"), ("Bruno Mars", "North America"),
    ("Post Malone", "North America"), ("Lady Gaga", "North America"),
    ("Coldplay", "Europe"), ("Linkin Park", "North America"),
    ("Adele", "Europe"), ("Hozier", "Europe"),
    ("Justin Bieber", "North America"), ("Miley Cyrus", "North America"),
    ("Lana Del Rey", "North America"), ("Harry Styles", "Europe"),
    ("The Beatles", "Europe"), ("Queen", "Europe"),
    ("Stromae", "Europe"), ("Aya Nakamura", "Europe"),
    ("Omah Lay", "West Africa"), ("Angélique Kidjo", "West Africa"),
    ("Fujii Kaze", "Japan"), ("YOASOBI", "Japan"),
    ("Ado", "Japan"), ("LiSA", "Japan"),
    ("NewJeans", "South Korea"), ("Stray Kids", "South Korea"),
    ("SEVENTEEN", "South Korea"), ("IU", "South Korea"),
    ("Jung Kook", "South Korea"), ("LISA", "Thailand"),
    ("BINI", "Philippines"), ("Moira Dela Torre", "Philippines"),
    ("Rich Brian", "Indonesia"), ("NIKI", "Indonesia"),
    ("Yuna", "Malaysia"),
    ("Mahmood", "Europe"), ("Amr Diab", "Middle East"),
    ("Nancy Ajram", "Middle East"), ("Elissa", "Middle East"),
    ("A-WA", "Middle East"), ("Elyanna", "Middle East"),
    ("Soolking", "North Africa"), ("Cheb Khaled", "North Africa"),
]

_cache: dict[str, object] = {"at": 0.0, "items": None}
_lock = threading.RLock()


def _image_batch(names: list[str]) -> dict[str, dict[str, str]]:
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query", "format": "json", "formatversion": 2,
            "prop": "pageimages|info", "inprop": "url", "piprop": "thumbnail",
            "pithumbsize": 360, "redirects": 1, "titles": "|".join(names),
        },
        headers={"User-Agent": "Viora/15.6 (artist pick thumbnails; browser links to source pages)"},
        timeout=3.0,
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", [])
    result = {}
    for page in pages:
        title = str(page.get("title") or "")
        image = page.get("thumbnail", {}).get("source")
        source = page.get("fullurl") or ("https://en.wikipedia.org/wiki/" + requests.utils.quote(title.replace(" ", "_")))
        if image and image.startswith("https://"):
            result[title.casefold()] = {"image": image, "source_url": source}
    return result


def popular_artist_picks() -> list[dict[str, str]]:
    now = time.monotonic()
    with _lock:
        cached = _cache.get("items")
        if cached and now - float(_cache.get("at", 0.0)) < 86400:
            return [dict(item) for item in cached]

    items = [{"name": name, "region": region, "image": "", "source_url": ""} for name, region in POPULAR_ARTISTS]
    if network_available():
        image_map: dict[str, dict[str, str]] = {}
        batches = [POPULAR_ARTISTS[i:i + 45] for i in range(0, len(POPULAR_ARTISTS), 45)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(_image_batch, ([name for name, _ in batch] for batch in batches)):
                image_map.update(result)
        for item in items:
            image = image_map.get(item["name"].casefold())
            if image:
                item.update(image)

    with _lock:
        _cache.update(at=now, items=[dict(item) for item in items])
    return items
