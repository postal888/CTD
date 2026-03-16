"""Deals feed API — TechCrunch RSS filtered by GPT, cached 24h.

Resilience: if refresh fails (feed down, GPT error, bad data),
the previous cache is kept and served as-is until a successful refresh.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
from fastapi import APIRouter, Query
from openai import OpenAI

import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deals", tags=["deals"])

FEED_USER_AGENT = "Mozilla/5.0 (compatible; CrackTheDeck/1.0; +https://github.com/postal888/CTD)"

CACHE_PATH = config.BASE_DIR / "deals_cache.json"
CACHE_TTL_HOURS = 24

TECHCRUNCH_FUNDING_FEED = "https://techcrunch.com/tag/funding/feed/"
TECHCRUNCH_MAIN_FEED = "https://techcrunch.com/feed/"

# Minimum deals GPT must return for us to accept the result
MIN_VALID_DEALS = 3

GPT_SYSTEM = """You are a filter for tech news. You receive a list of article headlines and links from TechCrunch.

Your task: keep ONLY articles about a specific startup or company that raised funding (VC round, investment, funding announcement). 
Exclude: general news, movies/entertainment, politics, "how to" articles, opinion pieces, or any headline that does not clearly describe a company raising money (e.g. "$X round", "raises $X", "lands $X", "secures funding").

For each KEPT article, extract:
- company: the startup/company name that raised (short name)
- amount: the funding amount exactly as in the headline (e.g. "$50M", "€10M", "$2.5M")
- round: if mentioned (e.g. "Seed", "Series A", "Series B"); otherwise null
- url: the link unchanged
- headline: the full headline unchanged
- date: from the headline or use empty string if unknown

Return valid JSON only, no markdown:
{"deals": [{"company": "...", "amount": "...", "round": "..." or null, "url": "...", "headline": "...", "date": "..."}]}

If no headlines are about startup funding, return {"deals": []}.
"""


def _format_date(published) -> str:
    if not published:
        return ""
    try:
        if hasattr(published, "tm_mon"):
            d = datetime(published.tm_year, published.tm_mon, published.tm_mday)
            return d.strftime("%b ") + str(d.day)
        if isinstance(published, str):
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            return dt.strftime("%b ") + str(dt.day)
    except Exception:
        pass
    return ""


def _load_cache(*, ignore_ttl: bool = False) -> dict | None:
    """Load cache. If ignore_ttl=True, return even expired cache (stale fallback)."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        updated = data.get("updated_at")
        if not updated:
            return None
        if not ignore_ttl:
            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - dt > timedelta(hours=CACHE_TTL_HOURS):
                return None
        # Sanity: cache must have real deals
        deals = data.get("deals") or []
        if not deals:
            return None
        return data
    except Exception:
        return None


def _save_cache(deals: list, source: str):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"updated_at": datetime.utcnow().isoformat() + "Z", "deals": deals, "source": source}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _fetch_feed_entries() -> list[dict]:
    entries = []
    try:
        feed = feedparser.parse(TECHCRUNCH_FUNDING_FEED, agent=FEED_USER_AGENT)
        entries = getattr(feed, "entries", []) or []
        if not entries:
            feed = feedparser.parse(TECHCRUNCH_MAIN_FEED, agent=FEED_USER_AGENT)
            entries = getattr(feed, "entries", []) or []
    except Exception as e:
        logger.warning("Deals feed fetch failed: %s", e)
    return entries


def _entries_to_text(entries: list[dict], max_items: int = 80) -> str:
    lines = []
    for i, e in enumerate(entries[:max_items]):
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        pub = e.get("published_parsed") or e.get("published")
        date_str = _format_date(pub)
        if title and link:
            lines.append(f"[{i+1}] {date_str} | {title}\n{link}")
    return "\n\n".join(lines)


def _validate_deal(d: dict) -> bool:
    """Check that a deal object looks sane — has company name and a $ amount."""
    company = (d.get("company") or "").strip()
    amount = (d.get("amount") or "").strip()
    if not company or len(company) < 2:
        return False
    if not amount or "$" not in amount:
        return False
    return True


