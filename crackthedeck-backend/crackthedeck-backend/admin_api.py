"""
CrackTheDeck — Admin API endpoints.

Protected by a simple token-based auth (JWT-like, but simpler for a single admin).

Usage in main.py:
    from admin_api import router as admin_router
    app.include_router(admin_router)

Env vars:
    ADMIN_USERNAME — admin login (default: admin)
    ADMIN_PASSWORD — admin password (MUST be set)
"""

import os
import time
import hashlib
import hmac
import json
import base64
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

import config
from admin_db import get_uploads, get_payments, get_contacts, get_feedbacks, get_dashboard_stats, update_upload_status, get_upload_by_report_id

logger = logging.getLogger("admin_api")

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", hashlib.sha256(f"ctd-{ADMIN_PASSWORD}".encode()).hexdigest())

if not ADMIN_PASSWORD:
    logger.warning("ADMIN_PASSWORD not set — admin panel will be inaccessible")


# ---------------------------------------------------------------------------
# Simple token auth (no external deps)
# ---------------------------------------------------------------------------

def _create_token(username: str) -> str:
    """Create a simple signed token (valid 24h)."""
    payload = json.dumps({"u": username, "exp": time.time() + 86400})
    b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), b64.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{b64}.{sig}"


def _verify_token(token: str) -> str | None:
    """Verify token and return username, or None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64, sig = parts
        expected = hmac.new(SECRET_KEY.encode(), b64.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("u")
    except Exception:
        return None


async def require_admin(request: Request) -> str:
    """Dependency: extract and verify admin token from Authorization header or cookie."""
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("ctd_admin_token", "")
    if not token:
        raise HTTPException(401, "Not authenticated")
    username = _verify_token(token)
    if not username:
        raise HTTPException(401, "Invalid or expired token")
    return username


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def admin_login(body: LoginRequest):
    if not ADMIN_PASSWORD:
        raise HTTPException(503, "Admin panel not configured")
    if body.username != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid credentials")
    token = _create_token(body.username)
    resp = JSONResponse({"success": True, "token": token})
    resp.set_cookie("ctd_admin_token", token, httponly=True, samesite="strict", max_age=86400)
    return resp


@router.post("/logout")
async def admin_logout():
    resp = JSONResponse({"success": True})
    resp.delete_cookie("ctd_admin_token")
    return resp


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def admin_dashboard(admin: str = Depends(require_admin)):
    stats = get_dashboard_stats()
    return JSONResponse(stats)


@router.get("/uploads")
async def admin_uploads(limit: int = 100, offset: int = 0, admin: str = Depends(require_admin)):
    return JSONResponse({"uploads": get_uploads(limit, offset)})


@router.get("/payments")
async def admin_payments(limit: int = 100, offset: int = 0, admin: str = Depends(require_admin)):
    return JSONResponse({"payments": get_payments(limit, offset)})


@router.get("/contacts")
async def admin_contacts(limit: int = 100, offset: int = 0, admin: str = Depends(require_admin)):
    return JSONResponse({"contacts": get_contacts(limit, offset)})


@router.get("/feedback")
async def admin_feedback(limit: int = 100, offset: int = 0, admin: str = Depends(require_admin)):
    return JSONResponse({"feedback": get_feedbacks(limit, offset)})


# ---------------------------------------------------------------------------
# File downloads (deck + report)
# ---------------------------------------------------------------------------

@router.get("/download/deck/{report_id}")
async def download_deck(report_id: str, admin: str = Depends(require_admin)):
    """Download the original uploaded deck file."""
    upload_dir = config.UPLOAD_DIR
    # Find file matching report_id prefix
    matches = list(upload_dir.glob(f"{report_id}*"))
    if not matches:
        raise HTTPException(404, "Deck file not found")
    fpath = matches[0]
    return FileResponse(str(fpath), filename=fpath.name, media_type="application/octet-stream")


# ---------------------------------------------------------------------------
# Send report (admin manually sends report for Pro/Expert)
# ---------------------------------------------------------------------------

@router.post("/send-report/{report_id}")
async def admin_send_report(report_id: str, admin: str = Depends(require_admin)):
    """Send the generated report to the customer (used for Pro/Expert after human review)."""
    upload = get_upload_by_report_id(report_id)
    if not upload:
        raise HTTPException(404, "Upload not found")

    email = upload.get("email", "")
    if not email:
        raise HTTPException(400, "No email address found for this upload")

    report_type = upload.get("report_type", "investor")
    company_name = upload.get("company_name", "your deck")

    # Check that PDF exists
    pdf_path = config.REPORTS_DIR / f"{report_id}_{report_type}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "Report PDF not found")

    # Send via internal email endpoint
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "http://127.0.0.1:8000/api/email/send-report",
            json={
                "email": email,
                "report_id": report_id,
                "report_type": report_type,
                "company_name": company_name,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, f"Email send failed: {resp.text[:200]}")

    # Update status
    update_upload_status(report_id, "sent")
    logger.info(f"Admin sent report {report_id} to {email}")
    return JSONResponse({"success": True, "message": f"Report sent to {email}", "email": email})


# ---------------------------------------------------------------------------
# Upload custom reviewed PDF and send to customer
# ---------------------------------------------------------------------------

@router.post("/send-custom-report/{report_id}")
async def admin_send_custom_report(
    report_id: str,
    file: UploadFile = File(...),
    admin: str = Depends(require_admin),
):
    """Upload a custom reviewed PDF and send it to the customer.
    
    Used for Pro/Expert orders where the admin downloads the AI-generated
    report, adds human comments, then uploads the reviewed version.
    """
    upload = get_upload_by_report_id(report_id)
    if not upload:
        raise HTTPException(404, "Upload not found")

    email = upload.get("email", "")
    if not email:
        raise HTTPException(400, "No email address found for this upload")

    # Validate file
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    
    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(400, "File too large (max 50MB)")
    if len(contents) < 100:
        raise HTTPException(400, "File appears to be empty")

    # Save the custom PDF (overwrite the AI-generated one)
    report_type = upload.get("report_type", "investor")
    company_name = upload.get("company_name", "your deck")
    pdf_path = config.REPORTS_DIR / f"{report_id}_{report_type}.pdf"
    pdf_path.write_bytes(contents)
    logger.info(f"Admin uploaded custom report for {report_id} ({len(contents)} bytes)")

    # Send via email
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "http://127.0.0.1:8000/api/email/send-report",
            json={
                "email": email,
                "report_id": report_id,
                "report_type": report_type,
                "company_name": company_name,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, f"Email send failed: {resp.text[:200]}")

    # Update status
    update_upload_status(report_id, "sent")
    logger.info(f"Admin sent custom report {report_id} to {email}")
    return JSONResponse({
        "success": True,
        "message": f"Custom report sent to {email}",
        "email": email,
        "file_size": len(contents),
    })


@router.get("/download/report/{report_id}/{report_type}")
async def download_report(report_id: str, report_type: str = "investor", admin: str = Depends(require_admin)):
    """Download the generated PDF report."""
    if report_type not in ("investor", "startup"):
        raise HTTPException(400, "Invalid report type")
    pdf_path = config.REPORTS_DIR / f"{report_id}_{report_type}.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "Report not found")
    return FileResponse(str(pdf_path), filename=f"CrackTheDeck_{report_id}_{report_type}.pdf", media_type="application/pdf")
