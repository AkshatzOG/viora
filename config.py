import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
IS_FROZEN = bool(getattr(__import__("sys"), "frozen", False))
APP_ROOT = Path(__import__("sys").executable).resolve().parent if IS_FROZEN else ROOT
USER_DATA_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Viora"

_BUNDLED_MPV = APP_ROOT / "runtime" / "mpv.exe"
_BUNDLED_YTDLP = APP_ROOT / "runtime" / "yt-dlp.exe"
MPV_PATH = os.environ.get("MPV_PATH", str(_BUNDLED_MPV) if IS_FROZEN and _BUNDLED_MPV.exists() else r"C:\mpv\mpv.exe")
YTDLP_PATH = os.environ.get("YTDLP_PATH", str(_BUNDLED_YTDLP) if IS_FROZEN and _BUNDLED_YTDLP.exists() else r"C:\mpv\yt-dlp.exe")

MAX_QUEUE_SIZE = int(os.environ.get("MAX_QUEUE_SIZE", "30"))
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", "20"))
SEARCH_WORKERS = int(os.environ.get("SEARCH_WORKERS", "5"))

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8888"))
AUTO_OPEN_BROWSER = os.environ.get("AUTO_OPEN_BROWSER", "1") == "1"
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "viora-local-only")
# Keep Python/source runs and packaged builds on the same per-user data roots.
# This prevents an installed app from appearing to have a brand-new profile.
DATA_DEFAULT = USER_DATA_ROOT / "data"
DOWNLOAD_DEFAULT = USER_DATA_ROOT / "downloads"
DATA_DIR = Path(os.environ.get("VIORA_DATA_DIR", os.environ.get("LMA_DATA_DIR", str(DATA_DEFAULT))))
DOWNLOAD_DIR = Path(os.environ.get("VIORA_DOWNLOAD_DIR", os.environ.get("LMA_DOWNLOAD_DIR", str(DOWNLOAD_DEFAULT))))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOAD_FORMAT = os.environ.get("VIORA_DOWNLOAD_FORMAT", os.environ.get("LMA_DOWNLOAD_FORMAT", "bestaudio/best"))
SEARCH_CACHE_TTL = float(os.environ.get("SEARCH_CACHE_TTL", "45"))
HOME_CACHE_TTL = float(os.environ.get("HOME_CACHE_TTL", "90"))
AUTOPLAY_ENABLED = os.environ.get("AUTOPLAY_ENABLED", "1") == "1"
