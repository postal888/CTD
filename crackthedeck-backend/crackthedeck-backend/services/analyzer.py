"""GPT-5.1 pitch deck analysis with two-pass structured extraction.

Pass 1: Extract raw data from slides (facts only, no opinions).
Pass 2: Analyze extracted data and generate investment assessment.

This two-pass approach prevents hallucination by separating
data extraction from evaluation.
"""

import json
import logging
from datetime import datetime

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)


# ── Pass 1: Data Extraction Prompts ─────────────────────────────────

EXTRACTION_SYSTEM = """You are a precise data extraction engine. Your ONLY job is to read pitch deck slides and extract factual information that is EXPLICITLY shown on the slides.

CRITICAL RULES:
- Extract ONLY text, numbers, and data points that are VISUALLY PRESENT on the slides.
- If a data point is NOT on any slide, you MUST return null for that field — NEVER guess or infer.
- For numbers (revenue, valuation, team size, etc.): copy them EXACTLY as shown on the slide.
- Do NOT calculate, estimate, or derive any values that aren't explicitly stated.
- Do NOT use your training data to fill in gaps — treat each deck as a completely unknown company.
- If you see a graph/chart, describe what is shown (axes, values, trends) but do NOT extrapolate.
- For each extracted fact, note which slide number it comes from (approximate if unclear).

LOGO RECOGNITION — VERY IMPORTANT:
- Many slides show company logos instead of (or in addition to) text names — for clients, partners, investors, advisors, and team members' prior employers.
- You MUST carefully examine every logo on every slide and identify the company/organization it represents.
- Common places for logos: client/partner slides, "backed by" or "investors" slides, team slides (previous employers), competition slides, and integration/ecosystem slides.
- If you recognize a logo, include the company name in the relevant field (clients, partners, team background, etc.).
- If a logo is unclear, describe it briefly (e.g., "unidentified logo — blue circle with white text") but still note it exists."""

EXTRACTION_USER = """Examine every slide in this pitch deck carefully. Extract ALL factual data points visible on the slides.

Return a JSON object with this EXACT structure:
{
  "company_name": "string — exact name as shown on slides, or null if not found",
  "company_name_local": "string — local language name if different from English, or null",
  "sector": "string — industry/sector as described in the deck, or null",
  "stage": "string — funding stage if explicitly mentioned (Pre-seed/Seed/Series A/etc), or null",
  "target_raise": "string — exact amount being raised with currency as shown, or null",
  "valuation": "string — exact valuation with currency as stated, or null if not disclosed",
  "total_slides": <SLIDE_COUNT>,

  "slide_data": [
    {
      "slide_num": 1,
      "title": "string — slide title or topic",
      "key_facts": ["string — each individual fact, number, or claim from this slide"]
    }
  ],

  "extracted_metrics": {
    "revenue": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "revenue_growth": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "cagr": {"value": "string or null — the COMPANY's own compound annual growth rate ONLY, NOT market CAGR", "source_slide": "number or null", "exact_quote": "string or null"},
    "mrr": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "arr": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "gross_margin": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "burn_rate": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "runway": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "customers": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "users": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "team_size": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "founded": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "tam": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "sam": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "som": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "ask_amount": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "valuation_claimed": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"},
    "previous_funding": {"value": "string or null", "source_slide": "number or null", "exact_quote": "string or null"}
  },

  "team_members": [
    {"name": "string", "role": "string", "background": "string or null", "source_slide": "number or null"}
  ],

  "competitors_mentioned": ["string — competitor names as listed in the deck, INCLUDING any identified from logos"],

  "clients_and_partners": [
    {"name": "string — company/organization name (from text OR logo recognition)", "type": "client|partner|investor|integration", "source_slide": "number", "identified_from": "text|logo|both"}
  ],

  "team_prior_companies": [
    {"company": "string — company name from text or logo on team/advisor slides", "person": "string or null — which team member", "source_slide": "number", "identified_from": "text|logo|both"}
  ],

  "investors_and_backers": [
    {"name": "string — investor/VC/accelerator name from text or logo", "source_slide": "number", "identified_from": "text|logo|both"}
  ],

  "use_of_funds": "string — exact breakdown if shown, or null",

  "business_model_description": "string — how the company makes money as described in deck, or null",

  "traction_evidence": ["string — each traction data point with exact numbers from slides"],

  "missing_information": ["string — key elements NOT found in the deck (e.g., 'No revenue figures shown', 'No team slide', 'No TAM/SAM/SOM')"]
}

REMEMBER: null is ALWAYS better than a guess. If you're not 100% sure a number appears on a slide, use null."""


