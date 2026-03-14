"""File upload handling: PPTX→PDF conversion, PDF→images."""

import logging
import subprocess
import uuid
import base64
from pathlib import Path

from pdf2image import convert_from_path

from config import UPLOAD_DIR, POPPLER_DIR, LIBREOFFICE_CMD

logger = logging.getLogger(__name__)


async def save_upload(file_bytes: bytes, filename: str) -> tuple[str, Path]:
    """Save uploaded file to presentations folder, return (report_id, file_path)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    report_id = uuid.uuid4().hex[:12]
    safe_name = f"{report_id}_{filename}"
    file_path = (UPLOAD_DIR / safe_name).resolve()
    file_path.write_bytes(file_bytes)
    logger.info(f"Saved to presentations: {file_path} ({len(file_bytes)} bytes)")
    return report_id, file_path


def convert_pptx_to_pdf(pptx_path: Path) -> Path:
    """Convert PPTX to PDF using LibreOffice headless."""
    output_dir = pptx_path.parent
    logger.info(f"Converting PPTX to PDF: {pptx_path}")
    cmd = [LIBREOFFICE_CMD, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx_path)]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        logger.error(f"LibreOffice conversion failed: {result.stderr}")
        raise RuntimeError(f"PPTX to PDF conversion failed: {result.stderr}")

    pdf_path = pptx_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError("PDF file not found after conversion")

    logger.info(f"Converted to PDF: {pdf_path}")
    return pdf_path


def pdf_to_images(pdf_path: Path, dpi: int = 200) -> list[str]:
    """Convert PDF pages to base64-encoded PNG images.

    Returns list of base64 strings for GPT-4o vision API.
    """
    logger.info(f"Converting PDF to images: {pdf_path}")
    poppler_kw = {"poppler_path": str(POPPLER_DIR)} if POPPLER_DIR.exists() else {}
    images = convert_from_path(str(pdf_path), dpi=dpi, **poppler_kw)

    base64_images = []
    for i, img in enumerate(images):
        from io import BytesIO
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        base64_images.append(b64)

    logger.info(f"Converted {len(base64_images)} pages to images")
    return base64_images


def get_slide_count(pdf_path: Path) -> int:
    """Get number of pages in PDF."""
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)
