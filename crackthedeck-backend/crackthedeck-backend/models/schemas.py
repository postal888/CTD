"""Pydantic models for API request/response and GPT-4o output schemas."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── Investor Report Schema ──────────────────────────────────────────

class InvestorCriterion(BaseModel):
    name: str
    score: int
    comment: str


class KeyMetrics(BaseModel):
    revenue: Optional[str] = None
    revenue_growth: Optional[str] = None
    cagr: Optional[str] = None
    ask: Optional[str] = None
    valuation_claimed: Optional[str] = None
    revenue_multiple: Optional[str] = None
    team_size: Optional[str] = None
    founded: Optional[str] = None
    stage: Optional[str] = None


class InvestorReport(BaseModel):
    company_name: str
    company_name_local: Optional[str] = None
    sector: str
    stage: str
    target_raise: str
    valuation: str
    revenue_multiple: str
    total_slides: int
    date: str

    overall_score: int
    overall_label: str
    overall_summary: str

    criteria: list[InvestorCriterion]
    key_metrics: KeyMetrics
    strengths: list[str]
    risks: list[str]


# ── Startup Report Schema ───────────────────────────────────────────

class ChecklistItem(BaseModel):
    element: str
    status: str  # strong / weak / missing / n/a
    notes: str


class ChecklistSummary(BaseModel):
    total: int
    strong: int
    weak: int
    missing: int


class FundraisingReadiness(BaseModel):
    level: str  # HIGH / MEDIUM / LOW
    summary: str
    completeness_pct: int
    completeness_note: str
    structure_pct: int
    structure_note: str
    strength_pct: int
    strength_note: str


class Issue(BaseModel):
    rank: int
    severity: str  # CRITICAL / HIGH / MEDIUM
    description: str


class RecommendedSlide(BaseModel):
    slide_number: int
    title: str
    section: str  # opening / core / close
    annotation: Optional[str] = None


class StartupReport(BaseModel):
    company_name: str
    company_name_local: Optional[str] = None
    total_slides: int
    date: str

    checklist: list[ChecklistItem]
    checklist_summary: ChecklistSummary
    fundraising_readiness: FundraisingReadiness
    issues: list[Issue]
    recommended_structure: list[RecommendedSlide]

    estimated_impact: str
    current_readiness: str
    target_readiness: str


# ── API Response ────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    report_id: str
    report_type: str
    company_name: str
    pdf_url: str
    data: dict  # Full analysis data (investor or startup)
