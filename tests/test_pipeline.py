import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from run_analysis import EarningsAnalyzer, _change, _display, _validate_transcript_call_date
from create_one_pager_pdf import (create_one_pager_pdf, _compact_summary, _compact_items,
                                  _direction_marker, _select_call_summary_insights, _draw_cards,
                                  COMPACT_LABELS, SEMANTIC_SYMBOL_COLORS, COLORS, OnePager,
                                  PDF_FONT_SCALE)
from create_interactive_dashboard import build_dashboard_data, create_interactive_dashboard
from robinhood_mcp_get_quote import get_quote, _decode
from sec_edgar_search import _matches_query
from telegram_notify import (deliver_reports, generate_call_message, generate_dashboard_message, _send,
                             _complete_insight_selection, SIGNAL_EMOJIS)
from web_search import _validate as _validate_transcript
from xbrl_parser import parse_xbrl_financials
from analysis_enrichment import (extract_transcript_sections, extract_risks, _sentences, _is_question,
                                 _qa_boundary_start, classify_financial_signal, classify_valuation_signal,
                                 classify_management_confidence, _signal as _transcript_signal)

XBRL = '''<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2026" xmlns:dei="http://xbrl.sec.gov/dei/2026">
<context id="q"><entity><identifier scheme="x">1</identifier></entity><period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period></context>
<context id="py"><entity><identifier scheme="x">1</identifier></entity><period><startDate>2025-04-01</startDate><endDate>2025-06-30</endDate></period></context>
<context id="seg"><entity><identifier scheme="x">1</identifier><segment><explicitMember dimension="x:SegmentAxis">x:A</explicitMember></segment></entity><period><startDate>2026-04-01</startDate><endDate>2026-06-30</endDate></period></context>
<context id="i"><entity><identifier scheme="x">1</identifier></entity><period><instant>2026-06-30</instant></period></context>
<dei:DocumentFiscalPeriodFocus contextRef="q">Q2</dei:DocumentFiscalPeriodFocus><dei:DocumentFiscalYearFocus contextRef="q">2026</dei:DocumentFiscalYearFocus>
<us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="q" unitRef="usd">1200000000</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
<us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="py" unitRef="usd">1000000000</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
<us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax contextRef="seg" unitRef="usd">9000000000</us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax>
<us-gaap:NetIncomeLoss contextRef="q" unitRef="usd">100000000</us-gaap:NetIncomeLoss><us-gaap:Assets contextRef="i" unitRef="usd">5000000000</us-gaap:Assets>
</xbrl>'''


def sample_data():
    return {"ticker":"TEST","fiscal_period":"Q2","fiscal_year":2026,"report_date":"2026-06-30",
            "grade":{"letter":"B","confidence":.9,"justification":"Verified evidence."},
            "thesis":{"recommendation":"HOLD","base_case":{"summary":"Base evidence"},"bull_case":{"summary":"Bull evidence"},"bear_case":{"summary":"Bear evidence"}},
            "financials":{"rows":[{"label":"Revenue","display":"$1.20B","tier":"best","comparison":"+20.0% YoY"}]},
            "valuation":{"current_price":10.0,"pe_ttm":20.0,"ps_annualized":2.0,"fcf_yield_annualized":3.0},
            "transcript_insights":[{"topic":"Q&A","detail":"Analyst questions were answered.","tier":"medium"}],
            "growth_drivers":[{"driver":"Revenue increased.","tier":"best"}],"risks":[{"risk":"Competition disclosed"}],
            "sources":{"filing_url":"https://www.sec.gov/Archives/edgar/data/1/filing.htm","transcript_url":"https://stockanalysis.com/stocks/test/transcripts/1-q2-2026/"}}


