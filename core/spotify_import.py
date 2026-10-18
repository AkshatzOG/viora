"""Local Spotify OAuth (PKCE) and user-authorized playlist metadata import."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_lock = threading.RLock()
_pending: dict[str, tuple[str, float]] = {}
_token: dict | None = None
_AUTH_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API_ROOT = "https://api.spotify.com/v1"
_SCOPES = "playlist-read-private playlist-read-collaborative"


class SpotifyImportError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def configured(client_id: str) -> bool:
    return bool(str(client_id or "").strip())


def status(client_id: str) -> dict:
    with _lock:
        connected = bool(_token and float(_token.get("expires_at", 0)) > time.time())
    return {"configured": configured(client_id), "connected": connected}


def authorization_url(client_id: str, redirect_uri: str) -> str:
    if not configured(client_id):
        raise SpotifyImportError("Spotify import needs a Spotify app Client ID. Add SPOTIFY_CLIENT_ID to your local .env file; setup steps are in the README.", 503)
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("ascii").rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    state = secrets.token_urlsafe(24)
    with _lock:
        now = time.time()
        for old_state, (_, expires) in list(_pending.items()):
            if expires < now:
                _pending.pop(old_state, None)
        _pending[state] = (verifier, now + 600)
    query = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": _SCOPES,
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    })
    return f"{_AUTH_URL}?{query}"


def _request_json(url: str, *, data: bytes | None = None, headers: dict | None = None) -> dict:
    request = Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read(4096).decode("utf-8", "replace")
        except Exception:
            pass
        try:
            payload = json.loads(detail)
            detail = str(payload.get("error_description") or payload.get("error", ""))
        except Exception:
            pass
        if exc.code == 401:
            message = "Spotify sign-in expired. Connect your Spotify account again."
        elif exc.code == 403:
            message = "Spotify did not allow access to this playlist. The signed-in account must own it or collaborate on it, and playlist access must be approved."
        elif exc.code == 404:
            message = "Spotify could not find this playlist for the signed-in account. Check the link and its sharing access."
        elif exc.code == 429:
            message = "Spotify is rate-limiting playlist imports. Wait a little, then retry."
        else:
            message = "Spotify could not complete the playlist request. Check the Spotify app setup and try again."
        raise SpotifyImportError(f"{message}{(' ' + detail) if detail and exc.code not in (401, 403, 404, 429) else ''}", exc.code) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SpotifyImportError("Viora could not reach Spotify. Check your internet connection and retry.", 503) from exc


def complete_authorization(client_id: str, redirect_uri: str, code: str, state: str) -> None:
    global _token
    with _lock:
        pending = _pending.pop(str(state or ""), None)
    if not pending or pending[1] < time.time():
        raise SpotifyImportError("Spotify sign-in could not be verified. Start Connect Spotify again.", 400)
    verifier = pending[0]
    body = urlencode({
        "client_id": client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }).encode("utf-8")
    result = _request_json(_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _lock:
        _token = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_at": time.time() + int(result.get("expires_in", 3600)),
        }


def _access_token(client_id: str) -> str:
    global _token
    with _lock:
        current = dict(_token or {})
    if not current:
        raise SpotifyImportError("Connect Spotify first to import a playlist.", 401)
    if float(current.get("expires_at", 0)) > time.time() + 45:
        return str(current.get("access_token", ""))
    refresh = current.get("refresh_token")
    if not refresh:
        with _lock:
            _token = None
        raise SpotifyImportError("Spotify sign-in expired. Connect your Spotify account again.", 401)
    body = urlencode({"client_id": client_id, "grant_type": "refresh_token", "refresh_token": refresh}).encode("utf-8")
    result = _request_json(_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _lock:
        _token = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token") or refresh,
            "expires_at": time.time() + int(result.get("expires_in", 3600)),
        }
        return str(_token["access_token"])


def fetch_playlist_tracks(client_id: str, playlist_id: str, limit: int = 100) -> list[dict[str, str]]:
    token = _access_token(client_id)
    result: list[dict[str, str]] = []
    offset = 0
    while len(result) < min(max(1, int(limit)), 100):
        url = f"{_API_ROOT}/playlists/{playlist_id}/items?limit=50&offset={offset}"
        page = _request_json(url, headers={"Authorization": f"Bearer {token}"})
        items = page.get("items") or []
        for item in items:
            track = item.get("item") or item.get("track") or {}
            if track.get("type") not in (None, "track"):
                continue
            title = str(track.get("name") or "").strip()
            artists = track.get("artists") or []
            artist = ", ".join(str(entry.get("name") or "").strip() for entry in artists if entry.get("name"))
            if title:
                result.append({"title": title[:220], "artist": artist[:180]})
                if len(result) >= min(max(1, int(limit)), 100):
                    break
        if not items or not page.get("next"):
            break
        offset += len(items)
    if not result:
        raise SpotifyImportError("Spotify returned no playable tracks from this playlist. It may be empty or inaccessible to this account.", 404)
    return result
