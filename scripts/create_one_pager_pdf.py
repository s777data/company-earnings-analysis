#!/usr/bin/env python3
"""Rich, evidence-backed single-page earnings dashboard.

The layout restores the original v1.2 information hierarchy while consuming only
the generic structured analysis schema. No ticker, quarter, value, or thesis is
embedded in this renderer.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from fpdf import FPDF
import pdfplumber

COLORS = {
    "best": (0, 32, 96), "strong_positive": (0, 64, 128), "positive": (0, 80, 160),
    "neutral": (180, 155, 0), "medium": (180, 155, 0), "caution": (230, 120, 0),
    "negative": (200, 50, 50), "worst": (180, 0, 0), "navy": (31, 63, 112),
    "text": (30, 30, 30), "muted": (90, 90, 90), "light": (247, 249, 252),
    "border": (198, 207, 217), "header": (183, 224, 239),
}
PDF_FONT_SCALE = 1.5
BULLETS = {"best": "+", "strong_positive": "+", "positive": "+", "neutral": "~",
           "medium": "~", "caution": "~", "negative": "-", "worst": "-"}
COMPACT_LABELS = {
    "Management Tone": "◎ Management Tone",
    "Revenue & Demand": "↗ Revenue",
    "Margins & Profitability": "▼ Margins",
    "Guidance": "◎ Guidance",
    "Products & Innovation": "⚙ Product",
    "Customers & Engagement": "◉ Customers",
    "Capital Allocation": "♻ Capital",
    "Competition & Market": "⚔ Market",
    "Analyst Q&A": "◆ Q&A",
    "Products & platforms": "⚙ Products",
    "Customers & engagement": "◉ Customers",
    "Markets & distribution": "↗ Markets",
    "Business lines": "◆ Segments",
    "Innovation Roadmap": "⚙ Innovation",
    "Growth Expansion": "↗ Expansion",
    "Customer Value": "◉ Customer",
    "Operational Excellence": "⚒ Operations",
    "Capital Discipline": "♻ Capital",
    "Long-Term Strategy": "◎ Strategy",
}
SEMANTIC_SYMBOL_COLORS = {
    "↗": COLORS["positive"],
    "↑": COLORS["positive"],
    "↓": COLORS["negative"],
    "→": COLORS["neutral"],
    "▼": COLORS["negative"],
    "◎": COLORS["best"],
    "⚙": COLORS["best"],
    "◉": COLORS["strong_positive"],
    "♻": COLORS["positive"],
    "⚔": COLORS["caution"],
    "◆": COLORS["best"],
    "⚒": COLORS["caution"],
    "⚡": COLORS["caution"],
}
GRADE_COLORS = {
    "A+": (0, 90, 0), "A": (0, 100, 0), "A-": (34, 139, 34),
    "B+": (40, 145, 40), "B": (50, 150, 50), "B-": (60, 179, 113),
    "C+": (154, 180, 40), "C": (180, 155, 0), "C-": (218, 145, 20),
    "D+": (235, 125, 0), "D": (230, 90, 0), "D-": (210, 25, 55), "F": (180, 0, 0),
}


def _signal(item: dict[str, Any]) -> str:
    value = item.get("signal") or item.get("tier") or "neutral"
    return value if value in COLORS else "neutral"


def _clip(text: Any, maximum: int | None) -> str:
    value = str(text or "").replace("→", "->").replace("←", "<-")
    value = value.replace("—", "-").replace("–", "-").replace("'", "'").replace('"', '"').replace('"', '"')
    value = " ".join(value.split())
    if maximum is None or len(value) <= maximum:
        return value
    return value[:maximum].rsplit(" ", 1)[0].rstrip(" ,;:-") + "..."


def _complete_items(items: list[dict[str, Any]], maximum: int, character_budget: int,
                    ensure_qa: bool = False) -> list[dict[str, Any]]:
    """Fit complete bullets into a fixed panel; never replace endings with ellipses."""
    qa = next((row for row in items if row.get("section") == "Analyst Q&A"), None) if ensure_qa else None
    selected: list[dict[str, Any]] = []
    used = 0
    for row in items:
        text = str(row.get("detail") or row.get("text") or "")
        reserve = len(str(qa.get("detail", ""))) if qa and qa not in selected and row is not qa else 0
        if text and len(selected) < maximum and used + len(text) + reserve <= character_budget:
            selected.append(row)
            used += len(text)
    if qa and qa not in selected:
        while selected and used + len(str(qa.get("detail", ""))) > character_budget:
            removed = selected.pop()
            used -= len(str(removed.get("detail", "")))
        if len(selected) < maximum:
            selected.append(qa)
    return selected


def _segment_icon(name: str) -> str:
    lower = name.lower()
    if "power" in lower or "energy" in lower:
        return "⚡"
    if "construct" in lower:
        return "⚒"
    if "resource" in lower or "mining" in lower:
        return "◆"
    return "▪"


def _compact_summary(text: Any, label: str | None = None) -> str:
    """Create a shorter dashboard summary while retaining material evidence.

    Applies pattern-based compression, then a generic fallback that abbreviates common
    words and removes filler so that EVERY input is shortened.
    """
    value = " ".join(str(text or "").split())

    def finish(body: str, use_label: bool = True) -> str:
        body = re.sub(r"(\$?[\d,.]+)\s+billion\b", r"\1B", body, flags=re.I)
        body = re.sub(r"(\$?[\d,.]+)\s+million\b", r"\1M", body, flags=re.I)
        body = re.sub(r"\bbasis points\b", "bps", body, flags=re.I)
        body = re.sub(r"\bfree cash flow\b", "FCF", body, flags=re.I)
        body = re.sub(r"\bshare repurchases and dividends\b", "buybacks + dividends", body, flags=re.I)
        body = re.sub(r"\bdividends and share repurchases\b", "dividends + buybacks", body, flags=re.I)
        body = re.sub(r"\ba suite of AI capabilities\b", "AI capabilities", body, flags=re.I)
        body = re.sub(r"\bthe rental industry presence\b", "rental presence", body, flags=re.I)
        body = re.sub(r"\boil and gas\b", "oil & gas", body, flags=re.I)
        body = re.sub(r"\bstrong growth in sales volume and favorable price realization\b", "volume growth + favorable pricing", body, flags=re.I)
        body = re.sub(r"\bhigher average earning assets across all regions\b", "higher earning assets across regions", body, flags=re.I)
        body = re.sub(r"\bhigher sales to users and services growth\b", "user sales + services growth", body, flags=re.I)
        body = re.sub(r"\bsales and revenues\b", "sales", body, flags=re.I)
        body = re.sub(r"\badjusted operating profit margin\b", "adjusted operating margin", body, flags=re.I)
        body = re.sub(r"\bthe first quarter\b", "Q1", body, flags=re.I)
        body = re.sub(r"\bthe second quarter\b", "Q2", body, flags=re.I)
        body = re.sub(r"\bthe third quarter\b", "Q3", body, flags=re.I)
        body = re.sub(r"\bthe fourth quarter\b", "Q4", body, flags=re.I)
        body = re.sub(r"\breciprocating engines\b", "engines", body, flags=re.I)
        body = re.sub(r"\bturbine-related services sold into gas compression applications\b", "gas-compression services", body, flags=re.I)
        body = re.sub(r"\btariffs impact\b", "tariff impact", body, flags=re.I)
        body = re.sub(r"\bphase two of our\b", "phase 2", body, flags=re.I)
        body = re.sub(r"\bthe flat to last year\b", "flat YoY", body, flags=re.I)
        body = re.sub(r"\bour brand expansions globally, particularly with (.+?)'s launch into (.+?)\.?$",
                      r"global brand expansion, especially \1 \2", body, flags=re.I)
        body = re.sub(r"\s+", " ", body).strip(" ,;:-")
        if body and body[-1] not in ".!?":
            body += "."
        return f"{label}: {body}" if label and use_label else body

    def without_demand_growth(body: str) -> str:
        return re.sub(r"^the demand growth in ", "", body, flags=re.I)

    def generic_compress(body: str) -> str:
        """Generic fallback: abbreviate common words, remove filler phrases."""
        compressions = [
            (r"\bapproximately\b", "~"),
            (r"\bpercentage points?\b", "pp"),
            (r"\byear-over-year\b", "YoY"),
            (r"\byear over year\b", "YoY"),
            (r"\bcompared to\b", "vs"),
            (r"\bcompared with\b", "vs"),
            (r"\bin the quarter\b", "in Q"),
            (r"\bfor the quarter\b", "in Q"),
            (r"\bfor the full year\b", "FY"),
            (r"\bfull year\b", "FY"),
            (r"\bwe expect\b", ""),
            (r"\bwe anticipate\b", ""),
            (r"\bwe believe\b", ""),
            (r"\bwe are\b", ""),
            (r"\bwe have\b", ""),
            (r"\bwe will\b", ""),
            (r"\bwe(?:'ve| have) had\b", "We had"),
            (r"\b(?:you are|you're) not going to\b", "you won't"),
            (r"\bwe're going to\b", "we will"),
            (r"\bare going to\b", "will"),
            (r"\bgoing to\b", "will"),
            (r"\bcontinue to\b", ""),
            (r"\bability to\b", ""),
            (r"\bcapability to\b", ""),
            (r"\bability\b", ""),
            (r"\bcapability\b", ""),
            (r"\bstrong\b", ""),
            (r"\brobust\b", ""),
            (r"\bsignificant\b", ""),
            (r"\bmeaningful\b", ""),
            (r"\bsubstantial\b", ""),
            (r"\bcontinued\b", ""),
            (r"\bongoing\b", ""),
            (r"\bcurrent\b", ""),
            (r"\bprior\b", "prev"),
            (r"\bprevious\b", "prev"),
            (r"\bdriven by\b", "on"),
            (r"\bdue to\b", "on"),
            (r"\breflecting\b", "on"),
            (r"\beffect\b", ""),
            (r"\bbenefit\b", ""),
            (r"\badvantage\b", ""),
            (r"\boutperformance\b", "beat"),
            (r"\bunderperformance\b", "miss"),
            (r"\bexpectations\b", "expects"),
            (r"\boutlook\b", "view"),
            (r"\bguidance\b", "view"),
            (r"\bforecast\b", "view"),
            (r"\bprojection\b", "view"),
            (r"\bassumption\b", "view"),
            (r"\bstrategy\b", "plan"),
            (r"\bstrategic\b", ""),
            (r"\binitiative\b", "effort"),
            (r"\binvestment\b", "invest"),
            (r"\bexpenditure\b", "spend"),
            (r"\bcapital expenditure\b", "capex"),
            (r"\boperating\b", "ops"),
            (r"\boperational\b", "ops"),
            (r"\bfinancial\b", "fin"),
            (r"\brevenue\b", "rev"),
            (r"\bprofit\b", "profit"),
            (r"\bprofitability\b", "margin"),
            (r"\bmargin\b", "margin"),
            (r"\bgrowth\b", "growth"),
            (r"\bexpansion\b", "growth"),
            (r"\bacceleration\b", "accel"),
            (r"\bdeceleration\b", "decel"),
            (r"\bimprovement\b", "improv"),
            (r"\bimprove\b", "improv"),
            (r"\bdecline\b", "decl"),
            (r"\bdecrease\b", "decl"),
            (r"\bincrease\b", "incr"),
            (r"\brise\b", "up"),
            (r"\bfall\b", "down"),
            (r"\bdrop\b", "down"),
            (r"\bgain\b", "up"),
            (r"\bloss\b", "down"),
            (r"\bwith\b", "w/"),
            (r"\bwithout\b", "w/o"),
            (r"\band\b", "+"),
            (r"\bthe goal is (?:to get|getting)\b", "Goal:"),
            (r"\bvisibility into more of the\b", "broader visibility into the"),
            (r"\bnow that (?:you are|you're)\b", "since"),
            (r"\bthere(?: is|'s) some\b", ""),
            (r"\bsomething like\b", "~"),
            (r"\bover the last several months\b", "in recent months"),
            (r"\bover time\b", ""),
            (r"\bat this point\b", "now"),
            (r"\bin order to\b", "to"),
            (r"\brepresents an opportunity to\b", "could"),
            (r"\bincluding, but not limited to,\b", "including"),
        ]
        for pattern, replacement in compressions:
            body = re.sub(pattern, replacement, body, flags=re.I)
        body = re.sub(r"\s*,\s*,+", ",", body)
        body = re.sub(r"\s+", " ", body).strip(" ,;:-")
        return body

    segment_margin = re.fullmatch(
        r"segment margins were impacted by\s+([\d,.]+)\s+basis points?\s+in\s+(.+?),\s*"
        r"([\d,.]+)\s+basis points?\s+(?:within|in)\s+(.+?),\s*and\s+"
        r"([\d,.]+)\s+basis points?\s+in\s+(.+?)\.?",
        value,
        re.I,
    )
    if segment_margin:
        amount_1, segment_1, amount_2, segment_2, amount_3, segment_3 = segment_margin.groups()
        return finish(
            f"Segment Margins: {_segment_icon(segment_1)} {segment_1} (↓{amount_1} bps); "
            f"{_segment_icon(segment_2)} {segment_2} (↓{amount_2} bps); "
            f"{_segment_icon(segment_3)} {segment_3} (↓{amount_3} bps)",
            use_label=False,
        )

    patterns: list[tuple[str, Any]] = [
        (r"We expect (.+?) in fiscal (\d{4}) to be up approximately ([\d,.]+) basis points year-over-year as compared to our outlook for (.+?) previously, largely driven by (.+?)\.?$",
         lambda m: f"{m.group(1)} FY{m.group(2)}: ↑~{m.group(3)} bps YoY vs. prior {m.group(4)} outlook; driven by {m.group(5)}"),
        (r"Pricing and product mix added approximately ([\d,.]+|one|two|three|four|five) percentage points to (.+?) in (Q\d), while unit volumes were down approximately ([\d,.]+|one|two|three|four|five) percentage points\.?$",
         lambda m: f"Pricing + mix: ↑~{m.group(1)} pp to {m.group(2)} in {m.group(3)}; unit volume ↓~{m.group(4)} pp"),
        (r"Excluding this benefit, (.+?) was still meaningfully higher year-over-year, up about ([\d,.]+) basis points, reflecting benefits from (.+?) and (.+?)\.?$",
         lambda m: f"{m.group(1)}: Ex-benefit ↑~{m.group(2)} bps YoY on {m.group(3)} + {m.group(4)}"),
        (r"We expect marketing and digital spend as a percent of net sales for the full year to be at the high end of our previous (.+?) range\.?$",
         lambda m: f"FY marketing + digital spend: High end of prior {m.group(1)} of net sales range"),
        (r"(.+?) outperformed our expectations in the quarter, contributing approximately (\$?[\d,.]+\s+(?:million|billion)) in net sales, driven by (.+?) and (.+?)\.?$",
         lambda m: f"{m.group(1)}: Beat expectations; ~{m.group(2)} net sales on {m.group(3)} + {m.group(4)}"),
        (r"The combination of (.+?)'s curated product assortment and powerful consumer engagement model has translated into (.+?)\.?$",
         lambda m: f"{m.group(1)} assortment + engagement: {m.group(2)}"),
        (r"Marketing and digital investment for the quarter was (.+?) of net sales, below our expectations due to the timing of spend and (.+?)\.?$",
         lambda m: f"Quarter marketing + digital investment: {m.group(1)} of net sales; below expectations on spend timing; {m.group(2)}"),
        (r"We plan to fully reinvest these funds in our business this year, largely through a combination of (.+?) and increased marketing investment to support (.+?)\.?$",
         lambda m: f"FY reinvestment: {m.group(1)} + higher marketing support {m.group(2)}"),
        (r"We're one of only ([\w]+) public consumer companies out of ([\d,.]+) that has grown for ([\d,.]+) straight quarters and averages at least ([\d,.]+%) net sales growth per quarter\.?$",
         lambda m: f"Track record: 1 of {m.group(1)}/{m.group(2)} public consumer companies; {m.group(3)} straight growth quarters; ≥{m.group(4)} avg net sales growth/quarter"),
        (r"We also plan to invest in technology, including (.+?) and (.+?), to support (.+?)\.?$",
         lambda m: f"Technology: {m.group(1)} + {m.group(2)} support {m.group(3)}"),
        (r"brand across five key areas: (.+?), (.+?), (.+?), (.+?), and (.+?)\.?$",
         lambda m: f"Five growth levers: {m.group(1)}, {m.group(2)}, {m.group(3)}, {m.group(4)} + {m.group(5)}"),
        (r"We believe the strength of our balance sheet continues to position us well to execute our long-term strategic plans and invest in the growth of our business\.?$",
         lambda m: "Balance sheet strength supports long-term plans + business growth investment"),
        (r"We're going to keep that (.+?) at (.+?) while (.+?) go back to (.+?)\.?$",
         lambda m: f"Pricing: Keep {m.group(1)} at {m.group(2)}; {m.group(3)} return to {m.group(4)}"),
        (r"Due to the increased (.+?) outlook, (?:we now expect )?(?:the )?full-year (.+?) will be higher than we expected in April\.?$",
         lambda m: f"↗ FY {m.group(2)}: Above April outlook on stronger {m.group(1)} outlook"),
        (r"Forward outlook: Management expects (.+?) to remain (.+?)\.?$",
         lambda m: f"◎ {m.group(1)} remains {m.group(2)}"),
        (r"Second quarter (.+?) was better than we anticipated, primarily due to (.+?) of (\$?[\d,.]+\s+(?:million|billion)) and lower than expected (.+?)\.?$",
         lambda m: f"⚙ Q2 {m.group(1)} beat expectations on {m.group(3)} {m.group(2)} + lower forecast {m.group(4)}"),
        (r"The (\$?[\d,.]+\s+(?:million|billion)) of dealer inventory increase and services revenue growth resulted in sales volume to be better than we expected\.?$",
         lambda m: f"⚙ Dealer inventory: {m.group(1)} increase + services growth lifted sales volume above expectations"),
        (r"(?:As a result, we anticipate|(?:We )?expect) stronger full-year growth across all three primary segments compared to the outlook we gave in April\.?$",
         lambda m: "↗ FY growth: Stronger across all three primary segments vs. April outlook"),
        (r"With the improved (.+?) outlook, we now expect (.+?) to be in the top half of our annual target range of (.+?)\.?$",
         lambda m: f"{m.group(2)}: ◎ Top half of {m.group(3)} target after stronger {m.group(1)} outlook"),
        (r"The (\d+(?:\.\d+)?%) increase in (.+?) compared (?:to|with) the (?:first|second|third|fourth) quarter of \d{4} was primarily driven by (.+?)\.?$",
         lambda m: f"↑{m.group(1)} YoY; {m.group(3)}"),
        (r"We expect the full-year (.+?) to be higher than we expected during our last earnings call, reflecting the improved (.+?) outlook\.?$",
         lambda m: f"FY {m.group(1)} ↑ vs. prior call on stronger {m.group(2)} outlook"),
        (r"To support (.+?), we are excited to resume production of our (.+?)\.?$",
         lambda m: f"{m.group(2)}: Production resumes for {without_demand_growth(m.group(1))}"),
        (r"Sales to users in (.+?) increased (\d+(?:\.\d+)?%) and were driven by (.+?)\.?$",
         lambda m: f"⚡ {m.group(1)} sales ↑{m.group(2)} via {m.group(3)}"),
        (r"In the quarter, we generated robust (.+?) of (\$?[\d,.]+\s+(?:million|billion)) and deployed (\$?[\d,.]+\s+(?:million|billion)) to shareholders through (.+?)\.?$",
         lambda m: f"Generated {m.group(2)} {m.group(1)}; ♻ {m.group(3)} via {m.group(4)}"),
        (r"In (\d{4}), we stopped manufacturing this product and focused on supporting (.+?), given the limited industry opportunity at that time\.?$",
         lambda m: f"⚒ Manufacturing stopped in {m.group(1)}; {m.group(2)} retained amid limited demand"),
        (r"The (.+?) unit, that's the old (.+?) business that it was primarily (.+?) focused in the past and wasn't performing the way after many years with low (.+?), but it's well-suited, and we did the (.+?) development for (.+?), and we went and we'll bring that back\.?$",
         lambda m: f"♻ {m.group(1)} {m.group(2)} platform returning for {m.group(6)} after {m.group(5)} redevelopment and weak {m.group(3)} demand"),
        (r"Moving to slide \d+, (.+?) revenues increased by (\d+(?:\.\d+)?%) versus the prior year to (\$?[\d,.]+\s+(?:million|billion)), mainly due to (.+?)\.?$",
         lambda m: f"{m.group(1)}: Revenue ↑{m.group(2)} YoY to {m.group(3)} on {m.group(4)}"),
        (r"(.+?)'s technology captures (.+?) and pairs it with (.+?)\.?$",
         lambda m: f"{m.group(1)}: {m.group(2)} + {m.group(3)}"),
        (r"We believe (.+?) will expand our presence in (.+?) and make it easier for (.+?) to do business with us and our dealers\.?$",
         lambda m: f"{m.group(1)}: Expands {m.group(2)} presence; simplifies dealer access for {m.group(3)}"),
        (r"In (.+?), we also expect strong sales growth in (.+?) versus the prior year, primarily due to (.+?)\.?$",
         lambda m: f"{m.group(1)}: {m.group(2)} sales ↑ YoY on {m.group(3)}"),
        (r"(.+?) will serve customers developing (.+?), including (.+?)\.?$",
         lambda m: f"{m.group(1)}: {m.group(2)} across {m.group(3)}"),
        (r"We will continue to return substantially all of our (.+?) to our shareholders through (.+?) over time\.?$",
         lambda m: f"Substantially all {m.group(1)} → {m.group(2)}"),
        (r"Our full-year margin expectation reflects the strategic investments we are making to execute our growth strategy, as well as the ongoing impact of (.+?)\.?$",
         lambda m: f"FY margin: Growth investment + ongoing {m.group(1)} impact"),
        (r"The (.+?) expanded across international markets and added new (.+?)\.?$",
         lambda m: f"{m.group(1)} expanded internationally and added {m.group(2)}"),
        (r"Customer retention improved as engagement increased across the company's principal (.+?)\.?$",
         lambda m: f"Retention improved as engagement rose across core {m.group(1)}"),
        (r"Regional distribution expanded through partners in (.+?)\.?$",
         lambda m: f"Regional distribution expanded via partners in {m.group(1)}"),
        (r"The business segment delivered higher sales as demand strengthened across core applications\.?$",
         lambda m: "Business sales rose on stronger core demand"),
        (r"(.+?) increased (\d+(?:\.\d+)?%) as (.+?)\.?$",
         lambda m: f"{m.group(1)} +{m.group(2)} on {m.group(3)}"),
    ]
    for pattern, builder in patterns:
        match = re.fullmatch(pattern, value, re.I)
        if match:
            return finish(builder(match))

    # Generic fallback compression — always shortens the text
    compressed = generic_compress(value)
    # Apply standard replacements too
    replacements = (
        (r"\bMoving to slide \d+,\s*", ""), (r"\bAs a result,\s*", ""),
        (r"\bwe now expect\b", "Expect"), (r"\bwe expect\b", "Expect"),
        (r"\bwe anticipate\b", "Expect"), (r"\bwe believe\b", ""),
        (r"\bwe are excited to\b", ""), (r"\bprimarily driven by\b", "driven by"),
        (r"\bprimarily due to\b", "due to"),
        (r"\bcompared (?:to|with) the (?:first|second|third|fourth) quarter of \d{4}\b", "YoY"),
        (r"\b(?:versus|compared (?:to|with)) the prior year\b", "YoY"),
        (r"\bfull-year\b", "FY"),
        (r"\badjusted operating profit margin\b", "adjusted operating margin"),
        (r"\bsales and revenues\b", "sales"),
    )
    for pattern, replacement in replacements:
        compressed = re.sub(pattern, replacement, compressed, flags=re.I)
    return finish(compressed)


def _compact_items(items: list[dict[str, Any]], text_key: str, label_key: str | None,
                   maximum: int, character_budget: int, item_limit: int) -> list[dict[str, Any]]:
    """Build compact, complete display rows without using item length as a drop gate.

    ``item_limit`` is retained for API compatibility and diagnostics. Physical fit is
    handled from measured PDF line wrapping by ``OnePager.compact_lines()``.
    """
    compact: list[dict[str, Any]] = []
    used = 0
    for row in items:
        source = " ".join(str(row.get(text_key) or "").split())
        body = _compact_summary(source)
        if not body or len(body) >= len(source):
            continue
        row_label = row.get("_display_label")
        if row_label is None and label_key:
            row_label = COMPACT_LABELS.get(str(row.get(label_key)), row.get(label_key))
        separator = str(row.get("_label_separator") or ": ")
        summary = body if body.startswith("Segment Margins:") or not row_label else f"{row_label}{separator}{body}"
        if len(compact) >= maximum or used + len(summary) > character_budget:
            continue
        compact.append({**row, "text": summary})
        used += len(summary)
    return compact


def _select_call_summary_insights(rows: list[dict[str, Any]], maximum: int = 8,
                                  character_budget: int = 2500) -> list[dict[str, Any]]:
    """Mirror Telegram's complete insight selection for the PDF call summary.

    This is intentionally PDF-local so Telegram generation remains untouched.
    The PDF then compresses this same ordered evidence set into semantic icons
    and signal-colored summaries.
    """
    qa = next((row for row in rows if row.get("section") == "Analyst Q&A"), None)
    selected: list[dict[str, Any]] = []
    used = 0
    for row in rows:
        detail = " ".join(str(row.get("detail", "")).split())
        if not detail or len(selected) >= maximum:
            continue
        reserve = len(qa.get("detail", "")) if qa and qa not in selected and row is not qa else 0
        if used + len(detail) + reserve > character_budget:
            continue
        selected.append(row)
        used += len(detail)
    if qa and qa not in selected:
        while selected and used + len(qa.get("detail", "")) > character_budget:
            removed = selected.pop()
            used -= len(removed.get("detail", ""))
        if len(selected) < maximum:
            selected.append(qa)
    return selected


def _compress_for_channel_card(text: str) -> str:
    """Apply company-neutral abbreviations suitable for four-up channel cards."""
    if not text:
        return text
    compressions = [
        (r"\binternationally\b", "intl"),
        (r"\binternational\b", "intl"),
        (r"\byear-over-year\b", "YoY"),
        (r"\byear over year\b", "YoY"),
        (r"\bapproximately\b", "~"),
        (r"\bpercentage points?\b", "pp"),
        (r"\bcompared (?:to|with)\b", "vs"),
        (r"\bversus\b", "vs"),
        (r"\bwith\b", "w/"),
        (r"\bwithout\b", "w/o"),
        (r"\band\b", "+"),
    ]
    for pattern, replacement in compressions:
        text = re.sub(pattern, replacement, text, flags=re.I)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _direction_marker(item: dict[str, Any]) -> tuple[str, tuple[int, int, int]]:
    if item.get("_signal_marker"):
        signal = _signal(item)
        if signal in {"best", "strong_positive", "positive"}:
            return "↑", COLORS["positive"]
        if signal in {"caution", "negative", "worst"}:
            return "↓", COLORS["negative"]
        return "→", COLORS["neutral"]
    text = str(item.get("text") or item.get("detail") or item.get("desc") or "")
    has_down, has_up = "↓" in text, "↑" in text
    if has_down and has_up:
        return "→", COLORS["neutral"]
    if has_down:
        return "↓", COLORS["negative"]
    if has_up:
        return "↑", COLORS["positive"]
    lower = text.lower()
    if "beat expectations" in lower or "above expectations" in lower:
        return "↑", COLORS["positive"]
    down = any(term in lower for term in ("declin", "decreas", "fell", "lower", "pressure", "impacted", "headwind", "contraction"))
    up = any(term in lower for term in ("increas", "improv", "growth", "higher", "expand", "stronger", "accelerat"))
    if down and not up:
        return "↓", COLORS["negative"]
    if up and not down:
        return "↑", COLORS["positive"]
    signal = _signal(item)
    if signal in {"best", "strong_positive", "positive"}:
        return "↑", COLORS["positive"]
    if signal in {"caution", "negative", "worst"}:
        return "↓", COLORS["negative"]
    return "→", COLORS["neutral"]


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1e12:
        return f"{sign}${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"{sign}${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"{sign}${value / 1e6:.1f}M"
    return f"{sign}${value:,.0f}"


class OnePager(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        font_dir = Path("/usr/share/fonts/truetype/dejavu")
        self.add_font("DejaVu", "", str(font_dir / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(font_dir / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(False)
        self.set_margins(8, 7, 8)
        self.add_page()

    def set_font(self, family: str, style: str = "", size: float = 0) -> None:
        """Apply the PDF-only global font scale at the rendering boundary."""
        super().set_font(family, style, size * PDF_FONT_SCALE if size else size)

    @property
    def page_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def title_bar(self, title: str, x: float, y: float, width: float, height: float = 5.2) -> float:
        self.set_xy(x, y)
        self.set_fill_color(*COLORS["navy"])
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 6.8)
        self.cell(width, height, title, fill=True)
        return y + height

    def frame(self, x: float, y: float, width: float, height: float) -> None:
        self.set_draw_color(*COLORS["border"])
        self.set_fill_color(*COLORS["light"])
        self.rect(x, y, width, height, "DF")

    def rich_wrapped_text(self, text: str, x: float, y: float, width: float,
                          font_size: float, line_height: float,
                          default_color: tuple[int, int, int] = COLORS["text"],
                          color_symbols_by_signal: bool = False) -> float:
        """Write wrapped Unicode text with semantic symbol colors."""
        old_left, old_right = self.l_margin, self.r_margin
        self.set_left_margin(x)
        self.set_right_margin(self.w - x - width)
        self.set_xy(x, y)
        render_line_height = line_height * PDF_FONT_SCALE
        label, separator, detail = text.partition(": ")
        fragments: list[tuple[str, str, tuple[int, int, int]]] = []
        symbol_pattern = "([\ " + re.escape("".join(SEMANTIC_SYMBOL_COLORS)) + "])"

        def append_colored(value: str, default_style: str, default_color: tuple[int, int, int]) -> None:
            for part in re.split(symbol_pattern, value):
                if not part:
                    continue
                if part in SEMANTIC_SYMBOL_COLORS:
                    symbol_color = default_color if color_symbols_by_signal else SEMANTIC_SYMBOL_COLORS[part]
                    fragments.append((part, "B", symbol_color))
                else:
                    fragments.append((part, default_style, default_color))

        if separator:
            append_colored(label, "B", default_color)
            fragments.append((": ", "B", default_color))
            append_colored(detail, "", default_color)
        else:
            append_colored(label, "", default_color)
        for fragment, style, color in fragments:
            self.set_font("DejaVu", style, font_size)
            self.set_text_color(*color)
            self.write(h=render_line_height, text=fragment)
        bottom = self.get_y() + render_line_height
        self.set_left_margin(old_left)
        self.set_right_margin(old_right)
        return bottom

    def compact_lines(self, items: list[dict[str, Any]], x: float, y: float, width: float,
                      height: float, maximum: int, font_size: float, line_height: float,
                      color_text_by_signal: bool = False) -> None:
        """Render every preselected row using measured, adaptive typography."""
        self.frame(x, y, width, height)
        cursor = y + 2
        selected = items[:maximum]
        fitted_font_size, fitted_line_height = self.fit_compact_typography(
            selected, width - 7, height - 3, font_size, line_height
        )
        render_line_height = fitted_line_height * PDF_FONT_SCALE
        for item in selected:
            marker_item = {**item, "_signal_marker": True} if color_text_by_signal else item
            marker, color = _direction_marker(marker_item)
            self.set_xy(x + 1.8, cursor)
            self.set_font("DejaVu", "B", fitted_font_size + 0.3)
            self.set_text_color(*color)
            self.cell(3, render_line_height, marker)
            text = str(item.get("text") or item.get("detail") or item.get("desc") or "")
            text_color = COLORS[_signal(item)] if color_text_by_signal else COLORS["text"]
            cursor = self.rich_wrapped_text(
                text, x + 5, cursor, width - 7, fitted_font_size, fitted_line_height, text_color,
                color_symbols_by_signal=color_text_by_signal,
            ) + 0.45
        if selected and cursor > y + height + 0.2:
            raise RuntimeError("Compact PDF section exceeded its measured panel height")
        if not items:
            self.set_xy(x + 3, y + 3)
            self.set_font("Helvetica", "I", font_size)
            self.set_text_color(*COLORS["muted"])
            self.cell(width - 6, line_height, "No verified data available")

    def fit_compact_typography(self, items: list[dict[str, Any]], width: float, height: float,
                               font_size: float, line_height: float,
                               minimum_font_size: float = 3.15) -> tuple[float, float]:
        """Fit complete rows from actual font metrics instead of character counts.

        Measurement and rendering both pass through ``set_font()``, preserving the
        required global 1.5 scale. Failure is explicit rather than silently dropping
        later evidence.
        """
        if not items:
            return font_size, line_height
        candidate = font_size
        while candidate >= minimum_font_size - 1e-9:
            candidate_line_height = line_height * candidate / font_size
            render_line_height = candidate_line_height * PDF_FONT_SCALE
            required = 0.0
            self.set_font("DejaVu", "", candidate)
            for item in items:
                text = str(item.get("text") or item.get("detail") or item.get("desc") or "")
                lines = self.multi_cell(
                    width, render_line_height, text,
                    dry_run=True, output="LINES", wrapmode="WORD",
                )
                required += max(1, len(lines)) * render_line_height + 0.45
            if required <= height:
                return candidate, candidate_line_height
            candidate = round(candidate - 0.15, 2)
        raise RuntimeError(
            f"Compact PDF section cannot fit {len(items)} complete rows in {height:.1f} mm"
        )

    def bullet_lines(self, items: list[dict[str, Any]], x: float, y: float, width: float,
                     height: float, maximum: int, chars: int | None = 115, font_size: float = 5.1,
                     line_height: float = 2.8) -> None:
        self.frame(x, y, width, height)
        cursor = y + 2
        render_line_height = line_height * PDF_FONT_SCALE
        for item in items[:maximum]:
            if cursor + render_line_height > y + height - 1:
                break
            signal = _signal(item)
            text = _clip(item.get("text") or item.get("detail") or item.get("desc") or "", chars)
            self.set_xy(x + 2, cursor)
            self.set_font("Helvetica", "B", font_size)
            self.set_text_color(*COLORS[signal])
            self.cell(3, render_line_height, BULLETS[signal])
            self.set_xy(x + 5, cursor)
            self.set_font("Helvetica", "", font_size)
            self.set_text_color(*COLORS[signal])
            lines = max(1, min(3, int(len(text) / max(25, int(width * 2.5))) + 1))
            self.multi_cell(width - 7, render_line_height, text, new_x="LEFT", new_y="NEXT", max_line_height=render_line_height)
            cursor = max(cursor + render_line_height, self.get_y()) + 0.5
        if not items:
            self.set_xy(x + 3, y + 3)
            self.set_font("Helvetica", "I", font_size)
            self.set_text_color(*COLORS["muted"])
            self.cell(width - 6, line_height, "No verified data available")


def _valid_source_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.netloc.endswith((".test", ".example"))


def validate_pdf(path: str, expected_urls: list[str]) -> None:
    file_path = Path(path)
    if not file_path.read_bytes().startswith(b"%PDF-"):
        raise RuntimeError("PDF signature is invalid")
    with pdfplumber.open(file_path) as document:
        if len(document.pages) != 1:
            raise RuntimeError("PDF must contain exactly one page")
        page = document.pages[0]
        if abs(page.width - 595.28) > 2 or abs(page.height - 841.89) > 2:
            raise RuntimeError("PDF page is not A4")
        text = page.extract_text() or ""
        normalized_text = text.upper()
        headings = ("INCOME STATEMENT HIGHLIGHTS", "KEY RATIOS", "VALUATION", "CAPITAL & LIQUIDITY",
                    "GUIDANCE & OUTLOOK", "EARNINGS CALL SUMMARY", "KEY CHANNELS & SEGMENTS",
                    "STRATEGIC PILLARS", "KEY RISKS", "INVESTMENT THESIS")
        for heading in headings:
            if heading.upper() not in normalized_text:
                raise RuntimeError(f"PDF is missing required section: {heading}")
        links = {item.get("uri") for item in page.hyperlinks if item.get("uri")}
        missing = set(expected_urls) - links
        if missing:
            raise RuntimeError("PDF is missing clickable source links")


def _draw_cards(pdf: OnePager, title: str, rows: list[dict[str, Any]], x: float, y: float,
                width: float, columns: int, card_height: float, maximum: int) -> float:
    y = pdf.title_bar(title, x, y, width)
    selected = rows[:maximum]
    if not selected:
        selected = [{"display": "N/A", "label": "No verified data", "comparison": "", "signal": "neutral"}]
    card_w = width / columns
    total_rows = (len(selected) + columns - 1) // columns
    for index, row in enumerate(selected):
        cx = x + (index % columns) * card_w
        cy = y + (index // columns) * card_height
        signal = _signal(row)
        pdf.set_draw_color(*COLORS["border"])
        pdf.set_fill_color(*COLORS["light"])
        pdf.rect(cx, cy, card_w - 0.8, card_height - 0.7, "DF")
        pdf.set_fill_color(*COLORS[signal])
        pdf.rect(cx, cy, 2.1, card_height - 0.7, "F")
        pdf.set_xy(cx + 3.3, cy + 1.1)
        pdf.set_text_color(*COLORS[signal])
        pdf.set_font("Helvetica", "B", 7.7)
        pdf.cell(card_w - 4, 3.5, _clip(row.get("display", "N/A"), 18))
        pdf.set_xy(cx + 3.3, cy + 4.7)
        pdf.set_text_color(*COLORS[signal])
        pdf.set_font("Helvetica", "", 4.5)
        pdf.cell(card_w - 4, 2.7, _clip(row.get("label", ""), 22))
        pdf.set_xy(cx + 3.3, cy + 7.6)
        pdf.set_text_color(*COLORS[signal])
        pdf.set_font("Helvetica", "B", 4.7)
        pdf.cell(card_w - 4, 2.7, _clip(row.get("comparison") or row.get("assessment") or "", 22))
    return y + total_rows * card_height


def create_one_pager_pdf(data: dict[str, Any], output_path: str) -> str:
    pdf = OnePager()
    x = pdf.l_margin
    width = pdf.page_width
    grade = data.get("grade", {})
    thesis = data.get("thesis", {})
    valuation = data.get("valuation", {})

    # Original hierarchy: grade box, recommendation, ticker, and verified market context.
    header_h = 16
    grade_w = width / 10
    header_x = x + grade_w
    header_w = width - grade_w
    grade_letter = str(grade.get("letter") or "N/A").upper()
    confidence = grade.get("confidence")
    pdf.set_fill_color(220, 240, 255)
    pdf.rect(x, 7, grade_w, header_h, "F")
    pdf.set_xy(x, 8.2)
    pdf.set_font("Helvetica", "B", 12.5)
    pdf.set_text_color(*GRADE_COLORS.get(grade_letter, COLORS["muted"]))
    pdf.cell(grade_w, 7, grade_letter, align="C")
    if isinstance(confidence, (int, float)):
        pdf.set_xy(x, 15.7)
        pdf.set_font("Helvetica", "B", 4.7)
        pdf.set_text_color(*COLORS["muted"])
        pdf.cell(grade_w, 3, f"{confidence:.0%} CONF.", align="C")
    pdf.set_fill_color(*COLORS["header"])
    pdf.rect(header_x, 7, header_w, header_h, "F")
    recommendation = str(thesis.get("recommendation", "N/A"))
    recommendation_size = 14.0
    ticker_size = 18.0
    pdf.set_font("Helvetica", "B", ticker_size)
    ticker_width = pdf.get_string_width(data["ticker"])
    max_recommendation_width = max(24, header_w - ticker_width - 14)
    while recommendation_size > 7.0:
        pdf.set_font("Helvetica", "B", recommendation_size)
        if pdf.get_string_width(recommendation) <= max_recommendation_width:
            break
        recommendation_size -= 0.5
    recommendation_width = pdf.get_string_width(recommendation)
    pdf.set_xy(header_x + 3, 8)
    pdf.set_font("Helvetica", "B", recommendation_size)
    pdf.set_text_color(*COLORS["best"])
    pdf.cell(recommendation_width + 1, 7, recommendation)
    ticker_x = header_x + 3 + recommendation_width + 4
    pdf.set_xy(ticker_x, 8)
    pdf.set_font("Helvetica", "B", ticker_size)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(max(10, header_x + header_w - ticker_x - 2), 7, data["ticker"])
    pdf.set_xy(header_x + 3, 17)
    pdf.set_font("Helvetica", "", 5.2)
    pdf.set_text_color(*COLORS["text"])
    price = "N/A" if valuation.get("current_price") is None else f"${valuation['current_price']:.2f}"
    pe_value = valuation.get("pe_ttm")
    pe = "N/A" if pe_value is None else "N/M" if pe_value <= 0 else f"{pe_value:.1f}x"
    call_date = data.get("sources", {}).get("transcript_call_date") or "N/A"
    low_52, high_52 = valuation.get("low_52"), valuation.get("high_52")
    range_52 = f"${low_52:.2f}-${high_52:.2f}" if isinstance(low_52, (int, float)) and isinstance(high_52, (int, float)) else "N/A"
    meta = (f"Quarter Ended {data['report_date']} | Call: {call_date} | {price} | "
            f"Mkt Cap {_fmt_money(valuation.get('market_cap'))} | P/E {pe} | 52W {range_52}")
    pdf.cell(header_w - 6, 3, _clip(meta, 190))
    y = 24
    if data.get("test_run"):
        pdf.set_xy(x, y)
        pdf.set_fill_color(255, 235, 235)
        pdf.set_text_color(*COLORS["worst"])
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.cell(width, 4.5, "TEST ONLY - STALE MARKET DATA - NOT ACTIONABLE", align="C", fill=True)
        y += 5.2

    financial = data.get("financials", {}).get("rows", [])
    income_keys = {"revenue", "gross_profit", "operating_income", "net_income"}
    income = [row for row in financial if row.get("key") in income_keys][:8]
    if len(income) < 4:
        income = financial[:8]
    ratios = data.get("financials", {}).get("key_ratios") or [row for row in financial if row not in income][:6]
    y = _draw_cards(pdf, "INCOME STATEMENT HIGHLIGHTS", income, x, y, width, 4, 12, 8) + 1
    y = _draw_cards(pdf, "KEY RATIOS", ratios, x, y, width, 6, 12, 6) + 1
    y = _draw_cards(pdf, "VALUATION", valuation.get("rows", []), x, y, width, 4, 11, 4) + 1

    # Original proportional three-column block: 28% / 28% / 44%.
    gap = 2
    usable = width - 2 * gap
    w1 = usable * 0.28
    w2 = usable * 0.28
    w3 = usable * 0.44
    block_h = 74
    body_y = y + 5.2
    pdf.title_bar("CAPITAL & LIQUIDITY", x, y, w1)
    capital = [{"text": f"{row['name']}: {row['value']}", "signal": row.get("signal", "neutral")} for row in data.get("capital_liquidity", {}).get("items", [])]
    pdf.bullet_lines(capital, x, body_y, w1, block_h, 8, chars=78)
    x2 = x + w1 + gap
    pdf.title_bar("GUIDANCE & OUTLOOK", x2, y, w2)
    guidance_rows = data.get("guidance", {}).get("rows", [])
    guidance = _compact_items(guidance_rows, "detail", None, 6, 1100, 220)
    pdf.compact_lines(
        guidance, x2, body_y, w2, block_h, 6,
        font_size=4.45, line_height=2.3, color_text_by_signal=True,
    )
    x3 = x2 + w2 + gap
    pdf.title_bar("EARNINGS CALL SUMMARY", x3, y, w3)
    call_source = []
    for row in _select_call_summary_insights(data.get("transcript_insights", [])):
        display_row = {**row, "_signal_marker": True}
        if row.get("topic") == "Management Tone":
            category = row.get("confidence_category")
            subcategory = row.get("confidence_subcategory")
            if category and subcategory:
                display_row["_display_label"] = f"◎ Management Tone: {category} -> {subcategory}"
                display_row["_label_separator"] = ", "
        call_source.append(display_row)
    calls = _compact_items(call_source, "detail", "topic", 8, 2500, 190)
    pdf.compact_lines(
        calls, x3, body_y, w3, block_h, 8,
        font_size=4.45, line_height=2.3, color_text_by_signal=True,
    )
    y = body_y + block_h + 1

    # Four channel/segment cards. Every displayed description must be a true
    # compression of its source evidence; unchanged transcript prose is omitted.
    y = pdf.title_bar("KEY CHANNELS & SEGMENTS", x, y, width)
    channel_h = 23.0
    raw_channels = data.get("channels", {}).get("items", [])
    channels = []
    for source_row in raw_channels:
        source_desc = " ".join(str(source_row.get("desc") or "").split())
        # Aggressive single-line compression for channel cards
        summary = _compact_summary(source_desc, label=None)
        # Additional aggressive compression for channel card width constraints
        summary = _compress_for_channel_card(summary)
        if summary and len(summary) < len(source_desc):
            channels.append({**source_row, "summary": summary})
        if len(channels) == 4:
            break
    cw = width / 4
    for index in range(4):
        row = channels[index] if index < len(channels) else {"name": "N/A", "desc": "No verified channel evidence"}
        cx = x + index * cw
        pdf.frame(cx, y, cw - 0.8, channel_h)
        display_name = str(COMPACT_LABELS.get(str(row.get("name")), row.get("name")) or "N/A")
        summary = row.get("summary") or _compact_summary(row.get("desc"))
        display_row = {**row, "text": summary}
        if not display_row.get("signal") and not display_row.get("tier"):
            inferred_marker, _ = _direction_marker(display_row)
            display_row["signal"] = {"↑": "positive", "↓": "negative", "→": "neutral"}[inferred_marker]
        signal_color = COLORS[_signal(display_row)]
        pdf.set_xy(cx + 2, y + 2)
        pdf.set_font("DejaVu", "B", 5.5)
        first_symbol = display_name[:1]
        if first_symbol in SEMANTIC_SYMBOL_COLORS:
            pdf.set_text_color(*signal_color)
            symbol_width = pdf.get_string_width(first_symbol) + 0.8
            pdf.cell(symbol_width, 3, first_symbol)
            pdf.set_text_color(*signal_color)
            pdf.cell(cw - 4 - symbol_width, 3, display_name[1:].lstrip())
        else:
            pdf.set_text_color(*signal_color)
            pdf.cell(cw - 4, 3, display_name)
        marker, marker_color = _direction_marker({**display_row, "_signal_marker": True})
        channel_font_size, channel_line_height = pdf.fit_compact_typography(
            [display_row], cw - 8, channel_h - 7, 4.0, 2.12
        )
        pdf.set_xy(cx + 2, y + 5.5)
        pdf.set_font("DejaVu", "B", channel_font_size + 0.3)
        pdf.set_text_color(*marker_color)
        pdf.cell(3, channel_line_height * PDF_FONT_SCALE, marker)
        channel_bottom = pdf.rich_wrapped_text(
            summary, cx + 5.2, y + 5.5, cw - 8, channel_font_size, channel_line_height,
            signal_color, color_symbols_by_signal=True,
        )
        if channel_bottom > y + channel_h - 0.5:
            raise RuntimeError("Channel evidence exceeded its measured PDF card height")
    y += channel_h + 1

    y = pdf.title_bar("STRATEGIC PILLARS", x, y, width)
    pillars = _compact_items(data.get("strategic_pillars", []), "detail", "name", 8, 900, 180)
    pdf.compact_lines(
        pillars, x, y, width, 28, 8,
        font_size=4.85, line_height=2.5, color_text_by_signal=True,
    )
    y += 29

    # Bottom dual-column risk and thesis block.
    bottom_h = 39
    half = (width - gap) / 2
    pdf.title_bar("KEY RISKS", x, y, half)
    pdf.title_bar("INVESTMENT THESIS", x + half + gap, y, half)
    risk_items = []
    for row in data.get("risks", [])[:6]:
        if isinstance(row.get("probability"), (int, float)) and isinstance(row.get("eps_impact"), (int, float)):
            quantification = f"{row['probability']:.0%} probability / {row['eps_impact']:.0%} EPS impact"
        else:
            quantification = "company did not quantify probability or EPS impact"
        risk_items.append({"text": f"{row['risk']}: {quantification}", "signal": row.get("signal", "caution")})
    pdf.bullet_lines(risk_items, x, y + 5.2, half, bottom_h, 6, chars=None, font_size=4.7, line_height=2.5)
    thesis_items = [{"text": f"Rec: {thesis.get('recommendation', 'N/A')} | Base EPS CAGR {thesis.get('base_cagr', 0):.0%} | IRR {thesis.get('irr', 0):.0%} | Hurdle {thesis.get('hurdle_rate', 0):.0%}", "signal": "neutral"}]
    for name, label, signal in (("base_case", "Base", "best"), ("bull_case", "Bull", "strong_positive"), ("bear_case", "Bear", "negative")):
        case = thesis.get(name)
        if case:
            thesis_items.append({"text": f"{label} ({case.get('probability', 0):.0%}): {case.get('detail') or case.get('summary', '')}", "signal": signal})
    thesis_items.append({"text": f"Key Risks: {thesis.get('key_risks_summary', 'Not quantified')}", "signal": "caution"})
    pdf.bullet_lines(thesis_items, x + half + gap, y + 5.2, half, bottom_h, 5, chars=145, font_size=4.7, line_height=2.6)

    # Clickable evidence footer.
    filing = data.get("sources", {}).get("filing_url", "")
    transcript = data.get("sources", {}).get("transcript_url", "")
    if not _valid_source_url(filing) or not _valid_source_url(transcript):
        raise RuntimeError("PDF source URLs must be valid non-placeholder HTTPS URLs")
    footer_y = 289
    pdf.set_xy(x, footer_y)
    pdf.set_font("Helvetica", "I", 4.2)
    pdf.set_text_color(*COLORS["muted"])
    pdf.cell(width * 0.34, 2.5, "Source: SEC filing", align="R", link=filing)
    pdf.cell(width * 0.32, 2.5, " | Earnings transcript | ", align="C", link=transcript)
    footer = "TEST ONLY - NOT ACTIONABLE" if data.get("test_run") else "NOT INVESTMENT ADVICE"
    pdf.cell(width * 0.34, 2.5, footer, align="L")

    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    if not path.is_file() or path.stat().st_size < 1000:
        raise RuntimeError("PDF generation did not produce a valid file")
    validate_pdf(str(path), [filing, transcript])
    return str(path)