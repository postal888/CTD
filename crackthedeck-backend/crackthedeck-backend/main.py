"""CrackTheDeck API — Pitch Deck Analysis Service.

FastAPI backend that analyzes startup pitch decks using GPT-4o vision
and generates structured PDF reports for investors and founders.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from deals_feed import router as deals_router
from stripe_payments import router as stripe_router, _analysis_jobs, _run_analysis_background, _generate_token
from paypal_payments import router as paypal_router
from resend_emails import router as email_router
from admin_api import router as admin_router
from cloudflare_analytics import cf_router
from admin_db import init_db, log_upload, log_feedback

# Frontend (crackthedeck-deploy) — serve from backend when opening http://localhost:8000
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "crackthedeck-deploy"
from services.file_processor import save_upload, convert_pptx_to_pdf, pdf_to_images, get_slide_count
from services.analyzer import analyze_deck
from services.report_generator import generate_investor_pdf, generate_startup_pdf
from utils.fonts import download_fonts

# ── Logging ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("crackthedeck")

# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="CrackTheDeck API",
    description="AI-powered pitch deck analysis for investors and founders",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(deals_router)
app.include_router(stripe_router)
app.include_router(paypal_router)
app.include_router(email_router)
app.include_router(admin_router)
app.include_router(cf_router)


@app.on_event("startup")
async def startup():
    """Pre-download fonts on startup."""
    logger.info("Starting CrackTheDeck API...")
    init_db()
    presentations_dir = config.UPLOAD_DIR.resolve()
    logger.info(f"Presentations dir (absolute): {presentations_dir}")
    download_fonts()
    logger.info("Fonts ready. Server started.")


# ── Endpoints ───────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check. If you see build 'no-mock' and your presentations_dir path, you're on the new backend."""
    return {
        "status": "ok",
        "service": "CrackTheDeck API",
        "build": "no-mock",
        "presentations_dir": str(config.UPLOAD_DIR),
    }


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    report_type: str = Form("investor"),
):
    """Analyze a pitch deck and generate a report.

    - **file**: PDF or PPTX pitch deck
    - **report_type**: 'investor' or 'startup'

    Returns JSON analysis data + PDF download URL.
    """
    # Validate report type
    if report_type not in ("investor", "startup"):
        raise HTTPException(400, "report_type must be 'investor' or 'startup'")

    # Validate file type
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "pptx"):
        raise HTTPException(400, "Only PDF and PPTX files are supported")

    # Read and validate size
    file_bytes = await file.read()
    max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(413, f"File too large. Maximum: {config.MAX_FILE_SIZE_MB}MB")

    logger.info(f"Received {ext.upper()} file: {filename} ({len(file_bytes)} bytes), type={report_type}")

    # Save upload
    report_id, file_path = await save_upload(file_bytes, filename)

    # Convert PPTX → PDF if needed
    pdf_path = file_path
    if ext == "pptx":
        try:
            pdf_path = convert_pptx_to_pdf(file_path)
        except Exception as e:
            logger.error(f"PPTX conversion failed: {e}")
            raise HTTPException(500, f"Failed to convert PPTX to PDF: {e}")

    # Get slide count
    slide_count = get_slide_count(pdf_path)
    logger.info(f"Deck has {slide_count} slides")

    # Convert PDF → images (120 DPI to limit memory on small servers)
    try:
        base64_images = pdf_to_images(pdf_path)
    except Exception as e:
        logger.error(f"PDF to images failed: {e}")
        raise HTTPException(500, f"Failed to process PDF: {e}")

    # Cap slides sent to GPT to avoid OOM (e.g. 1GB server); report still uses full slide_count

    # Analyze with GPT-4o
    try:
        analysis_data = analyze_deck(base64_images, slide_count, report_type)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(500, f"Analysis failed: {e}")

    # Generate PDF report
    try:
        if report_type == "investor":
            report_path = generate_investor_pdf(analysis_data, report_id)
        else:
            report_path = generate_startup_pdf(analysis_data, report_id)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(500, f"Report generation failed: {e}")

    # Build response
    pdf_url = f"/api/report/{report_id}/{report_type}/pdf"

    # Log to admin DB
    try:
        log_upload(
            report_id=report_id,
            filename=filename,
            file_size_bytes=len(file_bytes),
            report_type=report_type,
            company_name=analysis_data.get("company_name", ""),
        )
    except Exception:
        pass  # Don't break analysis if logging fails

    return JSONResponse({
        "report_id": report_id,
        "report_type": report_type,
        "company_name": analysis_data.get("company_name", "Unknown"),
        "pdf_url": pdf_url,
        "data": analysis_data,
    })


