# Viora v15 persistence layer
from __future__ import annotations

import json
import os
import sqlite3
import shutil
import threading
import time
import re
from pathlib import Path
from typing import Any

from config import DATA_DIR, IS_FROZEN, ROOT


class Database:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or (DATA_DIR / "library.db"))
        migrated_legacy = False
        if path is None and not self.path.exists() and not IS_FROZEN:
            # Migrate a prior source-install library into the shared per-user
            # location, so source and packaged Viora builds keep one profile.
            legacy = ROOT / "data" / "library.db"
            if legacy.is_file() and legacy.resolve() != self.path.resolve():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                source = sqlite3.connect(f"file:{legacy.as_posix()}?mode=ro", uri=True)
                target = sqlite3.connect(self.path)
                try:
                    source.backup(target)
                    migrated_legacy = True
                finally:
                    target.close()
                    source.close()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._configure()
        self._migrate()
        legacy_downloads = ROOT / "downloads"
        if migrated_legacy and legacy_downloads.is_dir() and any(legacy_downloads.iterdir()):
            # Preserve access to previously downloaded files without copying a
            # potentially large audio collection during first launch.
            self.set_setting("download_dir", str(legacy_downloads.resolve()))

    def _configure(self):
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA busy_timeout=3000")

    def _migrate(self):
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    searched_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tracks (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL DEFAULT 'youtube',
                    youtube_id TEXT,
                    title TEXT NOT NULL,
                    artist TEXT,
                    channel TEXT,
                    duration REAL,
                    thumbnail TEXT,
                    watch_url TEXT,
                    media_type TEXT NOT NULL DEFAULT 'MUSIC',
                    local_path TEXT,
                    is_downloaded INTEGER NOT NULL DEFAULT 0,
                    is_favorite INTEGER NOT NULL DEFAULT 0,
                    play_count INTEGER NOT NULL DEFAULT 0,
                    skip_count INTEGER NOT NULL DEFAULT 0,
                    last_played_at REAL,
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
                CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
                CREATE INDEX IF NOT EXISTS idx_tracks_favorite ON tracks(is_favorite);
                CREATE INDEX IF NOT EXISTS idx_tracks_downloaded ON tracks(is_downloaded);

                CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                    id UNINDEXED,
                    title,
                    artist,
                    channel,
                    content='tracks',
                    content_rowid='rowid'
                );

                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    played_seconds REAL DEFAULT 0,
                    completion_ratio REAL DEFAULT 0,
                    action TEXT DEFAULT 'play',
                    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_history_started ON history(started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_history_track ON history(track_id);

                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS playlist_settings (
                    playlist_id INTEGER PRIMARY KEY,
                    sort_mode TEXT NOT NULL DEFAULT 'manual',
                    FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id INTEGER NOT NULL,
                    track_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    added_at REAL NOT NULL,
                    PRIMARY KEY(playlist_id, track_id),
                    FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS onboarding (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    completed INTEGER NOT NULL DEFAULT 0,
                    favorite_artists TEXT DEFAULT '[]',
                    genres TEXT DEFAULT '[]',
                    languages TEXT DEFAULT '[]',
                    moods TEXT DEFAULT '[]',
                    discovery_level TEXT DEFAULT 'balanced',
                    updated_at REAL NOT NULL
                );
                """
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO onboarding(id, updated_at) VALUES(1, ?)",
                (time.time(),),
            )
            self._refresh_fts()

    def close(self):
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value or [], ensure_ascii=False)

    @staticmethod
    def _decode_list(value: str | None) -> list[str]:
        try:
            parsed = json.loads(value or "[]")
            return [str(x) for x in parsed if str(x).strip()]
        except Exception:
            return []

    def _refresh_fts(self):
        self._conn.execute("INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')")

    def set_setting(self, key: str, value: Any):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def get_setting(self, key: str, default: Any = None):
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except Exception:
            return row[0]

    def upsert_track(self, track: dict[str, Any], source: str | None = None) -> str:
        identity = str(
            track.get("id")
            or track.get("youtube_id")
            or track.get("local_id")
            or track.get("watch_url")
            or track.get("title")
        ).strip()
        if not identity:
            raise ValueError("Track needs an id or title")
        now = time.time()
        source = source or str(track.get("source") or ("local" if track.get("local_path") else "youtube"))
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO tracks(
                    id, source, youtube_id, title, artist, channel, duration,
                    thumbnail, watch_url, media_type, local_path,
                    is_downloaded, is_favorite, play_count, skip_count,
                    last_played_at, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    source=COALESCE(excluded.source, tracks.source),
                    youtube_id=COALESCE(excluded.youtube_id, tracks.youtube_id),
                    title=COALESCE(excluded.title, tracks.title),
                    artist=COALESCE(excluded.artist, tracks.artist),
                    channel=COALESCE(excluded.channel, tracks.channel),
                    duration=COALESCE(excluded.duration, tracks.duration),
                    thumbnail=COALESCE(excluded.thumbnail, tracks.thumbnail),
                    watch_url=COALESCE(excluded.watch_url, tracks.watch_url),
                    media_type=COALESCE(excluded.media_type, tracks.media_type),
                    local_path=COALESCE(excluded.local_path, tracks.local_path),
                    is_downloaded=MAX(tracks.is_downloaded, excluded.is_downloaded),
                    is_favorite=MAX(tracks.is_favorite, excluded.is_favorite)
                """,
                (
                    identity,
                    source,
                    track.get("youtube_id") or track.get("id"),
                    str(track.get("title") or "Unknown"),
                    track.get("artist"),
                    track.get("channel") or track.get("uploader"),
                    track.get("duration"),
                    track.get("thumbnail"),
                    track.get("watch_url"),
                    track.get("media_type") or "MUSIC",
                    track.get("local_path"),
                    1 if track.get("is_downloaded") or track.get("local_path") else 0,
                    1 if track.get("is_favorite") else 0,
                    int(track.get("play_count") or 0),
                    int(track.get("skip_count") or 0),
                    track.get("last_played_at"),
                    now,
                ),
            )
            self._refresh_fts()
        return identity

    def get_track(self, track_id: str):
        with self._lock:
            return self._row(self._conn.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone())

    def track_by_local_path(self, local_path: str):
        with self._lock:
            row = self._conn.execute("SELECT * FROM tracks WHERE local_path=? LIMIT 1", (local_path,)).fetchone()
        return self._row(row)

    def downloaded_tracks(self, limit=2000):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tracks WHERE is_downloaded=1 ORDER BY COALESCE(last_played_at,0) DESC, created_at DESC LIMIT ?",
                (max(1, min(int(limit), 10000)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_track(self, track_id: str):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM tracks WHERE id=?", (str(track_id),))
            self._refresh_fts()

    def delete_history_entry(self, history_id: int):
        with self._lock:
            target = self._conn.execute(
                "SELECT t.title, COALESCE(NULLIF(t.artist,''),t.channel,'') artist "
                "FROM history h JOIN tracks t ON t.id=h.track_id WHERE h.id=?",
                (int(history_id),),
            ).fetchone()
            if not target:
                return
            signature = self._history_signature(target[0], target[1])
            matches = self._conn.execute(
                "SELECT h.id,t.title,COALESCE(NULLIF(t.artist,''),t.channel,'') artist "
                "FROM history h JOIN tracks t ON t.id=h.track_id"
            ).fetchall()
            ids = [int(row[0]) for row in matches if self._history_signature(row[1], row[2]) == signature]
            with self._conn:
                for offset in range(0, len(ids), 800):
                    chunk = ids[offset:offset + 800]
                    marks = ",".join("?" for _ in chunk)
                    self._conn.execute(f"DELETE FROM history WHERE id IN ({marks})", chunk)

    def delete_search(self, query: str):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM search_history WHERE query=? COLLATE NOCASE", (str(query or ""),))

    def engagement(self, track_ids):
        track_ids = [str(x) for x in track_ids if x]
        if not track_ids:
            return {}
        marks = ",".join("?" for _ in track_ids)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT track_id, AVG(completion_ratio) completion_rate, "
                f"AVG(CASE WHEN action='skip' THEN 1.0 ELSE 0.0 END) skip_rate "
                f"FROM history WHERE track_id IN ({marks}) GROUP BY track_id",
                track_ids,
            ).fetchall()
        return {str(row[0]): {"completion_rate": float(row[1] or 0), "skip_rate": float(row[2] or 0)} for row in rows}

    def search_tracks(self, query: str, limit: int = 30, downloaded_only: bool = False):
        query = " ".join(str(query or "").split()).strip()
        limit = max(1, min(int(limit), 100))
        params: list[Any] = []
        downloaded_clause = "AND t.is_downloaded=1" if downloaded_only else ""

        with self._lock:
            if not query:
                rows = self._conn.execute(
                    f"SELECT t.* FROM tracks t WHERE 1=1 {downloaded_clause} "
                    "ORDER BY COALESCE(t.last_played_at,0) DESC, t.created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                tokens = [x for x in query.replace('"', ' ').split() if x]
                like = f"%{query}%"
                rows = self._conn.execute(
                    f"""
                    SELECT t.*,
                           (CASE WHEN lower(t.title) LIKE lower(?) THEN 40 ELSE 0 END
                            + CASE WHEN lower(COALESCE(t.artist,'')) LIKE lower(?) THEN 35 ELSE 0 END
                            + CASE WHEN lower(COALESCE(t.channel,'')) LIKE lower(?) THEN 20 ELSE 0 END
                            + CASE WHEN t.is_favorite=1 THEN 4 ELSE 0 END) AS relevance
                    FROM tracks t
                    WHERE (lower(t.title) LIKE lower(?)
                       OR lower(COALESCE(t.artist,'')) LIKE lower(?)
                       OR lower(COALESCE(t.channel,'')) LIKE lower(?)
                       OR lower(t.id) LIKE lower(?))
                      {downloaded_clause}
                    ORDER BY relevance DESC, COALESCE(t.last_played_at,0) DESC
                    LIMIT ?
                    """,
                    (like, like, like, like, like, like, like, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def list_tracks(self, limit=100, downloaded_only=False, favorites_only=False):
        clauses = []
        params: list[Any] = []
        if downloaded_only:
            clauses.append("is_downloaded=1")
        if favorites_only:
            clauses.append("is_favorite=1")
        where = " AND ".join(clauses) or "1=1"
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM tracks WHERE {where} ORDER BY COALESCE(last_played_at,0) DESC, created_at DESC LIMIT ?",
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [dict(r) for r in rows]

    def chart_tracks(self, kind="most-played", limit=50):
        """Return a local-only chart based on this device's play counts."""
        kind = str(kind or "most-played").lower()
        if kind not in {"most-played", "favorites"}:
            raise ValueError("Choose most-played or favorites.")
        favorite_clause = "AND is_favorite=1" if kind == "favorites" else "AND play_count>0"
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT * FROM tracks WHERE 1=1 {favorite_clause}
                    ORDER BY play_count DESC, is_favorite DESC,
                             COALESCE(last_played_at,0) DESC, title COLLATE NOCASE
                    LIMIT ?""",
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_favorite(self, track: dict[str, Any], value: bool):
        track_id = self.upsert_track(track)
        with self._lock, self._conn:
            self._conn.execute("UPDATE tracks SET is_favorite=? WHERE id=?", (1 if value else 0, track_id))
        return self.get_track(track_id)

    def record_play_start(self, track: dict[str, Any]) -> int:
        track_id = self.upsert_track(track)
        now = time.time()
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO history(track_id, started_at, action) VALUES(?,?,?)",
                (track_id, now, "play"),
            )
            self._conn.execute(
                "UPDATE tracks SET play_count=play_count+1, last_played_at=? WHERE id=?",
                (now, track_id),
            )
        return int(cur.lastrowid)

    def record_play_end(self, history_id: int, duration: float | None, played_seconds: float | None, action="complete"):
        started = time.time()
        played_seconds = max(0.0, float(played_seconds or 0))
        ratio = 0.0 if not duration else min(1.0, played_seconds / max(float(duration), 1.0))
        with self._lock, self._conn:
            row = self._conn.execute("SELECT track_id FROM history WHERE id=?", (history_id,)).fetchone()
            self._conn.execute(
                "UPDATE history SET ended_at=?, played_seconds=?, completion_ratio=?, action=? WHERE id=?",
                (started, played_seconds, ratio, action, history_id),
            )
            if action in {"skip", "error"} and row:
                self._conn.execute("UPDATE tracks SET skip_count=skip_count+1 WHERE id=?", (row[0],))

    @staticmethod
    def _history_signature(title, artist):
        clean = lambda value: re.sub(r"[^\w]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()
        title_key = clean(title)
        artist_key = clean(artist)
        return (title_key, artist_key) if artist_key else (title_key, "")

    def history(self, limit=50):
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT h.*, h.id AS history_id, t.id AS track_key, t.title, t.artist, t.channel, t.thumbnail, t.duration,
                       t.watch_url, t.local_path, t.is_downloaded, t.is_favorite, t.media_type, t.play_count, t.last_played_at
                FROM history h JOIN tracks t ON t.id=h.track_id
                ORDER BY h.started_at DESC LIMIT 3000
                """,
            ).fetchall()
        result, seen = [], set()
        for row in rows:
            item = dict(row)
            signature = self._history_signature(item.get("title"), item.get("artist") or item.get("channel"))
            if not signature[0] or signature in seen:
                continue
            seen.add(signature)
            result.append(item)
            if len(result) >= max(1, min(int(limit), 200)):
                break
        return result

    def backup_to(self, destination: Path):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(destination)
        try:
            with self._lock:
                self._conn.backup(target)
        finally:
            target.close()
        return destination

    def restore_from(self, source: Path):
        source = Path(source).resolve()
        probe = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        try:
            integrity = probe.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("The selected backup is damaged or incomplete.")
            tables = {row[0] for row in probe.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"settings", "tracks", "history", "playlists", "playlist_tracks", "onboarding"}.issubset(tables):
                raise ValueError("This is not a Viora library backup.")
        finally:
            probe.close()

        safety = self.path.with_name(self.path.name + ".before-restore")
        with self._lock:
            self._conn.close()
            try:
                if self.path.exists():
                    shutil.copy2(self.path, safety)
                for suffix in ("-wal", "-shm"):
                    sidecar = Path(str(self.path) + suffix)
                    if sidecar.exists():
                        sidecar.unlink()
                shutil.copy2(source, self.path)
                self._conn = sqlite3.connect(self.path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._configure()
                self._migrate()
            except Exception:
                try:
                    self._conn.close()
                except Exception:
                    pass
                if safety.exists():
                    shutil.copy2(safety, self.path)
                self._conn = sqlite3.connect(self.path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._configure()
                self._migrate()
                raise
            finally:
                if safety.exists():
                    safety.unlink()
        return self.stats()

    def clear_history(self):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM history")
            self._conn.execute("UPDATE tracks SET last_played_at=NULL, play_count=0, skip_count=0")

    def recent_tracks(self, limit=12):
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT t.* FROM tracks t
                WHERE t.last_played_at IS NOT NULL
                ORDER BY t.last_played_at DESC
                LIMIT 3000
                """,
            ).fetchall()
        result, seen = [], set()
        for row in rows:
            item = dict(row)
            signature = self._history_signature(item.get("title"), item.get("artist") or item.get("channel"))
            if not signature[0] or signature in seen:
                continue
            seen.add(signature)
            result.append(item)
            if len(result) >= max(1, min(int(limit), 100)):
                break
        return result

    def heard_track_ids(self):
        with self._lock:
            rows = self._conn.execute("SELECT DISTINCT track_id FROM history").fetchall()
        return {str(row[0]) for row in rows}

    def heard_track_signatures(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT t.title, COALESCE(NULLIF(t.artist,''),t.channel,'') artist "
                "FROM history h JOIN tracks t ON t.id=h.track_id"
            ).fetchall()
        return {self._history_signature(row[0], row[1]) for row in rows}

    def frequent_artists(self, limit=20):
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT COALESCE(NULLIF(artist,''), channel, 'Unknown') artist,
                       SUM(play_count) plays,
                       SUM(skip_count) skips
                FROM tracks
                WHERE artist IS NOT NULL OR channel IS NOT NULL
                GROUP BY artist
                ORDER BY plays DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def playlist_create(self, name: str, description: str = ""):
        name = " ".join(str(name or "").split()).strip()
        if not name:
            raise ValueError("Playlist name is required")
        now = time.time()
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO playlists(name,description,created_at,updated_at) VALUES(?,?,?,?)",
                (name[:120], str(description or "")[:500], now, now),
            )
            return int(cur.lastrowid)

    def playlist_rename(self, playlist_id: int, name: str):
        name = " ".join(str(name or "").split()).strip()
        if not name:
            raise ValueError("Playlist name is required")
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE playlists SET name=?, updated_at=? WHERE id=?",
                (name[:120], time.time(), int(playlist_id)),
            )
            if not cur.rowcount:
                return None
        return self.playlist_get(playlist_id)

    def playlist_reorder(self, playlist_id: int, track_ids: list[str]):
        track_ids = [str(x) for x in track_ids]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError("A track can appear only once in a playlist order")
        with self._lock, self._conn:
            current = [row[0] for row in self._conn.execute(
                "SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position",
                (int(playlist_id),),
            ).fetchall()]
            if not current:
                exists = self._conn.execute("SELECT 1 FROM playlists WHERE id=?", (int(playlist_id),)).fetchone()
                return self.playlist_get(playlist_id) if exists and not track_ids else None
            if set(current) != set(track_ids):
                raise ValueError("The requested order must include every playlist track exactly once")
            for position, track_id in enumerate(track_ids):
                self._conn.execute(
                    "UPDATE playlist_tracks SET position=? WHERE playlist_id=? AND track_id=?",
                    (position, int(playlist_id), track_id),
                )
            self._conn.execute("UPDATE playlists SET updated_at=? WHERE id=?", (time.time(), int(playlist_id)))
        return self.playlist_get(playlist_id)

    def playlists(self):
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT p.*, COUNT(pt.track_id) track_count,
                       (SELECT t.thumbnail FROM playlist_tracks pt2 JOIN tracks t ON t.id=pt2.track_id
                        WHERE pt2.playlist_id=p.id ORDER BY pt2.position LIMIT 1) thumbnail
                FROM playlists p LEFT JOIN playlist_tracks pt ON pt.playlist_id=p.id
                GROUP BY p.id ORDER BY p.updated_at DESC
                """
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            full = self.playlist_get(item["id"])
            tracks = (full or {}).get("tracks", [])
            item["sort_mode"] = (full or {}).get("sort_mode", "manual")
            item["artworks"] = [t.get("thumbnail") for t in tracks[:4] if t.get("thumbnail")]
            result.append(item)
        return result

    def playlist_get(self, playlist_id: int):
        with self._lock:
            row = self._conn.execute("SELECT * FROM playlists WHERE id=?", (int(playlist_id),)).fetchone()
            if not row:
                return None
            tracks = self._conn.execute(
                """
                SELECT t.*, pt.position FROM playlist_tracks pt JOIN tracks t ON t.id=pt.track_id
                WHERE pt.playlist_id=? ORDER BY pt.position
                """,
                (int(playlist_id),),
            ).fetchall()
        result = dict(row)
        result["tracks"] = [dict(x) for x in tracks]
        sort_row = self._conn.execute(
            "SELECT sort_mode FROM playlist_settings WHERE playlist_id=?", (int(playlist_id),)
        ).fetchone()
        result["sort_mode"] = sort_row[0] if sort_row else "manual"
        if result["sort_mode"] == "popular":
            result["tracks"].sort(key=lambda t: (int(t.get("play_count") or 0), t.get("title", "").casefold()), reverse=True)
        elif result["sort_mode"] == "least_played":
            result["tracks"].sort(key=lambda t: (int(t.get("play_count") or 0), t.get("title", "").casefold()))
        elif result["sort_mode"] == "title":
            result["tracks"].sort(key=lambda t: (t.get("title") or "").casefold())
        elif result["sort_mode"] == "artist":
            result["tracks"].sort(key=lambda t: (t.get("artist") or t.get("channel") or "").casefold())
        result["artworks"] = [t.get("thumbnail") for t in result["tracks"][:4] if t.get("thumbnail")]
        return result

    def playlist_set_sort(self, playlist_id: int, sort_mode: str):
        allowed = {"manual", "popular", "least_played", "title", "artist"}
        sort_mode = str(sort_mode or "manual").lower()
        if sort_mode not in allowed:
            raise ValueError("Choose manual, most played, least played, title, or artist sorting")
        with self._lock, self._conn:
            exists = self._conn.execute("SELECT 1 FROM playlists WHERE id=?", (int(playlist_id),)).fetchone()
            if not exists:
                return None
            self._conn.execute(
                "INSERT INTO playlist_settings(playlist_id,sort_mode) VALUES(?,?) "
                "ON CONFLICT(playlist_id) DO UPDATE SET sort_mode=excluded.sort_mode",
                (int(playlist_id), sort_mode),
            )
        return self.playlist_get(playlist_id)

    def playlist_add(self, playlist_id: int, track: dict[str, Any]):
        track_id = self.upsert_track(track)
        with self._lock, self._conn:
            pos = self._conn.execute(
                "SELECT COALESCE(MAX(position)+1,0) FROM playlist_tracks WHERE playlist_id=?",
                (int(playlist_id),),
            ).fetchone()[0]
            self._conn.execute(
                "INSERT OR IGNORE INTO playlist_tracks(playlist_id,track_id,position,added_at) VALUES(?,?,?,?)",
                (int(playlist_id), track_id, int(pos), time.time()),
            )
            self._conn.execute("UPDATE playlists SET updated_at=? WHERE id=?", (time.time(), int(playlist_id)))
        return self.playlist_get(playlist_id)

    def playlist_remove(self, playlist_id: int, track_id: str):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?", (int(playlist_id), track_id))
            self._conn.execute("UPDATE playlists SET updated_at=? WHERE id=?", (time.time(), int(playlist_id)))
            rows = self._conn.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position", (int(playlist_id),)).fetchall()
            for pos, row in enumerate(rows):
                self._conn.execute("UPDATE playlist_tracks SET position=? WHERE playlist_id=? AND track_id=?", (pos, int(playlist_id), row[0]))
        return self.playlist_get(playlist_id)

    def playlist_delete(self, playlist_id: int):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM playlists WHERE id=?", (int(playlist_id),))

    def add_search(self, query: str):
        query = " ".join(str(query or "").split()).strip()[:240]
        if not query:
            return self.recent_searches()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO search_history(query,searched_at) VALUES(?,?) "
                "ON CONFLICT(query) DO UPDATE SET searched_at=excluded.searched_at",
                (query, time.time()),
            )
            self._conn.execute(
                "DELETE FROM search_history WHERE id NOT IN "
                "(SELECT id FROM search_history ORDER BY searched_at DESC LIMIT 20)"
            )
        return self.recent_searches()

    def recent_searches(self, limit: int = 10):
        with self._lock:
            rows = self._conn.execute(
                "SELECT query, searched_at FROM search_history ORDER BY searched_at DESC LIMIT ?",
                (max(1, min(int(limit), 20)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_searches(self):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM search_history")

    def get_onboarding(self):
        with self._lock:
            row = self._conn.execute("SELECT * FROM onboarding WHERE id=1").fetchone()
        result = dict(row or {})
        for key in ("favorite_artists", "genres", "languages", "moods"):
            result[key] = self._decode_list(result.get(key))
        result["completed"] = bool(result.get("completed", 0))
        return result

    def save_onboarding(self, favorite_artists, genres, languages, moods, discovery_level="balanced"):
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO onboarding(id,completed,favorite_artists,genres,languages,moods,discovery_level,updated_at)
                VALUES(1,1,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    completed=1,
                    favorite_artists=excluded.favorite_artists,
                    genres=excluded.genres,
                    languages=excluded.languages,
                    moods=excluded.moods,
                    discovery_level=excluded.discovery_level,
                    updated_at=excluded.updated_at
                """,
                (
                    self._json(favorite_artists),
                    self._json(genres),
                    self._json(languages),
                    self._json(moods),
                    discovery_level if discovery_level in {"familiar", "balanced", "explorer"} else "balanced",
                    now,
                ),
            )
        return self.get_onboarding()

    def stats(self):
        with self._lock:
            return {
                "tracks": self._conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0],
                "downloads": self._conn.execute("SELECT COUNT(*) FROM tracks WHERE is_downloaded=1").fetchone()[0],
                "favorites": self._conn.execute("SELECT COUNT(*) FROM tracks WHERE is_favorite=1").fetchone()[0],
                "history": self._conn.execute("SELECT COUNT(*) FROM history").fetchone()[0],
                "playlists": self._conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0],
            }


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
