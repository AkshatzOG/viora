from __future__ import annotations

import os
import re
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from agent.brain import MusicBrain
from agent.router import AgentRouter
from config import HOST, PORT, FLASK_SECRET_KEY, AUTO_OPEN_BROWSER, DATA_DIR, DOWNLOAD_DIR
from core.connectivity import browser_online, network_available, set_browser_online
from core.charts import STOREFRONTS, regional_top_songs
from core.catalog import popular_artist_picks
from core.playlist_import import parse_playlist_file, playlist_import_status, start_playlist_import
from core.external_playlists import parse_external_playlist_source
from core.database import get_db
from core.downloader import download_status, download_track
from core.library import find_local, get_download_dir, is_local_file, library_items, normalize_track_for_client, scan_downloads, storage_info
from core.player_bridge import sync_history_from_player, play as smart_play
from core.recommender import home_recommendations, similar_to, prepare_for_playback
from core.rag import grounded_insight, retrieve_context
from tools.playback import player
from tools.youtube import search_parallel, search_youtube, prepare_tracks
from tools.ranker import rank_tracks


app = Flask(__name__)
APP_VERSION = "15.8.4"
app.secret_key = FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

brain = MusicBrain()
router = AgentRouter(brain)

_HOME_CACHE = {"at": 0.0, "data": None}
_HOME_LOCK = threading.RLock()

CHART_CATEGORIES = {
    "love": ("Love", "love songs official audio"), "pop": ("Pop", "pop hits official audio"),
    "english": ("English", "English songs official audio"), "hindi": ("Hindi", "Hindi songs official audio"),
    "phonk": ("Phonk", "phonk official audio"), "hiphop": ("Hip-hop", "hip hop official audio"),
    "afrobeats": ("Afrobeats", "afrobeats official audio"), "kpop": ("K-pop", "k-pop official audio"),
    "jpop": ("J-pop", "j-pop official audio"), "workout": ("Workout", "workout music official audio"),
    "chill": ("Chill", "chill songs official audio"), "focus": ("Focus", "focus music official audio"),
    "dance": ("Dance", "dance hits official audio"), "indie": ("Indie", "indie music official audio"),
    "rock": ("Rock", "rock songs official audio"), "rnb": ("R&B", "r and b official audio"),
    "latin": ("Latin", "latin music official audio"), "country": ("Country", "country music official audio"),
    "jazz": ("Jazz", "jazz songs official audio"), "metal": ("Metal", "metal music official audio"),
    "acoustic": ("Acoustic", "acoustic songs official audio"), "devotional": ("Devotional", "devotional songs official audio"),
    "punjabi": ("Punjabi", "punjabi songs official audio"), "electronic": ("Electronic", "electronic music official audio"),
    "throwbacks": ("Throwbacks", "classic hits official audio"),
}
CHART_DEFAULTS = ["top50", "week", "ytdaily", "viora_top", "pop", "hindi"]
CHART_EXTERNAL_IDS = {"week", "ytdaily", "spotifycharts"}
CHART_LOCAL_IDS = {"viora_top", "viora_favorites"}


def _invalidate_home():
    with _HOME_LOCK:
        _HOME_CACHE["at"] = 0.0
        _HOME_CACHE["data"] = None


def _home(force=False):
    now = time.monotonic()
    with _HOME_LOCK:
        if not force and _HOME_CACHE["data"] is not None and now - _HOME_CACHE["at"] < 60:
            return _HOME_CACHE["data"]
    data = home_recommendations()
    with _HOME_LOCK:
        _HOME_CACHE["at"] = now
        _HOME_CACHE["data"] = data
    return data


def _track_payload(raw):
    data = dict(raw or {})
    if not data.get("id"):
        data["id"] = data.get("youtube_id") or data.get("watch_url") or data.get("title")
    data["title"] = str(data.get("title") or "Unknown")
    data["artist"] = data.get("artist") or data.get("channel")
    data["channel"] = data.get("channel") or data.get("artist")
    return data


def _prepare_payload_track(track):
    track = _track_payload(track)
    mode = get_db().get_setting("playback_mode", "auto")
    if track.get("local_path") and is_local_file(track["local_path"]) and mode != "online":
        return track
    if mode == "offline":
        return None
    if not network_available():
        return None
    if mode == "online":
        track.pop("local_path", None)
        track["is_downloaded"] = False
    prepared = prepare_tracks([track], workers=1)
    return prepared[0] if prepared else None


