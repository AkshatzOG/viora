import os
import sys
from pathlib import Path

from config import MPV_PATH, YTDLP_PATH, DATA_DIR, DOWNLOAD_DIR

print("=== Viora installation check ===")
print("Python:", sys.version.split()[0])
print(f"MPV: {MPV_PATH} -> {'OK' if Path(MPV_PATH).exists() else 'MISSING'}")
print(f"yt-dlp: {YTDLP_PATH} -> {'OK' if Path(YTDLP_PATH).exists() else 'MISSING'}")
print(f"Data directory: {DATA_DIR}")
print(f"Download directory: {DOWNLOAD_DIR}")
try:
    import flask, requests, yt_dlp
    from python_mpv_jsonipc import MPV
    print("Python dependencies: OK")
except Exception as exc:
    print("Python dependencies: ERROR")
    print(repr(exc))
print("Ollama: not required")
print("Jev/TypeSafe: not required")
print("============================================")
