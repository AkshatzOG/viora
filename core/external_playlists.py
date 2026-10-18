"""Safe parsing and provider-aware previews for user-saved playlist links."""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit


class _IframeSourceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "iframe":
            source = dict(attrs).get("src")
            if source:
                self.sources.append(source)


def _provider(host: str) -> str | None:
    if host in {"open.spotify.com", "spotify.com", "www.spotify.com"}:
        return "Spotify"
    if host in {"music.apple.com", "embed.music.apple.com"}:
        return "Apple Music"
    if host in {"music.youtube.com", "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "youtube-nocookie.com"}:
        return "YouTube Music" if host == "music.youtube.com" else "YouTube"
    amazon_hosts = {
        "music.amazon.com", "music.amazon.co.uk", "music.amazon.de", "music.amazon.fr",
        "music.amazon.it", "music.amazon.es", "music.amazon.co.jp", "music.amazon.ca",
        "music.amazon.com.au", "music.amazon.com.br", "music.amazon.com.mx", "music.amazon.in",
        "music.amazon.nl", "music.amazon.se",
    }
    if host in amazon_hosts:
        return "Amazon Music"
    if host in {"tidal.com", "listen.tidal.com", "www.tidal.com"}:
        return "Tidal"
    if host in {"deezer.com", "www.deezer.com"}:
        return "Deezer"
    if host in {"soundcloud.com", "www.soundcloud.com"}:
        return "SoundCloud"
    return None


def parse_external_playlist_source(source: str) -> dict[str, str | bool]:
    """Validate a supported playlist URL or iframe and return safe link/embed data.

    The app stores links and displays official provider players where a stable
    embed URL is supported. It never reads playlist contents from cross-origin
    embeds or copies provider audio.
    """
    raw = unescape(str(source or "").strip())[:8000]
    parser = _IframeSourceParser()
    if "<iframe" in raw.casefold():
        parser.feed(raw)
        candidates = parser.sources
    else:
        candidates = [raw]

    for candidate in candidates:
        try:
            parsed = urlsplit(candidate.strip())
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except ValueError:
            continue
        if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password or port not in (None, 443):
            continue
        provider = _provider(host)
        if not provider:
            continue

        path = parsed.path or "/"
        query = parse_qs(parsed.query)
        playlist_id = ""
        embed_url = ""
        if provider == "Spotify":
            match = re.search(r"/(?:embed/)?playlist/([A-Za-z0-9]{10,64})(?:/|$)", path)
            if not match:
                continue
            playlist_id = match.group(1)
            embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}?theme=0"
        elif provider == "Apple Music":
            if not re.search(r"/(?:[a-z]{2}/)?playlist/", path, re.I):
                continue
            embed_url = urlunsplit(("https", "embed.music.apple.com", path, "", ""))
        elif provider in {"YouTube", "YouTube Music"}:
            ids = query.get("list", [])
            if not ids and host == "youtu.be":
                continue
            playlist_id = ids[0] if ids else ""
            if not playlist_id or not re.fullmatch(r"[A-Za-z0-9_-]{8,120}", playlist_id):
                continue
            embed_url = f"https://www.youtube.com/embed?listType=playlist&list={playlist_id}"
        elif provider == "Amazon Music":
            if not re.search(r"/(?:user-)?playlists?/(?:[^/]+/)?[A-Za-z0-9_-]{8,120}(?:/|$)", path, re.I):
                continue
        elif provider == "Tidal":
            if not re.search(r"/(?:browse/)?playlist/[A-Za-z0-9_-]{6,120}(?:/|$)", path, re.I):
                continue
        elif provider == "Deezer":
            if not re.search(r"/playlist/[A-Za-z0-9_-]{6,120}(?:/|$)", path, re.I):
                continue
        elif provider == "SoundCloud":
            if "/sets/" not in path:
                continue

        source_url = urlunsplit(("https", parsed.netloc.lower(), path, parsed.query, ""))
        return {
            "provider": provider,
            "source_url": source_url,
            "embed_url": embed_url,
            "embed_supported": bool(embed_url),
            "open_url": source_url,
            "default_name": f"{provider} playlist",
        }

    raise ValueError("Paste a playlist link or its embed code from Spotify, Apple Music, YouTube Music, Amazon Music, Tidal, Deezer, or SoundCloud.")