def _filter_deals_with_gpt(entries: list[dict]) -> tuple[list[dict], str]:
    """Send headlines to GPT, return (list of deals in our API format, source)."""
    if not entries:
        logger.warning("Deals: no feed entries to filter")
        return [], "TechCrunch RSS"
    text = _entries_to_text(entries)
    if not text:
        return [], "TechCrunch RSS"
    if not config.OPENAI_API_KEY:
        logger.warning("Deals: OPENAI_API_KEY not set, cannot filter with GPT")
        return [], "TechCrunch RSS"
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": GPT_SYSTEM},
                {"role": "user", "content": "Filter and extract funding deals from these headlines:\n\n" + text},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_completion_tokens=4096,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        deals_in = data.get("deals") or []
    except Exception as e:
        logger.warning("Deals GPT filter failed: %s", e, exc_info=True)
        return [], "TechCrunch RSS"

    # Normalize to API format and validate each deal
    deals = []
    skipped = 0
    for d in deals_in:
        if not _validate_deal(d):
            skipped += 1
            continue
        company = (d.get("company") or "").strip() or "Startup"
        amount = (d.get("amount") or "").strip() or "—"
        round_ = (d.get("round") or "").strip() or None
        url = (d.get("url") or "").strip() or "#"
        headline = (d.get("headline") or "").strip() or ""
        date = (d.get("date") or "").strip()
        ticker = f"{company} raises {amount}"
        if round_:
            ticker += f" ({round_})"
        deals.append({
            "company": company,
            "amount": amount,
            "round": round_,
            "ticker": ticker,
            "date": date,
            "url": url,
            "headline": headline[:120] + ("..." if len(headline) > 120 else ""),
        })
    if skipped:
        logger.info("Deals: skipped %d invalid deal entries from GPT", skipped)
    return deals, "TechCrunch RSS (GPT-filtered)"


def _try_refresh() -> dict | None:
    """Attempt to refresh deals from RSS+GPT. Returns new cache dict or None on failure."""
    entries = _fetch_feed_entries()
    if not entries:
        logger.warning("Deals refresh: feed returned no entries")
        return None

    deals, source = _filter_deals_with_gpt(entries)

    if len(deals) < MIN_VALID_DEALS:
        logger.warning("Deals refresh: only %d deals (min %d), rejecting update", len(deals), MIN_VALID_DEALS)
        return None

    # All checks passed — save and return
    _save_cache(deals, source)
    logger.info("Deals refresh: saved %d deals", len(deals))
    return {"deals": deals, "source": source, "updated_at": datetime.utcnow().isoformat() + "Z"}


@router.get("/latest")
def get_latest_deals(limit: int = Query(20, ge=1, le=50)):
    """Return cached deals. On cache expiry, try refresh; if refresh fails, serve stale cache."""

    # 1. Fresh cache? Serve it.
    fresh = _load_cache(ignore_ttl=False)
    if fresh is not None:
        deals = fresh.get("deals") or []
        return {
            "deals": deals[:limit],
            "total": len(deals),
            "source": fresh.get("source", "TechCrunch RSS"),
        }

    # 2. Cache expired or missing — try refresh
    refreshed = _try_refresh()
    if refreshed is not None:
        deals = refreshed.get("deals") or []
        return {
            "deals": deals[:limit],
            "total": len(deals),
            "source": refreshed.get("source", "TechCrunch RSS"),
        }

    # 3. Refresh failed — serve stale cache if available
    stale = _load_cache(ignore_ttl=True)
    if stale is not None:
        deals = stale.get("deals") or []
        logger.info("Deals: serving stale cache (%d deals) after refresh failure", len(deals))
        return {
            "deals": deals[:limit],
            "total": len(deals),
            "source": stale.get("source", "TechCrunch RSS") + " (cached)",
        }

    # 4. No cache at all — hide ticker
    logger.warning("Deals: no cache and refresh failed, returning empty")
    return {"deals": [], "total": 0, "source": "unavailable"}
