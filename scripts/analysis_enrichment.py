#!/usr/bin/env python3
"""Generic, evidence-linked enrichment for rich earnings dashboards.

This module intentionally contains methodology, not ticker-specific facts. Every
company statement comes from the supplied SEC filing/XBRL data or transcript.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

SIGNALS = ("best", "strong_positive", "positive", "neutral", "caution", "negative", "worst")
SIGNAL_EMOJIS = {
    "best": "🟦", "strong_positive": "🔷", "positive": "🔵", "neutral": "🟡",
    "caution": "🟠", "negative": "🔴", "worst": "🟥",
}

# CapEx Color Scoring - 80% CapEx/Revenue intensity, 20% YoY growth
# Percentile-based scoring for historical/peer comparison
CAPEX_COLOR_THRESHOLDS = [
    (20, "best", "Very low financial burden"),
    (40, "strong_positive", "Low / manageable"),
    (60, "positive", "Moderate"),
    (80, "caution", "High"),
    (101, "negative", "Very high financial burden"),
]

# Historical CapEx/Revenue and CapEx YoY data for percentile ranking
# This can be populated from historical data or peer companies
CAPEX_HISTORICAL_DATA = {
    "capex_revenue_pct": [],  # List of historical CapEx/Revenue percentages
    "capex_yoy": [],          # List of historical CapEx YoY growth rates
}

# Methodology-level rules; these apply uniformly to every company.
TOPICS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Management Tone", "outlook", ("confident", "optimistic", "cautious", "uncertain", "outlook")),
    ("Revenue & Demand", "revenue", ("revenue", "sales", "demand", "orders", "bookings", "volume")),
    ("Margins & Profitability", "margin", ("margin", "profitability", "operating income", "gross profit")),
    ("Guidance", "guidance", ("guidance", "we expect", "we anticipate", "we forecast", "outlook")),
    ("Products & Innovation", "product", ("product", "platform", "innovation", "launch", "technology", "research")),
    ("Customers & Engagement", "customer", ("customer", "user", "engagement", "retention", "subscriber", "client")),
    ("Capital Allocation", "capital", ("capital expenditure", "capex", "buyback", "repurchase", "dividend", "investment")),
    ("Competition & Market", "competition", ("competition", "competitive", "market share", "pricing", "industry")),
]
RISK_TOPICS: list[tuple[str, tuple[str, ...]]] = [
    ("Competitive pressure", ("competition", "competitive pressure", "market share loss", "pricing pressure")),
    ("Regulatory / legal exposure", ("regulatory", "litigation", "legal proceeding", "investigation", "compliance")),
    ("Demand / macro exposure", ("headwind", "macroeconomic", "recession", "demand weakness", "slowdown")),
    ("Capital intensity / cash-flow pressure", ("capital expenditures", "capex", "cash flow pressure", "investment cycle")),
    ("Supply / execution exposure", ("supply constraint", "shortage", "execution risk", "delay", "disruption")),
]
PILLAR_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Innovation Roadmap", ("innovation", "technology", "product roadmap", "platform", "artificial intelligence", " ai ")),
    ("Growth Expansion", ("expand", "growth opportunity", "new market", "international", "capacity", "demand growth")),
    ("Customer Value", ("customer value", "customer success", "retention", "engagement", "services")),
    ("Operational Excellence", ("efficiency", "productivity", "manufacturing", "cost reduction", "operations")),
    ("Capital Discipline", ("free cash flow", "share repurchase", "repurchases", "dividend", "capital allocation")),
    ("Long-Term Strategy", ("long-term", "strategy", "strategic", "2030", "future")),
]
POSITIVE = ("accelerat", "beat", "confident", "exceed", "growth", "improv", "increase", "raise", "record", "strong",
            "advance", "expand", "on track", "scale")
NEGATIVE = ("cautious", "declin", "decrease", "headwind", "lower", "miss", "pressure", "risk", "slow", "uncertain", "weak")

# Ordered confidence taxonomy supplied by the reporting contract. Classification
# is performed once during transcript enrichment; Telegram and PDF only render
# the resulting structured fields.
CONFIDENCE_TAXONOMY: tuple[tuple[str, str, int, tuple[tuple[str, int], ...]], ...] = (
    ("Confident", "Resolute", 1, (("remain committed", 5), ("committed", 4),
                                  ("no doubt", 5), ("without question", 5),
                                  ("we will", 3), ("will continue", 2), ("must", 2))),
    ("Confident", "Authoritative", 2, (("we know", 4), ("we have demonstrated", 4),
                                       ("proven", 3), ("clear that", 3),
                                       ("track record", 3), ("we delivered", 2))),
    ("Confident", "Decisive", 3, (("we have decided", 5), ("we decided", 5),
                                  ("we are taking", 4), ("we took", 4),
                                  ("we are executing", 4), ("moving forward", 3),
                                  ("we launched", 3))),
    ("Confident", "Assured", 4, (("we expect", 3), ("we anticipate", 3),
                                 ("we believe", 2), ("confident", 4),
                                 ("confidence", 4), ("on track", 4), ("strong", 1))),
    ("Vague", "Evasive", 1, (("cannot comment", 6), ("can't comment", 6),
                              ("not prepared to", 5), ("will not speculate", 6),
                              ("won't speculate", 6), ("cannot disclose", 5))),
    ("Vague", "Equivocal", 2, (("on the one hand", 5), ("on the other hand", 5),
                               ("could go either", 6), ("depends on", 3),
                               ("difficult to predict", 4), ("uncertain", 3))),
    ("Vague", "Noncommittal", 3, (("may", 1), ("might", 2), ("could", 1),
                                  ("possibly", 2), ("potentially", 1),
                                  ("we are evaluating", 3))),
    ("Vague", "Ambiguous", 4, (("over time", 1), ("in the future", 1),
                               ("various", 1), ("some opportunities", 2),
                               ("flexibility", 1), ("as appropriate", 2))),
    ("Not Confident", "Defensive / Faltering", 1, (("let me be clear", 5),
                                                     ("to be clear", 3),
                                                     ("we disagree", 5),
                                                     ("not accurate", 5),
                                                     ("misunderstanding", 4))),
    ("Not Confident", "Anxious", 2, (("concerned", 4), ("worried", 5),
                                     ("challenging", 2), ("pressure", 2),
                                     ("headwind", 3), ("risk", 1))),
    ("Not Confident", "Hesitant", 3, (("i guess", 1), ("probably", 1),
                                      ("hard to say", 5), ("not sure", 5))),
    ("Not Confident", "Tentative", 4, (("we hope", 4), ("we intend", 2),
                                       ("we plan", 2), ("we aim", 3),
                                       ("our target", 1))),
)
BOILERPLATE = (
    "press star", "telephone keypad", "withdraw your question", "call is being recorded",
    "operator instructions", "transcript summary record", "load transcript", "download transcript",
    "cookie", "privacy policy", "seeking alpha", "stockanalysis.com", "copyright",
    "joining me today", "conference call participants", "chief financial officer,", "senior vice president of",
    "welcome to today's conference call",
)
PARTICIPANT_TITLE_TERMS = (
    "equity research analyst", "research analyst", "managing director",
    "chief executive officer", "chief financial officer", "investor relations",
)
QA_SECTION_HEADINGS = {
    "question and answer",
    "question and answer session",
    "questions and answers",
    "questions and answers session",
    "q and a",
    "q and a session",
    "q a",
    "q a session",
}
ANALYST_ROLE_TERMS = (
    "analyst", "equity research", "research analyst", "managing director",
)
MANAGEMENT_ROLE_TERMS = (
    "chief executive officer", "chief financial officer", "chief operating officer",
    "chief technology officer", "chief revenue officer", "chief accounting officer",
    "president and ceo", "founder and ceo", "co-founder and ceo",
    "evp and cfo", "svp and cfo", "investor relations", " ceo", " cfo", " coo",
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" \t\r\n-|")


def _qa_boundary_start(text: str) -> int:
    """Locate the Q&A transition using transcript lines, not a heading regex.

    Providers do not consistently emit a literal ``Question-and-Answer``
    heading. StockAnalysis commonly begins the section with operator prose such
    as ``Your first question today comes from``. This detector recognizes both
    normalized headings and unambiguous operator transitions while retaining the
    original character offset used by evidence citations.
    """
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        normalized = raw_line.casefold()
        for character in "-–—:&./":
            normalized = normalized.replace(character, " ")
        normalized = " ".join(normalized.split())
        words = set(normalized.split())

        is_heading = normalized in QA_SECTION_HEADINGS
        is_first_question = (
            "first question" in normalized
            and any(phrase in normalized for phrase in ("comes from", "take", "go to", "is from"))
        )
        is_operator_handoff = any(phrase in normalized for phrase in (
            "open the call for questions",
            "ready for questions",
            "operator for questions",
            "begin the question portion",
            "one moment for questions",
            "kick off the q",
            "go to questions",
            "turn to questions",
            "open up the call",
            "turn the call back over to the operator",
            "turn the call over to",
            "get our q a started",
            "get our q&a started",
        ))
        # A heading may include decorative words, but it must still consist only
        # of Q&A/session vocabulary after punctuation normalization.
        is_heading_variant = (
            bool({"question", "questions"} & words)
            and bool({"answer", "answers"} & words)
            and words <= {"question", "questions", "and", "answer", "answers", "session"}
        )
        # Also detect "Q&A" or "Q A" in a short line as a heading variant
        is_qa_heading = normalized in {"q a", "q&a", "q a started", "q&a started", "begin q a", "begin q&a"}
        if is_heading or is_heading_variant or is_first_question or is_operator_handoff or is_qa_heading:
            return offset
        offset += len(raw_line)
    return len(text)


def _speaker_role_markers(text: str) -> list[tuple[int, str]]:
    """Return source offsets where transcript speaker roles change."""
    markers: list[tuple[int, str]] = [(0, "unknown")]
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        normalized = " ".join(raw_line.casefold().replace(":", " ").split())
        word_count = len(normalized.split())
        role = None
        if word_count <= 4 and normalized.startswith("operator"):
            role = "operator"
        elif word_count <= 18 and any(term in normalized for term in ANALYST_ROLE_TERMS):
            role = "analyst"
        elif word_count <= 24 and any(term in f" {normalized}" for term in MANAGEMENT_ROLE_TERMS):
            role = "management"
        if role and role != markers[-1][1]:
            markers.append((offset, role))
        offset += len(raw_line)
    return markers


def _speaker_role_at(markers: list[tuple[int, str]], offset: int) -> str:
    role = "unknown"
    for marker_offset, marker_role in markers:
        if marker_offset > offset:
            break
        role = marker_role
    return role


def _is_participant_label(text: str) -> bool:
    """Reject speaker-name/title rows that are not substantive call evidence."""
    lower = text.lower().strip(" .,:;-")
    evidence_cues = (
        "revenue", "sales", "demand", "margin", "profit", "guidance", "outlook",
        "product", "customer", "growth", "increase", "decrease", "cash flow", "%", "$",
    )
    return (len(lower.split()) <= 20
            and any(title in lower for title in PARTICIPANT_TITLE_TERMS)
            and not any(cue in lower for cue in evidence_cues)
            and not re.search(r"\d", lower))


def _sentences(text: str) -> list[dict[str, Any]]:
    """Return complete, source-offset sentences while excluding provider/operator noise."""
    qa_start = _qa_boundary_start(text)
    speaker_roles = _speaker_role_markers(text)
    rows: list[dict[str, Any]] = []
    # Protect decimal points during boundary detection without changing offsets.
    scan_text = re.sub(r"(?<=\d)\.(?=\d)", "·", text)
    # Keep offsets in original text. Newlines are also boundaries for transcript speakers.
    for match in re.finditer(r"[^.!?\n]{25,}(?:[!?]+|\.|(?=\n|$))", scan_text):
        sentence = _clean(text[match.start():match.end()])
        lower = sentence.lower()
        if len(sentence) < 45 or len(sentence) > 520 or len(sentence.split()) < 7:
            continue
        if sentence[:1].islower():
            continue
        if any(noise in lower for noise in BOILERPLATE):
            continue
        if _is_participant_label(sentence):
            continue
        if lower.startswith(("operator:", "operator ", "editor's note", "company participants", "conference call participants")):
            continue
        rows.append({"text": sentence, "start": match.start(), "end": match.end(),
                     "section": "Analyst Q&A" if match.start() >= qa_start else "Prepared Remarks",
                     "speaker_role": _speaker_role_at(speaker_roles, match.start())})
    return rows


def _is_question(text: str) -> bool:
    lower = text.lower().strip()
    cues = (
        "my question", "core question", "can you", "could you", "would you",
        "how do you", "how you think about", "what is your", "what you're assuming",
        "what are you", "any color", "i guess i want to", "i want to ask",
        "i wanted to ask", "i'd like to ask", "i would like to ask", "maybe one on",
        "wondering if", "just wondering",
    )
    return (_is_participant_label(text) or lower.endswith("?")
            or lower.startswith(("analyst:", "operator:")) or any(cue in lower for cue in cues))


def _is_usable_evidence(row: dict[str, Any]) -> bool:
    """Allow prepared remarks and verified management answers, never analyst prompts."""
    if row.get("section") != "Analyst Q&A":
        return True
    return row.get("speaker_role") == "management" and not _is_question(str(row.get("text") or ""))


def _phrase_count(text: str, phrase: str) -> int:
    """Count complete words/phrases; never match `confident` in `confidential`."""
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in phrase.split()) + r"(?!\w)"
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def _keyword_count(text: str, keyword: str) -> int:
    if keyword == "confident":
        return len(re.findall(r"(?<!\w)confiden(?:t|ce)(?!\w)", text, flags=re.IGNORECASE))
    return text.lower().count(keyword.lower())


def classify_management_confidence(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Classify management's aggregate call language using the approved taxonomy."""
    management_rows = [
        row for row in rows
        if _is_usable_evidence(row)
        and (row.get("section") != "Analyst Q&A" or row.get("speaker_role") == "management")
    ]
    corpus = " ".join(str(row.get("text") or "") for row in management_rows)
    if not corpus.strip():
        return {
            "confidence_category": "Vague",
            "confidence_subcategory": "Ambiguous",
            "confidence_rank": 4,
            "confidence_reasoning": "No substantive management language was available for a stronger confidence classification.",
        }

    scores: dict[tuple[str, str], int] = {}
    matched: dict[tuple[str, str], list[str]] = {}
    ranks: dict[tuple[str, str], int] = {}
    category_scores = {"Confident": 0, "Vague": 0, "Not Confident": 0}
    for category, subcategory, rank, cues in CONFIDENCE_TAXONOMY:
        key = (category, subcategory)
        score = 0
        cue_hits: list[str] = []
        for phrase, weight in cues:
            count = _phrase_count(corpus, phrase)
            if count:
                score += count * weight
                cue_hits.append(f"{phrase} ({count})")
        scores[key] = score
        matched[key] = cue_hits
        ranks[key] = rank
        category_scores[category] += score

    if not any(category_scores.values()):
        category, subcategory = "Vague", "Ambiguous"
    else:
        # On equal aggregate evidence, prefer the more conservative category.
        conservative_tie_break = {"Confident": 0, "Vague": 1, "Not Confident": 2}
        category = max(category_scores, key=lambda value: (category_scores[value], conservative_tie_break[value]))
        options = [key for key in scores if key[0] == category]
        category, subcategory = max(options, key=lambda key: (scores[key], -ranks[key]))

    key = (category, subcategory)
    evidence = ", ".join(matched[key][:3]) or "no dominant lexical cue"
    return {
        "confidence_category": category,
        "confidence_subcategory": subcategory,
        "confidence_rank": ranks.get(key, 4),
        "confidence_reasoning": (
            f"Aggregate management-language scores were Confident {category_scores['Confident']}, "
            f"Vague {category_scores['Vague']}, and Not Confident {category_scores['Not Confident']}; "
            f"the leading {subcategory.lower()} cues were {evidence}."
        ),
    }