# ── Feedback ────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    report_id: str = ""
    rating: int
    reasons: list[str] = []
    comment: str = ""

@app.post("/api/feedback")
async def submit_feedback(body: FeedbackRequest):
    """Save user feedback (1-5 stars + optional reasons/comment)."""
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(400, "Rating must be 1-5")
    log_feedback(
        report_id=body.report_id,
        rating=body.rating,
        reasons=", ".join(body.reasons) if body.reasons else "",
        comment=body.comment,
    )
    logger.info(f"Feedback received: rating={body.rating}, report={body.report_id}")
    return JSONResponse({"status": "ok"})


# ── Match funds (proxy to funds-rag-service) ─────────────────────────


class MatchFundsRequest(BaseModel):
    """Startup params for fund matching (from deck analysis or manual)."""
    company_name: Optional[str] = None
    sector: Optional[str] = None
    stage: Optional[str] = None
    geography: Optional[str] = None
    target_raise: Optional[str] = None
    description: Optional[str] = None
    language: str = "en"


@app.get("/api/match-funds/countries")
async def match_funds_countries():
    """Return list of countries from funds DB (for geography dropdown). Proxies to funds-rag-service."""
    rag_url = config.FUNDS_RAG_URL
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{rag_url}/api/rag/countries")
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError as e:
        logger.warning("Funds RAG unreachable (countries): %s. Is RAG running? docker compose up -d in funds-rag-service", e)
        return {"countries": []}
    except httpx.TimeoutException as e:
        logger.warning("Funds RAG timeout (countries): %s", e)
        return {"countries": []}
    except httpx.HTTPStatusError as e:
        logger.warning("Funds RAG error (countries): %s %s", e.response.status_code, e.response.text[:200])
        return {"countries": []}