# ── Pass 2: Analysis Prompts ────────────────────────────────────────

INVESTOR_ANALYSIS_SYSTEM = """You are CrackTheDeck — an expert investment analyst who evaluates startup pitch decks for professional investors.

You will receive TWO inputs:
1. Raw extracted data from the pitch deck (facts only)
2. The original deck slides for visual reference

CRITICAL RULES:
- Base your ENTIRE analysis on the extracted data. Do NOT invent metrics or facts.
- If extracted_metrics shows null for a field, that data is NOT in the deck — note it as missing, score accordingly.
- Every number you cite in comments MUST come from the extracted data with a source slide reference.
- When data is missing, say "Not disclosed in the deck" — never fill in plausible numbers.
- Your scores should PENALIZE missing critical information (revenue, traction, team details).
- Be specific: instead of "strong traction", say "29 customers with $1.2M ARR as shown on slide 8".
- Focus ONLY on investment merit — never comment on slide design or formatting.
- COMMENT LENGTH: Each criteria comment MUST be 2-3 sentences MAX (~40-60 words). Write a concise executive summary of the key finding, not a detailed description. Highlight the single most important insight and the key evidence. Do NOT list every feature or metric — summarize.
- Pay special attention to clients_and_partners, team_prior_companies, and investors_and_backers from the extracted data.
  * Evaluate the QUALITY and RELEVANCE of named clients/partners — are they enterprise/Fortune 500, well-known brands, or small unknowns?
  * For team backgrounds: note if team members come from strong companies (FAANG, top consulting, domain leaders).
  * For investors/backers: note if the startup has backing from reputable VCs, accelerators, or strategic investors.
  * These signal credibility and should influence Team & Execution, Traction, and Competitive Position scores."""

INVESTOR_ANALYSIS_USER = """Based on the extracted data below and the deck slides, provide your investment analysis.

=== EXTRACTED DATA ===
<EXTRACTED_DATA>
=== END EXTRACTED DATA ===

Now analyze this investment opportunity. Return a JSON object with this EXACT structure:
{
  "company_name": "string — from extracted data",
  "company_name_local": "string or null — from extracted data",
  "sector": "string — from extracted data",
  "stage": "string — from extracted data, or 'Not disclosed' if null",
  "target_raise": "string — from extracted data, or 'Not disclosed'",
  "valuation": "string — from extracted data, or 'Not disclosed'",
  "revenue_multiple": "string — calculate ONLY if both revenue and valuation are in extracted data, otherwise 'N/A — insufficient data'",
  "total_slides": <SLIDE_COUNT>,
  "date": "<CURRENT_DATE>",

  "overall_score": number (0-100),
  "overall_label": "string — one of: STRONG OPPORTUNITY / MODERATE OPPORTUNITY / WEAK OPPORTUNITY / HIGH RISK",
  "overall_summary": "string — MAX 2 short sentences (~30-40 words). Concise investment thesis: what the company does, key strength, key risk. Must fit in 3 lines of text.",

  "criteria": [
    {"name": "Market Opportunity", "score": number_1_to_10, "comment": "2-3 sentences MAX — cite key TAM/SAM/SOM numbers or note missing"},
    {"name": "Product Maturity", "score": number_1_to_10, "comment": "2-3 sentences MAX — key product evidence and maturity level"},
    {"name": "Traction & Revenue", "score": number_1_to_10, "comment": "2-3 sentences MAX — cite key revenue/growth/customer numbers"},
    {"name": "Competitive Position", "score": number_1_to_10, "comment": "2-3 sentences MAX — key competitive advantages or gaps"},
    {"name": "Business Model", "score": number_1_to_10, "comment": "2-3 sentences MAX — revenue model summary and key concern"},
    {"name": "Team & Execution", "score": number_1_to_10, "comment": "2-3 sentences MAX — key team strengths and notable backgrounds"},
    {"name": "Scalability", "score": number_1_to_10, "comment": "2-3 sentences MAX — scalability drivers and constraints"},
    {"name": "Financial Health", "score": number_1_to_10, "comment": "2-3 sentences MAX — financial data availability and key finding"},
    {"name": "Deal Structure", "score": number_1_to_10, "comment": "2-3 sentences MAX — deal terms evaluation"},
    {"name": "Exit Potential", "score": number_1_to_10, "comment": "2-3 sentences MAX — exit pathways and likelihood"}
  ],

  "key_metrics": {
    "revenue": "string — EXACT value from extracted_metrics.revenue, or 'Not disclosed'",
    "revenue_growth": "string — EXACT value from extracted_metrics.revenue_growth, or 'Not disclosed'",
    "cagr": "string — the COMPANY's own CAGR ONLY (NOT market CAGR). If extracted_metrics.cagr is null or contains market CAGR, return 'Not disclosed'",
    "ask": "string — EXACT value from extracted_metrics.ask_amount, or 'Not disclosed'",
    "valuation_claimed": "string — EXACT value from extracted_metrics.valuation_claimed, or 'Not disclosed'",
    "revenue_multiple": "string — calculate ONLY if both values exist, otherwise 'N/A'",
    "team_size": "string — from extracted data, or 'Not disclosed'",
    "founded": "string — from extracted data, or 'Not disclosed'",
    "stage": "string — from extracted data, or 'Not disclosed'"
  },

  "strengths": ["string — max 5, each must reference specific data from the deck with slide reference"],
  "risks": ["string — max 5, including risks from MISSING information"]
}

SCORING RULES:
- overall_score = weighted average of criteria scores × 10 (round to nearest integer)
- If critical data is missing (revenue, traction, team), those criteria score ≤ 4
- If the deck has strong verifiable data points, score higher
- A deck that claims numbers without evidence should be noted as a risk
- 'Not disclosed' fields should be cited exactly — do not rephrase or paraphrase"""