def _signal(text: str) -> str:
    lower = text.lower()
    positive = sum(_keyword_count(lower, word) for word in POSITIVE)
    negative = sum(_keyword_count(lower, word) for word in NEGATIVE)
    if positive >= negative + 3: return "best"
    if positive >= negative + 2: return "strong_positive"
    if positive > negative: return "positive"
    if negative >= positive + 3: return "worst"
    if negative >= positive + 2: return "negative"
    if negative > positive: return "caution"
    return "neutral"


def classify_financial_signal(metric: str, change: float | None, 
                              value: float | None = None,
                              revenue: float | None = None,
                              prior_value: float | None = None) -> str:
    if change is None: return "neutral"
    name = metric.lower()
    # A falling diluted weighted-average share count is anti-dilutive and usually
    # consistent with net repurchases, while a rising count signals dilution.
    # Share count alone does not prove the cause; capital-allocation evidence is
    # required before describing the movement as a buyback.
    if "share" in name:
        if change <= -0.05: return "strong_positive"
        if change < 0: return "positive"
        if change <= 0.02: return "neutral"
        if change < 0.05: return "caution"
        if change < 0.10: return "negative"
        return "worst"
    # CapEx - use new CapEx color scoring based on CapEx/Revenue percentile
    if "capex" in name or "capital expenditure" in name:
        if value is not None and revenue is not None and revenue > 0:
            # Calculate CapEx intensity score
            signal, _ = _capex_color_score(value, revenue, change)
            return signal
    # Expense/capex/debt growth is not automatically good.
    inverse = any(word in name for word in ("capex", "capital expenditure", "debt", "liabilit", "expense", "cost"))
    if inverse:
        if change <= -0.10: return "positive"
        if change < 0: return "neutral"
        if change < 0.10: return "caution"
        if change < 0.25: return "negative"
        return "worst"
    value = change
    income_like = any(word in name for word in ("income", "profit", "cash flow", "eps", "ebitda"))
    thresholds = (0.50, 0.25, 0.10, 0.00, -0.15, -0.30) if income_like else (0.30, 0.20, 0.10, 0.05, 0.00, -0.10)
    if value >= thresholds[0]: return "best"
    if value >= thresholds[1]: return "strong_positive"
    if value >= thresholds[2]: return "positive"
    if value >= thresholds[3]: return "neutral"
    if value >= thresholds[4]: return "caution"
    if value >= thresholds[5]: return "negative"
    return "worst"


