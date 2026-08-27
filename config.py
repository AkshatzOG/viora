import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "45"))
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "-1")
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "2048"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "180"))

MPV_PATH = os.environ.get("MPV_PATH", r"C:\mpv\mpv.exe")
YTDLP_PATH = os.environ.get("YTDLP_PATH", r"C:\mpv\yt-dlp.exe")

MAX_QUEUE_SIZE = int(os.environ.get("MAX_QUEUE_SIZE", "30"))
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", "20"))
SEARCH_WORKERS = int(os.environ.get("SEARCH_WORKERS", "5"))

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8888"))
AUTO_OPEN_BROWSER = os.environ.get("AUTO_OPEN_BROWSER", "1") == "1"

FLASK_SECRET_KEY = os.environ.get(
    "FLASK_SECRET_KEY", "local-music-agent-local-only"
)

# Optional explicit Ollama executable. If empty, the launcher searches
# common Windows install locations and finally PATH.
OLLAMA_EXE = os.environ.get("OLLAMA_EXE", "").strip()
if not OLLAMA_EXE:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Ollama" / "ollama.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            OLLAMA_EXE = str(candidate)
            break
if not OLLAMA_EXE:
    OLLAMA_EXE = "ollama"
