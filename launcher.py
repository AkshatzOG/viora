import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import requests

from config import HOST, PORT, AUTO_OPEN_BROWSER, DATA_DIR

ROOT = Path(__file__).resolve().parent
STATE = DATA_DIR / ".runtime.json"
PYTHON = sys.executable


def healthy():
    try:
        return requests.get(f"http://{HOST}:{PORT}/health", timeout=1).ok
    except Exception:
        return False


def main():
    if getattr(sys, "frozen", False):
        from app import app
        if AUTO_OPEN_BROWSER:
            threading.Timer(1.0, lambda: webbrowser.open(f"http://{HOST}:{PORT}/")).start()
        app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)
        return 0
    if healthy():
        print(f"Viora is already running at http://{HOST}:{PORT}")
        if AUTO_OPEN_BROWSER:
            webbrowser.open(f"http://{HOST}:{PORT}/")
        return 0

    state = {"flask_pid": None}
    flask = subprocess.Popen(
        [PYTHON, str(ROOT / "app.py")],
        cwd=ROOT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    state["flask_pid"] = flask.pid
    STATE.write_text(json.dumps(state), encoding="utf-8")

    for _ in range(80):
        if healthy():
            if AUTO_OPEN_BROWSER:
                webbrowser.open(f"http://{HOST}:{PORT}/")
            break
        time.sleep(0.25)

    try:
        flask.wait()
    finally:
        try: STATE.unlink()
        except Exception: pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