def classify_valuation_signal(name: str, value: float | None) -> tuple[str, str]:
    if value is None: return "neutral", "Unavailable"
    key = name.lower()
    if "yield" not in key and value <= 0:
        return "caution", "Not meaningful"
    if "yield" in key:
        cuts = [(6, "best", "Attractive"), (4, "strong_positive", "Strong"), (2.5, "positive", "Healthy"),
                (1.5, "neutral", "Fair"), (.8, "caution", "Low"), (.3, "negative", "Minimal")]
        for floor, signal, label in cuts:
            if value >= floor: return signal, label
        return "worst", "Extreme"
    if "p/s" in key:
        cuts = [(1.5, "best", "Cheap"), (3, "strong_positive", "Attractive"), (5, "positive", "Fair"),
                (8, "neutral", "Moderate"), (12, "caution", "Premium"), (20, "negative", "Expensive")]
    elif "p/e" in key:
        cuts = [(12, "best", "Cheap"), (18, "strong_positive", "Attractive"), (25, "positive", "Fair"),
                (35, "neutral", "Moderate"), (50, "caution", "Premium"), (80, "negative", "Expensive")]
    else:
        cuts = [(10, "best", "Cheap"), (15, "strong_positive", "Attractive"), (20, "positive", "Fair"),
                (30, "neutral", "Moderate"), (40, "caution", "Premium"), (60, "negative", "Expensive")]
    for ceiling, signal, label in cuts:
        if value < ceiling: return signal, label
    return "worst", "Extreme"


