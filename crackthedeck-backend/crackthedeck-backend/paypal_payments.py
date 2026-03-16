"""
CrackTheDeck — PayPal integration.
Server-side order creation + capture via PayPal REST API.

Usage in main.py:
    from paypal_payments import router as paypal_router
    app.include_router(paypal_router)

Env vars required:
    PAYPAL_CLIENT_ID   — from PayPal developer dashboard
    PAYPAL_SECRET      — from PayPal developer dashboard
    PAYPAL_MODE        — 'sandbox' or 'live'
"""

import os
import json
import time
import asyncio
import hashlib
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

logger = logging.getLogger("paypal_payments")

router = APIRouter(prefix="/api/paypal", tags=["paypal"])

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")
PAYPAL_API = "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com"

SITE_URL = os.getenv("SITE_URL", "https://crackthedeck.com").rstrip("/")

# Plan → price in USD
PLAN_PRICES = {
    "basic": "1.00",   # temporarily $1 for testing, normally $19
    "pro": "49.00",
    "expert": "499.00",
}

PLAN_NAMES = {
    "basic": "CrackTheDeck Basic — AI Pitch Deck Analysis",
    "pro": "CrackTheDeck Pro — AI + Human Investor Review",
    "expert": "CrackTheDeck Expert — Full IC Simulation",
}

# Reuse pending uploads dir from stripe_payments
PENDING_DIR = Path("pending_uploads")
PENDING_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# DB helpers (same as stripe_payments)
# ---------------------------------------------------------------------------

def _log_payment_db(token, order_id, email, plan, amount, currency="usd"):
    try:
        from admin_db import log_payment
        log_payment(token=token, session_id=f"paypal_{order_id}", email=email, plan=plan, amount=int(float(amount) * 100), currency=currency)
    except Exception:
        pass


def _log_upload_db(report_id, filename, file_size_bytes, email="", company="", plan="basic", report_type="investor", company_name="", status="completed"):
    try:
        from admin_db import log_upload
        log_upload(report_id=report_id, filename=filename, file_size_bytes=file_size_bytes, email=email, company=company, plan=plan, report_type=report_type, company_name=company_name, status=status)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# PayPal auth
# ---------------------------------------------------------------------------

_token_cache = {"token": None, "expires": 0}


async def _get_access_token() -> str:
    """Get PayPal OAuth2 access token (cached)."""
    if _token_cache["token"] and time.time() < _token_cache["expires"]:
        return _token_cache["token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PAYPAL_API}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires"] = time.time() + data.get("expires_in", 3600) - 60
        return data["access_token"]


# ---------------------------------------------------------------------------
# Helpers (shared with stripe flow)
# ---------------------------------------------------------------------------

def _generate_token() -> str:
    return hashlib.sha256(f"{time.time()}{os.urandom(16).hex()}".encode()).hexdigest()[:24]


def _save_pending(token: str, file_bytes: bytes, filename: str, metadata: dict):
    folder = PENDING_DIR / token
    folder.mkdir(exist_ok=True)
    (folder / filename).write_bytes(file_bytes)
    (folder / "meta.json").write_text(json.dumps({
        "filename": filename,
        "email": metadata.get("email", ""),
        "company": metadata.get("company", ""),
        "stage": metadata.get("stage", ""),
        "plan": metadata.get("plan", ""),
        "report_type": metadata.get("report_type", "investor"),
        "created_at": time.time(),
    }))


def _load_pending(token: str) -> dict | None:
    meta_path = PENDING_DIR / token / "meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    if time.time() - meta.get("created_at", 0) > 7200:
        return None
    return meta


def _get_pending_file(token: str) -> tuple[bytes, str] | None:
    meta = _load_pending(token)
    if not meta:
        return None
    fpath = PENDING_DIR / token / meta["filename"]
    if not fpath.exists():
        return None
    return fpath.read_bytes(), meta["filename"]


def _cleanup_pending(token: str):
    folder = PENDING_DIR / token
    if folder.exists():
        for f in folder.iterdir():
            f.unlink()
        folder.rmdir()