def _ensure_track_saved(track):
    return get_db().upsert_track(track)


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return render_template("index.html", app_version=APP_VERSION, theme=get_db().get_setting("theme", "dark"))


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(app.static_folder, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/command", methods=["POST"])
def command():
    text = str((request.get_json(silent=True) or {}).get("text", "")).strip()
    if not text:
        return jsonify({"reply": "Say something first."}), 400
    try:
        reply = router.process(text)
        _invalidate_home()
        if router.last_intent.get("action") == "CLOSE":
            _shutdown_process()
        return jsonify({"reply": reply, "status": player.status()})
    except Exception as exc:
        print("[app] command error:", repr(exc))
        return jsonify({"reply": "Something went wrong while handling that command.", "error": str(exc), "status": player.status()}), 500


@app.route("/api/agent", methods=["POST"])
def api_agent():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("message") or "").strip()
    if not prompt:
        return jsonify({"error": "Type a request for the Viora Agent."}), 400
    context = retrieve_context(prompt, limit=8)
    insight = grounded_insight(prompt, context)
    try:
        playlist_request = re.search(r"\b(?:make|create|build|put together)\s+(?:me\s+)?(?:a\s+)?playlist\b", prompt, re.I)
        if playlist_request:
            named = re.search(r"\b(?:called|named|titled)\s+([^,.!?]+)", prompt, re.I)
            mood_query = re.sub(r"\b(?:please|make|create|build|put together|me|a|an|the|new|playlist|called|named|titled)\b", " ", prompt, flags=re.I)
            mood_query = re.sub(r"\s+", " ", mood_query).strip(" .,!?:;")
            mood_query = re.sub(r"^(?:for|about|with)\s+", "", mood_query, flags=re.I)
            name = (named.group(1).strip() if named else mood_query.title() or "Viora Mix")[:80]
            intent = brain.understand(f"recommend 12 songs for {mood_query or name}")
            intent["action"] = "RECOMMEND"
            tracks = router._resolve(intent)
            prepared = prepare_for_playback(tracks[:30])
            if not prepared:
                reply = "I couldn't find enough grounded music results to make that playlist yet. Try a clearer mood or artist."
                router.last_intent = {**intent, "action": "CREATE_PLAYLIST", "playlist_name": name}
            else:
                playlist_id = get_db().playlist_create(name)
                for track in prepared:
                    get_db().playlist_add(playlist_id, track)
                playlist = get_db().playlist_get(playlist_id)
                router.last_intent = {**intent, "action": "CREATE_PLAYLIST", "playlist_name": name}
                reply = f"I made “{playlist['name']}” with {len(playlist['tracks'])} retrieved tracks, using your playback mode and music profile."
                context["tracks"] = playlist["tracks"]
                _invalidate_home()
        else:
            reply = insight if insight is not None else router.process(prompt)
            if insight is not None:
                router.last_intent = {"action": "LOCAL_INSIGHT", "query": prompt, "reason": "retrieved local context"}
    except Exception as exc:
        print("[agent] request failed:", repr(exc))
        return jsonify({"error": "The agent couldn't finish that request. Try a shorter prompt."}), 500
    status_data = player.status()
    if router.last_intent.get("action") == "CLOSE":
        threading.Timer(0.4, _shutdown_process).start()
    # Personal RAG context belongs to insight replies only. It must never be
    # shown as the answer to an unrelated query such as "trending phonk".
    source_tracks = (context.get("tracks") or [])[:5] if router.last_intent.get("action") == "LOCAL_INSIGHT" else (router.last_tracks or [])[:6]
    return jsonify({
        "reply": reply,
        "intent": dict(router.last_intent or {}),
        "sources": [
            {key: track.get(key) for key in ("id", "title", "artist", "channel", "thumbnail", "watch_url", "local_path", "is_downloaded", "is_favorite", "duration")}
            for track in source_tracks[:6]
        ],
        "retrieval": "local-library-rag",
        "status": status_data,
    })


@app.route("/api/artists")
def api_artists():
    return jsonify(get_db().frequent_artists(100))


@app.route("/api/artist-picks")
def api_artist_picks():
    try:
        return jsonify(popular_artist_picks())
    except Exception as exc:
        print("[artists] image lookup failed:", repr(exc))
        from core.catalog import POPULAR_ARTISTS
        return jsonify([{"name": name, "region": region, "image": "", "source_url": ""} for name, region in POPULAR_ARTISTS])


@app.route("/api/charts")
def api_charts():
    storefront = str(request.args.get("region", "IN")).upper()
    try:
        force_refresh = request.args.get("refresh", "0").lower() in {"1", "true", "yes"}
        return jsonify(regional_top_songs(storefront, request.args.get("limit", 100), force_refresh=force_refresh))
    except ValueError as exc:
        return jsonify({"error": str(exc), "regions": STOREFRONTS}), 400
    except Exception as exc:
        print("[charts] feed unavailable:", repr(exc))
        return jsonify({"error": "The chart source is unavailable right now. Try again in a moment."}), 503