def extract_transcript_sections(text: str, url: str, maximum: int = 10) -> dict[str, Any]:
    candidates = _sentences(text)
    if not candidates:
        raise RuntimeError("TRANSCRIPT_ANALYSIS_FAILED: no coherent transcript sentences survived validation")
    insights: list[dict[str, Any]] = []
    used: set[str] = set()
    for topic, category, terms in TOPICS:
        ranked = []
        for sentence in candidates:
            lower = sentence["text"].lower()
            if not _is_usable_evidence(sentence):
                continue
            hits = sum(bool(_keyword_count(lower, term)) for term in terms)
            if not hits: continue
            score = (hits * 5 + (2 if re.search(r"\d", sentence["text"]) else 0)
                     + (3 if sentence["section"] == "Prepared Remarks" else 0)
                     - (5 if sentence["text"].rstrip().endswith("?") else 0))
            ranked.append((score, sentence))
        if not ranked: continue
        ranked.sort(key=lambda item: (item[0], -abs(len(item[1]["text"]) - 165)), reverse=True)
        sentence = next((item[1] for item in ranked if item[1]["text"] not in used), None)
        if not sentence: continue
        used.add(sentence["text"])
        signal = _signal(sentence["text"])
        direction = "supportive" if signal in {"best", "strong_positive", "positive"} else "adverse" if signal in {"negative", "worst"} else "mixed or monitoring"
        insights.append({"topic": topic, "category": category, "detail": sentence["text"], "signal": signal, "tier": signal,
                         "reasoning": f"The cited {sentence['section'].lower()} evidence is {direction} for {topic.lower()}.",
                         "section": sentence["section"],
                         "citation": {"source": "earnings call transcript", "url": url,
                                      "start": sentence["start"], "end": sentence["end"]}})
    confidence = classify_management_confidence(candidates)
    for insight in insights:
        if insight.get("topic") == "Management Tone":
            category = confidence["confidence_category"]
            subcategory = confidence["confidence_subcategory"]
            cues = next(
                row[3] for row in CONFIDENCE_TAXONOMY
                if row[0] == category and row[1] == subcategory
            )
            confidence_evidence = [
                sentence for sentence in candidates
                if _is_usable_evidence(sentence)
                and any(_phrase_count(sentence["text"], phrase) for phrase, _ in cues)
            ]
            if confidence_evidence:
                confidence_evidence.sort(
                    key=lambda sentence: (
                        sum(_phrase_count(sentence["text"], phrase) * weight for phrase, weight in cues),
                        2 if sentence["section"] == "Prepared Remarks" else 0,
                        -abs(len(sentence["text"]) - 165),
                    ),
                    reverse=True,
                )
                sentence = confidence_evidence[0]
                tone_signal = _signal(sentence["text"])
                tone_direction = ("supportive" if tone_signal in {"best", "strong_positive", "positive"}
                                  else "adverse" if tone_signal in {"negative", "worst"}
                                  else "mixed or monitoring")
                insight.update({
                    "detail": sentence["text"],
                    "signal": tone_signal,
                    "tier": tone_signal,
                    "reasoning": f"The cited {sentence['section'].lower()} evidence is {tone_direction} for management tone.",
                    "section": sentence["section"],
                    "citation": {"source": "earnings call transcript", "url": url,
                                 "start": sentence["start"], "end": sentence["end"]},
                })
            insight.update(confidence)
            break
    # Ensure at least one substantive Q&A observation is represented.
    if not any(row["section"] == "Analyst Q&A" for row in insights):
        qa = next((row for row in candidates
                   if row["section"] == "Analyst Q&A"
                   and _is_usable_evidence(row)
                   and any(term in row["text"].lower() for _, _, terms in TOPICS for term in terms)), None)
        if qa:
            signal = _signal(qa["text"])
            insights.append({"topic": "Analyst Q&A", "category": "qa", "detail": qa["text"], "signal": signal, "tier": signal,
                             "reasoning": "This is a substantive management response from the analyst Q&A section.", "section": "Analyst Q&A",
                             "citation": {"source": "earnings call transcript", "url": url, "start": qa["start"], "end": qa["end"]}})
    if not any(row["section"] == "Analyst Q&A" for row in insights):
        raise RuntimeError("TRANSCRIPT_QA_ANALYSIS_FAILED: no substantive Q&A response was identified")

    guidance_ranked = []
    for sentence in candidates:
        lower = sentence["text"].lower()
        if not _is_usable_evidence(sentence):
            continue
        forward_hits = sum(term in lower for term in ("guidance", "we expect", "we anticipate", "we forecast", "outlook"))
        directional_hits = sum(term in lower for term in ("growth", "margin", "higher", "lower", "increase", "decrease", "range", "%", "$"))
        if forward_hits and directional_hits and not any(fluff in lower for fluff in ("will discuss", "provide an update", "slide five")):
            guidance_ranked.append((forward_hits * 4 + directional_hits + (2 if re.search(r"\d", sentence["text"]) else 0), sentence))
    guidance_ranked.sort(key=lambda item: (item[0], -abs(len(item[1]["text"]) - 165)), reverse=True)
    guidance = []
    for _, sentence in guidance_ranked[:6]:
        guidance.append({"name": "Forward outlook", "detail": sentence["text"], "signal": _signal(sentence["text"]),
                         "citation": {"source": "earnings call transcript", "url": url,
                                      "start": sentence["start"], "end": sentence["end"]}})

    channels = []
    channel_rules = [
        ("Products & platforms", ("product", "platform", "service")),
        ("Customers & engagement", ("customer", "user", "subscriber", "engagement")),
        ("Markets & distribution", ("market", "region", "international", "north america", "europe", "asia")),
        ("Business lines", ("segment", "business", "enterprise", "consumer")),
    ]
    used_channel_text: set[str] = set()
    for label, terms in channel_rules:
        ranked = []
        for item in candidates:
            lower = item["text"].lower()
            if not _is_usable_evidence(item):
                continue
            hits = sum(term in lower for term in terms)
            if not hits or item["text"] in used_channel_text:
                continue
            if any(fluff in lower for fluff in ("will discuss", "provide an update", "joining me", "participants")):
                continue
            score = hits * 4 + (2 if re.search(r"\d", item["text"]) else 0) + (2 if item["section"] == "Prepared Remarks" else 0)
            ranked.append((score, item))
        if ranked:
            # Channel cards are fixed-height. Only publish evidence that fits as
            # a complete sentence; omit the card rather than append ellipses.
            ranked = [item for item in ranked if len(item[1]["text"]) <= 210]
            if not ranked:
                continue
            ranked.sort(key=lambda item: (item[0], -abs(len(item[1]["text"]) - 165)), reverse=True)
            row = ranked[0][1]; used_channel_text.add(row["text"])
            channels.append({"name": label, "desc": row["text"], "citation": {"source": "earnings call transcript", "url": url,
                                                                               "start": row["start"], "end": row["end"]}})

    # Strategic pillars are durable themes, not a second copy of the earnings
    # call summary. Select separate evidence and exclude every sentence already
    # used in call insights, guidance, or channel cards.
    used_pillar_text = {row["detail"] for row in insights}
    used_pillar_text.update(row["detail"] for row in guidance)
    used_pillar_text.update(row["desc"] for row in channels)
    pillars = []
    for label, terms in PILLAR_RULES:
        ranked = []
        for item in candidates:
            lower = f" {item['text'].lower()} "
            if item["text"] in used_pillar_text or not _is_usable_evidence(item):
                continue
            hits = sum(term in lower for term in terms)
            if not hits:
                continue
            score = hits * 5 + (2 if item["section"] == "Prepared Remarks" else 0)
            ranked.append((score, item))
        if not ranked:
            continue
        ranked.sort(key=lambda item: (item[0], -abs(len(item[1]["text"]) - 155)), reverse=True)
        row = ranked[0][1]
        used_pillar_text.add(row["text"])
        signal = _signal(row["text"])
        pillars.append({"name": label, "detail": row["text"], "signal": signal,
                        "citation": {"source": "earnings call transcript", "url": url,
                                     "start": row["start"], "end": row["end"]}})
    return {"insights": insights[:maximum], "guidance": guidance, "channels": channels, "strategic_pillars": pillars,
            "sentence_count": len(candidates)}


