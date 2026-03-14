import openai
from typing import List

from app.config import settings

client = openai.OpenAI(api_key=settings.openai_api_key)


def get_embedding(text: str) -> List[float]:
    """Get embedding for a single text."""
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding


def get_embeddings_batch(texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Get embeddings for a batch of texts."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
        )
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)
    return all_embeddings


async def get_embedding_async(text: str) -> List[float]:
    """Async wrapper — uses sync client under the hood (OpenAI SDK is sync)."""
    return get_embedding(text)


def build_fund_text(row: dict) -> str:
    """Build a rich text representation of a fund for embedding (CSV-style row)."""
    parts = []
    if row.get("investor_name"):
        parts.append(f"Investor: {row['investor_name']}")
    if row.get("overview"):
        parts.append(f"Overview: {row['overview']}")
    if row.get("description"):
        parts.append(f"Description: {row['description']}")
    if row.get("country"):
        parts.append(f"Country: {row['country']}")
    if row.get("city"):
        parts.append(f"City: {row['city']}")
    if row.get("investor_type"):
        parts.append(f"Investor Type: {row['investor_type']}")
    if row.get("practice_areas"):
        parts.append(f"Practice Areas: {row['practice_areas']}")
    if row.get("feed_name"):
        parts.append(f"Feed: {row['feed_name']}")
    if row.get("business_models"):
        parts.append(f"Business Models: {row['business_models']}")
    if row.get("founded_year"):
        parts.append(f"Founded: {row['founded_year']}")
    return " | ".join(parts)


def build_fund_text_from_jsonl(row: dict) -> str:
    """Use the pre-built 'text' field from funds JSONL (e.g. funds_clean.jsonl) for embedding."""
    return (row.get("text") or "").strip() or build_fund_text(_jsonl_to_legacy_row(row))


def _jsonl_to_legacy_row(row: dict) -> dict:
    """Map JSONL keys to legacy build_fund_text keys (for fallback)."""
    return {
        "investor_name": row.get("name") or "",
        "country": row.get("hq_country") or "",
        "city": row.get("hq_city") or "",
        "investor_type": row.get("type") or "",
        "description": row.get("description") or "",
        "overview": row.get("description") or "",
        "practice_areas": row.get("fund_model") or "",
        "business_models": row.get("sectors") or "",
        "founded_year": str(row.get("founded_year") or ""),
    }
