import os
import threading
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

from agent.brain import MusicBrain
from agent.router import AgentRouter
from tools.playback import player


app = Flask(__name__)
APP_VERSION = "14"
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "local-music-agent-secret",
)

brain = MusicBrain()
router = AgentRouter(brain)


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return render_template("index.html", app_version=APP_VERSION)


def _shutdown_process():
    try:
        player.close()
    except Exception as exc:
        print("[app] player close:", repr(exc))

    def die():
        time.sleep(0.25)
        os._exit(0)

    threading.Thread(
        target=die,
        daemon=True,
    ).start()


@app.route("/command", methods=["POST"])
def command():
    text = str(
        (request.get_json(silent=True) or {}).get(
            "text",
            "",
        )
    ).strip()

    if not text:
        return jsonify(
            {"reply": "Say something first."}
        ), 400

    try:
        reply = router.process(text)

        if router.last_intent.get("action") == "CLOSE":
            _shutdown_process()

        return jsonify(
            {
                "reply": reply,
                "status": player.status(),
            }
        )

    except Exception as exc:
        print("[app] command error:", repr(exc))

        return jsonify(
            {
                "reply": (
                    "Something went wrong while handling "
                    "that command."
                ),
                "error": str(exc),
            }
        ), 500


@app.route("/pause", methods=["POST"])
def pause():
    player.pause()
    return jsonify(
        {
            "reply": "Paused.",
            "status": player.status(),
        }
    )


@app.route("/resume", methods=["POST"])
def resume():
    player.resume()
    return jsonify(
        {
            "reply": "Resumed.",
            "status": player.status(),
        }
    )


@app.route("/toggle-pause", methods=["POST"])
def toggle_pause():
    paused = player.toggle_pause()

    return jsonify(
        {
            "reply": "Paused." if paused else "Resumed.",
            "status": player.status(),
        }
    )


@app.route("/next", methods=["POST"])
def next_track():
    moved = player.next()

    return jsonify(
        {
            "reply": (
                "Skipped to the next track."
                if moved
                else "There is no next track in the queue."
            ),
            "status": player.status(),
        }
    )


@app.route("/previous", methods=["POST"])
def previous_track():
    moved = player.previous()

    return jsonify(
        {
            "reply": (
                "Going back to the previous track."
                if moved
                else "There is no previous track available."
            ),
            "status": player.status(),
        }
    )


@app.route("/queue/play/<int:index>", methods=["POST"])
def play_queue_item(index):
    moved = player.play_queue_item(index)

    return jsonify(
        {
            "reply": (
                "Playing the selected queued track."
                if moved
                else "That queued track is no longer available."
            ),
            "status": player.status(),
        }
    )


@app.route("/status")
def status():
    return jsonify(player.status())


@app.route("/context")
def context():
    return jsonify(brain.memory.context())


@app.route("/clear-filter", methods=["POST"])
def clear_filter():
    brain.clear_filters()

    return jsonify(
        {
            "reply": "Session filter cleared.",
            "status": player.status(),
        }
    )


@app.route("/shutdown", methods=["POST"])
def shutdown():
    _shutdown_process()
    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "ollama_model": os.environ.get(
                "OLLAMA_MODEL",
                "llama3.2",
            ),
            "player": player.status(),
        }
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8888")),
        debug=False,
        use_reloader=False,
        threaded=True,
    )
