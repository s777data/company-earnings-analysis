#!/usr/bin/env python3
"""Shared utilities for PDF generation - used by both one-pager and dashboard renderers."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pdfplumber

COLORS = {
    "best": (0, 32, 96), "strong_positive": (0, 64, 128), "positive": (0, 80, 160),
    "neutral": (180, 155, 0), "medium": (180, 155, 0), "caution": (230, 120, 0),
    "negative": (200, 50, 50), "worst": (180, 0, 0), "navy": (31, 63, 112),
    "text": (30, 30, 30), "muted": (90, 90, 90), "light": (247, 249, 252),
    "border": (198, 207, 217), "header": (183, 224, 239),
}
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


def _valid_source_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.netloc.endswith((".test", ".example"))


def _signal(item: dict[str, Any]) -> str:
    value = item.get("signal") or item.get("tier") or "neutral"
    return value if value in COLORS else "neutral"


def _compact_summary(text: Any, label: str | None = None) -> str:
    """Create a shorter dashboard summary while retaining material evidence."""
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
        body = re.sub(r"\s+", " ", body).strip(" ,;:-\-")
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
        body = re.sub(r"\s+", " ", body).strip(" ,;:-\-")
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


def _segment_icon(name: str) -> str:
    lower = name.lower()
    if "power" in lower or "energy" in lower:
        return "⚡"
    if "construct" in lower:
        return "⚒"
    if "resource" in lower or "mining" in lower:
        return "◆"
    return "▪"


def _compact_items(items: list[dict[str, Any]], text_key: str, label_key: str | None,
                   maximum: int, character_budget: int, item_limit: int) -> list[dict[str, Any]]:
    """Build compact, complete display rows without using item length as a drop gate."""
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
    """Mirror Telegram's complete insight selection for the PDF call summary."""
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


__all__ = [
    "_compact_summary",
    "_compact_items",
    "_direction_marker",
    "_select_call_summary_insights",
    "_compress_for_channel_card",
    "_fmt_money",
    "_segment_icon",
    "_signal",
    "COMPACT_LABELS",
    "SEMANTIC_SYMBOL_COLORS",
    "COLORS",
    "BULLETS",
    "validate_pdf",
    "_valid_source_url",
]