def extract_risks(text: str, filing_url: str, transcript_url: str, maximum: int = 6) -> list[dict[str, Any]]:
    sentences = _sentences(text)
    risks = []
    for label, terms in RISK_TOPICS:
        row = next((item for item in sentences
                    if _is_usable_evidence(item)
                    and any(term in item["text"].lower() for term in terms)), None)
        if not row: continue
        source_url = transcript_url if row["start"] >= text.find("\n\nTRANSCRIPT\n") > -1 else filing_url
        risks.append({"risk": label, "evidence": row["text"], "probability": None, "eps_impact": None,
                      "quantification": "Not company-disclosed; no probability or EPS impact invented",
                      "signal": "caution" if _signal(row["text"]) not in {"negative", "worst"} else _signal(row["text"]),
                      "citation": {"source": "SEC filing / earnings transcript", "url": source_url,
                                   "start": row["start"], "end": row["end"]}})
        if len(risks) == maximum: break
    return risks


def build_capital_liquidity(financial_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = {"cash", "long_term_debt", "total_assets", "total_liabilities", "total_equity", "operating_cash_flow", "capex"}
    items = []
    by_key = {row.get("key"): row for row in financial_rows}
    for key in keys:
        row = by_key.get(key)
        if row:
            items.append({"name": row["label"], "value": row["display"], "signal": row.get("signal", row.get("tier", "neutral")),
                          "citation": row.get("citation")})
    cash, debt = by_key.get("cash"), by_key.get("long_term_debt")
    if cash and debt:
        net = cash["value"] - debt["value"]
        items.append({"name": "Net cash / (debt)", "value": _money(net), "signal": "positive" if net >= 0 else "caution",
                      "citation": [cash.get("citation"), debt.get("citation")]})
    return items


def _percentile_rank(value: float, historical_data: list[float]) -> float:
    """Calculate percentile rank (0-100) of a value against historical data."""
    if not historical_data or len(historical_data) < 2:
        return 50.0  # Default to middle if insufficient data
    sorted_data = sorted(historical_data)
    n = len(sorted_data)
    # Count values less than or equal to the value
    count = sum(1 for x in sorted_data if x <= value)
    # Percentile rank formula: (count / n) * 100
    return min(100.0, max(0.0, (count / n) * 100))


def _capex_color_score(capex_value: float, revenue_value: float, capex_yoy: float | None,
                       historical_capex_revenue: list[float] | None = None,
                       historical_capex_yoy: list[float] | None = None) -> tuple[str, str]:
    """
    Calculate CapEx color score based on 80% CapEx/Revenue intensity + 20% YoY growth.
    
    Returns (signal, label) tuple.
    """
    # Calculate CapEx intensity as % of revenue
    if revenue_value is None or revenue_value <= 0:
        return "neutral", "Revenue unavailable for CapEx intensity calculation"
    
    capex_intensity = (capex_value / revenue_value) * 100  # As percentage
    
    # Get historical data (use defaults if not provided)
    hist_revenue = historical_capex_revenue or CAPEX_HISTORICAL_DATA.get("capex_revenue_pct", [])
    hist_yoy = historical_capex_yoy or CAPEX_HISTORICAL_DATA.get("capex_yoy", [])
    
    # Calculate percentile scores
    intensity_score = _percentile_rank(capex_intensity, hist_revenue)
    yoy_score = _percentile_rank(capex_yoy, hist_yoy) if capex_yoy is not None else 50.0
    
    # Composite score: 80% intensity, 20% YoY
    composite_score = 0.80 * intensity_score + 0.20 * yoy_score
    
    # Map to signal based on thresholds
    for threshold, signal, label in CAPEX_COLOR_THRESHOLDS:
        if composite_score <= threshold:
            return signal, label
    
    return "negative", "Very high financial burden"


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1e9: return f"{sign}${value / 1e9:.2f}B"
    if value >= 1e6: return f"{sign}${value / 1e6:.1f}M"
    return f"{sign}${value:,.0f}"
