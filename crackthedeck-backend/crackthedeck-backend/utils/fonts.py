"""Font downloading and caching utilities."""

import logging
import subprocess
import zipfile
from pathlib import Path
import httpx
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import FONTS_DIR

logger = logging.getLogger(__name__)

# Font sources: (name, download_url, zip_inner_path or None)
FONT_SOURCES = [
    ("JetBrainsMono-Bold", "https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/ttf/JetBrainsMono-Bold.ttf", None),
    ("JetBrainsMono-Regular", "https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/ttf/JetBrainsMono-Regular.ttf", None),
    # Inter comes from release zip — download separately
    ("Inter-Regular", None, None),
    ("Inter-Bold", None, None),
    ("Inter-SemiBold", None, None),
]

INTER_ZIP_URL = "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip"
INTER_FILES = {
    "Inter-Regular": "extras/ttf/Inter-Regular.ttf",
    "Inter-Bold": "extras/ttf/Inter-Bold.ttf",
    "Inter-SemiBold": "extras/ttf/Inter-SemiBold.ttf",
}

_fonts_loaded = False


def _download_inter_fonts() -> None:
    """Download and extract Inter fonts from release zip."""
    # Check if already extracted
    if all((FONTS_DIR / f"{name}.ttf").exists() for name in INTER_FILES):
        return

    zip_path = FONTS_DIR / "Inter-4.0.zip"
    if not zip_path.exists():
        logger.info("Downloading Inter font family...")
        try:
            resp = httpx.get(INTER_ZIP_URL, follow_redirects=True, timeout=60)
            resp.raise_for_status()
            zip_path.write_bytes(resp.content)
        except Exception as e:
            logger.warning(f"Failed to download Inter fonts: {e}")
            return

    try:
        with zipfile.ZipFile(str(zip_path)) as zf:
            for name, inner_path in INTER_FILES.items():
                out_path = FONTS_DIR / f"{name}.ttf"
                if not out_path.exists():
                    data = zf.read(inner_path)
                    out_path.write_bytes(data)
                    logger.info(f"Extracted font: {name}")
    except Exception as e:
        logger.warning(f"Failed to extract Inter fonts: {e}")


def download_fonts() -> None:
    """Download all fonts and register with ReportLab."""
    global _fonts_loaded
    if _fonts_loaded:
        return

    # Download JetBrains Mono (direct TTF links)
    for name, url, _ in FONT_SOURCES:
        if url is None:
            continue
        font_path = FONTS_DIR / f"{name}.ttf"
        if not font_path.exists():
            logger.info(f"Downloading font: {name}")
            try:
                resp = httpx.get(url, follow_redirects=True, timeout=30)
                resp.raise_for_status()
                font_path.write_bytes(resp.content)
            except Exception as e:
                logger.warning(f"Failed to download {name}: {e}")
                continue

    # Download Inter fonts from zip
    _download_inter_fonts()

    # Register all fonts
    for name, _, _ in FONT_SOURCES:
        font_path = FONTS_DIR / f"{name}.ttf"
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(font_path)))
                logger.info(f"Registered font: {name}")
            except Exception as e:
                logger.warning(f"Failed to register {name}: {e}")

    _fonts_loaded = True


def get_font(style: str = "body") -> str:
    """Get font name by style, with fallback to Helvetica."""
    font_map = {
        "heading": "JetBrainsMono-Bold",
        "heading-regular": "JetBrainsMono-Regular",
        "body": "Inter-Regular",
        "body-bold": "Inter-Bold",
        "body-semi": "Inter-SemiBold",
    }
    name = font_map.get(style, "Inter-Regular")
    try:
        pdfmetrics.getFont(name)
        return name
    except KeyError:
        return "Helvetica-Bold" if "Bold" in name or "Semi" in name else "Helvetica"
