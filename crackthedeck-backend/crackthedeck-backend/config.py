"""Application configuration."""

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Paths (needed to load .env from project dir regardless of cwd)
BASE_DIR = Path(__file__).parent
# .env next to config.py; override=True so file wins over shell env
load_dotenv(BASE_DIR / ".env", override=True)
# Uploaded pitch decks (PDF/PPTX) — always use absolute path
UPLOAD_DIR = (BASE_DIR / "presentations").resolve()
REPORTS_DIR = (BASE_DIR / "reports").resolve()
FONTS_DIR = Path(tempfile.gettempdir()) / "crackthedeck_fonts"
# Poppler (PDF → images). Folder containing pdftoppm.exe (local poppler-25.12.0 or POPPLER_DIR in .env)
_def_poppler = BASE_DIR / "poppler-25.12.0" / "Library" / "bin"
POPPLER_DIR = Path(os.getenv("POPPLER_DIR", str(_def_poppler)))
# LibreOffice (PPTX → PDF). Windows: path to soffice.exe; Linux/Mac: "libreoffice"
_win_soffice = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "LibreOffice" / "program" / "soffice.exe"
LIBREOFFICE_CMD = os.getenv("LIBREOFFICE_CMD") or (str(_win_soffice) if os.name == "nt" and _win_soffice.exists() else "libreoffice")

# Create dirs
UPLOAD_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
FONTS_DIR.mkdir(exist_ok=True)

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# App
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Funds RAG service (matching funds to startup profile)
FUNDS_RAG_URL = os.getenv("FUNDS_RAG_URL", "http://localhost:8100").rstrip("/")