class ExtractionTests(unittest.TestCase):
    def test_xbrl_current_prior_and_dimension_filter(self):
        result = parse_xbrl_financials(XBRL, "2026-06-30")
        self.assertEqual(result["fiscal_period"], "Q2")
        self.assertEqual(result["metrics"]["revenue"]["value"], 1200000000)
        self.assertEqual(result["metrics"]["revenue"]["prior_value"], 1000000000)

    def test_xbrl_including_assessed_tax_revenue_concept(self):
        xbrl = XBRL.replace(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
        )
        result = parse_xbrl_financials(xbrl, "2026-06-30")
        self.assertEqual(result["metrics"]["revenue"]["value"], 1200000000)
        self.assertEqual(result["metrics"]["revenue"]["concept"],
                         "RevenueFromContractWithCustomerIncludingAssessedTax")

    def test_query_is_enforced(self):
        self.assertTrue(_matches_query({"form":"8-K","items":"2.02","primaryDocDescription":""}, "earnings"))
        self.assertFalse(_matches_query({"form":"8-K","items":"5.02","primaryDocDescription":"director appointment"}, "earnings"))

    def test_transcript_requires_prepared_and_qa(self):
        text = ("TEST Q2 2026 chief executive officer prepared remarks analyst question and answer " * 300)
        self.assertTrue(_validate_transcript(text,"TEST","Q2",2026)[0])
        self.assertFalse(_validate_transcript("TEST Q2 2026 short summary","TEST","Q2",2026)[0])

    def test_grade_tolerates_unreported_operating_metric(self):
        analyzer = EarningsAnalyzer("TEST")
        analyzer.data = {
            "financials": {"rows": [
                {"key": "revenue", "value": 120, "prior_value": 100},
                {"key": "net_income", "value": -10, "prior_value": -20},
            ]},
            "transcript_insights": [],
            "sources": {"earnings_release_url": None, "transcript_url": "https://example.com/t"},
            "valuation": {"market_cap": 1000, "current_price": 10, "pe_ttm": None},
            "risks": [],
        }
        analyzer.grade_and_thesis()
        self.assertIn(analyzer.data["grade"]["letter"], {"A", "B", "C", "D", "F"})
        self.assertEqual(analyzer.data["thesis"]["recommendation"], "INSUFFICIENT DATA")

    def test_financial_format_keeps_number(self):
        self.assertEqual(_display(1_250_000_000,"revenue"), "$1.25B")
        self.assertEqual(_display(2.34,"eps_diluted"), "$2.34")

    def test_key_ratio_cards_are_derived_from_generic_financial_rows(self):
        analyzer = EarningsAnalyzer("TEST")
        analyzer.data = {"_xbrl": parse_xbrl_financials(XBRL, "2026-06-30"),
                         "sources": {"xbrl_url": "https://www.sec.gov/test.xml"}}
        analyzer.financials()
        ratios = analyzer.data["financials"]["key_ratios"]
        self.assertLessEqual(len(ratios), 6)
        self.assertTrue(any(row["label"] == "Revenue Growth" for row in ratios))

    def test_transcript_enrichment_uses_complete_sentences_and_real_qa(self):
        prepared = (
            "Chief Executive Officer: We are confident because customer demand increased strongly across our core platform.\n"
            "Chief Financial Officer: We expect revenue growth to improve next year while operating margin remains stable.\n"
            "Our new product platform increased customer engagement and improved retention across major markets.\n"
        )
        qa = (
            "Question-and-Answer Session\n"
            "Analyst: Can you explain the competitive environment and capital allocation priorities?\n"
            "Chief Executive Officer: Competition remains intense, but customer retention improved and our product roadmap is strong.\n"
            "Chief Financial Officer: We expect capital expenditures to increase as we invest in long-term capacity.\n"
            "Operator: To ask a question, press star one on your telephone keypad.\n"
        )
        result = extract_transcript_sections(prepared + qa, "https://stockanalysis.com/stocks/test/transcripts/1-q2-2026/")
        self.assertTrue(any(row["section"] == "Analyst Q&A" for row in result["insights"]))
        qa_rows = [row for row in result["insights"] if row["section"] == "Analyst Q&A"]
        self.assertTrue(all("can you explain" not in row["detail"].lower() for row in qa_rows))
        all_text = " ".join(row["detail"] for row in result["insights"])
        self.assertNotIn("press star", all_text.lower())
        self.assertNotIn("transcript summary record", all_text.lower())
        self.assertTrue(all(row["detail"][0].isupper() for row in result["insights"]))

    def test_line_based_qa_boundary_supports_operator_transitions(self):
        transitions = (
            "Your first question today comes from the line of Jane Smith from Example Research.",
            "Our first question comes from Jane Smith with Example Research.",
            "We will now take our first question from Jane Smith.",
        )
        for transition in transitions:
            with self.subTest(transition=transition):
                transcript = (
                    "Prepared Remarks\n"
                    "Chief Executive Officer: Revenue increased as customer demand remained strong across the platform.\n"
                    "Operator\nThank you.\n"
                    f"{transition}\n"
                    "Jane Smith\nEquity Research Analyst, Example Research\n"
                    "Clearly, the launch industry needs new vehicles operating at higher cadence.\n"
                    "Can you discuss customer demand and the expected product launch cadence?\n"
                    "Chief Executive Officer: We expect customer demand to remain strong, and the product launch cadence will accelerate during the second half.\n"
                )
                self.assertEqual(_qa_boundary_start(transcript), transcript.index(transition))
                result = extract_transcript_sections(
                    transcript,
                    "https://stockanalysis.com/stocks/test/transcripts/1-q2-2026/",
                )
                qa_rows = [row for row in result["insights"] if row["section"] == "Analyst Q&A"]
                self.assertTrue(qa_rows)
                self.assertTrue(all("can you discuss" not in row["detail"].lower() for row in qa_rows))
                self.assertTrue(any("launch cadence will accelerate" in row["detail"] for row in qa_rows))
                published_evidence = [row["detail"] for row in result["insights"] + result["guidance"]]
                published_evidence += [row["desc"] for row in result["channels"]]
                published_evidence += [row["detail"] for row in result["strategic_pillars"]]
                self.assertFalse(any("launch industry needs" in text.lower() for text in published_evidence))

    def test_line_based_qa_boundary_retains_explicit_headings(self):
        for heading in ("Question-and-Answer Session", "Questions & Answers", "Q&A Session"):
            with self.subTest(heading=heading):
                transcript = f"Prepared remarks remain here.\n{heading}\nManagement response follows.\n"
                self.assertEqual(_qa_boundary_start(transcript), transcript.index(heading))

    def test_line_based_qa_boundary_ignores_narrative_question_words(self):
        transcript = (
            "Prepared Remarks\n"
            "Management reviewed customer questions and answers from the annual product survey.\n"
            "The first question for management planning concerns long-term manufacturing capacity.\n"
        )
        self.assertEqual(_qa_boundary_start(transcript), len(transcript))

    def test_provider_welcome_boilerplate_is_not_evidence(self):
        transcript = (
            "Hello, and welcome to today's conference call to discuss quarterly financial results and business highlights.\n"
            "Management said customer demand increased as the product platform expanded across international markets.\n"
        )
        rows = _sentences(transcript)
        self.assertFalse(any("welcome to today's conference call" in row["text"].lower() for row in rows))
        self.assertTrue(any("customer demand increased" in row["text"].lower() for row in rows))

    def test_risk_probabilities_are_not_invented(self):
        text = "Management disclosed regulatory litigation risk and competitive pressure in its principal market."
        risks = extract_risks(text, "https://www.sec.gov/a", "https://stockanalysis.com/b")
        self.assertTrue(risks)
        self.assertTrue(all(row["probability"] is None and row["eps_impact"] is None for row in risks))
        self.assertTrue(all("no probability" in row["quantification"] for row in risks))

    def test_participant_title_is_not_qa_evidence(self):
        transcript = (
            "Prepared Remarks\nManagement expects revenue growth to improve as customer demand expands.\n"
            "Question-and-Answer Session\nManaging Director and Senior Equity Research Analyst, Raymond James\n"
            "has pricing power and continues to deliver extraordinary value every day.\n"
            "Customer demand increased 25% as product engagement strengthened across key markets.\n"
        )
        rows = _sentences(transcript)
        self.assertFalse(any("Equity Research Analyst" in row["text"] for row in rows))
        self.assertFalse(any(row["text"].startswith("has pricing power") for row in rows))
        self.assertTrue(any("Customer demand increased 25%" in row["text"] for row in rows))
        self.assertTrue(_is_question(
            "What you're assuming with the guide, and how you think about the margin impact."
        ))
        self.assertTrue(_is_question(
            "I guess I want to maybe move past the first launch and talk about scale."
        ))

    def test_decimal_amount_is_not_split_mid_sentence(self):
        rows = _sentences("Management returned $1.2 billion to shareholders through dividends and repurchases.")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["text"].startswith("Management returned $1.2 billion"))

    def test_negative_pe_is_not_classified_as_cheap(self):
        signal, assessment = classify_valuation_signal("P/E (TTM)", -2.0)
        self.assertEqual(signal, "caution")
        self.assertEqual(assessment, "Not meaningful")

    def test_declining_diluted_shares_is_positive_anti_dilution(self):
        self.assertEqual(classify_financial_signal("shares_diluted", -0.019), "positive")
        self.assertEqual(classify_financial_signal("shares_diluted", 0.03), "caution")

    def test_strategic_pillars_use_distinct_evidence(self):
        prepared = (
            "Management said revenue growth improved because customer demand remained strong across all regions.\n"
            "Our long-term strategy is to double manufacturing capacity while improving operating efficiency.\n"
            "We expect operating margin to increase as pricing and productivity gains offset inflation.\n"
            "The product roadmap includes a new technology platform designed for international expansion.\n"
            "Free cash flow supports dividends and share repurchases under our disciplined capital allocation plan.\n"
        )
        qa = ("Question-and-Answer Session\nAnalyst: Can you discuss demand?\n"
              "Chief Executive Officer: Customer retention improved and our services pipeline remains strong.\n")
        result = extract_transcript_sections(prepared + qa, "https://stockanalysis.com/stocks/test/transcripts/1-q2-2026/")
        insight_text = {row["detail"] for row in result["insights"]}
        self.assertTrue(result["strategic_pillars"])
        self.assertTrue(all(row["detail"] not in insight_text for row in result["strategic_pillars"]))

    def test_transcript_validation_accepts_provider_neutral_initial_remarks(self):
        transcript = "\n".join((
            "AST SpaceMobile (ASTS) Q2 2026 Earnings Call Transcript",
            "Welcome to the second quarter 2026 business update.",
            "Chairman and CEO",
            "After our initial remarks, we will start our Q and A section.",
        )) + (" Management discussion." * 500)
        valid, failures = _validate_transcript(transcript, "ASTS", "Q2", 2026)
        self.assertTrue(valid, failures)

    def test_management_confidence_taxonomy_and_word_boundaries(self):
        cases = (
            ("We remain committed to delivering the program.", "Confident", "Resolute"),
            ("We know this market and have a proven track record.", "Confident", "Authoritative"),
            ("We have decided to move forward with the launch.", "Confident", "Decisive"),
            ("We expect demand to remain healthy.", "Confident", "Assured"),
            ("We cannot comment on that matter.", "Vague", "Evasive"),
            ("The result depends on several unresolved factors.", "Vague", "Equivocal"),
            ("We might evaluate additional alternatives.", "Vague", "Noncommittal"),
            ("We see some opportunities over time.", "Vague", "Ambiguous"),
            ("We disagree; that characterization is not accurate.", "Not Confident", "Defensive / Faltering"),
            ("We are worried about the continuing disruption.", "Not Confident", "Anxious"),
            ("I am not sure how the quarter will develop.", "Not Confident", "Hesitant"),
            ("We hope to reach the milestone next year.", "Not Confident", "Tentative"),
        )
        for text, category, subcategory in cases:
            with self.subTest(subcategory=subcategory):
                result = classify_management_confidence([{"text": text, "section": "Prepared Remarks"}])
                self.assertEqual(result["confidence_category"], category)
                self.assertEqual(result["confidence_subcategory"], subcategory)
        false_positive = classify_management_confidence([
            {"text": "A confidential customer signed the agreement.", "section": "Prepared Remarks"}
        ])
        self.assertEqual((false_positive["confidence_category"], false_positive["confidence_subcategory"]),
                         ("Vague", "Ambiguous"))
        self.assertEqual(_transcript_signal("A confidential customer signed the agreement."), "neutral")

    def test_management_tone_statement_supports_classification_not_risk_boilerplate(self):
        transcript = (
            "Chief Executive Officer: For more information about risks, refer to the Risk Factors section of our annual report.\n"
            "Chief Executive Officer: We are confident, expect commercial customer demand to expand, and believe execution remains on track.\n"
            "Question-and-Answer Session\n"
            "Analyst: Can you discuss demand?\n"
            "Chief Executive Officer: We expect customer adoption to increase as service becomes available.\n"
        )
        result = extract_transcript_sections(transcript, "https://stockanalysis.com/test")
        tone = next(row for row in result["insights"] if row["topic"] == "Management Tone")
        self.assertEqual((tone["confidence_category"], tone["confidence_subcategory"]),
                         ("Confident", "Assured"))
        self.assertIn("expect", tone["detail"].lower())
        self.assertNotIn("risk factors", tone["detail"].lower())
        self.assertIn("supportive", tone["reasoning"])

    def test_management_execution_language_is_positive(self):
        text = ("Commercial readiness continues to advance, government demand continues to expand, "
                "our deployment roadmap remains on track, and our operational capabilities continue to scale.")
        self.assertIn(_transcript_signal(text), {"positive", "strong_positive", "best"})

    def test_transcript_call_date_must_follow_report_date(self):
        value, warning = _validate_transcript_call_date("2025-12-31", "2026-06-30")
        self.assertIsNone(value)
        self.assertIn("consistency validation", warning)
        value, warning = _validate_transcript_call_date("2026-08-04", "2026-06-30")
        self.assertEqual(value, "2026-08-04")
        self.assertIsNone(warning)


