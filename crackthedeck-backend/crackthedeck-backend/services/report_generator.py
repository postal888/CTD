"""PDF report generation with ReportLab canvas API.

Generates two report types with cyberpunk/dark theme:
- Investor Report (3 pages)
- Startup/Founder Report (4 pages)
"""

import math
import logging
from pathlib import Path

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from config import REPORTS_DIR
from utils.fonts import download_fonts, get_font

logger = logging.getLogger(__name__)

# ── Design Tokens ───────────────────────────────────────────────────

W, H = landscape(A4)  # 842 x 595

BG = HexColor("#0F0F1A")
SURFACE = HexColor("#1A1A2E")
GREEN = HexColor("#00FF88")
CYAN = HexColor("#00BBFF")
GOLD = HexColor("#FFD700")
RED = HexColor("#FF4466")
WHITE = HexColor("#E0E0E0")
MUTED = HexColor("#888888")
DARK_MUTED = HexColor("#555555")

MARGIN = 50
INNER_W = W - 2 * MARGIN


# ── Helpers ─────────────────────────────────────────────────────────

def _bg(c: canvas.Canvas):
    """Fill page with dark background."""
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def _footer(c: canvas.Canvas, report_label: str):
    """Draw footer on every page."""
    c.setFont(get_font("heading-regular"), 7)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 20, "CrackTheDeck // crackthedeck.com")
    c.drawRightString(W - MARGIN, 20, f"Confidential — {report_label}")


def _corner_brackets(c: canvas.Canvas, size: int = 30, inset: int = 30):
    """Draw decorative corner brackets."""
    c.setStrokeColor(GREEN)
    c.setLineWidth(2)
    # Top-left
    c.line(inset, H - inset, inset + size, H - inset)
    c.line(inset, H - inset, inset, H - inset - size)
    # Top-right
    c.line(W - inset, H - inset, W - inset - size, H - inset)
    c.line(W - inset, H - inset, W - inset, H - inset - size)
    # Bottom-left
    c.line(inset, inset, inset + size, inset)
    c.line(inset, inset, inset, inset + size)
    # Bottom-right
    c.line(W - inset, inset, W - inset - size, inset)
    c.line(W - inset, inset, W - inset, inset + size)


def _draw_arc(c: canvas.Canvas, cx: float, cy: float, r: float,
              pct: float, color, label: str, note: str):
    """Draw a percentage arc chart with label below."""
    # Background arc
    c.setStrokeColor(HexColor("#2A2A3E"))
    c.setLineWidth(8)
    c.arc(cx - r, cy - r, cx + r, cy + r, 0, 360)

    # Foreground arc
    c.setStrokeColor(color)
    c.setLineWidth(8)
    angle = pct / 100 * 360
    c.arc(cx - r, cy - r, cx + r, cy + r, 90, -angle)

    # Percentage text
    c.setFillColor(WHITE)
    c.setFont(get_font("body-bold"), 18)
    c.drawCentredString(cx, cy - 6, f"{pct}%")

    # Label
    c.setFont(get_font("body-bold"), 10)
    c.setFillColor(WHITE)
    c.drawCentredString(cx, cy - r - 22, label)

    # Note
    c.setFont(get_font("body"), 7)
    c.setFillColor(MUTED)
    # Wrap note to ~25 chars per line
    words = note.split()
    lines = []
    line = ""
    for w in words:
        if len(line) + len(w) + 1 > 30:
            lines.append(line.strip())
            line = w + " "
        else:
            line += w + " "
    if line.strip():
        lines.append(line.strip())
    for i, ln in enumerate(lines[:3]):
        c.drawCentredString(cx, cy - r - 35 - i * 10, ln)


def _score_color(score: int, max_score: int = 10):
    """Return color based on score threshold."""
    if score >= max_score * 0.7:
        return GREEN
    elif score >= max_score * 0.5:
        return GOLD
    return RED


def _severity_color(severity: str):
    """Return badge color for issue severity."""
    return {"CRITICAL": RED, "HIGH": GOLD, "MEDIUM": CYAN}.get(severity, MUTED)


def _section_color(section: str):
    """Return color for deck section."""
    return {"opening": GREEN, "core": CYAN, "close": GOLD}.get(section, MUTED)


# ── Investor Report ─────────────────────────────────────────────────