@app.route("/api/charts/viora")
def api_viora_charts():
    kind = str(request.args.get("kind", "most-played")).lower()
    if kind not in {"most-played", "favorites"}:
        return jsonify({"error": "Choose a Viora chart type."}), 400
    rows = get_db().chart_tracks(kind=kind, limit=50)
    return jsonify({
        "kind": kind,
        "results": rows,
        "source": "Viora · this device only",
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
    })


@app.route("/api/chart-mix")
def api_chart_mix():
    category = str(request.args.get("category", "")).lower()
    if category not in CHART_CATEGORIES:
        return jsonify({"error": "Choose a chart from the Viora chart catalog."}), 400
    title, query = CHART_CATEGORIES[category]
    if get_db().get_setting("playback_mode", "auto") == "offline" or not network_available():
        return jsonify({"category": category, "title": title, "results": [], "offline": True, "source": "Viora search mix"})
    try:
        candidates = search_parallel([f'"{query}"', query], limit_each=12, workers=2)
        results = rank_tracks(candidates, query=query, limit=24, prefer_tracks=True)
        for track in results:
            get_db().upsert_track(track)
        return jsonify({"category": category, "title": title, "results": results, "offline": False, "source": "Viora search mix · official-source signals first"})
    except Exception as exc:
        print("[chart mix] search failed:", repr(exc))
        return jsonify({"category": category, "title": title, "results": [], "offline": False, "error": "This discovery mix is unavailable right now."}), 503


@app.route("/api/network", methods=["GET", "POST"])
def api_network():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        online = payload.get("online")
        if not isinstance(online, bool):
            return jsonify({"error": "Send a boolean online state."}), 400
        set_browser_online(online)
    online = browser_online()
    return jsonify({"online": network_available(), "detected": online is not None, "mode": get_db().get_setting("playback_mode", "auto")})


@app.route("/api/audio-reactivity")
def api_audio_reactivity():
    if not get_db().get_setting("music_reactive", True):
        return jsonify({"audio_energy": 0, "audio_beat": 0, "audio_bass": 0})
    return jsonify(player.audio_analyzer.values())


@app.route("/api/playlist-import", methods=["POST"])
def api_playlist_import():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "Choose a playlist export to import."}), 400
    try:
        raw = uploaded.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            return jsonify({"error": "Playlist exports must be under 5 MB."}), 413
        text = raw.decode("utf-8-sig", errors="replace")
        tracks = parse_playlist_file(uploaded.filename or "playlist.txt", text)
        job_id = start_playlist_import(uploaded.filename or "playlist", request.form.get("name", ""), tracks)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        print("[playlist import] failed to start:", repr(exc))
        return jsonify({"error": "Viora could not read that playlist export."}), 400
    return jsonify({"job_id": job_id, "total": len(tracks), "message": "Matching started in the background. You can keep listening while Viora builds the playlist."}), 202


@app.route("/api/playlist-import/<job_id>")
def api_playlist_import_progress(job_id):
    job = playlist_import_status(job_id)
    return (jsonify(job), 200) if job else (jsonify({"error": "That import has expired or is unknown."}), 404)


@app.route("/api/playlist-embed", methods=["POST"])
def api_playlist_embed():
    payload = request.get_json(silent=True) or {}
    try:
        embed = parse_external_playlist_source(payload.get("source", ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        **embed,
        "message": (f"{embed['provider']} provides this playlist preview. Viora saves the link and uses the provider's player; it does not copy playlist tracks or audio." if embed["embed_supported"] else f"{embed['provider']} does not provide a supported Viora embed here. Save the link and open it in {embed['provider']} when you want to listen."),
    })


def _saved_external_playlists():
    saved = get_db().get_setting("saved_service_playlists", [])
    return [item for item in saved if isinstance(item, dict)] if isinstance(saved, list) else []


