"""
Normalize stages and parse check size from JSONL → DB (hard filters).
"""
import re
from typing import Tuple, List, Optional

# Canonical stages for hard filter (lowercase, hyphenated)
CANONICAL_STAGES = {"pre-seed", "seed", "series-a", "series-b", "growth"}

# Map JSONL / free text variants → canonical
STAGE_ALIASES = {
    "pre-seed": "pre-seed",
    "preseed": "pre-seed",
    "pre seed": "pre-seed",
    "seed": "seed",
    "early-stage": "seed",
    "early stage": "seed",
    "early": "seed",
    "series a": "series-a",
    "series-a": "series-a",
    "series a": "series-a",
    "middle-stage": "series-a",
    "middle stage": "series-a",
    "series b": "series-b",
    "series-b": "series-b",
    "later-stage": "series-b",
    "later stage": "series-b",
    "growth": "growth",
    "pre-ipo": "growth",
    "pre ipo": "growth",
    "m&a": "growth",
    "ma": "growth",
    "late": "series-b",
}


def normalize_stages(stages_str: Optional[str]) -> List[str]:
    """
    Parse 'stages' string from JSONL → list of canonical stage strings.
    E.g. "seed, early-stage, Series A" → ["seed", "series-a"]
    """
    if not stages_str or not isinstance(stages_str, str):
        return []
    seen = set()
    result = []
    # Split by comma, semicolon, " and " — keep "Series A" etc. as one token
    parts = re.split(r"\s*[,;]\s*|\s+and\s+", stages_str, flags=re.IGNORECASE)
    for p in parts:
        p = p.strip().lower().replace(" ", "-")
        if not p or len(p) < 2:
            continue
        canonical = STAGE_ALIASES.get(p)
        if not canonical:
            # Try exact match in CANONICAL_STAGES
            if p in CANONICAL_STAGES:
                canonical = p
            else:
                # Fuzzy: "seriesa" -> series-a
                if "series" in p and "a" in p:
                    canonical = "series-a"
                elif "series" in p and "b" in p:
                    canonical = "series-b"
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def normalize_stage_single(stage_str: Optional[str]) -> Optional[str]:
    """Normalize a single startup stage (from match request) to canonical form."""
    if not stage_str:
        return None
    stages = normalize_stages(stage_str)
    return stages[0] if stages else None


# Approximate rates to USD (for check size parsing)
_JPY_TO_USD = 0.0067   # ~150 JPY per USD
_EUR_TO_USD = 1.08
_GBP_TO_USD = 1.27


def _parse_amount(s: str) -> Tuple[Optional[float], Optional[str]]:
    """Parse one amount like '200K', '$2.5M', '¥100M'. Returns (value, unit) or (None, None)."""
    s = s.strip()
    if not s:
        return None, None
    # Currency
    mult = 1.0
    if s.startswith("$"):
        s = s[1:].strip()
    elif s.startswith("¥") or s.startswith("JPY"):
        s = s.lstrip("¥JPY").strip()
        mult = _JPY_TO_USD
    elif s.startswith("€") or s.startswith("EUR"):
        s = s.lstrip("€EUR").strip()
        mult = _EUR_TO_USD
    elif s.startswith("£") or s.startswith("GBP"):
        s = s.lstrip("£GBP").strip()
        mult = _GBP_TO_USD
    # Number + K/M/B
    m = re.match(r"^([\d,.]+)\s*([KMB])?\s*$", s, re.IGNORECASE)
    if not m:
        return None, None
    try:
        num_str = m.group(1).replace(",", "")
        val = float(num_str)
    except ValueError:
        return None, None
    unit = (m.group(2) or "").upper()
    if unit == "K":
        val *= 1_000
    elif unit == "M":
        val *= 1_000_000
    elif unit == "B":
        val *= 1_000_000_000
    return val * mult, "USD"


def parse_check_size_to_usd(check_size_str: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse check_size string from JSONL → (check_min_usd, check_max_usd).
    E.g. "$200K-$2.5M" → (200_000, 2_500_000), "¥50M-¥100M" → (335_000, 670_000).
    Returns (None, None) if not parseable.
    """
    if not check_size_str or not isinstance(check_size_str, str):
        return None, None
    check_size_str = check_size_str.strip()
    if not check_size_str or "not publicly specified" in check_size_str.lower() or "not specified" in check_size_str.lower():
        return None, None
    # Take first segment that looks like a range (number-number or number to number)
    range_match = re.search(
        r"([$¥€£]?\s*[\d,.]+[KMB]?\s*)\s*[-–—to]+\s*([$¥€£]?\s*[\d,.]+[KMB]?)",
        check_size_str,
        re.IGNORECASE,
    )
    if not range_match:
        # Single amount?
        single = re.search(r"[$¥€£]?\s*[\d,.]+[KMB]?\s*", check_size_str)
        if single:
            val, _ = _parse_amount(single.group(0))
            if val is not None:
                return val, val
        return None, None
    low, _ = _parse_amount(range_match.group(1))
    high, _ = _parse_amount(range_match.group(2))
    if low is not None and high is not None:
        return min(low, high), max(low, high)
    return None, None


def parse_raise_to_usd(raise_str: Optional[str]) -> Optional[float]:
    """
    Parse startup target_raise (e.g. '$2M', '500K') → single USD value for filter.
    """
    if not raise_str or not isinstance(raise_str, str):
        return None
    raise_str = raise_str.strip()
    if not raise_str:
        return None
    val, _ = _parse_amount(raise_str)
    return val
