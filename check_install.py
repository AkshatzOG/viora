import os
import sys
from pathlib import Path

print("=== Local Music Agent installation check ===")
print("Python:", sys.version.split()[0])

checks = [
    ("MPV", os.environ.get("MPV_PATH", r"C:\mpv\mpv.exe")),
    ("yt-dlp", os.environ.get("YTDLP_PATH", r"C:\mpv\yt-dlp.exe")),
]

for name, value in checks:
    path = Path(value)
    print(f"{name}: {value} -> {'OK' if path.exists() else 'MISSING'}")

try:
    import flask
    import requests
    import yt_dlp
    from python_mpv_jsonipc import MPV
    print("Python dependencies: OK")
except Exception as exc:
    print("Python dependencies: ERROR")
    print(repr(exc))

try:
    import urllib.request
    with urllib.request.urlopen(
        "http://127.0.0.1:11434/api/tags",
        timeout=2,
    ) as response:
        print("Ollama API:", response.status)
except Exception as exc:
    print("Ollama API: NOT RUNNING")
    print(repr(exc))

print("============================================")