STARTUP_ANALYSIS_SYSTEM = """You are CrackTheDeck — an expert pitch deck advisor who helps startup founders improve their fundraising materials.

You will receive TWO inputs:
1. Raw extracted data from the pitch deck (facts only)
2. The original deck slides for visual reference

CRITICAL RULES:
- Base analysis on extracted data. What's missing from the deck IS the main feedback.
- Reference specific slide numbers for every piece of feedback.
- When something is missing, explain WHY it matters and WHAT to add.
- Be constructive but brutally specific — not generic advice.
- Evaluate the quality of clients, partners, investors, and team backgrounds identified from both text AND logos in the extracted data."""

STARTUP_ANALYSIS_USER = """Based on the extracted data below and the deck slides, provide your founder review.

=== EXTRACTED DATA ===
<EXTRACTED_DATA>
=== END EXTRACTED DATA ===

Return a JSON object with this EXACT structure:
{
  "company_name": "string",
  "company_name_local": "string or null",
  "total_slides": <SLIDE_COUNT>,
  "date": "<CURRENT_DATE>",

  "checklist": [
    {"element": "Problem Statement", "status": "strong|weak|missing", "notes": "string — specific feedback with slide reference"},
    {"element": "Solution / Product", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Market Size (TAM/SAM/SOM)", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Traction / Revenue", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Business Model", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Competition", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Team", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Case Studies", "status": "strong|weak|missing|n/a", "notes": "string"},
    {"element": "Financial Projections", "status": "strong|weak|missing", "notes": "string"},
    {"element": "The Ask (amount + terms)", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Use of Funds", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Valuation Basis", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Exit Strategy", "status": "strong|weak|missing", "notes": "string"},
    {"element": "Risk Factors", "status": "strong|weak|missing", "notes": "string"}
  ],

  "checklist_summary": {"total": 14, "strong": number, "weak": number, "missing": number},

  "fundraising_readiness": {
    "level": "HIGH|MEDIUM|LOW",
    "summary": "string — 1-2 sentences based on extracted data",
    "completeness_pct": number_0_to_100,
    "completeness_note": "string — what's present vs missing",
    "structure_pct": number_0_to_100,
    "structure_note": "string — flow and organization feedback",
    "strength_pct": number_0_to_100,
    "strength_note": "string — quality of evidence and data"
  },

  "issues": [
    {"rank": 1, "severity": "CRITICAL|HIGH|MEDIUM", "description": "string — specific actionable issue with slide reference"}
  ],

  "recommended_structure": [
    {"slide_number": 1, "title": "string", "section": "opening|core|close", "annotation": "string or null"}
  ],

  "estimated_impact": "string — e.g. '+15-20 points on deck score'",
  "current_readiness": "HIGH|MEDIUM|LOW",
  "target_readiness": "HIGH|MEDIUM|LOW"
}

RULES:
- issues array must have exactly 10 items, ordered by severity (CRITICAL first)
- recommended_structure should be 12-18 slides
- Every issue MUST reference a specific slide or missing element
- Use extracted data to justify every rating"""