@app.route("/api/external-playlists", methods=["GET", "POST"])
def api_external_playlists():
    db = get_db()
    if request.method == "GET":
        saved = _saved_external_playlists()
        return jsonify({"playlists": saved, "count": len(saved)})
    payload = request.get_json(silent=True) or {}
    try:
        source = parse_external_playlist_source(payload.get("source", ""))
        name = " ".join(str(payload.get("name") or source["default_name"]).split()).strip()[:120]
        saved = _saved_external_playlists()
        duplicate = next((item for item in saved if item.get("source_url") == source["source_url"]), None)
        if duplicate:
            return jsonify({"playlist": duplicate, "playlists": saved, "count": len(saved), "message": "That playlist link is already saved."}), 200
        if len(saved) >= 100:
            return jsonify({"error": "You can save up to 100 service playlist links."}), 400
        item = {"id": uuid.uuid4().hex[:16], "name": name or str(source["default_name"]), **source, "created_at": time.time(), "updated_at": time.time()}
        saved.insert(0, item)
        db.set_setting("saved_service_playlists", saved)
        persisted = _saved_external_playlists()
        return jsonify({"playlist": item, "playlists": persisted, "count": len(persisted), "message": "Playlist link saved to your library."}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/external-playlists/<item_id>", methods=["PUT", "DELETE"])
def api_external_playlist_item(item_id):
    db = get_db()
    saved = _saved_external_playlists()
    index = next((i for i, item in enumerate(saved) if str(item.get("id")) == str(item_id)), None)
    if index is None:
        return jsonify({"error": "Saved playlist link was not found."}), 404
    if request.method == "DELETE":
        saved.pop(index)
        db.set_setting("saved_service_playlists", saved)
        persisted = _saved_external_playlists()
        return jsonify({"ok": True, "playlists": persisted, "count": len(persisted)})
    payload = request.get_json(silent=True) or {}
    item = dict(saved[index])
    if "source" in payload:
        try:
            parsed = parse_external_playlist_source(payload.get("source", ""))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        item.update(parsed)
    if "name" in payload:
        name = " ".join(str(payload.get("name") or "").split()).strip()
        if not name:
            return jsonify({"error": "Playlist name cannot be empty."}), 400
        item["name"] = name[:120]
    item["updated_at"] = time.time()
    saved[index] = item
    db.set_setting("saved_service_playlists", saved)
    persisted = _saved_external_playlists()
    return jsonify({"playlist": item, "playlists": persisted, "count": len(persisted), "message": "Saved playlist updated."})


@app.route("/api/backup", methods=["GET", "POST"])
def api_backup():
    if request.method == "GET":
        destination = Path(DATA_DIR) / f"viora-backup-{uuid.uuid4().hex}.db"
        try:
            get_db().backup_to(destination)
            response = send_file(destination, as_attachment=True, download_name="viora-library-backup.db", mimetype="application/vnd.sqlite3")
            response.call_on_close(lambda: destination.unlink(missing_ok=True))
            return response
        except Exception as exc:
            destination.unlink(missing_ok=True)
            print("[backup] export failed:", repr(exc))
            return jsonify({"error": "Viora could not create a library backup."}), 500
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"error": "Choose a Viora .db backup file to restore."}), 400
    suffix = Path(uploaded.filename or "").suffix.lower()
    if suffix not in {".db", ".sqlite", ".sqlite3"}:
        return jsonify({"error": "Choose a Viora .db or .sqlite backup."}), 400
    temp_path = Path(DATA_DIR) / f"restore-{uuid.uuid4().hex}.db"
    try:
        uploaded.save(temp_path)
        stats = get_db().restore_from(temp_path)
        _invalidate_home()
        return jsonify({"ok": True, "stats": stats, "message": "Your library, playlists, history, favorites and settings were restored."})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        print("[backup] restore failed:", repr(exc))
        return jsonify({"error": "Viora could not restore that backup. Your current library was kept if validation failed."}), 500
    finally:
        temp_path.unlink(missing_ok=True)


@app.route("/api/home")
def api_home():
    return jsonify(_home(force=request.args.get("refresh") == "1"))


@app.route("/api/onboarding")
def api_onboarding():
    return jsonify(get_db().get_onboarding())