def generate_investor_pdf(data: dict, report_id: str) -> Path:
    """Generate 3-page Investor Intelligence Report PDF."""
    download_fonts()
    pdf_path = REPORTS_DIR / f"{report_id}_investor.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=landscape(A4))
    c.setTitle(f"CrackTheDeck Investor Report — {data.get('company_name', 'Unknown')}")
    c.setAuthor("Perplexity Computer")

    _investor_cover(c, data)
    c.showPage()
    _investor_analysis(c, data)
    c.showPage()
    _investor_metrics(c, data)
    c.showPage()

    c.save()
    logger.info(f"Generated investor PDF: {pdf_path}")
    return pdf_path


def _investor_cover(c: canvas.Canvas, data: dict):
    _bg(c)
    _corner_brackets(c)

    # Title
    y = H - 160
    c.setFont(get_font("heading"), 48)
    c.setFillColor(GREEN)
    c.drawCentredString(W / 2, y, "CRACKTHEDECK")

    y -= 40
    c.setFont(get_font("heading-regular"), 16)
    c.setFillColor(CYAN)
    c.drawCentredString(W / 2, y, "INVESTOR INTELLIGENCE REPORT")

    # Decorative line
    y -= 15
    c.setStrokeColor(GREEN)
    c.setLineWidth(1)
    c.line(W / 2 - 120, y, W / 2 + 120, y)

    # Decorative dots
    y -= 15
    c.setFillColor(GREEN)
    for i in range(5):
        c.circle(W / 2 - 20 + i * 10, y, 2, fill=1, stroke=0)

    # Company name
    y -= 30
    c.setFont(get_font("body-bold"), 22)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, y, data.get("company_name", ""))

    if data.get("company_name_local"):
        y -= 22
        c.setFont(get_font("body"), 14)
        c.setFillColor(MUTED)
        c.drawCentredString(W / 2, y, f"({data['company_name_local']})")

    # Date box
    y -= 40
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.5)
    c.rect(W / 2 - 80, y - 5, 160, 25, fill=0, stroke=1)
    c.setFont(get_font("body"), 12)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, y + 3, data.get("date", ""))

    # Terminal lines
    y -= 50
    c.setFont(get_font("heading-regular"), 11)
    c.setFillColor(GREEN)
    c.drawCentredString(W / 2, y, f"> {data.get('total_slides', 0)} slides scanned")
    y -= 18
    c.drawCentredString(W / 2, y, "> generating report_")

    # Bottom tagline
    c.setFont(get_font("body"), 10)
    c.setFillColor(MUTED)
    c.drawCentredString(W / 2, 55, "AI-Powered Pitch Deck Analysis")

    _footer(c, "Investor Report")


