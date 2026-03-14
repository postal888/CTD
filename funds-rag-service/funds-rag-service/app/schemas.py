from pydantic import BaseModel, Field
from typing import List, Optional


# ─────────────── Startup profile (extracted from pitch) ───────────────


class StartupProfile(BaseModel):
    """Parameters extracted from a pitch deck by GPT-4o."""
    company_name: Optional[str] = None
    industry: Optional[str] = Field(default=None, description="e.g. fintech, healthtech, edtech, SaaS")
    sub_industry: Optional[str] = Field(default=None, description="More specific vertical")
    stage: Optional[str] = Field(default=None, description="e.g. pre-seed, seed, Series A, Series B")
    business_model: Optional[str] = Field(default=None, description="e.g. B2B SaaS, marketplace, D2C")
    geography: Optional[str] = Field(default=None, description="Where the startup operates")
    target_raise: Optional[str] = Field(default=None, description="Amount seeking, e.g. $2M")
    description: Optional[str] = Field(default=None, description="Short summary of what the company does")


# ─────────────────────── Search / RAG ─────────────────────────


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language search query")
    top_k: int = Field(default=10, ge=1, le=100)
    country: Optional[str] = None
    investor_type: Optional[str] = None
    min_score: Optional[float] = None


class FundResult(BaseModel):
    id: int
    investor_name: str
    domain_name: Optional[str] = None
    overview: Optional[str] = None
    founded_year: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    description: Optional[str] = None
    investor_type: Optional[str] = None
    practice_areas: Optional[str] = None
    feed_name: Optional[str] = None
    business_models: Optional[str] = None
    investment_score: Optional[float] = None
    check_min_usd: Optional[float] = None
    check_max_usd: Optional[float] = None
    check_size_text: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None
    similarity: float = Field(default=0.0, description="Cosine similarity 0-1")


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[FundResult]


# ──────────────────── Fund matching ─────────────────────


class MatchRequest(BaseModel):
    """Input for the full fund-matching pipeline."""
    startup: StartupProfile = Field(..., description="Startup parameters (from pitch analysis or manual)")
    top_k: int = Field(default=10, ge=1, le=100, description="How many fund candidates to consider")
    language: str = Field(default="en", description="Response language: en, ru, pt")


class FundRecommendation(BaseModel):
    investor_name: str
    country: Optional[str] = None
    city: Optional[str] = None
    overview: Optional[str] = None
    business_models: Optional[str] = None
    check_size: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None
    similarity: float
    reasoning: str = Field(..., description="Why this fund is a good match")


class MatchResponse(BaseModel):
    startup: StartupProfile
    total_candidates: int
    recommendations: List[FundRecommendation]
    summary: str = Field(..., description="GPT-4o generated summary of fund matching results")


# ──────────────────── Extract from pitch text ─────────────────────


class ExtractRequest(BaseModel):
    """Extract startup profile from raw pitch text."""
    pitch_text: str = Field(..., description="Raw text extracted from pitch deck (PDF/PPTX)")


class ExtractResponse(BaseModel):
    startup: StartupProfile


# ──────────────────────── Stats / Health ────────────────────────


class StatsResponse(BaseModel):
    total_funds: int
    countries: int
    investor_types: List[str]
    top_countries: List[dict]


class HealthResponse(BaseModel):
    status: str
    funds_indexed: int
