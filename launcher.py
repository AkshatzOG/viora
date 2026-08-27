import json, os, subprocess, sys, time, webbrowser
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent
STATE=ROOT/".runtime.json"
PYTHON=sys.executable


def running():
    try: return requests.get("http://127.0.0.1:11434/api/tags",timeout=1).ok
    except Exception: return False

def main():
    state={"ollama_owned":False,"flask_pid":None,"ollama_pid":None}
    if not running():
        try:
            p=subprocess.Popen(["ollama","serve"],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            state["ollama_owned"]=True; state["ollama_pid"]=p.pid
        except FileNotFoundError:
            print("Ollama executable not found. Install Ollama or add it to PATH.")
            return 1
        for _ in range(60):
            if running(): break
            time.sleep(.25)
    flask=subprocess.Popen([PYTHON,str(ROOT/"app.py")],cwd=ROOT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    state["flask_pid"]=flask.pid
    STATE.write_text(json.dumps(state),encoding="utf-8")
    for _ in range(60):
        try:
            if requests.get("http://127.0.0.1:8888/health",timeout=.5).ok:
                webbrowser.open("http://127.0.0.1:8888/")
                break
        except Exception: pass
        time.sleep(.25)
    try: flask.wait()
    finally:
        try:
            if state["ollama_owned"] and state["ollama_pid"]:
                subprocess.run(["taskkill","/PID",str(state["ollama_pid"]),"/T","/F"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except Exception: pass
        try: STATE.unlink()
        except Exception: pass
    return 0

if __name__=="__main__": raise SystemExit(main())