def _investor_analysis(c: canvas.Canvas, data: dict):
    _bg(c)

    # Title
    c.setFont(get_font("heading"), 16)
    c.setFillColor(GREEN)
    c.drawString(MARGIN, H - 45, f"INVESTMENT ANALYSIS // {data.get('company_name', '').upper()}")

    # Divider
    c.setStrokeColor(GREEN)
    c.setLineWidth(1)
    c.line(MARGIN, H - 52, W - MARGIN, H - 52)

    # Score box
    score = data.get("overall_score", 0)
    box_y = H - 175
    c.setFillColor(SURFACE)
    c.roundRect(MARGIN, box_y, 200, 115, 8, fill=1, stroke=0)

    # Score arc
    arc_cx = MARGIN + 80
    arc_cy = box_y + 60
    arc_r = 40
    c.setStrokeColor(HexColor("#2A2A3E"))
    c.setLineWidth(8)
    c.arc(arc_cx - arc_r, arc_cy - arc_r, arc_cx + arc_r, arc_cy + arc_r, 0, 360)
    c.setStrokeColor(GOLD)
    c.setLineWidth(8)
    c.arc(arc_cx - arc_r, arc_cy - arc_r, arc_cx + arc_r, arc_cy + arc_r, 90, -score / 100 * 360)

    c.setFont(get_font("body-bold"), 32)
    c.setFillColor(WHITE)
    c.drawCentredString(arc_cx, arc_cy - 10, str(score))
    c.setFont(get_font("body"), 12)
    c.setFillColor(MUTED)
    c.drawCentredString(arc_cx, arc_cy - 28, "/100")

    c.setFont(get_font("heading-regular"), 8)
    c.setFillColor(CYAN)
    c.drawCentredString(arc_cx, box_y + 108, "OVERALL SCORE")

    # Label + summary
    summary_x = MARGIN + 220
    c.setFillColor(SURFACE)
    c.roundRect(summary_x, box_y, INNER_W - 220, 115, 8, fill=1, stroke=0)

    c.setFont(get_font("heading"), 14)
    c.setFillColor(GREEN)
    c.drawString(summary_x + 15, box_y + 88, data.get("overall_label", ""))

    c.setFont(get_font("body"), 10)
    c.setFillColor(WHITE)
    summary_text = data.get("overall_summary", "")
    # Simple word wrap
    words = summary_text.split()
    lines = []
    line = ""
    for w in words:
        test = line + " " + w if line else w
        if c.stringWidth(test, get_font("body"), 10) > INNER_W - 260:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    for i, ln in enumerate(lines[:3]):
        c.drawString(summary_x + 15, box_y + 65 - i * 14, ln)

    # Deal metrics strip
    metrics_y = box_y - 5
    c.setFont(get_font("heading-regular"), 8)
    c.setFillColor(MUTED)
    strip_parts = [
        f"TARGET: {data.get('target_raise', 'N/A')}",
        f"VALUATION: {data.get('valuation', 'N/A')}",
        f"MULTIPLE: {data.get('revenue_multiple', 'N/A')}",
        f"STAGE: {data.get('stage', 'N/A')}",
    ]
    strip_text = "  |  ".join(strip_parts)
    c.drawCentredString(W / 2, metrics_y, strip_text)

    # 10 criteria in 2x5 grid
    criteria = data.get("criteria", [])
    card_w = (INNER_W - 20) / 2
    card_h = 62
    start_y = metrics_y - 20

    for i, crit in enumerate(criteria[:10]):
        col = i % 2
        row = i // 2
        x = MARGIN + col * (card_w + 20)
        y = start_y - row * (card_h + 6)

        # Card background
        c.setFillColor(SURFACE)
        c.roundRect(x, y - card_h + 10, card_w, card_h, 5, fill=1, stroke=0)

        sc = crit.get("score", 0)
        color = _score_color(sc)

        # Name
        c.setFont(get_font("body-semi"), 10)
        c.setFillColor(CYAN)
        c.drawString(x + 10, y - 5, crit.get("name", ""))

        # Score
        c.setFont(get_font("body-bold"), 12)
        c.setFillColor(color)
        c.drawRightString(x + card_w - 10, y - 5, f"{sc}/10")

        # Progress bar
        bar_y = y - 20
        bar_w = card_w - 20
        c.setFillColor(HexColor("#2A2A3E"))
        c.roundRect(x + 10, bar_y, bar_w, 5, 2, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(x + 10, bar_y, bar_w * sc / 10, 5, 2, fill=1, stroke=0)

        # Comment (truncate if needed)
        comment = crit.get("comment", "")
        c.setFont(get_font("body"), 7)
        c.setFillColor(MUTED)
        max_w = card_w - 20
        while c.stringWidth(comment, get_font("body"), 7) > max_w and len(comment) > 10:
            comment = comment[:-4] + "..."
        c.drawString(x + 10, bar_y - 14, comment)

    _footer(c, "Investor Report")


def _investor_metrics(c: canvas.Canvas, data: dict):
    _bg(c)

    # Title
    c.setFont(get_font("heading"), 16)
    c.setFillColor(GREEN)
    c.drawString(MARGIN, H - 45, f"KEY METRICS & INVESTMENT THESIS // {data.get('company_name', '').upper()}")

    c.setStrokeColor(GREEN)
    c.setLineWidth(1)
    c.line(MARGIN, H - 52, W - MARGIN, H - 52)

    # Left column: Key Metrics
    km = data.get("key_metrics", {})
    metrics_items = [
        ("Revenue", km.get("revenue")),
        ("Revenue Growth", km.get("revenue_growth")),
        ("CAGR (3yr)", km.get("cagr")),
        ("Ask", km.get("ask")),
        ("Pre-money Valuation", km.get("valuation_claimed")),
        ("Revenue Multiple", km.get("revenue_multiple")),
        ("Team Size", km.get("team_size")),
        ("Founded", km.get("founded")),
        ("Stage", km.get("stage")),
    ]

    col_w = 280
    x = MARGIN
    y_start = H - 70

    # Metrics box
    c.setStrokeColor(CYAN)
    c.setLineWidth(1)
    c.roundRect(x, 40, col_w, y_start - 30, 8, fill=0, stroke=1)

    c.setFont(get_font("heading-regular"), 10)
    c.setFillColor(CYAN)
    c.drawString(x + 15, y_start - 15, "KEY METRICS")

    y = y_start - 40
    for label, value in metrics_items:
        if value:
            c.setFont(get_font("body"), 8)
            c.setFillColor(MUTED)
            c.drawString(x + 15, y, label)
            c.setFont(get_font("body-bold"), 14)
            c.setFillColor(WHITE)
            c.drawString(x + 15, y - 18, str(value))
            y -= 52

    # Right column: Strengths + Risks
    rx = MARGIN + col_w + 25
    rw = INNER_W - col_w - 25

    # Strengths box
    strengths = data.get("strengths", [])
    sh = 25 + len(strengths) * 22
    sy = y_start - 5

    c.setStrokeColor(GREEN)
    c.setLineWidth(1)
    c.roundRect(rx, sy - sh, rw, sh, 8, fill=0, stroke=1)

    c.setFont(get_font("heading-regular"), 10)
    c.setFillColor(GREEN)
    c.drawString(rx + 15, sy - 18, "INVESTMENT STRENGTHS")

    c.setFont(get_font("body"), 8)
    c.setFillColor(WHITE)
    for i, s in enumerate(strengths[:5]):
        text = f"{i + 1}.  {s}"
        # Truncate if too long
        while c.stringWidth(text, get_font("body"), 8) > rw - 30 and len(text) > 20:
            text = text[:-4] + "..."
        c.drawString(rx + 15, sy - 38 - i * 22, text)

    # Risks box
    risks = data.get("risks", [])
    rh = 25 + len(risks) * 22
    ry = sy - sh - 20

    c.setStrokeColor(RED)
    c.setLineWidth(1)
    c.roundRect(rx, ry - rh, rw, rh, 8, fill=0, stroke=1)

    c.setFont(get_font("heading-regular"), 10)
    c.setFillColor(RED)
    c.drawString(rx + 15, ry - 18, "INVESTMENT RISKS")

    c.setFont(get_font("body"), 8)
    c.setFillColor(WHITE)
    for i, r in enumerate(risks[:5]):
        text = f"{i + 1}.  {r}"
        while c.stringWidth(text, get_font("body"), 8) > rw - 30 and len(text) > 20:
            text = text[:-4] + "..."
        c.drawString(rx + 15, ry - 38 - i * 22, text)

    _footer(c, "Investor Report")


# ── Startup Report ──────────────────────────────────────────────────

def generate_startup_pdf(data: dict, report_id: str) -> Path:
    """Generate 4-page Startup/Founder Deck Review PDF."""
    download_fonts()
    pdf_path = REPORTS_DIR / f"{report_id}_startup.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=landscape(A4))
    c.setTitle(f"CrackTheDeck Founder Report — {data.get('company_name', 'Unknown')}")
    c.setAuthor("Perplexity Computer")

    _startup_cover(c, data)
    c.showPage()
    _startup_checklist(c, data)
    c.showPage()
    _startup_readiness(c, data)
    c.showPage()
    _startup_action_plan(c, data)
    c.showPage()

    c.save()
    logger.info(f"Generated startup PDF: {pdf_path}")
    return pdf_path


def _startup_cover(c: canvas.Canvas, data: dict):
    _bg(c)
    _corner_brackets(c)

    y = H - 160
    c.setFont(get_font("heading"), 48)
    c.setFillColor(GREEN)
    c.drawCentredString(W / 2, y, "CRACKTHEDECK")

    y -= 40
    c.setFont(get_font("heading-regular"), 16)
    c.setFillColor(CYAN)
    c.drawCentredString(W / 2, y, "FOUNDER DECK REVIEW")

    y -= 35
    c.setFont(get_font("body-bold"), 22)
    c.setFillColor(WHITE)
    c.drawCentredString(W / 2, y, data.get("company_name", ""))

    if data.get("company_name_local"):
        y -= 22
        c.setFont(get_font("body"), 14)
        c.setFillColor(MUTED)
        c.drawCentredString(W / 2, y, f"({data['company_name_local']})")

    y -= 30
    c.setFont(get_font("body"), 12)
    c.setFillColor(MUTED)
    c.drawCentredString(W / 2, y, data.get("date", ""))

    # Terminal lines
    y -= 40
    c.setFont(get_font("heading-regular"), 11)
    c.setFillColor(GREEN)
    c.drawCentredString(W / 2, y, f"> {data.get('total_slides', 0)} slides scanned")
    y -= 18
    c.drawCentredString(W / 2, y, "> generating report_")

    # Tagline
    c.setFont(get_font("heading-regular"), 12)
    c.setFillColor(GREEN)
    c.drawCentredString(W / 2, 55, "Fix Your Pitch. Close Your Round.")

    _footer(c, "Founder Report")


def _startup_checklist(c: canvas.Canvas, data: dict):
    _bg(c)

    # Title
    c.setFont(get_font("heading"), 16)
    c.setFillColor(GREEN)
    c.drawString(MARGIN, H - 45, f"DECK COMPLETENESS // {data.get('company_name', '').upper()}")

    c.setStrokeColor(GREEN)
    c.setLineWidth(1)
    c.line(MARGIN, H - 52, W - MARGIN, H - 52)

    # Table header
    y = H - 72
    c.setFont(get_font("heading-regular"), 8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN + 10, y, "ELEMENT")
    c.drawString(MARGIN + 310, y, "STATUS")
    c.drawString(MARGIN + 370, y, "NOTES")

    # Checklist rows
    checklist = data.get("checklist", [])
    row_h = 30
    y -= 10

    status_colors = {
        "strong": GREEN,
        "weak": GOLD,
        "missing": RED,
        "n/a": MUTED,
    }

    for i, item in enumerate(checklist[:14]):
        ry = y - i * row_h

        # Alternating row bg
        if i % 2 == 0:
            c.setFillColor(SURFACE)
            c.rect(MARGIN, ry - 8, INNER_W, row_h, fill=1, stroke=0)

        # Element name
        c.setFont(get_font("body-semi"), 9)
        c.setFillColor(WHITE)
        c.drawString(MARGIN + 10, ry + 5, item.get("element", ""))

        # Status dot
        status = item.get("status", "missing")
        color = status_colors.get(status, MUTED)
        c.setFillColor(color)
        c.circle(MARGIN + 325, ry + 8, 5, fill=1, stroke=0)

        # Notes
        notes = item.get("notes", "")
        c.setFont(get_font("body"), 7.5)
        c.setFillColor(MUTED)
        max_notes_w = INNER_W - 380
        while c.stringWidth(notes, get_font("body"), 7.5) > max_notes_w and len(notes) > 10:
            notes = notes[:-4] + "..."
        c.drawString(MARGIN + 370, ry + 5, notes)

    # Summary line
    summary = data.get("checklist_summary", {})
    sy = y - len(checklist) * row_h - 10
    c.setFont(get_font("body-bold"), 10)
    c.setFillColor(WHITE)
    total = summary.get("total", 14)
    strong = summary.get("strong", 0)
    weak = summary.get("weak", 0)
    missing = summary.get("missing", 0)
    present = total - missing
    c.drawString(MARGIN + 10, sy,
                 f"{present} of {total} elements present  |  {strong} strong  |  {weak} weak  |  {missing} missing")

    # Color bar
    bar_y = sy - 18
    bar_w = INNER_W * 0.6
    bar_h = 10
    bar_x = MARGIN + 10

    # Strong segments
    if total > 0:
        sw = bar_w * strong / total
        c.setFillColor(GREEN)
        c.rect(bar_x, bar_y, sw, bar_h, fill=1, stroke=0)

        ww = bar_w * weak / total
        c.setFillColor(GOLD)
        c.rect(bar_x + sw, bar_y, ww, bar_h, fill=1, stroke=0)

        mw = bar_w * missing / total
        c.setFillColor(RED)
        c.rect(bar_x + sw + ww, bar_y, mw, bar_h, fill=1, stroke=0)

    # Legend
    legend_y = bar_y - 18
    legend_items = [("Strong", GREEN), ("Weak", GOLD), ("Missing", RED), ("N/A", MUTED)]
    lx = bar_x
    for label, color in legend_items:
        c.setFillColor(color)
        c.circle(lx + 4, legend_y + 3, 4, fill=1, stroke=0)
        c.setFont(get_font("body"), 7)
        c.setFillColor(MUTED)
        c.drawString(lx + 12, legend_y, label)
        lx += 80

    _footer(c, "Founder Report")


def _startup_readiness(c: canvas.Canvas, data: dict):
    _bg(c)

    # Title
    c.setFont(get_font("heading"), 16)
    c.setFillColor(GREEN)
    c.drawString(MARGIN, H - 45, f"FUNDRAISING READINESS // {data.get('company_name', '').upper()}")

    c.setStrokeColor(GREEN)
    c.setLineWidth(1)
    c.line(MARGIN, H - 52, W - MARGIN, H - 52)

    fr = data.get("fundraising_readiness", {})
    level = fr.get("level", "MEDIUM")
    level_color = {"HIGH": GREEN, "MEDIUM": GOLD, "LOW": RED}.get(level, GOLD)

    # Large level label
    c.setFont(get_font("heading"), 36)
    c.setFillColor(level_color)
    c.drawString(MARGIN, H - 100, level)

    # Summary
    c.setFont(get_font("body"), 10)
    c.setFillColor(WHITE)
    summary = fr.get("summary", "")
    words = summary.split()
    lines = []
    line = ""
    for w in words:
        test = line + " " + w if line else w
        if c.stringWidth(test, get_font("body"), 10) > 350:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    for i, ln in enumerate(lines[:3]):
        c.drawString(MARGIN, H - 120 - i * 14, ln)

    # Three arc charts
    arc_y = H - 105
    arc_r = 38
    arc_spacing = 150
    arc_start_x = W / 2 + 50

    arcs = [
        (fr.get("completeness_pct", 0), CYAN, "Completeness", fr.get("completeness_note", "")),
        (fr.get("structure_pct", 0), GOLD, "Structure", fr.get("structure_note", "")),
        (fr.get("strength_pct", 0), GREEN, "Strength", fr.get("strength_note", "")),
    ]

    for j, (pct, color, label, note) in enumerate(arcs):
        cx = arc_start_x + j * arc_spacing
        _draw_arc(c, cx, arc_y, arc_r, pct, color, label, note)

    # TOP ISSUES
    issues_y = H - 235
    c.setFont(get_font("heading"), 14)
    c.setFillColor(RED)
    c.drawString(MARGIN, issues_y, "TOP ISSUES")

    c.setStrokeColor(HexColor("#2A2A3E"))
    c.setLineWidth(0.5)
    c.line(MARGIN, issues_y - 8, W - MARGIN, issues_y - 8)

    issues = data.get("issues", [])
    iy = issues_y - 28

    for issue in issues[:10]:
        rank = issue.get("rank", 0)
        severity = issue.get("severity", "MEDIUM")
        desc = issue.get("description", "")
        sev_color = _severity_color(severity)

        # Rank number
        c.setFont(get_font("body-semi"), 10)
        c.setFillColor(WHITE)
        c.drawRightString(MARGIN + 20, iy, f"{rank}.")

        # Severity badge
        badge_w = 55
        badge_h = 14
        bx = MARGIN + 28
        c.setFillColor(sev_color)
        c.roundRect(bx, iy - 3, badge_w, badge_h, 3, fill=1, stroke=0)
        c.setFont(get_font("heading-regular"), 7)
        c.setFillColor(BG)
        c.drawCentredString(bx + badge_w / 2, iy + 1, severity)

        # Description
        c.setFont(get_font("body"), 8.5)
        c.setFillColor(WHITE)
        desc_text = desc
        max_desc_w = INNER_W - 100
        while c.stringWidth(desc_text, get_font("body"), 8.5) > max_desc_w and len(desc_text) > 10:
            desc_text = desc_text[:-4] + "..."
        c.drawString(bx + badge_w + 10, iy, desc_text)

        iy -= 28

    _footer(c, "Founder Report")


def _startup_action_plan(c: canvas.Canvas, data: dict):
    _bg(c)

    # Title
    c.setFont(get_font("heading"), 16)
    c.setFillColor(GREEN)
    c.drawString(MARGIN, H - 45, f"ACTION PLAN // {data.get('company_name', '').upper()}")

    c.setStrokeColor(GREEN)
    c.setLineWidth(1)
    c.line(MARGIN, H - 52, W - MARGIN, H - 52)

    # Subtitle
    c.setFont(get_font("heading-regular"), 12)
    c.setFillColor(WHITE)
    c.drawString(MARGIN, H - 72, "RECOMMENDED DECK STRUCTURE")

    slides_total = data.get("total_slides", 0)
    c.setFont(get_font("body"), 9)
    c.setFillColor(MUTED)
    rec_slides = data.get("recommended_structure", [])
    c.drawString(MARGIN, H - 88,
                 f"Restructure your {slides_total}-slide deck into this {len(rec_slides)}-slide format:")

    # Two columns of slides
    col_w = INNER_W / 2 - 10
    col1_x = MARGIN
    col2_x = MARGIN + col_w + 20
    start_y = H - 110
    row_h = 26
    mid = (len(rec_slides) + 1) // 2

    for i, slide in enumerate(rec_slides):
        if i < mid:
            x = col1_x
            y = start_y - i * row_h
        else:
            x = col2_x
            y = start_y - (i - mid) * row_h

        section = slide.get("section", "core")
        color = _section_color(section)

        # Dot
        c.setFillColor(color)
        c.circle(x + 6, y + 4, 4, fill=1, stroke=0)

        # Slide text
        c.setFont(get_font("body"), 9)
        c.setFillColor(WHITE)
        c.drawString(x + 16, y, f"{slide['slide_number']}. {slide['title']}")

        # Annotation
        if slide.get("annotation"):
            ann_x = x + 16 + c.stringWidth(
                f"{slide['slide_number']}. {slide['title']}  ", get_font("body"), 9)
            c.setFont(get_font("heading-regular"), 8)
            c.setFillColor(RED)
            c.drawString(ann_x, y, slide["annotation"])

    # Section legend
    legend_y = start_y - max(mid, len(rec_slides) - mid) * row_h - 15
    legend_items = [("Opening", GREEN), ("Core narrative", CYAN), ("Close", GOLD)]
    lx = MARGIN
    for label, color in legend_items:
        c.setFillColor(color)
        c.circle(lx + 4, legend_y + 3, 4, fill=1, stroke=0)
        c.setFont(get_font("body"), 8)
        c.setFillColor(MUTED)
        c.drawString(lx + 12, legend_y, label)
        lx += 130

    # Impact box
    impact_y = legend_y - 35
    c.setStrokeColor(GREEN)
    c.setFillColor(HexColor("#0A2A1A"))
    c.setLineWidth(1)
    c.roundRect(MARGIN, impact_y - 15, INNER_W, 45, 6, fill=1, stroke=1)

    c.setFont(get_font("heading-regular"), 12)
    c.setFillColor(GREEN)
    c.drawString(MARGIN + 15, impact_y + 15,
                 f"ESTIMATED IMPACT: {data.get('estimated_impact', '')}")

    c.setFont(get_font("body"), 10)
    c.setFillColor(WHITE)
    c.drawString(MARGIN + 15, impact_y - 3,
                 f"Current: {data.get('current_readiness', '')}  →  Target: {data.get('target_readiness', '')} fundraising readiness")

    # CTA
    cta_y = impact_y - 60
    c.setFont(get_font("heading"), 22)
    c.setFillColor(GREEN)
    c.drawCentredString(W / 2, cta_y, "YOUR DECK. UPGRADED.")

    c.setFont(get_font("heading-regular"), 12)
    c.setFillColor(CYAN)
    c.drawCentredString(W / 2, cta_y - 25, "crackthedeck.com")

    # Summary strip
    issues_count = len(data.get("issues", []))
    missing = data.get("checklist_summary", {}).get("missing", 0)
    readiness = data.get("current_readiness", "")
    c.setFont(get_font("body"), 9)
    c.setFillColor(MUTED)
    strip = f"{slides_total} Slides Analyzed  |  {issues_count} Issues  |  {missing} Missing Elements  |  {readiness} Readiness"
    c.drawCentredString(W / 2, cta_y - 50, strip)

    _footer(c, "Founder Report")
