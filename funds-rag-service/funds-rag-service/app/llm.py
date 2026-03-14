"""
GPT-4o calls for:
1. Extracting startup parameters from pitch text
2. Generating fund match recommendations

All heavy lifting is on OpenAI side — zero GPU load on server.
"""
import json
import re
from typing import List

import openai

from app.config import settings
from app.schemas import StartupProfile, FundResult, FundRecommendation

client = openai.OpenAI(api_key=settings.openai_api_key)


# ───────────── Extract startup profile from pitch ─────────────


EXTRACT_SYSTEM = """You are an expert startup analyst. 
Given raw text from a pitch deck, extract the following parameters as JSON:
- company_name: company name
- industry: primary industry (fintech, healthtech, edtech, SaaS, AI, etc.)
- sub_industry: more specific vertical
- stage: funding stage (pre-seed, seed, Series A, Series B, growth, etc.)
- business_model: business model type (B2B SaaS, marketplace, D2C, platform, etc.)
- geography: where the company operates or is headquartered
- target_raise: how much they are raising (e.g. "$2M", "€5M")
- description: one-sentence summary of what the company does

Return ONLY valid JSON, no markdown, no extra text.
If a field cannot be determined, use null."""


def extract_startup_profile(pitch_text: str) -> StartupProfile:
    """Extract startup parameters from pitch deck text using GPT-4o."""
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.1,
        max_tokens=500,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": pitch_text[:15000]},  # limit to ~15k chars
        ],
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown code block if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    data = json.loads(raw)
    return StartupProfile(**data)


# ───────────── Generate fund match recommendations ─────────────


def _build_recommendation_prompt(
    startup: StartupProfile,
    funds: List[FundResult],
    language: str,
) -> str:
    """Build the prompt for GPT-4o to generate fund recommendations."""

    lang_instruction = {
        "en": "Respond in English.",
        "ru": "Отвечай на русском языке.",
        "pt": "Responda em português.",
    }.get(language, "Respond in English.")

    fund_descriptions = []
    for i, f in enumerate(funds, 1):
        parts = [f"#{i} {f.investor_name} (similarity: {f.similarity:.2f})"]
        if f.country:
            parts.append(f"  Country: {f.country}")
        if f.overview:
            parts.append(f"  Overview: {f.overview}")
        if f.business_models:
            parts.append(f"  Models: {f.business_models}")
        if f.description:
            parts.append(f"  Description: {f.description[:300]}")
        if f.website:
            parts.append(f"  Website: {f.website}")
        fund_descriptions.append("\n".join(parts))

    startup_info = []
    if startup.company_name:
        startup_info.append(f"Company: {startup.company_name}")
    if startup.industry:
        startup_info.append(f"Industry: {startup.industry}")
    if startup.sub_industry:
        startup_info.append(f"Sub-industry: {startup.sub_industry}")
    if startup.stage:
        startup_info.append(f"Stage: {startup.stage}")
    if startup.business_model:
        startup_info.append(f"Business model: {startup.business_model}")
    if startup.geography:
        startup_info.append(f"Geography: {startup.geography}")
    if startup.target_raise:
        startup_info.append(f"Raising: {startup.target_raise}")
    if startup.description:
        startup_info.append(f"Description: {startup.description}")

    return f"""You are a venture capital matchmaking expert. 
{lang_instruction}

STARTUP PROFILE:
{chr(10).join(startup_info)}

CANDIDATE FUNDS (ranked by semantic similarity):
{chr(10).join(fund_descriptions)}

TASK:
1. For each fund, write a short "reasoning" (1-2 sentences) explaining why it's a good or mediocre fit for this startup.
2. Rank them by actual fit (not just similarity score). Consider: industry match, stage fit, geographic relevance, business model alignment.
3. Write a "summary" — 2-3 sentence actionable overview for the founder.

Return ONLY valid JSON in this exact format:
{{
  "recommendations": [
    {{
      "investor_name": "...",
      "reasoning": "..."
    }}
  ],
  "summary": "..."
}}

Order recommendations from best fit to worst. Include ALL {len(funds)} funds."""


def _repair_recommendation_json(raw: str, funds: List[FundResult], parse_error: json.JSONDecodeError) -> dict:
    """On truncated/malformed JSON, return a fallback so the API still returns fund list."""
    repaired = raw.strip()
    # Find end of last complete recommendation object
    i1, i2, i3 = repaired.rfind('"},\n'), repaired.rfind('"},'), repaired.rfind('}\n    }')
    end = max(
        (i1 + 4) if i1 >= 0 else -1,
        (i2 + 3) if i2 >= 0 else -1,
        (i3 + 6) if i3 >= 0 else -1,
    )
    if end > 0:
        repaired = repaired[:end].rstrip().rstrip(",")
        if not repaired.endswith("]"):
            repaired += '\n  ], "summary": "Part of the recommendations were truncated."}'
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
    # Fallback: original order, no GPT reasoning
    return {
        "recommendations": [
            {"investor_name": f.investor_name, "reasoning": "(Recommendation text was truncated.)"}
            for f in funds
        ],
        "summary": "Fund list is shown in similarity order. Detailed recommendations were truncated.",
    }


def generate_recommendations(
    startup: StartupProfile,
    funds: List[FundResult],
    language: str = "en",
) -> dict:
    """Call GPT-4o to generate fund recommendations."""
    prompt = _build_recommendation_prompt(startup, funds, language)

    # Enough tokens for 100+ funds (investor_name + reasoning each) + summary
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=16000,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Truncated or malformed JSON (e.g. unclosed string) — repair or fallback
        return _repair_recommendation_json(raw, funds, e)