class SafetyTests(unittest.TestCase):
    @patch("run_analysis._now")
    @patch("run_analysis.get_quote")
    def test_stale_quote_requires_explicit_test_override(self, quote, now):
        from datetime import datetime, timezone
        now.return_value = datetime(2026, 8, 9, tzinfo=timezone.utc)
        quote.return_value = {"price": 100.0, "market_cap": 1_000_000_000,
                              "updated_at": "2026-08-08T20:00:00+00:00", "source": "robinhood-trading MCP"}
        normal = EarningsAnalyzer("TEST"); normal.data["_xbrl"] = {"metrics": {"revenue": {"value": 100, "duration_days": 91}}}
        with self.assertRaisesRegex(RuntimeError, "STALE_QUOTE"):
            normal.quote_and_valuation()
        test = EarningsAnalyzer("TEST", allow_stale_quote_for_test=True)
        test.data["_xbrl"] = {"metrics": {"revenue": {"value": 100, "duration_days": 91}}}
        test.quote_and_valuation()
        self.assertTrue(test.data["test_run"])
        self.assertTrue(test.data["valuation"]["quote_is_stale"])
        self.assertIn("not actionable", test.data["warnings"][0])

    @patch("robinhood_mcp_get_quote._expected_account", return_value=None)
    @patch("robinhood_mcp_get_quote._call")
    def test_quote_requires_expected_account(self, call, expected):
        with self.assertRaisesRegex(RuntimeError, "ROBINHOOD_EXPECTED_ACCOUNT"):
            get_quote("TEST")
        call.assert_not_called()

    def test_delivery_dry_run_never_sends(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "a.pdf"; pdf.write_bytes(b"%PDF" + b"x"*1200)
            with patch("telegram_notify.subprocess.run") as run:
                result = deliver_reports(sample_data(), str(pdf), dry_run=True)
            self.assertEqual(len(result), 2); run.assert_not_called()

    def test_delivery_rejects_missing_attachment(self):
        with self.assertRaisesRegex(RuntimeError, "missing or empty"):
            deliver_reports(sample_data(), "/missing.pdf", dry_run=False)

    def test_delivery_requires_json_receipt(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"; create_one_pager_pdf(sample_data(), str(pdf))
            with patch("telegram_notify.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "not-json", "")):
                with self.assertRaisesRegex(RuntimeError, "malformed JSON"):
                    _send("message", str(pdf), "telegram")

    def test_delivery_success_receipt_and_command(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"; create_one_pager_pdf(sample_data(), str(pdf))
            result = subprocess.CompletedProcess([], 0, json.dumps({"success": True, "message_id": "m1"}), "")
            with patch("telegram_notify.subprocess.run", return_value=result) as run:
                receipt = _send("message", str(pdf), "telegram")
            self.assertTrue(receipt["success"]); self.assertEqual(receipt["backend_id"], "m1")
            args = run.call_args.args[0]
            self.assertEqual(args[:5], ["hermes", "send", "--to", "telegram", "--json"])
            self.assertIn("MEDIA:" + str(pdf.resolve()), args[5])


class OutputTests(unittest.TestCase):
    def test_pdf_global_font_scale_is_exactly_one_point_five(self):
        self.assertEqual(PDF_FONT_SCALE, 1.5)
        pdf = OnePager()
        pdf.set_font("Helvetica", "", 10)
        self.assertAlmostEqual(pdf.font_size_pt, 15.0, places=6)

    def test_cross_ticker_compaction_preserves_material_evidence(self):
        cases = [
            (
                "Pricing and product mix added approximately 39 percentage points to net sales growth in Q1, while unit volumes were down approximately three percentage points.",
                ("39", "three", "Q1", "net sales growth", "↑", "↓"),
            ),
            (
                "Excluding this benefit, gross margin was still meaningfully higher year-over-year, up about 350 basis points, reflecting benefits from pricing and lower year-over-year tariff rates.",
                ("350", "pricing", "tariff"),
            ),
            (
                "Rhode outperformed our expectations in the quarter, contributing approximately $160 million in net sales, driven by strong retail demand and a record-breaking summer innovation launch on rhodeskin.",
                ("Rhode", "$160M", "retail demand", "rhodeskin"),
            ),
            (
                "We're one of only six public consumer companies out of 516 that has grown for 30 straight quarters and averages at least 20% net sales growth per quarter.",
                ("six", "516", "30", "20%"),
            ),
            (
                "We also plan to invest in technology, including AI capabilities and phase two of our SAP integration and working capital, to support our brand expansions globally, particularly with Rhode's launch into Europe.",
                ("AI", "SAP", "working capital", "Rhode", "Europe"),
            ),
            (
                "We're going to keep that 10% at the lower pricing while the other items go back to the original pre-price levels.",
                ("10%", "lower pricing", "other items", "pre-price levels"),
            ),
        ]
        for source, required in cases:
            summary = _compact_summary(source)
            self.assertLess(len(summary), len(source))
            self.assertNotIn("...", summary)
            for token in required:
                self.assertIn(token, summary)

        marker, color = _direction_marker({"text": "Pricing + mix ↑39 pp; unit volume ↓3 pp"})
        self.assertEqual(marker, "→")
        self.assertEqual(color, COLORS["neutral"])

    def test_segment_margin_summary_is_compact_and_preserves_every_metric(self):
        source = ("Segment margins were impacted by 90 basis points in Power & Energy, "
                  "340 basis points within Construction Industries, and 260 basis points in Resource Industries.")
        summary = _compact_summary(source, "Margins & Profitability")
        self.assertLess(len(summary), len(source))
        self.assertEqual(summary, ("Segment Margins: ⚡ Power & Energy (↓90 bps); "
                                   "⚒ Construction Industries (↓340 bps); "
                                   "◆ Resource Industries (↓260 bps)."))
        for metric in ("90", "340", "260"):
            self.assertIn(metric, summary)
        self.assertNotIn("...", summary)

    def test_every_selected_display_row_is_a_true_compression(self):
        rows = [
            {"topic": "Revenue", "detail": "The 24% increase in sales and revenues compared to the second quarter of 2025 was primarily driven by strong growth in sales volume and favorable price realization."},
            {"topic": "Capital", "detail": "In the quarter, we generated robust MP&E free cash flow of $5.1 billion and deployed $2.2 billion to shareholders through share repurchases and dividends."},
            {"topic": "Product", "detail": "To support the demand growth in power generation and oil and gas applications, we are excited to resume production of our 10 MW medium-speed gas reciprocating engine platform."},
            {"topic": "Strategy", "detail": "Our full-year margin expectation reflects the strategic investments we are making to execute our growth strategy, as well as the ongoing impact of tariffs."},
        ]
        selected = _compact_items(rows, "detail", "topic", 8, 1000, 190)
        self.assertEqual(len(selected), len(rows))
        for source, display in zip(rows, selected):
            compact_body = _compact_summary(source["detail"])
            self.assertLess(len(compact_body), len(source["detail"]))
            self.assertNotIn("...", display["text"])
        combined = " ".join(row["text"] for row in selected)
        for metric in ("24%", "$5.1B", "$2.2B", "10 MW"):
            self.assertIn(metric, combined)

    def test_guidance_rows_are_all_compacted_with_metrics_and_comparisons(self):
        rows = [
            {"detail": "Due to the increased sales outlook, full-year adjusted operating margin will be higher than we expected in April.", "signal": "positive"},
            {"detail": "We expect the full-year adjusted operating margin to be higher than we expected during our last earnings call, reflecting the improved sales outlook.", "signal": "positive"},
            {"detail": "Second quarter adjusted operating margin was better than we anticipated, primarily due to IEEPA tariff recoveries of $392 million and lower than expected tariff costs.", "signal": "positive"},
            {"detail": "With the improved sales and adjusted operating margin outlook, we now expect segment free cash flow to be in the top half of our annual target range of $6 billion-$15 billion.", "signal": "positive"},
            {"detail": "The $400 million of dealer inventory increase and services revenue growth resulted in sales volume to be better than we expected.", "signal": "positive"},
            {"detail": "We expect stronger full-year growth across all three primary segments compared to the outlook we gave in April.", "signal": "positive"},
        ]
        selected = _compact_items(rows, "detail", None, 6, 1100, 220)
        self.assertEqual(len(selected), 6)
        for source, display in zip(rows, selected):
            self.assertLess(len(display["text"]), len(source["detail"]))
            self.assertNotIn("...", display["text"])
        combined = " ".join(row["text"] for row in selected)
        for token in ("April", "prior call", "$392M", "$6B-$15B", "$400M", "all three primary segments"):
            self.assertIn(token, combined)

    def test_compact_semantic_symbols_exist_in_embedded_pdf_font(self):
        from fontTools.ttLib import TTFont
        font = TTFont("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        try:
            cmap = {code for table in font["cmap"].tables for code in table.cmap}
        finally:
            font.close()
        symbols = {character for label in COMPACT_LABELS.values() for character in label
                   if not character.isalnum() and not character.isspace()}
        symbols.update("⚡⚒◆♻↑↓→")
        self.assertTrue(all(ord(symbol) in cmap for symbol in symbols))

    def test_market_channel_opportunity_is_true_compression(self):
        source = ("A growing presence there also represents an opportunity to address Europe's "
                  "launch deficit by bringing a domestic mission-tested launch partner to the "
                  "region to eliminate space access bottlenecks.")
        summary = _compact_summary(source)
        self.assertLess(len(summary), len(source))
        self.assertIn("Europe's launch deficit", summary)
        self.assertIn("domestic mission-tested launch partner", summary)
        self.assertIn("space access bottlenecks", summary)

    def test_pdf_direction_arrows_use_signal_spectrum_endpoints(self):
        import pdfplumber
        data = sample_data()
        data["transcript_insights"] = [
            {"topic": "Margins & Profitability",
             "detail": ("Segment margins were impacted by 90 basis points in Power & Energy, "
                        "340 basis points within Construction Industries, and 260 basis points in Resource Industries."),
             "signal": "caution"},
            {"topic": "Revenue & Demand", "detail": "Revenue increased 12% as customer demand improved.",
             "signal": "positive"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "direction-colors.pdf"
            create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as document:
                chars = document.pages[0].chars
        down = [char for char in chars if char.get("text") == "↓"]
        up = [char for char in chars if char.get("text") == "↑"]
        self.assertTrue(down)
        self.assertTrue(up)
        self.assertTrue(all(color[0] > color[1] and color[0] > color[2]
                            for color in (char["non_stroking_color"] for char in down)))
        self.assertTrue(all(color[2] > color[1] > color[0]
                            for color in (char["non_stroking_color"] for char in up)))

    def test_requested_sections_use_signal_font_colors(self):
        import pdfplumber
        data = sample_data()
        data["guidance"] = {"rows": [
            {
                "detail": "Forward outlook: Management expects full-year revenue growth to remain resilient.",
                "signal": "positive",
            },
            {
                "detail": "Second quarter adjusted operating margin was better than we anticipated, primarily due to tariff recoveries of $392 million and lower than expected tariff costs.",
                "signal": "caution",
            },
        ]}
        data["transcript_insights"] = [
            {"topic": "Revenue & Demand", "detail": "Revenue increased 12% as customer demand improved.", "signal": "positive"},
            {"topic": "Margins & Profitability", "detail": ("Segment margins were impacted by 90 basis points in Power & Energy, "
                                                               "340 basis points within Construction Industries, and 260 basis points in Resource Industries."),
             "signal": "caution"},
        ]
        data["channels"] = {"items": [
            {"name": "Products & platforms", "desc": "The product platform expanded across international markets and added new enterprise capabilities.", "signal": "positive"},
            {"name": "Business lines", "desc": "The business segment delivered higher sales as demand strengthened across core applications.", "signal": "caution"},
        ]}
        data["strategic_pillars"] = [
            {"name": "Growth Expansion", "detail": "We believe Major Projects will expand our presence in rentals and make it easier for large contractors to do business with us and our dealers.", "signal": "positive"},
            {"name": "Long-Term Strategy", "detail": "Our full-year margin expectation reflects the strategic investments we are making to execute our growth strategy, as well as the ongoing impact of tariffs.", "signal": "caution"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signal-font-colors.pdf"
            create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as document:
                page = document.pages[0]
                ppm = page.width / 210
                def alpha_colors(box):
                    chars = page.crop(tuple(value * ppm for value in box)).chars
                    return {tuple(round(value, 4) for value in char["non_stroking_color"])
                            for char in chars if str(char.get("text", "")).isalpha()}
                guidance_colors = alpha_colors((63, 77, 119, 145))
                earnings_colors = alpha_colors((119, 77, 203, 145))
                channel_colors = alpha_colors((8, 145, 203, 171))
                pillar_colors = alpha_colors((8, 171, 203, 210))
        positive = tuple(round(value / 255, 4) for value in COLORS["positive"])
        caution = tuple(round(value / 255, 4) for value in COLORS["caution"])
        for colors in (guidance_colors, earnings_colors, channel_colors, pillar_colors):
            self.assertIn(positive, colors)
            self.assertIn(caution, colors)

    def test_call_message_preserves_complete_sentences_without_ellipsis(self):
        data = sample_data()
        sentence = "Management expects durable growth because customer retention improved across every major market."
        data["transcript_insights"] = [{"topic": "Demand", "detail": sentence, "signal": "positive",
                                        "section": "Prepared Remarks", "citation": {"start": 1, "end": 99}}]
        message = generate_call_message(data)
        self.assertIn(sentence, message)
        self.assertNotIn("…", message)

    def test_telegram_uses_complete_best_to_worst_signal_spectrum(self):
        spectrum = {
            "best": "🟦", "strong_positive": "🔷", "positive": "🔵", "neutral": "🟡",
            "caution": "🟠", "negative": "🔴", "worst": "🟥",
        }
        self.assertEqual({signal: SIGNAL_EMOJIS[signal] for signal in spectrum}, spectrum)
        data = sample_data()
        data["financials"]["rows"] = [
            {"label": f"Metric-{signal}", "display": "1", "comparison": "verified", "signal": signal}
            for signal in spectrum
        ]
        data["transcript_insights"] = [
            {"topic": f"Topic-{signal}", "detail": f"Complete evidence for {signal} sentiment.",
             "reasoning": "Signal follows evidence.", "signal": signal,
             "section": "Prepared Remarks", "citation": {"start": 1, "end": 20}}
            for signal in spectrum
        ]
        dashboard = generate_dashboard_message(data)
        call = generate_call_message(data)
        for signal, emoji in spectrum.items():
            self.assertIn(f"{emoji} Metric-{signal}", dashboard)
            self.assertIn(f"{emoji} **Topic-{signal}**", call)
        self.assertIn(f"{spectrum['caution']} Key Risks:", dashboard)

    def test_pdf_font_primitives_use_complete_signal_spectrum(self):
        import pdfplumber
        spectrum = ("best", "strong_positive", "positive", "neutral", "caution", "negative", "worst")
        cards = [{"display": f"D{index}", "label": f"card{signal}",
                  "comparison": f"cmp{signal}", "signal": signal}
                 for index, signal in enumerate(spectrum)]
        compact = [{"text": f"⚙ compact{signal}", "signal": signal} for signal in spectrum]
        bullets = [{"text": f"bullet{signal}", "signal": signal} for signal in spectrum]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "complete-spectrum.pdf"
            pdf = OnePager()
            _draw_cards(pdf, "CARDS", cards, 8, 8, 194, 4, 12, 7)
            pdf.compact_lines(compact, 8, 45, 194, 65, 7, 5.0, 2.5,
                              color_text_by_signal=True)
            pdf.bullet_lines(bullets, 8, 114, 194, 65, 7, chars=None, font_size=5.0,
                             line_height=2.8)
            pdf.output(str(path))
            with pdfplumber.open(path) as document:
                page = document.pages[0]
                for signal in spectrum:
                    expected = tuple(round(value / 255, 4) for value in COLORS[signal])
                    for token in (f"card{signal}", f"cmp{signal}", f"compact{signal}", f"bullet{signal}"):
                        match = page.search(token)[0]
                        chars = page.crop((match["x0"], match["top"], match["x1"], match["bottom"])).chars
                        colors = {tuple(round(value, 4) for value in char["non_stroking_color"])
                                  for char in chars if str(char.get("text", "")).isalnum()}
                        self.assertEqual(colors, {expected}, token)
                icons = [char for char in page.chars if char.get("text") == "⚙"]
                self.assertEqual(len(icons), len(spectrum))
                for icon, signal in zip(icons, spectrum):
                    actual = tuple(round(value, 4) for value in icon["non_stroking_color"])
                    expected = tuple(round(value / 255, 4) for value in COLORS[signal])
                    self.assertEqual(actual, expected, f"icon-{signal}")

    def test_pdf_call_summary_mirrors_telegram_selection_colors_and_icons(self):
        import pdfplumber
        data = sample_data()
        rows = [
            {"topic": "Management Tone", "detail": "We've had a confidential defense prime sign up for two launches in 2027.",
             "signal": "positive", "section": "Prepared Remarks",
             "confidence_category": "Confident", "confidence_subcategory": "Assured"},
            {"topic": "Revenue & Demand", "detail": "Revenue increased approximately 12% year-over-year as high-impact program demand strengthened.", "signal": "positive", "section": "Prepared Remarks"},
            {"topic": "Margins & Profitability", "detail": "Gross margin improved approximately 200 basis points year-over-year due to favorable product mix.", "signal": "neutral", "section": "Prepared Remarks"},
            {"topic": "Guidance", "detail": "We expect full-year revenue to increase approximately 10% year-over-year.", "signal": "neutral", "section": "Prepared Remarks"},
            {"topic": "Products & Innovation", "detail": "We are continuing to expand the product platform with new enterprise capabilities.", "signal": "neutral", "section": "Prepared Remarks"},
            {"topic": "Customers & Engagement", "detail": "Strong customer engagement continued across every major international market.", "signal": "neutral", "section": "Prepared Remarks"},
            {"topic": "Capital Allocation", "detail": "Capital expenditure was approximately $100 million as infrastructure investment continued.", "signal": "neutral", "section": "Prepared Remarks"},
            {"topic": "Competition & Market", "detail": "Continued market expansion strengthened the company's competitive position.", "signal": "neutral", "section": "Prepared Remarks"},
            {"topic": "Analyst Q&A", "detail": "Management expects demand to remain resilient through 2027.", "signal": "neutral", "section": "Analyst Q&A"},
        ]
        data["transcript_insights"] = rows
        telegram_rows = _complete_insight_selection(rows)
        pdf_rows = _select_call_summary_insights(rows)
        self.assertEqual([row["topic"] for row in pdf_rows],
                         [row["topic"] for row in telegram_rows])
        compact = _compact_items(pdf_rows, "detail", "topic", 8, 2500, 190)
        self.assertEqual(len(compact), 8)
        self.assertTrue(all(str(COMPACT_LABELS[row["topic"]])[0] in SEMANTIC_SYMBOL_COLORS
                            for row in compact))
        revenue_summary = next(row["text"] for row in compact if row["topic"] == "Revenue & Demand")
        self.assertIn("high-impact", revenue_summary)
        self.assertNotIn("high- program", revenue_summary)
        self.assertEqual(_direction_marker({"text": "capital expenditures increased", "signal": "neutral",
                                            "_signal_marker": True})[0], "→")
        call_message = generate_call_message(data)
        self.assertIn("🔵 **Management Tone**: Confident -> Assured, We've had", call_message)
        self.assertNotIn("🟢 **Management Tone**", call_message)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "telegram-aligned-call-summary.pdf"
            create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as document:
                page = document.pages[0]
                ppm = page.width / 210
                call_chars = page.crop((119 * ppm, 77 * ppm, 203 * ppm, 145 * ppm)).chars
                call_text = "".join(char.get("text", "") for char in call_chars)
                colors = {tuple(round(value, 4) for value in char["non_stroking_color"])
                          for char in call_chars if str(char.get("text", "")).isalpha()}
        for label in ("Management Tone", "Revenue", "Margins", "Guidance", "Product", "Customers", "Capital", "Market"):
            self.assertIn(label, call_text)
        self.assertIn("Management Tone: Confident -> Assured,", call_text)
        self.assertNotIn("Q&A", call_text)
        positive = tuple(round(value / 255, 4) for value in COLORS["positive"])
        neutral = tuple(round(value / 255, 4) for value in COLORS["neutral"])
        self.assertEqual(COLORS["positive"], (0, 80, 160))
        self.assertIn(positive, colors)
        self.assertIn(neutral, colors)

    def test_unquantified_risks_do_not_render_na_placeholders(self):
        data = sample_data()
        data["risks"] = [{"risk": "Competition", "probability": None, "eps_impact": None,
                           "evidence": "Competition remains intense.", "signal": "caution"}]
        message = generate_dashboard_message(data)
        self.assertNotIn("N/A prob", message)
        self.assertIn("not quantified by the company", message)

    def test_pdf_guidance_and_channels_preserve_complete_sentences(self):
        import pdfplumber
        data = sample_data()
        guidance_sentence = "Management expects full-year revenue growth to improve while operating margins remain resilient."
        channel_sentences = [
            "The product platform expanded across international markets and added new enterprise capabilities.",
            "Customer retention improved as engagement increased across the company's principal services.",
            "Regional distribution expanded through partners in North America, Europe, and Asia.",
            "The business segment delivered higher sales as demand strengthened across core applications.",
        ]
        data["guidance"] = {"rows": [{"name": "Forward outlook", "detail": guidance_sentence,
                                        "signal": "positive"}]}
        data["channels"] = {"items": [{"name": f"Channel {index}", "desc": sentence}
                                         for index, sentence in enumerate(channel_sentences, 1)]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "complete-sections.pdf"
            create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as document:
                page = document.pages[0]
                text = page.extract_text() or ""
                guidance_heading = page.search("GUIDANCE & OUTLOOK")[0]
                channel_heading = page.search("KEY CHANNELS & SEGMENTS")[0]
                pillar_heading = page.search("STRATEGIC PILLARS")[0]
                guidance_text = page.crop((0, guidance_heading["bottom"], page.width,
                                           channel_heading["top"])).extract_text() or ""
                channel_text = page.crop((0, channel_heading["bottom"], page.width,
                                          pillar_heading["top"])).extract_text() or ""
        self.assertNotIn("...", text)
        self.assertIn("resilient.", guidance_text)
        # Channel content preserved (may be compressed); verify key concepts appear
        self.assertTrue(any(word in channel_text.lower() for word in ("capab", "caps", "capabilities")))
        self.assertTrue(any(word in channel_text.lower() for word in ("serv", "svcs", "services")))
        self.assertTrue(any(word in channel_text.lower() for word in ("asia", "apac")))
        self.assertTrue(any(word in channel_text.lower() for word in ("demand", "strong")))

    def test_pdf_app_like_channels_and_pillars_do_not_become_placeholders(self):
        import pdfplumber
        data = sample_data()
        data["channels"] = {"items": [
            {"name": "Products & platforms", "desc": "What's been working well with the self-service platform now that you're generally available?"},
            {"name": "Customers & engagement", "desc": "The goal is getting more mid-market customers that can give our model visibility into more of the user's transactional behavior."},
            {"name": "Markets & distribution", "desc": "There is some market data suggesting mobile application downloads are down approximately 12% year-over-year in recent months."},
            {"name": "Business lines", "desc": "Results were below guidance due to slower model improvements, but momentum strengthened in gaming and consumer segments."},
        ]}
        data["strategic_pillars"] = [
            {"name": "Innovation Roadmap", "detail": "We continue to compound improvements in the technology and templates, with more customer success stories supporting platform adoption.", "signal": "positive"},
            {"name": "Growth Expansion", "detail": "We are still early in the category and can expand supply into non-gaming applications and open-web placements.", "signal": "neutral"},
            {"name": "Customer Value", "detail": "Analytics providers do not capture all incremental services revenue generated with customers across the category.", "signal": "caution"},
            {"name": "Operational Excellence", "detail": "The platform can automatically generate interactive end cards with high operating efficiency.", "signal": "positive"},
            {"name": "Capital Discipline", "detail": "We manage the business to EBITDA dollars and free cash flow rather than a fixed margin percentage.", "signal": "neutral"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generic-completeness.pdf"
            create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as document:
                page = document.pages[0]
                text = page.extract_text() or ""
                channel_heading = page.search("KEY CHANNELS & SEGMENTS")[0]
                pillar_heading = page.search("STRATEGIC PILLARS")[0]
                risk_heading = page.search("KEY RISKS")[0]
                channel_text = page.crop((0, channel_heading["bottom"], page.width,
                                          pillar_heading["top"])).extract_text() or ""
                pillar_text = page.crop((0, pillar_heading["bottom"], page.width,
                                         risk_heading["top"])).extract_text() or ""
        self.assertNotIn("No verified channel evidence", channel_text)
        self.assertNotIn("No verified data available", pillar_text)
        for label in ("Products", "Customers", "Markets", "Segments"):
            self.assertIn(label, channel_text)
        for label in ("Innovation", "Expansion", "Customer", "Operations", "Capital"):
            self.assertIn(label, pillar_text)
        self.assertNotIn("...", text)

    def test_pdf_adaptive_guidance_layout_renders_every_preselected_row(self):
        import pdfplumber
        data = sample_data()
        names = ("Aurora", "Borealis", "Cirrus", "Denali", "Equinox", "Frontier")
        data["guidance"] = {"rows": [
            {"detail": f"We expect {name} revenue to increase 12% year-over-year with operating margin remaining stable.",
             "signal": "positive"}
            for name in names
        ]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive-guidance.pdf"
            create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as document:
                page = document.pages[0]
                guidance_heading = page.search("GUIDANCE & OUTLOOK")[0]
                channel_heading = page.search("KEY CHANNELS & SEGMENTS")[0]
                guidance_text = page.crop((0, guidance_heading["bottom"], page.width,
                                           channel_heading["top"])).extract_text() or ""
        for name in names:
            self.assertIn(name, guidance_text)

    def test_compact_items_treats_item_limit_as_layout_hint(self):
        source = ("We expect revenue between $2.055 billion and $2.085 billion, representing "
                  "46%-48% year-over-year growth with operating margin remaining stable.")
        selected = _compact_items(
            [{"topic": "Guidance", "detail": source, "signal": "positive"}],
            "detail", "topic", maximum=1, character_budget=500, item_limit=60,
        )
        self.assertEqual(len(selected), 1)
        self.assertLess(len(_compact_summary(source)), len(source))
        self.assertIn("$2.055B", selected[0]["text"])
        self.assertIn("46%-48%", selected[0]["text"])

    def test_test_run_is_labeled_in_pdf_and_both_messages(self):
        import pdfplumber
        data = sample_data(); data["test_run"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.pdf"; create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as pdf:
                text = pdf.pages[0].extract_text() or ""
        self.assertIn("TEST ONLY - STALE MARKET DATA - NOT ACTIONABLE", text)
        self.assertIn("TEST ONLY", generate_dashboard_message(data))
        self.assertIn("TEST ONLY", generate_call_message(data))

    def test_save_delivers_automatically_by_default(self):
        analyzer = EarningsAnalyzer("TEST", output_format="json"); analyzer.data = sample_data()
        with tempfile.TemporaryDirectory() as directory, patch("run_analysis.deliver_reports", return_value=[{"success": True}]) as deliver:
            paths = analyzer.save(directory)
        deliver.assert_called_once(); self.assertIn("delivery", paths)

    def test_pdf_is_one_page_and_contains_sources(self):
        import pdfplumber
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.pdf"; create_one_pager_pdf(sample_data(), str(path))
            with pdfplumber.open(path) as pdf:
                self.assertEqual(len(pdf.pages), 1)
                text = pdf.pages[0].extract_text()
                links = {item.get("uri") for item in pdf.pages[0].hyperlinks}
            self.assertIn("INCOME STATEMENT HIGHLIGHTS", text)
            self.assertIn("90% CONF.", text)
            self.assertIn("Quarter Ended 2026-06-30", text)
            self.assertIn("CAPITAL & LIQUIDITY", text)
            self.assertIn("GUIDANCE & OUTLOOK", text)
            self.assertIn("EARNINGS CALL SUMMARY", text)
            self.assertIn("KEY CHANNELS & SEGMENTS", text)
            self.assertIn("STRATEGIC PILLARS", text)
            self.assertIn("KEY RISKS", text)
            self.assertIn("INVESTMENT THESIS", text)
            self.assertIn(sample_data()["sources"]["filing_url"], links)

    def test_pdf_rejects_placeholder_sources(self):
        data = sample_data(); data["sources"]["filing_url"] = "https://sec.test/filing"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "non-placeholder"):
                create_one_pager_pdf(data, str(Path(directory) / "report.pdf"))

    def test_long_recommendation_does_not_overlap_ticker(self):
        import pdfplumber
        data = sample_data(); data["thesis"]["recommendation"] = "INSUFFICIENT DATA"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "long-header.pdf"; create_one_pager_pdf(data, str(path))
            with pdfplumber.open(path) as pdf:
                words = [word for word in pdf.pages[0].extract_words() if word["top"] < 55]
        data_word = next(word for word in words if word["text"] == "DATA")
        ticker_word = next(word for word in words if word["text"] == "TEST")
        self.assertLess(data_word["x1"], ticker_word["x0"])

    def test_thesis_not_predetermined_buy(self):
        analyzer = EarningsAnalyzer("TEST")
        analyzer.data = sample_data() | {
            "financials":{"rows":[{"key":"revenue","value":90,"prior_value":100},{"key":"operating_income","value":8,"prior_value":10},{"key":"net_income","value":7,"prior_value":10},{"key":"operating_cash_flow","value":8,"prior_value":10}]},
            "transcript_insights":[{"tier":"worst"},{"tier":"worst"}],
            "valuation":{"current_price":100,"pe_ttm":50},
            "sources":{"earnings_release_url":"x","transcript_url":"y"}}
        analyzer.grade_and_thesis()
        self.assertNotEqual(analyzer.data["thesis"]["recommendation"], "BUY")

    def test_markdown_restores_both_rich_messages_and_sources(self):
        analyzer = EarningsAnalyzer("TEST")
        text = analyzer.markdown(sample_data())
        self.assertIn("Message 1 — Enhanced Dashboard", text)
        self.assertIn("Financial Highlights", text)
        self.assertIn("Key Risk Matrix", text)
        self.assertIn("Key Drivers", text)
        self.assertIn("Message 2 — Earnings Call Summary", text)
        self.assertIn("Evidence Register", text)
        self.assertIn(sample_data()["sources"]["filing_url"], text)

    def test_runtime_sources_do_not_embed_company_fixtures(self):
        source_paths = [ROOT / "run_analysis.py", ROOT / "scripts" / "analysis_enrichment.py",
                        ROOT / "scripts" / "create_one_pager_pdf.py", ROOT / "scripts" / "telegram_notify.py"]
        source = "\n".join(path.read_text() for path in source_paths)
        for forbidden in ("if self.ticker ==", "META Q", "CAT Q", "ABNB Q", "Family of Apps", "Reality Labs"):
            self.assertNotIn(forbidden, source)


class InteractiveDashboardTests(unittest.TestCase):
    def test_dashboard_schema_is_company_neutral_and_metadata_complete(self):
        data = sample_data()
        data["financials"]["key_ratios"] = [{
            "key": "operating_margin", "label": "Operating Margin", "value": 0.25,
            "display": "25.0%", "comparison": "current quarter", "signal": "positive",
        }]
        data["valuation"]["rows"] = [{
            "key": "ps_annualized", "label": "P/S (annualized)", "value": 2.0,
            "display": "2.0x", "assessment": "Moderate", "signal": "neutral",
        }]
        report = build_dashboard_data(data)
        self.assertEqual(report["company"]["ticker"], "TEST")
        cards = (report["sections"]["income_statement"] + report["sections"]["key_ratios"]
                 + report["sections"]["valuation"])
        required = {"raw_value", "display_value", "status", "description", "why_it_matters",
                    "directionality", "formula", "scale", "source_note"}
        self.assertTrue(cards)
        self.assertTrue(all(required <= set(card) for card in cards))
        ps = next(card for card in cards if card["key"] == "ps_annualized")
        self.assertGreaterEqual(len(ps["scale"]), 4)

    def test_static_site_has_required_structure_and_local_data_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(create_interactive_dashboard(sample_data(), directory))
            expected = (
                "index.html", "css/dashboard.css", "css/print.css", "js/dashboard.js",
                "assets/fonts/InterVariable.woff2", "data/report.json", "data/report.js",
                "data/TEST-2026-Q2.json",
            )
            for relative in expected:
                path = Path(directory) / relative
                self.assertTrue(path.is_file() and path.stat().st_size > 0, relative)
            self.assertIn("window.EARNINGS_REPORT", (Path(directory) / "data/report.js").read_text())
            self.assertIn('src="data/report.js"', index.read_text())

    def test_presentation_code_has_no_reference_ticker_or_fixed_metric_values(self):
        files = [ROOT / "earnings-dashboard" / "index.html",
                 ROOT / "earnings-dashboard" / "css" / "dashboard.css",
                 ROOT / "earnings-dashboard" / "css" / "print.css",
                 ROOT / "earnings-dashboard" / "js" / "dashboard.js",
                 ROOT / "scripts" / "create_interactive_dashboard.py"]
        source = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for forbidden in ("RKLB", "$234.1M", "57.9x", "$79.99", "$54.4B"):
            self.assertNotIn(forbidden, source)

    def test_section_order_interaction_and_accessibility_contract(self):
        html = (ROOT / "earnings-dashboard" / "index.html").read_text(encoding="utf-8")
        headings = [
            "Income Statement Highlights", "Key Ratios", "Valuation", "Capital &amp; Liquidity",
            "Guidance &amp; Outlook", "Earnings Call Summary", "Key Channels &amp; Segments",
            "Strategic Pillars", "Key Risks", "Investment Thesis",
        ]
        positions = [html.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('<dialog id="metric-dialog"', html)
        self.assertIn('aria-labelledby="dialog-title"', html)
        script = (ROOT / "earnings-dashboard" / "js" / "dashboard.js").read_text(encoding="utf-8")
        for behavior in ('button.type = "button"', 'dialog.showModal()', 'lastTrigger.focus()',
                         'window.print()', 'event.target.files'):
            self.assertIn(behavior, script)

    def test_a4_print_contract_and_bundled_inter_font(self):
        dashboard_css = (ROOT / "earnings-dashboard" / "css" / "dashboard.css").read_text()
        print_css = (ROOT / "earnings-dashboard" / "css" / "print.css").read_text()
        self.assertIn('font-family: "Inter"', dashboard_css)
        self.assertIn("width: 210mm", dashboard_css)
        self.assertIn("height: 297mm", dashboard_css)
        self.assertIn("@page { size: A4 portrait; margin: 0; }", print_css)
        self.assertIn("print-color-adjust: exact", print_css)
        font = ROOT / "earnings-dashboard" / "assets" / "fonts" / "InterVariable.woff2"
        self.assertTrue(font.is_file() and font.stat().st_size > 100_000)


if __name__ == "__main__": unittest.main()
