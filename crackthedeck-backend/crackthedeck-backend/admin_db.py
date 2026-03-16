"""
CrackTheDeck — Admin database (SQLite).

Logs uploads, payments, contact form submissions for the admin panel.

Usage in main.py:
    from admin_db import init_db, log_upload, log_contact, log_payment
    
    @app.on_event("startup")
    async def startup():
        init_db()
"""

import sqlite3
import time
import threading
import logging
from pathlib import Path

logger = logging.getLogger("admin_db")

DB_PATH = Path(__file__).parent / "admin.db"
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT,
            filename TEXT,
            file_ext TEXT,
            file_size_bytes INTEGER,
            email TEXT DEFAULT '',
            company TEXT DEFAULT '',
            plan TEXT DEFAULT 'free',
            report_type TEXT DEFAULT 'investor',
            status TEXT DEFAULT 'completed',
            company_name TEXT DEFAULT '',
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT,
            session_id TEXT,
            email TEXT DEFAULT '',
            plan TEXT,
            amount INTEGER,
            currency TEXT DEFAULT 'usd',
            status TEXT DEFAULT 'completed',
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            message TEXT,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT DEFAULT '',
            rating INTEGER,
            reasons TEXT DEFAULT '',
            comment TEXT DEFAULT '',
            created_at REAL
        );
    """)
    conn.commit()
    logger.info(f"Admin DB initialized at {DB_PATH}")


def log_upload(
    report_id: str,
    filename: str,
    file_size_bytes: int,
    email: str = "",
    company: str = "",
    plan: str = "free",
    report_type: str = "investor",
    company_name: str = "",
    status: str = "completed",
):
    """Log a deck upload/analysis."""
    try:
        conn = _get_conn()
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        conn.execute(
            """INSERT INTO uploads 
               (report_id, filename, file_ext, file_size_bytes, email, company, plan, report_type, status, company_name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_id, filename, ext, file_size_bytes, email, company, plan, report_type, status, company_name, time.time()),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to log upload: {e}")


def log_payment(
    token: str,
    session_id: str,
    email: str,
    plan: str,
    amount: int,
    currency: str = "usd",
):
    """Log a successful payment."""
    try:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO payments (token, session_id, email, plan, amount, currency, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)""",
            (token, session_id, email, plan, amount, currency, time.time()),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to log payment: {e}")


def log_contact(name: str, email: str, message: str):
    """Log a contact form submission."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO contact_messages (name, email, message, created_at) VALUES (?, ?, ?, ?)",
            (name, email, message, time.time()),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to log contact: {e}")


def get_uploads(limit: int = 100, offset: int = 0) -> list[dict]:
    """Get recent uploads."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM uploads ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_payments(limit: int = 100, offset: int = 0) -> list[dict]:
    """Get recent payments."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM payments ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_contacts(limit: int = 100, offset: int = 0) -> list[dict]:
    """Get recent contact messages."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM contact_messages ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def log_feedback(
    report_id: str = "",
    rating: int = 0,
    reasons: str = "",
    comment: str = "",
):
    """Log a user feedback submission."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO feedback (report_id, rating, reasons, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (report_id, rating, reasons, comment, time.time()),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")


def get_feedbacks(limit: int = 100, offset: int = 0) -> list[dict]:
    """Get recent feedback entries."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def update_upload_status(report_id: str, status: str) -> bool:
    """Update upload status (e.g. pending_review -> sent)."""
    try:
        conn = _get_conn()
        cur = conn.execute(
            "UPDATE uploads SET status = ? WHERE report_id = ?",
            (status, report_id),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update upload status: {e}")
        return False


def get_upload_by_report_id(report_id: str) -> dict | None:
    """Get a single upload by report_id.
    
    If multiple records exist (e.g. free analysis + paid upgrade),
    prefer the one with email and highest id.
    """
    conn = _get_conn()
    # Prefer record with email, then latest id
    row = conn.execute(
        "SELECT * FROM uploads WHERE report_id = ? ORDER BY (email != '' AND email IS NOT NULL) DESC, id DESC LIMIT 1",
        (report_id,),
    ).fetchone()
    return dict(row) if row else None


def get_dashboard_stats() -> dict:
    """Get summary stats for admin dashboard."""
    conn = _get_conn()
    now = time.time()
    day_ago = now - 86400
    week_ago = now - 604800

    total_uploads = conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
    uploads_today = conn.execute("SELECT COUNT(*) FROM uploads WHERE created_at > ?", (day_ago,)).fetchone()[0]
    uploads_week = conn.execute("SELECT COUNT(*) FROM uploads WHERE created_at > ?", (week_ago,)).fetchone()[0]

    total_payments = conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    revenue_total = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments").fetchone()[0]
    payments_week = conn.execute("SELECT COUNT(*) FROM payments WHERE created_at > ?", (week_ago,)).fetchone()[0]

    total_contacts = conn.execute("SELECT COUNT(*) FROM contact_messages").fetchone()[0]
    contacts_week = conn.execute("SELECT COUNT(*) FROM contact_messages WHERE created_at > ?", (week_ago,)).fetchone()[0]

    total_feedback = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    feedback_week = conn.execute("SELECT COUNT(*) FROM feedback WHERE created_at > ?", (week_ago,)).fetchone()[0]
    avg_rating = conn.execute("SELECT ROUND(AVG(rating), 1) FROM feedback").fetchone()[0] or 0

    return {
        "uploads": {"total": total_uploads, "today": uploads_today, "week": uploads_week},
        "payments": {"total": total_payments, "week": payments_week, "revenue_cents": revenue_total},
        "contacts": {"total": total_contacts, "week": contacts_week},
        "feedback": {"total": total_feedback, "week": feedback_week, "avg_rating": avg_rating},
    }
