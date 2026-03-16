"""
CrackTheDeck — Stripe Checkout integration.
One-time payments for Pro ($49) and Expert ($499) plans.

Usage in main.py:
    from stripe_payments import router as stripe_router
    app.include_router(stripe_router)

Env vars required:
    STRIPE_SECRET_KEY    — sk_test_... or sk_live_...
    STRIPE_WEBHOOK_SECRET — whsec_...
    SITE_URL             — https://crackthedeck.com  (no trailing slash)
"""

import os
import json
import time
import asyncio
import hashlib
import logging
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger("stripe_payments")

# Lazy import to avoid circular dependency at module level
def _log_payment_db(token, session_id, email, plan, amount, currency="usd"):
    try:
        from admin_db import log_payment
        log_payment(token=token, session_id=session_id, email=email, plan=plan, amount=amount, currency=currency)
    except Exception:
        pass

def _log_upload_db(report_id, filename, file_size_bytes, email="", company="", plan="basic", report_type="investor", company_name="", status="completed"):
    try:
        from admin_db import log_upload
        log_upload(report_id=report_id, filename=filename, file_size_bytes=file_size_bytes, email=email, company=company, plan=plan, report_type=report_type, company_name=company_name, status=status)
    except Exception:
        pass

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# ---------------------------------------------------------------------------
# Stripe SDK init
# ---------------------------------------------------------------------------
try:
    import stripe
except ImportError:
    raise ImportError("stripe package not installed. Run: pip install stripe")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
SITE_URL = os.getenv("SITE_URL", "https://crackthedeck.com").rstrip("/")

# ---------------------------------------------------------------------------
# Price mapping — set your Stripe Price IDs here after creating Products
# in Stripe Dashboard → Products.
#
# You can also use env vars STRIPE_PRICE_PRO / STRIPE_PRICE_EXPERT so you
# don't have to redeploy when switching from test to live prices.
# ---------------------------------------------------------------------------
PRICE_MAP = {
    "basic": os.getenv("STRIPE_PRICE_BASIC", ""),    # price_xxx from Stripe
    "pro": os.getenv("STRIPE_PRICE_PRO", ""),       # price_xxx from Stripe
    "expert": os.getenv("STRIPE_PRICE_EXPERT", ""),  # price_xxx from Stripe
}

# ---------------------------------------------------------------------------
# Pending uploads dir — files saved before payment, keyed by session token
# ---------------------------------------------------------------------------
PENDING_DIR = Path("pending_uploads")
PENDING_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# In-memory analysis job tracking (async background tasks)
# ---------------------------------------------------------------------------
_analysis_jobs = {}  # token -> { "status": "processing"|"done"|"error", "result": dict|None, "error": str|None }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_token() -> str:
    """Short unique token for tracking upload → payment → analysis."""
    return hashlib.sha256(f"{time.time()}{os.urandom(16).hex()}".encode()).hexdigest()[:24]


def _save_pending(token: str, file_bytes: bytes, filename: str, metadata: dict):
    """Save uploaded file + metadata to disk, awaiting payment confirmation."""
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
    """Load pending upload metadata. Returns None if expired or missing."""
    meta_path = PENDING_DIR / token / "meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    # Expire after 2 hours
    if time.time() - meta.get("created_at", 0) > 7200:
        return None
    return meta


def _get_pending_file(token: str) -> tuple[bytes, str] | None:
    """Return (file_bytes, filename) for a pending upload."""
    meta = _load_pending(token)
    if not meta:
        return None
    fpath = PENDING_DIR / token / meta["filename"]
    if not fpath.exists():
        return None
    return fpath.read_bytes(), meta["filename"]


def _cleanup_pending(token: str):
    """Remove pending upload after successful processing."""
    folder = PENDING_DIR / token
    if folder.exists():
        for f in folder.iterdir():
            f.unlink()
        folder.rmdir()

# ---------------------------------------------------------------------------
# Background analysis runner
# ---------------------------------------------------------------------------