@app.post("/api/match-funds")
async def match_funds(body: MatchFundsRequest):
    """
    Match funds to startup profile. Proxies to funds-rag-service.
    Params can come from deck analysis (sector, stage, target_raise) or be entered manually.
    """
    rag_url = config.FUNDS_RAG_URL
    startup = {
        "company_name": body.company_name,
        "industry": body.sector,
        "sub_industry": None,
        "stage": body.stage,
        "business_model": None,
        "geography": body.geography,
        "target_raise": body.target_raise,
        "description": body.description or "",
    }
    payload = {
        "startup": startup,
        "top_k": 100,
        "language": body.language or "en",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{rag_url}/api/rag/match", json=payload)
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError as e:
        logger.warning(f"Funds RAG unreachable: {e}")
        raise HTTPException(
            status_code=503,
            detail="Fund matching is temporarily unavailable. Please try again later.",
        )
    except httpx.HTTPStatusError as e:
        logger.warning(f"Funds RAG error: {e.response.status_code} {e.response.text}")
        detail = e.response.text
        if len(detail) > 500:
            detail = detail[:500] + "..."
        raise HTTPException(
            status_code=min(e.response.status_code, 502),
            detail=detail or "Fund matching request failed.",
        )
    except httpx.TimeoutException as e:
        logger.warning(f"Funds RAG timeout: {e}")
        raise HTTPException(504, "Fund matching timed out. The RAG service is slow or overloaded.")
    except Exception as e:
        logger.exception(f"Match funds error: {e}")
        raise HTTPException(500, f"Fund matching failed: {str(e)}")


def _build_full_description_from_analysis(analysis_data: dict, max_chars: int = 12000) -> str:
    """Собираем всё из анализа деки в один текст для RAG — summary, метрики, сильные стороны, риски, критерии."""
    parts = []

    summary = (analysis_data.get("overall_summary") or "").strip()
    if summary:
        parts.append(summary)

    key_metrics = analysis_data.get("key_metrics") or {}
    if isinstance(key_metrics, dict):
        metrics_strs = []
        for k, v in key_metrics.items():
            if v and str(v).strip():
                metrics_strs.append(f"{k}: {v}")
        if metrics_strs:
            parts.append("Key metrics: " + "; ".join(metrics_strs))

    strengths = analysis_data.get("strengths") or []
    if strengths:
        parts.append("Strengths: " + "; ".join(s for s in strengths if s and str(s).strip()))

    risks = analysis_data.get("risks") or []
    if risks:
        parts.append("Risks: " + "; ".join(r for r in risks if r and str(r).strip()))

    criteria = analysis_data.get("criteria") or []
    if criteria:
        crit_strs = []
        for c in criteria:
            if isinstance(c, dict):
                name = c.get("name") or ""
                comment = (c.get("comment") or "").strip()
                if name and comment:
                    crit_strs.append(f"{name}: {comment}")
            elif getattr(c, "name", None) and getattr(c, "comment", None):
                crit_strs.append(f"{c.name}: {c.comment}")
        if crit_strs:
            parts.append("Assessment: " + " ".join(crit_strs))

    valuation = (analysis_data.get("valuation") or "").strip()
    if valuation and valuation.lower() not in ("not disclosed", "n/a"):
        parts.append(f"Valuation: {valuation}")

    text = " ".join(parts)
    return text[:max_chars] if len(text) > max_chars else text


def _analysis_to_startup_profile(analysis_data: dict) -> dict:
    """Маппинг анализа деки в профиль для RAG: берём всю инфу из презы (описание = полный текст из анализа)."""
    sector = (analysis_data.get("sector") or "").strip()
    stage = (analysis_data.get("stage") or "").strip()
    description = _build_full_description_from_analysis(analysis_data)
    if not description.strip():
        description = (analysis_data.get("overall_summary") or "").strip()
    return {
        "company_name": (analysis_data.get("company_name") or "").strip() or None,
        "industry": sector if sector else None,
        "sub_industry": None,
        "stage": stage if stage else None,
        "business_model": None,
        "geography": None,
        "target_raise": (analysis_data.get("target_raise") or "").strip() or None,
        "description": description or "",
    }


@app.post("/api/match-funds-from-deck")
async def match_funds_from_deck(file: UploadFile = File(...)):
    """
    Upload a pitch deck (PDF/PPTX). We analyze it, extract startup profile,
    then run fund matching and return recommendations.
    """
    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "pptx"):
        raise HTTPException(400, "Only PDF and PPTX files are supported")

    file_bytes = await file.read()
    max_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(413, f"File too large. Maximum: {config.MAX_FILE_SIZE_MB}MB")

    logger.info(f"Match-from-deck: {filename} ({len(file_bytes)} bytes)")

    report_id, file_path = await save_upload(file_bytes, filename)
    pdf_path = file_path
    if ext == "pptx":
        try:
            pdf_path = convert_pptx_to_pdf(file_path)
        except Exception as e:
            logger.error(f"PPTX conversion failed: {e}")
            raise HTTPException(500, "Failed to convert PPTX to PDF")

    slide_count = get_slide_count(pdf_path)
    try:
        base64_images = pdf_to_images(pdf_path)
    except Exception as e:
        logger.error(f"PDF to images failed: {e}")
        raise HTTPException(500, "Failed to process PDF")

    try:
        analysis_data = analyze_deck(base64_images, slide_count, "investor")
    except Exception as e:
        logger.error(f"Deck analysis failed: {e}")
        raise HTTPException(500, "Analysis failed")

    startup = _analysis_to_startup_profile(analysis_data)
    if not startup.get("industry") and not startup.get("stage") and not startup.get("description"):
        raise HTTPException(400, "Could not extract enough from the deck (sector, stage, or summary). Try adding clearer slides.")

    rag_url = config.FUNDS_RAG_URL
    payload = {"startup": startup, "top_k": 100, "language": "en"}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(f"{rag_url}/api/rag/match", json=payload)
            r.raise_for_status()
            match_data = r.json()
    except httpx.ConnectError:
        raise HTTPException(503, "Fund matching is temporarily unavailable. Please try again later.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(min(e.response.status_code, 502), (e.response.text or "RAG error")[:500])
    except httpx.TimeoutException:
        raise HTTPException(504, "Fund matching timed out.")

    return JSONResponse({
        "profile": {
            "company_name": startup.get("company_name"),
            "sector": startup.get("industry"),
            "stage": startup.get("stage"),
            "target_raise": startup.get("target_raise"),
            "description": startup.get("description"),
            "geography": startup.get("geography"),
        },
        "recommendations": match_data.get("recommendations", []),
        "summary": match_data.get("summary", ""),
        "total_candidates": match_data.get("total_candidates", 0),
    })


@app.get("/api/report/{report_id}/{report_type}/pdf")
async def download_report(report_id: str, report_type: str):
    """Download generated PDF report."""
    if report_type not in ("investor", "startup"):
        raise HTTPException(400, "Invalid report type")

    pdf_path = config.REPORTS_DIR / f"{report_id}_{report_type}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "Report not found")

    company = report_id  # Could be enriched with actual company name
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"CrackTheDeck_{report_type}_{report_id}.pdf",
    )


# ── Serve frontend (open http://localhost:8000 in browser) ──────────

if FRONTEND_DIR.exists():
    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ── Run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
