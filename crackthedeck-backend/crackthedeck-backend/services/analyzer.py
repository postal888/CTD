"""GPT-4o pitch deck analysis with structured prompts."""

import json
import logging
from datetime import datetime

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)


# ── System Prompts ──────────────────────────────────────────────────

INVESTOR_SYSTEM_PROMPT = """You are CrackTheDeck — an expert investment analyst who evaluates startup pitch decks for professional investors. You analyze decks purely from an investment perspective: market opportunity, traction quality, team capability, deal structure, and exit potential. You do NOT comment on presentation design, slide count, or formatting — investors don't care about that. You care about whether this is a good investment.

You must respond with a single JSON object matching the exact schema provided. Be specific with data points — cite exact numbers from the slides. Be brutally honest in your assessment."""

STARTUP_SYSTEM_PROMPT = """You are CrackTheDeck — an expert pitch deck advisor who helps startup founders improve their fundraising materials. You evaluate decks on three axes:
1. COMPLETENESS — does the deck contain all elements investors expect?
2. STRUCTURE — is the narrative well-organized, is key info in the right place?
3. STRENGTH — is the underlying business/product strong enough to raise successfully?

You must respond with a single JSON object matching the exact schema provided. Be specific — cite exact slide numbers and data points. Be constructive but honest."""


# ── User Prompts ────────────────────────────────────────────────────

INVESTOR_USER_PROMPT = """Analyze this pitch deck for an investor. Extract all data and evaluate the investment opportunity.

Return a JSON object with this EXACT structure:
{
  "company_name": "string — company name as shown in deck",
  "company_name_local": "string or null — local language name if different",
  "sector": "string — industry/sector",
  "stage": "string — funding stage (Pre-seed/Seed/Series A/etc or 'First raise')",
  "target_raise": "string — amount being raised with currency",
  "valuation": "string — stated valuation with currency, or 'Not disclosed'",
  "revenue_multiple": "string — valuation/revenue multiple, or 'N/A'",
  "total_slides": <SLIDE_COUNT>,
  "date": "<CURRENT_DATE>",

  "overall_score": number (0-100),
  "overall_label": "string — one of: STRONG OPPORTUNITY / MODERATE OPPORTUNITY / WEAK OPPORTUNITY / HIGH RISK",
  "overall_summary": "string — 1-2 sentence investment thesis summary",

  "criteria": [
    {"name": "Market Opportunity", "score": number_1_to_10, "comment": "string — 1 sentence with specific data from deck"},
    {"name": "Product Maturity", "score": number_1_to_10, "comment": "string"},
    {"name": "Traction & Revenue", "score": number_1_to_10, "comment": "string"},
    {"name": "Competitive Position", "score": number_1_to_10, "comment": "string"},
    {"name": "Business Model", "score": number_1_to_10, "comment": "string"},
    {"name": "Team & Execution", "score": number_1_to_10, "comment": "string"},
    {"name": "Scalability", "score": number_1_to_10, "comment": "string"},
    {"name": "Financial Health", "score": number_1_to_10, "comment": "string"},
    {"name": "Deal Structure", "score": number_1_to_10, "comment": "string"},
    {"name": "Exit Potential", "score": number_1_to_10, "comment": "string"}
  ],

  "key_metrics": {
    "revenue": "string or null",
    "revenue_growth": "string or null",
    "cagr": "string or null",
    "ask": "string or null",
    "valuation_claimed": "string or null",
    "revenue_multiple": "string or null",
    "team_size": "string or null",
    "founded": "string or null",
    "stage": "string or null"
  },

  "strengths": ["string — max 5, investment-focused, each 1 sentence"],
  "risks": ["string — max 5, investment-focused, each 1 sentence"]
}

RULES:
- overall_score = average of all 10 criteria scores × 10
- Focus ONLY on investment merit — never comment on slide design, deck length, or formatting
- Every comment must reference specific data from the slides
- If data is missing from the deck, score that criterion lower and note what's missing
- Strengths and risks should be about the BUSINESS, not the presentation"""


STARTUP_USER_PROMPT = """Analyze this pitch deck for the founder. Evaluate completeness, structure, and fundraising strength.

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
    "summary": "string — 1-2 sentences explaining the level",
    "completeness_pct": number_0_to_100,
    "completeness_note": "string — brief explanation",
    "structure_pct": number_0_to_100,
    "structure_note": "string — brief explanation",
    "strength_pct": number_0_to_100,
    "strength_note": "string — brief explanation"
  },

  "issues": [
    {"rank": 1, "severity": "CRITICAL|HIGH|MEDIUM", "description": "string — specific actionable issue"}
  ],

  "recommended_structure": [
    {"slide_number": 1, "title": "string", "section": "opening|core|close", "annotation": "string or null"}
  ],

  "estimated_impact": "string — e.g. '+15-20 points on deck score'",
  "current_readiness": "HIGH|MEDIUM|LOW",
  "target_readiness": "HIGH|MEDIUM|LOW"
}

RULES:
- issues array must have exactly 10 items, ordered by severity (CRITICAL first, then HIGH, then MEDIUM)
- recommended_structure should be a realistic 12-18 slide structure
- Be specific about what's wrong and how to fix it — not generic advice
- Reference specific slide numbers when relevant"""


# ── Analysis Function ───────────────────────────────────────────────

def analyze_deck(
    base64_images: list[str],
    slide_count: int,
    report_type: str,
) -> dict:
    """Analyze pitch deck images with GPT-4o.

    Args:
        base64_images: List of base64-encoded PNG images (one per slide).
        slide_count: Total number of slides.
        report_type: 'investor' or 'startup'.

    Returns:
        Parsed JSON dict with analysis results.
    """
    # Select prompts
    if report_type == "investor":
        system_prompt = INVESTOR_SYSTEM_PROMPT
        user_text = INVESTOR_USER_PROMPT
    else:
        system_prompt = STARTUP_SYSTEM_PROMPT
        user_text = STARTUP_USER_PROMPT

    # Inject dynamic values
    current_date = datetime.now().strftime("%B %Y")
    user_text = user_text.replace("<SLIDE_COUNT>", str(slide_count))
    user_text = user_text.replace("<CURRENT_DATE>", current_date)

    # Build messages with images
    content_parts = [{"type": "text", "text": user_text}]
    for i, b64 in enumerate(base64_images):
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })

    client = OpenAI(api_key=OPENAI_API_KEY)

    logger.info(f"Sending {len(base64_images)} slides to GPT-4o ({report_type} analysis)")

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content
    logger.info(f"GPT-4o response length: {len(raw)} chars")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GPT-4o JSON: {e}")
        logger.error(f"Raw response: {raw[:500]}")
        raise ValueError(f"GPT-4o returned invalid JSON: {e}")

    return data