# ---------------------------------------------------------------------------
# In-memory analysis job tracking (shared namespace prefix to avoid collision)
# ---------------------------------------------------------------------------
_analysis_jobs = {}


async def _run_analysis_background(token: str, file_bytes: bytes, filename: str, report_type: str, email: str = "", plan: str = "basic"):
    """Run analysis in background — same logic as stripe_payments."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            files = {"file": (filename, file_bytes)}
            data = {"report_type": report_type}
            resp = await client.post("http://127.0.0.1:8000/api/analyze", files=files, data=data)
            if resp.status_code != 200:
                _analysis_jobs[token] = {"status": "error", "result": None, "error": f"Analysis returned {resp.status_code}"}
                logger.error(f"Background analysis failed for {token}: {resp.status_code}")
            else:
                result = resp.json()
                _analysis_jobs[token] = {"status": "done", "result": result, "error": None}
                logger.info(f"Background analysis complete for {token}, plan={plan}")

                is_review_plan = plan in ("pro", "expert")
                upload_status = "pending_review" if is_review_plan else "completed"

                _log_upload_db(
                    report_id=result.get("report_id", token),
                    filename=filename,
                    file_size_bytes=len(file_bytes),
                    email=email,
                    plan=plan,
                    report_type=report_type,
                    company_name=result.get("company_name", ""),
                    status=upload_status,
                )

                if is_review_plan:
                    if email:
                        try:
                            await client.post(
                                "http://127.0.0.1:8000/api/email/report-pending",
                                json={"email": email, "company_name": result.get("company_name", "your deck"), "plan": plan},
                                timeout=httpx.Timeout(30.0),
                            )
                        except Exception as e:
                            logger.warning(f"Pending-review email exception: {e}")
                else:
                    if email and result.get("report_id"):
                        try:
                            await client.post(
                                "http://127.0.0.1:8000/api/email/send-report",
                                json={
                                    "email": email,
                                    "report_id": result["report_id"],
                                    "report_type": result.get("report_type", "investor"),
                                    "company_name": result.get("company_name", "your deck"),
                                },
                                timeout=httpx.Timeout(30.0),
                            )
                        except Exception as e:
                            logger.warning(f"Auto-email exception: {e}")
    except Exception as e:
        _analysis_jobs[token] = {"status": "error", "result": None, "error": str(e)}
        logger.error(f"Background analysis exception for {token}: {e}")
    finally:
        _cleanup_pending(token)


# ---------------------------------------------------------------------------
# 1. Pre-upload: save file, return token
# ---------------------------------------------------------------------------

@router.post("/prepare-upload")
async def prepare_upload(
    file: UploadFile = File(...),
    plan: str = Form(...),
    email: str = Form(""),
    company: str = Form(""),
    stage: str = Form(""),
    report_type: str = Form("investor"),
):
    """Save uploaded file and return a token. Frontend uses this token in PayPal order."""
    plan = plan.lower().strip()
    if plan not in PLAN_PRICES:
        raise HTTPException(400, f"Unknown plan: {plan}")

    token = _generate_token()
    file_bytes = await file.read()
    _save_pending(token, file_bytes, file.filename, {
        "email": email, "company": company, "stage": stage,
        "plan": plan, "report_type": report_type,
    })

    return JSONResponse({"token": token, "plan": plan, "amount": PLAN_PRICES[plan]})


# ---------------------------------------------------------------------------
# 2. Create PayPal order
# ---------------------------------------------------------------------------

@router.post("/create-order")
async def create_order(request: Request):
    """Create a PayPal order. Called from PayPal JS SDK button."""
    body = await request.json()
    token = body.get("token", "")
    plan = body.get("plan", "basic").lower().strip()

    if plan not in PLAN_PRICES:
        raise HTTPException(400, f"Unknown plan: {plan}")

    meta = _load_pending(token) if token else None

    access_token = await _get_access_token()

    order_data = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "USD",
                "value": PLAN_PRICES[plan],
            },
            "description": PLAN_NAMES.get(plan, "CrackTheDeck Analysis"),
            "custom_id": token,
        }],
        "application_context": {
            "brand_name": "CrackTheDeck",
            "landing_page": "NO_PREFERENCE",
            "user_action": "PAY_NOW",
            "return_url": f"{SITE_URL}/payment-success",
            "cancel_url": f"{SITE_URL}/payment-cancel",
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PAYPAL_API}/v2/checkout/orders",
            json=order_data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code not in (200, 201):
            logger.error(f"PayPal create order error: {resp.status_code} {resp.text}")
            raise HTTPException(502, "Failed to create PayPal order")

        result = resp.json()
        logger.info(f"PayPal order created: {result['id']} for token={token}, plan={plan}")
        return JSONResponse({"id": result["id"]})


# ---------------------------------------------------------------------------
# 3. Capture PayPal order (after buyer approves)
# ---------------------------------------------------------------------------

@router.post("/capture-order")
async def capture_order(request: Request):
    """Capture payment after buyer approves. Triggers analysis."""
    body = await request.json()
    order_id = body.get("orderID", "")

    if not order_id:
        raise HTTPException(400, "Missing orderID")

    access_token = await _get_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PAYPAL_API}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code not in (200, 201):
            logger.error(f"PayPal capture error: {resp.status_code} {resp.text}")
            raise HTTPException(502, "Failed to capture payment")

        result = resp.json()
        status = result.get("status", "")
        logger.info(f"PayPal order {order_id} captured, status={status}")

        if status != "COMPLETED":
            raise HTTPException(402, f"Payment not completed: {status}")

        # Extract token from custom_id
        token = ""
        capture_amount = "0"
        for pu in result.get("purchase_units", []):
            token = pu.get("payments", {}).get("captures", [{}])[0].get("custom_id", "") or pu.get("custom_id", "")
            captures = pu.get("payments", {}).get("captures", [])
            if captures:
                capture_amount = captures[0].get("amount", {}).get("value", "0")
            if not token:
                token = pu.get("custom_id", "")

        if not token:
            logger.error(f"No token found in PayPal order {order_id}")
            raise HTTPException(500, "Payment captured but upload token missing")

        meta = _load_pending(token)
        if not meta:
            raise HTTPException(404, "Upload not found or expired")

        # Log payment
        payer_email = result.get("payer", {}).get("email_address", meta.get("email", ""))
        _log_payment_db(
            token=token,
            order_id=order_id,
            email=payer_email or meta.get("email", ""),
            plan=meta.get("plan", "basic"),
            amount=capture_amount,
        )

        # Mark as paid
        paid_path = PENDING_DIR / token / "paid.flag"
        paid_path.write_text(json.dumps({
            "paypal_order_id": order_id,
            "amount": capture_amount,
            "currency": "usd",
            "paid_at": time.time(),
        }))

        # Launch analysis
        file_result = _get_pending_file(token)
        if not file_result:
            raise HTTPException(404, "File not found")
        file_bytes, filename = file_result

        _analysis_jobs[token] = {"status": "processing", "result": None, "error": None}
        asyncio.create_task(
            _run_analysis_background(token, file_bytes, filename, meta.get("report_type", "investor"), meta.get("email", ""), meta.get("plan", "basic"))
        )
        logger.info(f"Launched background analysis for PayPal token {token}")

        return JSONResponse({
            "status": "success",
            "token": token,
            "plan": meta.get("plan", "basic"),
            "email": meta.get("email", ""),
        })


# ---------------------------------------------------------------------------
# 4. Analysis status polling (same as stripe)
# ---------------------------------------------------------------------------

@router.get("/analysis-status")
async def analysis_status(token: str = ""):
    if not token:
        raise HTTPException(400, "Missing token")
    job = _analysis_jobs.get(token)
    if not job:
        return JSONResponse({"status": "unknown"})
    if job["status"] == "done":
        return JSONResponse({"status": "done", "result": job["result"]})
    elif job["status"] == "error":
        return JSONResponse({"status": "error", "error": job.get("error", "Unknown error")})
    return JSONResponse({"status": "processing"})


# ---------------------------------------------------------------------------
# 5. Client ID endpoint (frontend needs it for JS SDK)
# ---------------------------------------------------------------------------

@router.get("/client-id")
async def get_client_id():
    return JSONResponse({"client_id": PAYPAL_CLIENT_ID})