@app.route("/api/onboarding", methods=["POST"])
def api_save_onboarding():
    data = request.get_json(silent=True) or {}
    result = get_db().save_onboarding(
        data.get("favorite_artists") or [],
        data.get("genres") or [],
        data.get("languages") or [],
        data.get("moods") or [],
        data.get("discovery_level") or "balanced",
    )
    for key in ("hide_heard", "show_community"):
        if key in data:
            get_db().set_setting(key, bool(data[key]))
    _invalidate_home()
    return jsonify(result)


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    db = get_db()
    chart_preferences = db.get_setting("chart_preferences", CHART_DEFAULTS)
    valid_chart_ids = {"top50", "top100", *CHART_EXTERNAL_IDS, *CHART_LOCAL_IDS, *CHART_CATEGORIES.keys()}
    if not isinstance(chart_preferences, list):
        chart_preferences = CHART_DEFAULTS
    chart_preferences = [item for item in chart_preferences if item in valid_chart_ids][:12] or CHART_DEFAULTS
    if request.method == "GET":
        return jsonify({
            "theme": db.get_setting("theme", "dark"),
            "hide_heard": db.get_setting("hide_heard", True),
            "show_community": db.get_setting("show_community", True),
            "reduced_motion": db.get_setting("reduced_motion", False),
            "music_reactive": db.get_setting("music_reactive", True),
            "playback_mode": db.get_setting("playback_mode", "auto"),
            "chart_preferences": chart_preferences,
            "storage": storage_info(),
        })
    data = request.get_json(silent=True) or {}
    allowed = {"theme", "hide_heard", "show_community", "reduced_motion", "music_reactive", "playback_mode", "download_dir", "chart_preferences"}
    if not data or set(data) - allowed:
        return jsonify({"error": "Unknown or empty setting."}), 400
    if "theme" in data:
        theme = str(data["theme"]).lower()
        if theme not in {"dark", "light"}:
            return jsonify({"error": "Theme must be dark or light."}), 400
        db.set_setting("theme", theme)
    for key in ("hide_heard", "show_community", "reduced_motion", "music_reactive"):
        if key in data:
            db.set_setting(key, bool(data[key]))
    if "chart_preferences" in data:
        requested = data["chart_preferences"]
        if not isinstance(requested, list):
            return jsonify({"error": "Choose chart cards from the chart list."}), 400
        selected = list(dict.fromkeys(str(item) for item in requested if str(item) in valid_chart_ids))
        if len(selected) < 3:
            return jsonify({"error": "Choose at least 3 charts."}), 400
        if len(selected) > 12:
            return jsonify({"error": "Choose no more than 12 charts."}), 400
        db.set_setting("chart_preferences", selected)
    if "playback_mode" in data:
        mode = str(data["playback_mode"]).lower()
        if mode not in {"auto", "online", "offline"}:
            return jsonify({"error": "Playback mode must be auto, online, or offline."}), 400
        db.set_setting("playback_mode", mode)
        if mode == "offline":
            player.filter_queue(lambda track: is_local_file(track.get("local_path")))
            current = player.current_track or {}
            if current and not is_local_file(current.get("local_path")):
                player.stop()
        _invalidate_home()
    if "download_dir" in data:
        value = str(data["download_dir"] or "").strip()
        if not value:
            return jsonify({"error": "Choose a download folder path."}), 400
        try:
            folder = Path(value).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return jsonify({"error": f"Viora could not use that folder: {exc}"}), 400
        db.set_setting("download_dir", str(folder))
        _invalidate_home()
    return jsonify({
        "theme": db.get_setting("theme", "dark"),
        "hide_heard": db.get_setting("hide_heard", True),
        "show_community": db.get_setting("show_community", True),
        "reduced_motion": db.get_setting("reduced_motion", False),
        "music_reactive": db.get_setting("music_reactive", True),
        "playback_mode": db.get_setting("playback_mode", "auto"),
        "chart_preferences": db.get_setting("chart_preferences", CHART_DEFAULTS),
        "storage": storage_info(),
    })


@app.route("/api/taste")
def api_taste():
    from core.taste import infer_taste_summary
    return jsonify(infer_taste_summary())


@app.route("/api/search")
def api_search():
    q = str(request.args.get("q", "")).strip()
    try:
        limit = max(1, min(int(request.args.get("limit", 24)), 50))
    except (TypeError, ValueError):
        return jsonify({"error": "Search limit must be a number from 1 to 50."}), 400
    if not q:
        return jsonify({"local": [], "online": []})
    db = get_db()
    db.add_search(q)
    local = find_local(q, limit=limit)
    online = []
    mode = db.get_setting("playback_mode", "auto")
    try:
        if mode == "offline" or not network_available():
            return jsonify({"local": [normalize_track_for_client(x) for x in local], "online": [], "online_available": False, "offline_mode": True})
        raw = search_parallel(
            [f'"{q}" official audio', f'"{q}" official music video', q],
            limit_each=max(8, min(limit, 16)),
            workers=3,
        )
        online = rank_tracks(raw, query=q, limit=limit, prefer_tracks=True)
        for t in online:
            db.upsert_track(t)
    except Exception as exc:
        print("[app] online search failed:", repr(exc))
    return jsonify({"local": [normalize_track_for_client(x) for x in local], "online": online, "online_available": bool(online)})


@app.route("/api/recent-searches", methods=["GET", "DELETE"])
def api_recent_searches():
    db = get_db()
    if request.method == "DELETE":
        db.clear_searches()
        return jsonify({"searches": []})
    return jsonify({"searches": db.recent_searches()})


