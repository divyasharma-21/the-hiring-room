import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "hiring_room.db"

UPLOAD_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# NOTE: gemini-2.0-flash was shut down 2026-06-01, and gemini-2.5-flash is no
# longer available to new API keys as of this build — Google's own 404 error
# points to gemini-3.6-flash as the current replacement.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
