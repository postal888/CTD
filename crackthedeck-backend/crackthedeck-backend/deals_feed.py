"""Deals feed API — TechCrunch RSS filtered by GPT, cached 24h."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
from fastapi import APIRouter, Query
from openai import OpenAI

import config

router = APIRouter(prefix="/api/deals", tags=["deals"])

# Cache: refresh at most once per day
CACHE_PATH = config.BASE_DIR / "deals_cache.json"
CACHE_TTL_HOURS = 24

TECHCRUNCH_FUNDING_FEED = "https://techcrunch.com/tag/funding/feed/"
TECHCRUNCH_MAIN_FEED = "https://techcrunch.com/feed/"

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

_FALLBACK_DEALS = [
    {"company": "TechCrunch", "amount": "—", "round": None, "ticker": "Latest funding news", "date": "", "url": "https://techcrunch.com/", "headline": "Visit TechCrunch for funding news"},
]


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


def _load_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        updated = data.get("updated_at")
        if not updated:
            return None
        dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - dt > timedelta(hours=CACHE_TTL_HOURS):
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
        feed = feedparser.parse(TECHCRUNCH_FUNDING_FEED)
        entries = getattr(feed, "entries", []) or []
        if not entries:
            feed = feedparser.parse(TECHCRUNCH_MAIN_FEED)
            entries = getattr(feed, "entries", []) or []
    except Exception:
        pass
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


def _filter_deals_with_gpt(entries: list[dict]) -> tuple[list[dict], str]:
    """Send headlines to GPT, return (list of deals in our API format, source)."""
    if not entries:
        return [], "TechCrunch RSS"
    text = _entries_to_text(entries)
    if not text:
        return [], "TechCrunch RSS"
    if not config.OPENAI_API_KEY:
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
            max_tokens=4096,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        deals_in = data.get("deals") or []
    except Exception:
        return [], "TechCrunch RSS"
    # Normalize to API format: company, amount, round, ticker, date, url, headline
    deals = []
    for d in deals_in:
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
    return deals, "TechCrunch RSS (GPT-filtered)"


@router.get("/latest")
def get_latest_deals(limit: int = Query(20, ge=1, le=50)):
    """Return cached deals (refresh once per day); on refresh, feed is filtered by GPT to only startup funding."""
    cached = _load_cache()
    if cached is not None:
        deals = cached.get("deals") or []
        return {
            "deals": deals[:limit],
            "total": len(deals),
            "source": cached.get("source", "TechCrunch RSS"),
        }
    entries = _fetch_feed_entries()
    if not entries:
        return {"deals": _FALLBACK_DEALS, "total": len(_FALLBACK_DEALS), "source": "TechCrunch RSS"}
    deals, source = _filter_deals_with_gpt(entries)
    if not deals:
        return {"deals": _FALLBACK_DEALS, "total": len(_FALLBACK_DEALS), "source": source}
    _save_cache(deals, source)
    return {"deals": deals[:limit], "total": len(deals), "source": source}