async def _run_analysis_background(token: str, file_bytes: bytes, filename: str, report_type: str, email: str = "", plan: str = "basic"):
    """Run analysis in a background asyncio task. Stores result in _analysis_jobs."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            files = {"file": (filename, file_bytes)}
            data = {"report_type": report_type}
            resp = await client.post("http://127.0.0.1:8000/api/analyze", files=files, data=data)
            if resp.status_code != 200:
                _analysis_jobs[token] = {"status": "error", "result": None, "error": f"Analysis returned {resp.status_code}"}
                logger.error(f"Background analysis failed for {token}: {resp.status_code} {resp.text[:500]}")
            else:
                result = resp.json()
                _analysis_jobs[token] = {"status": "done", "result": result, "error": None}
                logger.info(f"Background analysis complete for {token}, plan={plan}")

                # Determine status based on plan
                # Basic: auto-send report immediately
                # Pro/Expert: save as pending_review for human review
                is_review_plan = plan in ("pro", "expert")
                upload_status = "pending_review" if is_review_plan else "completed"

                # Log paid upload to admin DB
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
                    # Pro/Expert: send "your report is being reviewed" notification
                    if email:
                        try:
                            email_resp = await client.post(
                                "http://127.0.0.1:8000/api/email/report-pending",
                                json={
                                    "email": email,
                                    "company_name": result.get("company_name", "your deck"),
                                    "plan": plan,
                                },
                                timeout=httpx.Timeout(30.0),
                            )
                            if email_resp.status_code == 200:
                                logger.info(f"Sent pending-review email to {email} for token {token}")
                            else:
                                logger.warning(f"Pending-review email failed for {token}: {email_resp.status_code}")
                        except Exception as email_err:
                            logger.warning(f"Pending-review email exception for {token}: {email_err}")
                else:
                    # Basic: auto-send report immediately
                    if email and result.get("report_id"):
                        try:
                            email_resp = await client.post(
                                "http://127.0.0.1:8000/api/email/send-report",
                                json={
                                    "email": email,
                                    "report_id": result["report_id"],
                                    "report_type": result.get("report_type", "investor"),
                                    "company_name": result.get("company_name", "your deck"),
                                },
                                timeout=httpx.Timeout(30.0),
                            )
                            if email_resp.status_code == 200:
                                logger.info(f"Auto-sent report email to {email} for token {token}")
                            else:
                                logger.warning(f"Auto-email failed for {token}: {email_resp.status_code}")
                        except Exception as email_err:
                            logger.warning(f"Auto-email exception for {token}: {email_err}")

    except Exception as e:
        _analysis_jobs[token] = {"status": "error", "result": None, "error": str(e)}
        logger.error(f"Background analysis exception for {token}: {e}")
    finally:
        # Cleanup pending files after analysis (success or failure)
        _cleanup_pending(token)


# ---------------------------------------------------------------------------
# 1. Pre-upload: save file + create checkout session
# ---------------------------------------------------------------------------

@router.post("/create-checkout-session")
async def create_checkout_session(
    file: UploadFile = File(...),
    plan: str = Form(...),
    email: str = Form(""),
    company: str = Form(""),
    stage: str = Form(""),
    report_type: str = Form("investor"),
):
    """
    Frontend calls this instead of /api/analyze for paid plans.
    1. Saves uploaded file to pending_uploads/{token}/
    2. Creates a Stripe Checkout Session
    3. Returns { url: stripe_checkout_url } for redirect
    """
    plan = plan.lower().strip()
    if plan not in PRICE_MAP or not PRICE_MAP[plan]:
        raise HTTPException(400, f"Unknown or unconfigured plan: {plan}. "
                            "Make sure STRIPE_PRICE_PRO and STRIPE_PRICE_EXPERT env vars are set.")

    # Save file to pending
    token = _generate_token()
    file_bytes = await file.read()
    _save_pending(token, file_bytes, file.filename, {
        "email": email,
        "company": company,
        "stage": stage,
        "plan": plan,
        "report_type": report_type,
    })

    # Create Stripe Checkout Session
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=email if email else None,
            line_items=[{
                "price": PRICE_MAP[plan],
                "quantity": 1,
            }],
            metadata={
                "token": token,
                "plan": plan,
                "email": email,
                "company": company,
            },
            success_url=f"{SITE_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}&token={token}",
            cancel_url=f"{SITE_URL}/payment-cancel?token={token}",
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        _cleanup_pending(token)
        raise HTTPException(502, f"Payment service error: {str(e)}")

    return JSONResponse({"url": session.url, "session_id": session.id, "token": token})


# ---------------------------------------------------------------------------
# 2. Webhook — Stripe calls this after payment
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint. Listens for checkout.session.completed.
    After payment, triggers analysis automatically.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        event = json.loads(payload)
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Invalid signature")
        except Exception as e:
            raise HTTPException(400, str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        token = session.get("metadata", {}).get("token", "")
        payment_status = session.get("payment_status", "")

        logger.info(f"Payment completed: token={token}, status={payment_status}, "
                    f"amount={session.get('amount_total')}, email={session.get('customer_email')}")

        if token and payment_status == "paid":
            # Mark as paid
            meta = _load_pending(token)
            if meta:
                paid_path = PENDING_DIR / token / "paid.flag"
                paid_path.write_text(json.dumps({
                    "session_id": session.get("id"),
                    "payment_intent": session.get("payment_intent"),
                    "amount_total": session.get("amount_total"),
                    "currency": session.get("currency"),
                    "paid_at": time.time(),
                }))
                logger.info(f"Marked token {token} as paid")
                # Log payment to admin DB
                _log_payment_db(
                    token=token,
                    session_id=session.get("id", ""),
                    email=session.get("customer_email", meta.get("email", "")),
                    plan=meta.get("plan", ""),
                    amount=session.get("amount_total", 0),
                    currency=session.get("currency", "usd"),
                )

    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# 3. Payment verification endpoint (frontend polls or calls after redirect)
# ---------------------------------------------------------------------------

@router.get("/verify-payment")
async def verify_payment(token: str = "", session_id: str = ""):
    """
    Called from the success page. Checks if the payment went through.
    Returns { paid: true/false, meta: { ... } }
    """
    if not token:
        raise HTTPException(400, "Missing token")

    # Check paid.flag (set by webhook)
    paid_path = PENDING_DIR / token / "paid.flag"
    if paid_path.exists():
        meta = _load_pending(token)
        return JSONResponse({"paid": True, "meta": meta})

    # Fallback: check directly with Stripe if webhook hasn't arrived yet
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
                meta = _load_pending(token)
                return JSONResponse({"paid": True, "meta": meta})
        except Exception:
            pass

    return JSONResponse({"paid": False, "meta": None})


# ---------------------------------------------------------------------------
# 4. Trigger analysis after confirmed payment (ASYNC — returns immediately)
# ---------------------------------------------------------------------------

@router.post("/process-paid")
async def process_paid(request: Request):
    """
    Called from the success page after verifying payment.
    Launches analysis as a background asyncio task and returns immediately.
    Frontend polls /api/stripe/analysis-status?token=... for results.
    """
    body = await request.json()
    token = body.get("token", "")
    if not token:
        raise HTTPException(400, "Missing token")

    # If already processing or done, return current status
    if token in _analysis_jobs:
        job = _analysis_jobs[token]
        if job["status"] == "done":
            return JSONResponse({"status": "done", "result": job["result"]})
        elif job["status"] == "processing":
            return JSONResponse({"status": "processing"})
        # If error, allow retry by falling through

    # Verify it's actually paid
    paid_path = PENDING_DIR / token / "paid.flag"
    meta = _load_pending(token)
    if not meta:
        raise HTTPException(404, "Upload not found or expired")

    # Also check with Stripe if webhook flag not yet set
    session_id = body.get("session_id", "")
    if not paid_path.exists() and session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status != "paid":
                raise HTTPException(402, "Payment not confirmed yet")
        except stripe.error.StripeError:
            raise HTTPException(402, "Could not verify payment")
    elif not paid_path.exists():
        raise HTTPException(402, "Payment not confirmed yet")

    # Load the file
    file_result = _get_pending_file(token)
    if not file_result:
        raise HTTPException(404, "File not found")
    file_bytes, filename = file_result

    # Mark as processing and launch background task
    _analysis_jobs[token] = {"status": "processing", "result": None, "error": None}
    customer_email = meta.get("email", "")
    customer_plan = meta.get("plan", "basic")
    asyncio.create_task(
        _run_analysis_background(token, file_bytes, filename, meta.get("report_type", "investor"), customer_email, customer_plan)
    )

    logger.info(f"Launched background analysis for token {token}")
    return JSONResponse({"status": "processing"})


# ---------------------------------------------------------------------------
# 4b. Analysis status polling endpoint
# ---------------------------------------------------------------------------

@router.get("/analysis-status")
async def analysis_status(token: str = ""):
    """
    Frontend polls this every few seconds after process-paid returns 'processing'.
    Returns:
      { status: "processing" }                         — still working
      { status: "done", result: { ...analysis... } }   — finished, includes pdf_url etc.
      { status: "error", error: "..." }                — failed
      { status: "unknown" }                            — token not found in jobs
    """
    if not token:
        raise HTTPException(400, "Missing token")

    job = _analysis_jobs.get(token)
    if not job:
        return JSONResponse({"status": "unknown"})

    if job["status"] == "done":
        result = job["result"]
        # Clean up from memory after delivery (keep for 5 min in case of re-polls)
        # We don't delete immediately so the client can retry if the response is lost
        return JSONResponse({"status": "done", "result": result})
    elif job["status"] == "error":
        return JSONResponse({"status": "error", "error": job.get("error", "Unknown error")})
    else:
        return JSONResponse({"status": "processing"})


# ---------------------------------------------------------------------------
# 5. Cancel — cleanup pending upload
# ---------------------------------------------------------------------------

@router.get("/cancel")
async def payment_cancel(token: str = ""):
    """Optional: cleanup pending upload if user cancels payment."""
    if token:
        _cleanup_pending(token)
    return RedirectResponse(f"{SITE_URL}?payment=cancelled")
