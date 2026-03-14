from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, distinct

from app.config import settings
from app.database import init_db, get_session
from app.models import Fund
from app.embeddings import get_embedding, build_fund_text
from app.fund_parsers import normalize_stage_single, parse_raise_to_usd
from app.llm import extract_startup_profile, generate_recommendations
from app.schemas import (
    SearchRequest,
    SearchResponse,
    FundResult,
    MatchRequest,
    MatchResponse,
    FundRecommendation,
    ExtractRequest,
    ExtractResponse,
    StatsResponse,
    HealthResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="CrackTheDeck Funds RAG",
    description="Fund matching API: vector search + GPT-4o recommendations",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────── Helpers ───────────────────────────


# How many vector candidates to fetch before applying filters (ivfflat is used only when ORDER BY embedding is on base table).
# Large pool so that after stage/geo filters we still get enough results.
VECTOR_CANDIDATE_MULTIPLIER = 20
VECTOR_CANDIDATE_CAP = 3000


def _row_to_fund_result(row, similarity: float) -> FundResult:
    return FundResult(
        id=row.id,
        investor_name=row.investor_name,
        domain_name=row.domain_name,
        overview=row.overview,
        founded_year=str(row.founded_year) if row.founded_year else None,
        country=row.country,
        state=row.state,
        city=row.city,
        description=row.description,
        investor_type=row.investor_type,
        practice_areas=row.practice_areas,
        feed_name=row.feed_name,
        business_models=row.business_models,
        investment_score=row.investment_score,
        check_min_usd=float(row.check_min_usd) if getattr(row, "check_min_usd", None) is not None else None,
        check_max_usd=float(row.check_max_usd) if getattr(row, "check_max_usd", None) is not None else None,
        check_size_text=row.check_size_text,
        website=row.website,
        linkedin=row.linkedin,
        twitter=row.twitter,
        similarity=round(similarity, 4),
    )


async def _vector_search(
    query_text: str,
    top_k: int,
    session: AsyncSession,
    country: str = None,
    investor_type: str = None,
    min_score: float = None,
    geography: str = None,
    stage_filter: str = None,
    raise_usd: float = None,
) -> list[FundResult]:
    """
    Vector-first hybrid search so ivfflat index is used:
    1. Get top-N candidates by embedding only (ORDER BY embedding LIMIT N).
    2. Filter those candidates by stage / check size / geography (small set, no full scan).
    """
    query_embedding = get_embedding(query_text)
    embedding_literal = str(query_embedding)

    candidate_limit = min(VECTOR_CANDIDATE_CAP, max(top_k * VECTOR_CANDIDATE_MULTIPLIER, 200))

    # Ensure ivfflat uses a reasonable probe count for good recall
    await session.execute(text("SET LOCAL ivfflat.probes = 10"))

    # Step 1: pure vector search — no WHERE, so planner uses ivfflat
    step1_sql = text("""
        SELECT f.id, 1 - (f.embedding <=> :embedding) AS similarity
        FROM funds f
        ORDER BY f.embedding <=> :embedding
        LIMIT :candidate_limit
    """)
    step1_result = await session.execute(
        step1_sql, {"embedding": embedding_literal, "candidate_limit": candidate_limit}
    )
    ordered_candidates = step1_result.fetchall()  # list of (id, similarity)
    if not ordered_candidates:
        return []

    ordered_ids = [r.id for r in ordered_candidates]
    sim_by_id = {r.id: float(r.similarity) for r in ordered_candidates}

    # Step 2: filters applied only to this small set (no full table scan, no ILIKE on whole table)
    filters = ["f.id = ANY(CAST(:ids AS INTEGER[]))"]
    params = {"ids": ordered_ids}

    # Include funds that have no stage data (NULL) or whose stage matches
    if stage_filter:
        filters.append("(f.stage IS NULL OR :stage_filter = ANY(f.stage))")
        params["stage_filter"] = stage_filter
    if raise_usd is not None:
        filters.append("(f.check_min_usd IS NULL OR :raise_usd >= f.check_min_usd)")
        filters.append("(f.check_max_usd IS NULL OR :raise_usd <= f.check_max_usd)")
        params["raise_usd"] = float(raise_usd)
    if country:
        filters.append("f.country ILIKE :country")
        params["country"] = f"%{country}%"
    if investor_type:
        filters.append("f.investor_type ILIKE :investor_type")
        params["investor_type"] = f"%{investor_type}%"
    if min_score is not None:
        filters.append("f.investment_score >= :min_score")
        params["min_score"] = min_score
    if geography:
        params["geo"] = f"%{geography}%"
        filters.append(
            "(f.country ILIKE :geo OR f.state ILIKE :geo OR f.city ILIKE :geo "
            "OR f.description ILIKE :geo OR f.overview ILIKE :geo)"
        )

    where_clause = " AND ".join(filters)
    step2_sql = text(f"""
        SELECT
            f.id, f.investor_name, f.domain_name, f.overview,
            f.founded_year, f.country, f.state, f.city, f.description,
            f.investor_type, f.practice_areas, f.feed_name,
            f.business_models, f.investment_score,
            f.check_min_usd, f.check_max_usd, f.check_size_text,
            f.website, f.linkedin, f.twitter
        FROM funds f
        WHERE {where_clause}
    """)
    step2_result = await session.execute(step2_sql, params)
    rows_by_id = {row.id: row for row in step2_result.fetchall()}

    # Preserve vector order, take first top_k that passed filters
    out = []
    for fid in ordered_ids:
        if fid not in rows_by_id:
            continue
        row = rows_by_id[fid]
        out.append(_row_to_fund_result(row, sim_by_id[fid]))
        if len(out) >= top_k:
            break
    return out


# ──────────────────────── Health ────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)):
    count = (await session.execute(select(func.count(Fund.id)))).scalar() or 0
    return HealthResponse(status="ok", funds_indexed=count)


# ────────────── Extract startup profile from pitch ──────────


@app.post("/api/rag/extract", response_model=ExtractResponse)
async def extract_profile(req: ExtractRequest):
    """
    Extract startup parameters from raw pitch text.
    Uses GPT-4o (runs on OpenAI, not on server).

    Call this from crackthedeck after parsing the PDF/PPTX.
    """
    try:
        profile = extract_startup_profile(req.pitch_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GPT-4o extraction error: {e}")
    return ExtractResponse(startup=profile)


# ──────────── Full fund matching pipeline ───────────────────


@app.post("/api/rag/match", response_model=MatchResponse)
async def match_funds(req: MatchRequest, session: AsyncSession = Depends(get_session)):
    """
    MAIN ENDPOINT — Full fund matching pipeline:

    1. Build search query from startup parameters (fast, local)
    2. pgvector finds top-N candidate funds (fast, local SQL)
    3. GPT-4o ranks & explains matches (runs on OpenAI, not on server)

    Input: StartupProfile (from /api/rag/extract or from crackthedeck pitch analysis)
    Output: Ranked fund recommendations with reasoning
    """
    # Step 1: Build semantic search query — explicit format so different inputs yield different embeddings
    parts = []
    if req.startup.industry:
        parts.append(f"Industry: {req.startup.industry}")
    if req.startup.sub_industry:
        parts.append(f"Sub-industry: {req.startup.sub_industry}")
    if req.startup.stage:
        parts.append(f"Stage: {req.startup.stage}")
    if req.startup.business_model:
        parts.append(f"Business model: {req.startup.business_model}")
    if req.startup.geography:
        parts.append(f"Geography: {req.startup.geography}")
    if req.startup.description:
        parts.append(req.startup.description)

    if not parts:
        raise HTTPException(status_code=400, detail="At least one startup parameter is required")

    search_query = ". ".join(parts)

    # Step 2: Vector-first search; stage + geography filters only (no check-size filter so we get more funds; check size still shown in cards)
    stage_canonical = normalize_stage_single(req.startup.stage)
    try:
        candidates = await _vector_search(
            search_query,
            req.top_k,
            session,
            geography=req.startup.geography,
            stage_filter=stage_canonical,
            raise_usd=None,  # don't filter by check size — show more funds, user sees check in card
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector search error: {e}")

    if not candidates:
        return MatchResponse(
            startup=req.startup,
            total_candidates=0,
            recommendations=[],
            summary="No matching funds found in the database.",
        )

    # Step 3: GPT-4o generates recommendations (runs on OpenAI)
    try:
        gpt_result = generate_recommendations(req.startup, candidates, req.language)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GPT-4o recommendation error: {e}")

    # Merge GPT reasoning with fund data
    reasoning_map = {
        r["investor_name"]: r["reasoning"]
        for r in gpt_result.get("recommendations", [])
    }

    recommendations = []
    for fund in candidates:
        recommendations.append(
            FundRecommendation(
                investor_name=fund.investor_name,
                city=fund.city,
                country=fund.country,
                overview=fund.overview,
                business_models=fund.business_models,
                check_size=fund.check_size_text,
                website=fund.website,
                linkedin=fund.linkedin,
                similarity=fund.similarity,
                reasoning=reasoning_map.get(fund.investor_name, ""),
            )
        )

    # Re-sort by GPT's preferred order
    gpt_order = [r["investor_name"] for r in gpt_result.get("recommendations", [])]
    if gpt_order:
        order_map = {name: i for i, name in enumerate(gpt_order)}
        recommendations.sort(key=lambda r: order_map.get(r.investor_name, 999))

    return MatchResponse(
        startup=req.startup,
        total_candidates=len(recommendations),
        recommendations=recommendations,
        summary=gpt_result.get("summary", ""),
    )


# ──────────────────── Vector search (direct) ────────────────


@app.post("/api/rag/search", response_model=SearchResponse)
async def search_funds(req: SearchRequest, session: AsyncSession = Depends(get_session)):
    """Direct semantic search — without GPT-4o recommendations."""
    try:
        results = await _vector_search(
            req.query, req.top_k, session,
            country=req.country,
            investor_type=req.investor_type,
            min_score=req.min_score,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")

    return SearchResponse(query=req.query, total_results=len(results), results=results)


# ──────────────────── Text search / listing ─────────────────


@app.get("/api/rag/funds")
async def list_funds(
    q: str = "", country: str = "", limit: int = 20, offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """Simple text search with pagination (no embeddings, no GPT)."""
    query = select(Fund)
    if q:
        query = query.where(
            Fund.investor_name.ilike(f"%{q}%")
            | Fund.overview.ilike(f"%{q}%")
            | Fund.description.ilike(f"%{q}%")
        )
    if country:
        query = query.where(Fund.country.ilike(f"%{country}%"))
    query = query.order_by(Fund.investment_score.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    funds = result.scalars().all()
    return {"total": len(funds), "offset": offset, "limit": limit, "results": [f.to_dict() for f in funds]}


# ──────────────────────── Countries list (for geography dropdown) ─────────────────────────────


@app.get("/api/rag/countries")
async def get_countries(session: AsyncSession = Depends(get_session)):
    """Return sorted list of unique country names from the funds table (for dropdown)."""
    result = await session.execute(select(Fund.country).distinct())
    raw = [r[0] for r in result if r[0]]
    # Split composite values like "Japan,; United States" or "Singapore,; Indonesia"
    seen = set()
    for s in raw:
        for part in s.replace(";", ",").split(","):
            name = part.strip()
            if name:
                seen.add(name)
    return {"countries": sorted(seen)}


# ──────────────────────── Stats ─────────────────────────────


@app.get("/api/rag/stats", response_model=StatsResponse)
async def get_stats(session: AsyncSession = Depends(get_session)):
    total = (await session.execute(select(func.count(Fund.id)))).scalar() or 0
    countries_result = await session.execute(
        select(Fund.country, func.count(Fund.id).label("cnt"))
        .group_by(Fund.country).order_by(text("cnt DESC")).limit(20)
    )
    top_countries = [{"country": r.country, "count": r.cnt} for r in countries_result]
    types_result = await session.execute(select(distinct(Fund.investor_type)))
    investor_types = [r[0] for r in types_result if r[0]]
    unique_countries = (await session.execute(select(func.count(distinct(Fund.country))))).scalar() or 0
    return StatsResponse(
        total_funds=total, countries=unique_countries,
        investor_types=investor_types, top_countries=top_countries,
    )