@app.route("/api/agent-chat", methods=["GET", "POST"])
def api_agent_chat():
    db = get_db()
    if request.method == "GET":
        return jsonify({"messages": db.get_setting("agent_chat", [])})
    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return jsonify({"error": "Agent conversation must be a list of messages."}), 400
    safe_messages = []
    for item in messages[-60:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        message = {"role": item["role"], "text": str(item.get("text") or "")[:4000]}
        if item.get("sourceLabel") in {"From your local library and listening history", "Songs Viora found"}:
            message["sourceLabel"] = item["sourceLabel"]
        sources = item.get("sources")
        if isinstance(sources, list):
            message["sources"] = [
                {key: str(track.get(key) or "")[:1000] for key in ("id", "title", "artist", "channel", "thumbnail", "watch_url", "local_path")}
                for track in sources[:6] if isinstance(track, dict)
            ]
        safe_messages.append(message)
    db.set_setting("agent_chat", safe_messages)
    return jsonify({"ok": True, "count": len(safe_messages)})


@app.route("/api/play", methods=["POST"])
def api_play():
    payload = request.get_json(silent=True) or {}
    if get_db().get_setting("playback_mode", "auto") == "offline" and not is_local_file(payload.get("local_path")):
        return jsonify({"error": "Offline mode only plays tracks saved on this device."}), 409
    if not network_available() and not is_local_file(payload.get("local_path")):
        return jsonify({"error": "Internet is unavailable. Choose a track saved on this device to keep listening."}), 409
    track = _prepare_payload_track(payload)
    if not track:
        return jsonify({"reply": "That track could not be prepared for playback."}), 400
    _ensure_track_saved(track)
    ok = smart_play(track, preserve_queue=True)
    if ok:
        brain.remember_song(track)
        _invalidate_home()
        return jsonify({"reply": f"Now playing: {track.get('title','Unknown')}", "status": player.status()})
    status_data = player.status()
    detail = status_data.get("player_error")
    message = "MPV could not start that track."
    if detail:
        message += f" {detail}"
    return jsonify({"error": message, "status": status_data}), 500


@app.route("/api/preview", methods=["POST"])
def api_preview():
    payload = request.get_json(silent=True) or {}
    if get_db().get_setting("playback_mode", "auto") == "offline" and not is_local_file(payload.get("local_path")):
        return jsonify({"error": "Offline mode only previews tracks saved on this device."}), 409
    if not network_available() and not is_local_file(payload.get("local_path")):
        return jsonify({"error": "Internet is unavailable. Preview a track saved on this device instead."}), 409
    track = _prepare_payload_track(payload)
    if not track:
        return jsonify({"error": "That track could not be prepared for preview."}), 400
    try:
        started = player.preview(track, seconds=20)
    except Exception as exc:
        print("[app] preview error:", repr(exc))
        return jsonify({"error": f"MPV could not start that preview. {player.status().get('player_error') or ''}".strip()}), 500
    if not started:
        return jsonify({"error": f"MPV could not start that preview. {player.status().get('player_error') or ''}".strip()}), 500
    return jsonify({"reply": "Previewing for 20 seconds; your playback will resume afterward.", "status": player.status()})


@app.route("/api/queue", methods=["POST"])
def api_queue():
    data = request.get_json(silent=True) or {}
    tracks = data.get("tracks") if isinstance(data, dict) else data
    tracks = list(tracks or [])
    if not tracks:
        return jsonify({"reply": "No tracks to queue."}), 400
    mode = get_db().get_setting("playback_mode", "auto")
    local = [t for t in tracks if mode != "online" and t.get("local_path") and is_local_file(t.get("local_path"))]
    if (mode == "offline" or not network_available()) and len(local) != len(tracks):
        return jsonify({"error": "Offline mode only queues tracks saved on this device."}), 409
    online = [t for t in tracks if t not in local]
    prepared = list(local)
    if online:
        prepared.extend(prepare_tracks(online, workers=min(6, len(online))))
    player.queue(prepared)
    for t in prepared: _ensure_track_saved(t)
    return jsonify({"reply": f"Queued {len(prepared)} track(s).", "status": player.status()})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    # Stop the current song while leaving the user's upcoming queue intact.
    player.stop(clear_queue=False)
    return jsonify({"status": player.status(), "reply": "Playback stopped."})


@app.route("/api/queue/shuffle", methods=["POST"])
def api_shuffle_queue():
    player.shuffle_queue()
    return jsonify({"status": player.status()})


@app.route("/api/queue/clear", methods=["POST"])
def api_clear_queue():
    player.clear_queue()
    return jsonify({"status": player.status()})


@app.route("/api/queue/save", methods=["POST"])
def api_save_queue():
    name = str((request.get_json(silent=True) or {}).get("name") or "").strip()
    status = player.status()
    tracks = ([status["current_track"]] if status.get("current_track") else []) + list(status.get("queued_tracks") or [])
    if not tracks:
        return jsonify({"error": "There is no current track or queue to save."}), 400
    try:
        playlist_id = get_db().playlist_create(name or "Saved queue")
        for track in tracks:
            get_db().playlist_add(playlist_id, track)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    _invalidate_home()
    return jsonify(get_db().playlist_get(playlist_id))


@app.route("/api/track/favorite", methods=["POST"])
def api_favorite():
    data = _track_payload(request.get_json(silent=True) or {})
    value = bool(data.pop("favorite", True))
    result = get_db().set_favorite(data, value)
    _invalidate_home()
    return jsonify(normalize_track_for_client(result))


@app.route("/api/playlists", methods=["GET"])
def api_playlists():
    return jsonify(get_db().playlists())


@app.route("/api/playlists", methods=["POST"])
def api_create_playlist():
    data = request.get_json(silent=True) or {}
    try:
        pid = get_db().playlist_create(data.get("name"), data.get("description", ""))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    _invalidate_home()
    return jsonify(get_db().playlist_get(pid))


@app.route("/api/playlists/<int:playlist_id>")
def api_get_playlist(playlist_id):
    playlist = get_db().playlist_get(playlist_id)
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404
    return jsonify(playlist)


@app.route("/api/playlists/<int:playlist_id>", methods=["PATCH"])
def api_update_playlist(playlist_id):
    data = request.get_json(silent=True) or {}
    try:
        playlist = get_db().playlist_rename(playlist_id, data.get("name", ""))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404
    _invalidate_home()
    return jsonify(playlist)


@app.route("/api/playlists/<int:playlist_id>/tracks", methods=["POST"])
def api_playlist_add(playlist_id):
    data = _track_payload(request.get_json(silent=True) or {})
    try:
        playlist = get_db().playlist_add(playlist_id, data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    _invalidate_home()
    return jsonify(playlist)


@app.route("/api/playlists/<int:playlist_id>/tracks/<path:track_id>", methods=["DELETE"])
def api_playlist_remove(playlist_id, track_id):
    return jsonify(get_db().playlist_remove(playlist_id, track_id))


@app.route("/api/playlists/<int:playlist_id>/tracks/reorder", methods=["POST"])
def api_playlist_reorder(playlist_id):
    data = request.get_json(silent=True) or {}
    try:
        playlist = get_db().playlist_reorder(playlist_id, data.get("track_ids") or [])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404
    _invalidate_home()
    return jsonify(playlist)


@app.route("/api/playlists/<int:playlist_id>/sort", methods=["POST"])
def api_playlist_sort(playlist_id):
    data = request.get_json(silent=True) or {}
    try:
        playlist = get_db().playlist_set_sort(playlist_id, data.get("sort_mode", "manual"))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404
    _invalidate_home()
    return jsonify(playlist)


@app.route("/api/playlists/<int:playlist_id>", methods=["DELETE"])
def api_playlist_delete(playlist_id):
    get_db().playlist_delete(playlist_id)
    _invalidate_home()
    return jsonify({"ok": True})


@app.route("/api/playlists/<int:playlist_id>/play", methods=["POST"])
def api_playlist_play(playlist_id):
    playlist = get_db().playlist_get(playlist_id)
    if not playlist:
        return jsonify({"error": "Playlist not found"}), 404
    data = request.get_json(silent=True) or {}
    shuffle = bool(data.get("shuffle"))
    mode = get_db().get_setting("playback_mode", "auto")
    offline = mode == "offline" or not network_available()
    tracks = []
    for item in playlist.get("tracks", []):
        if mode != "online" and item.get("local_path") and is_local_file(item.get("local_path")):
            tracks.append(item)
        elif offline:
            continue
        else:
            online_item = dict(item)
            if get_db().get_setting("playback_mode", "auto") == "online":
                online_item.pop("local_path", None)
                online_item["is_downloaded"] = False
            tracks.extend(prepare_tracks([online_item], workers=1))
    if not tracks:
        return jsonify({"error": "This playlist has no playable tracks."}), 400
    if shuffle:
        import random
        random.shuffle(tracks)
    if not smart_play(tracks[0], preserve_queue=False):
        detail = player.status().get("player_error")
        message = "MPV could not start the playlist."
        if detail:
            message += f" {detail}"
        return jsonify({"error": message, "status": player.status()}), 500
    player.queue(tracks[1:])
    _invalidate_home()
    return jsonify({"reply": f"Playing {playlist['name']}.", "status": player.status()})


@app.route("/api/library")
def api_library():
    scan_downloads()
    return jsonify(library_items(limit=200))


@app.route("/api/library/<path:track_id>", methods=["DELETE"])
def api_library_delete(track_id):
    track = get_db().get_track(track_id)
    if not track:
        return jsonify({"error": "Track not found."}), 404
    path_value = track.get("local_path")
    if path_value and is_local_file(path_value):
        path = Path(path_value).resolve()
        try:
            path.relative_to(get_download_dir())
        except ValueError:
            return jsonify({"error": "This file is outside Viora’s managed download folder."}), 403
        try:
            path.unlink()
        except OSError as exc:
            return jsonify({"error": f"Could not remove the audio file: {exc}"}), 400
    get_db().delete_track(track_id)
    _invalidate_home()
    return jsonify({"ok": True})


@app.route("/api/favorites")
def api_favorites():
    return jsonify(get_db().list_tracks(limit=200, favorites_only=True))


@app.route("/api/history", methods=["GET", "DELETE"])
def api_history():
    if request.method == "DELETE":
        get_db().clear_history()
        _invalidate_home()
        return jsonify({"ok": True})
    return jsonify(get_db().history(limit=100))


@app.route("/api/history/<int:history_id>", methods=["DELETE"])
def api_history_delete(history_id):
    get_db().delete_history_entry(history_id)
    _invalidate_home()
    return jsonify({"ok": True})


@app.route("/api/recent-searches/<path:query>", methods=["DELETE"])
def api_recent_search_delete(query):
    get_db().delete_search(query)
    return jsonify({"searches": get_db().recent_searches()})


@app.route("/api/download", methods=["POST"])
def api_download():
    if get_db().get_setting("playback_mode", "auto") == "offline" or not network_available():
        return jsonify({"error": "Switch to Auto or Online mode to download music."}), 409
    data = _track_payload(request.get_json(silent=True) or {})
    track_id = str(data.get("id"))
    existing = get_db().get_track(track_id)
    if existing and existing.get("local_path") and is_local_file(existing["local_path"]):
        return jsonify({"status": "downloaded", "progress": 100, "track": existing})

    def worker():
        try:
            download_track(data)
            _invalidate_home()
        except Exception as exc:
            print("[download] failed:", repr(exc))

    threading.Thread(target=worker, name="lma-download", daemon=True).start()
    return jsonify({"status": "downloading", "progress": 0, "track_id": track_id})


@app.route("/api/download/<path:track_id>")
def api_download_status(track_id):
    return jsonify(download_status(track_id))


@app.route("/pause", methods=["POST"])
def pause():
    player.pause(); return jsonify({"reply": "Paused.", "status": player.status()})


@app.route("/resume", methods=["POST"])
def resume():
    player.resume(); return jsonify({"reply": "Resumed.", "status": player.status()})


@app.route("/toggle-pause", methods=["POST"])
def toggle_pause():
    paused = player.toggle_pause(); return jsonify({"reply": "Paused." if paused else "Resumed.", "status": player.status()})


@app.route("/next", methods=["POST"])
def next_track():
    moved = player.next(); return jsonify({"reply": "Skipped to the next track." if moved else "There is no next track in the queue.", "status": player.status()})


@app.route("/previous", methods=["POST"])
def previous_track():
    moved = player.previous(); return jsonify({"reply": "Going back to the previous track." if moved else "There is no previous track available.", "status": player.status()})


@app.route("/queue/play/<int:index>", methods=["POST"])
def play_queue_item(index):
    moved = player.play_queue_item(index); _invalidate_home()
    return jsonify({"reply": "Playing the selected queued track." if moved else "That queued track is no longer available.", "status": player.status()})


@app.route("/api/queue/<int:index>", methods=["DELETE"])
def api_remove_queue_item(index):
    removed = player.remove_queue_item(index)
    return jsonify({"ok": removed, "status": player.status()}), (200 if removed else 404)


@app.route("/clear-filter", methods=["POST"])
def clear_filter():
    brain.clear_filters(); return jsonify({"reply": "Session filter cleared.", "status": player.status()})


@app.route("/status")
def status():
    if sync_history_from_player():
        _invalidate_home()
    return jsonify(player.status())


@app.route("/context")
def context():
    return jsonify(brain.memory.context())


def _shutdown_process():
    try:
        player.close()
    except Exception as exc:
        print("[app] player close:", repr(exc))
    def die():
        time.sleep(0.25); os._exit(0)
    threading.Thread(target=die, daemon=True).start()


@app.route("/shutdown", methods=["POST"])
def shutdown():
    _shutdown_process(); return jsonify({"ok": True})


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    threading.Timer(0.4, _shutdown_process).start()
    return jsonify({"ok": True, "message": "Viora is closing."})


@app.route("/health")
def health():
    scan_downloads()
    return jsonify({
        "ok": True,
        "app_version": APP_VERSION,
        "ai": "local decision + recommendation engine",
        "ads": False,
        "online_source": "YouTube/yt-dlp",
        "local_storage": str(DATA_DIR),
        "download_directory": str(DOWNLOAD_DIR),
        "player": player.status(),
    })


if __name__ == "__main__":
    scan_downloads()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)