# ── Analysis Functions ──────────────────────────────────────────────

def _call_gpt(client, model, system_prompt, user_content, max_completion_tokens=8192, temperature=0.2):
    """Call GPT with given prompts and return parsed JSON."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
    )
    raw = response.choices[0].message.content
    logger.info(f"GPT response length: {len(raw)} chars, model: {model}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GPT JSON: {e}")
        logger.error(f"Raw response: {raw[:1000]}")
        raise ValueError(f"GPT returned invalid JSON: {e}")


def analyze_deck(
    base64_images: list[str],
    slide_count: int,
    report_type: str,
) -> dict:
    """Analyze pitch deck images with GPT-5.1 using two-pass approach.

    Pass 1: Extract all factual data from slides (no opinions).
    Pass 2: Analyze extracted data to produce investment/founder report.

    Args:
        base64_images: List of base64-encoded PNG images (one per slide).
        slide_count: Total number of slides.
        report_type: 'investor' or 'startup'.

    Returns:
        Parsed JSON dict with analysis results.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)
    model = OPENAI_MODEL
    current_date = datetime.now().strftime("%B %Y")

    # ── Pass 1: Extract raw data ──
    logger.info(f"[Pass 1] Extracting data from {len(base64_images)} slides with {model}")

    extraction_text = EXTRACTION_USER.replace("<SLIDE_COUNT>", str(slide_count))

    extraction_content = [{"type": "text", "text": extraction_text}]
    for i, b64 in enumerate(base64_images):
        extraction_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })

    extracted_data = _call_gpt(
        client, model, EXTRACTION_SYSTEM, extraction_content,
        max_completion_tokens=12288, temperature=0.1,
    )

    logger.info(f"[Pass 1] Extracted data: {len(json.dumps(extracted_data))} chars")
    logger.info(f"[Pass 1] Missing info: {extracted_data.get('missing_information', [])}")

    # ── Pass 2: Analyze extracted data ──
    logger.info(f"[Pass 2] Analyzing extracted data ({report_type} report)")

    extracted_json_str = json.dumps(extracted_data, indent=2, ensure_ascii=False)

    if report_type == "investor":
        analysis_system = INVESTOR_ANALYSIS_SYSTEM
        analysis_user_template = INVESTOR_ANALYSIS_USER
    else:
        analysis_system = STARTUP_ANALYSIS_SYSTEM
        analysis_user_template = STARTUP_ANALYSIS_USER

    analysis_text = (
        analysis_user_template
        .replace("<EXTRACTED_DATA>", extracted_json_str)
        .replace("<SLIDE_COUNT>", str(slide_count))
        .replace("<CURRENT_DATE>", current_date)
    )

    # Pass 2 also gets images for visual reference (but extracted data is primary)
    analysis_content = [{"type": "text", "text": analysis_text}]
    for i, b64 in enumerate(base64_images):
        analysis_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "low",  # low detail in pass 2 — just for reference
            },
        })

    analysis_data = _call_gpt(
        client, model, analysis_system, analysis_content,
        max_completion_tokens=8192, temperature=0.3,
    )

    logger.info(f"[Pass 2] Analysis complete: score={analysis_data.get('overall_score', 'N/A')}")

    # Attach extraction metadata for debugging/transparency
    analysis_data["_extraction"] = {
        "missing_information": extracted_data.get("missing_information", []),
        "slides_analyzed": len(base64_images),
        "total_slides": slide_count,
        "model": model,
        "method": "two-pass-extraction",
    }

    return analysis_data
