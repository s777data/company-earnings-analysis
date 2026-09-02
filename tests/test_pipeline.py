import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from run_analysis import (EarningsAnalyzer, _change, _display, _extract_investor_relations_url,
                          _validate_transcript_call_date)
from pdf_utils import (_compact_summary, _compact_items,
                                  _direction_marker, _select_call_summary_insights,
                                  COMPACT_LABELS, SEMANTIC_SYMBOL_COLORS, COLORS,
                                  validate_pdf)
from create_interactive_dashboard import build_dashboard_data, create_interactive_dashboard
from render_interactive_dashboard_pdf import render_dashboard_pdf
from robinhood_mcp_get_quote import get_quote, _decode
from sec_edgar_search import _matches_query
from telegram_notify import (generate_call_message, generate_dashboard_message,
                             _complete_insight_selection, SIGNAL_EMOJIS)
from web_search import _validate as _validate_transcript
from xbrl_parser import parse_xbrl_financials
from valuation_metrics import build_valuation_sections, MAIN_ORDER, PROFIT_ORDER, RISK_ORDER
from analysis_enrichment import (extract_transcript_sections, extract_risks, _sentences, _is_question,
                                 _qa_boundary_start, classify_financial_signal, classify_valuation_signal,
                                 classify_management_confidence, _signal as _transcript_signal)
from kpi_metrics import (ALLOWED_SOURCES, DASHBOARD_KPI_LIMIT, build_business_kpis,
                         read_derived_kpis, upsert_derived_kpis)

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


class BusinessKpiTests(unittest.TestCase):
    def _rows(self, count=13):
        rows = []
        for index in range(count):
            rows.append({
                "company": "Example Corp", "ticker": "TEST", "sector": "Industrial Technology",
                "metric": f"Operating KPI {index + 1}",
                "latest_quarter": f"Q2 2026: {index + 10}%",
                "prior_year_quarter": f"Q2 2025: {index + 8}%",
                "analyst_view": "Improved versus the prior-year quarter on a core operating driver.",
                "source": ("IR", "SEC", "IR/SEC")[index % 3],
                "importance": "Tier 1 — Core" if index < 8 else "Tier 2 — High",
            })
        return rows

    def test_reference_upsert_dedupes_and_selects_top_twelve(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "KPI_derived_reference.json"
            upsert_derived_kpis(self._rows(), path, added_on="2026-08-16")
            update = self._rows(1)[0]
            update["latest_quarter"] = "Q2 2026: 99%"
            upsert_derived_kpis([update], path, added_on="2026-08-17")
            stored = read_derived_kpis(path)
            self.assertEqual(len(stored), 13)
            self.assertEqual(stored[0]["latest_quarter"], "Q2 2026: 99%")
            self.assertEqual(stored[0]["date_added"], "2026-08-17")
            result = build_business_kpis(
                company="Example Corp", ticker="TEST", sector="Industrial Technology",
                filing_url="https://www.sec.gov/filing", release_url="https://www.sec.gov/ex99-1",
                ir_url="https://ir.example.com/q2-2026", fiscal_period="Q2", fiscal_year=2026,
                reference_path=path,
            )
        self.assertEqual(result["selection_status"], "COMPLETE")
        self.assertEqual(len(result["rows"]), DASHBOARD_KPI_LIMIT)
        self.assertTrue(all(row["source"] in ALLOWED_SOURCES for row in result["rows"]))
        self.assertEqual(result["rows"][0]["latest_quarter"], "99%")
        self.assertEqual(result["rows"][0]["latest_period"], "Q2 2026")

    def test_stale_period_rows_are_not_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "KPI_derived_reference.json"
            stale = self._rows(1)[0]
            stale["latest_quarter"] = "Q1 2026: 10%"
            upsert_derived_kpis([stale], path)
            result = build_business_kpis(
                company="Example Corp", ticker="TEST", sector="Industrial Technology",
                filing_url="https://www.sec.gov/filing", release_url=None,
                fiscal_period="Q2", fiscal_year=2026, reference_path=path,
            )
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["selection_status"], "INCOMPLETE")
        self.assertEqual(result["stale_period_rows"], 1)

    def test_missing_company_requires_derived_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            result = build_business_kpis(
                company="No Rows Inc", ticker="NONE", sector="Software",
                filing_url="https://www.sec.gov/filing", release_url=None,
                fiscal_period="Q2", fiscal_year=2026,
                reference_path=Path(directory) / "KPI_derived_reference.json",
            )
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["selection_status"], "DERIVED_REFERENCE_REQUIRED")
        self.assertIn("No current-period source-derived KPI rows exist", result["note"])

    def test_build_business_kpis_note_contains_specific_message(self):
        """Test that the note message is specific and actionable, not generic."""
        with tempfile.TemporaryDirectory() as directory:
            result = build_business_kpis(
                company="Test Corp", ticker="TEST", sector="Technology",
                filing_url="https://www.sec.gov/filing", release_url=None,
                fiscal_period="Q2", fiscal_year=2026,
                reference_path=Path(directory) / "KPI_derived_reference.txt",
            )
        # The note should be the specific message about current ticker, not generic catalogue message
        self.assertIn("current-period source-derived KPI rows exist for this ticker", result["note"])
        self.assertNotIn("business KPI catalogue was available", result["note"])


class DashboardRenderTests(unittest.TestCase):
    """Tests for dashboard data structure and rendering."""

    def test_business_kpis_object_format_in_dashboard_data(self):
        """Test that business_kpis is an object with rows, selection_status, and note."""
        from create_interactive_dashboard import build_dashboard_data
        
        sample = sample_data()
        sample["business_kpis"] = {
            "rows": [],
            "selection_status": "DERIVED_REFERENCE_REQUIRED",
            "note": "No current-period source-derived KPI rows exist for this ticker."
        }
        
        dashboard = build_dashboard_data(sample)
        kpis = dashboard["sections"]["business_kpis"]
        
        # Should be an object, not an array
        self.assertIsInstance(kpis, dict)
        self.assertIn("rows", kpis)
        self.assertIn("selection_status", kpis)
        self.assertIn("note", kpis)
        self.assertEqual(kpis["selection_status"], "DERIVED_REFERENCE_REQUIRED")
        self.assertEqual(kpis["note"], "No current-period source-derived KPI rows exist for this ticker.")

    def test_business_kpis_empty_rows_shows_correct_note(self):
        """Test that empty KPI rows use the specific note from analysis data."""
        from create_interactive_dashboard import build_dashboard_data
        
        sample = sample_data()
        sample["business_kpis"] = {
            "rows": [],
            "selection_status": "DERIVED_REFERENCE_REQUIRED",
            "note": "No current-period source-derived KPI rows exist for this ticker."
        }
        
        dashboard = build_dashboard_data(sample)
        kpis = dashboard["sections"]["business_kpis"]
        
        self.assertEqual(kpis["rows"], [])
        self.assertEqual(kpis["note"], "No current-period source-derived KPI rows exist for this ticker.")

    def test_kpi_derived_reference_populated_for_ticker_and_quarter(self):
        """Test that when KPI data is added for the ticker/quarter, it's used in analysis.
        
        This regression test ensures the workflow: BUSINESS_KPI_METRICS_REFERENCE.md 
        derivation -> KPI_derived_reference.json population -> analysis uses it.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "KPI_derived_reference.json"
            
            # Simulate deriving KPIs from IR/SEC sources per BUSINESS_KPI_METRICS_REFERENCE.md
            # for TPR Q3 FY2026
            tpr_kpi_rows = [
                {
                    "company": "Tapestry, Inc.",
                    "ticker": "TPR",
                    "sector": "Consumer Discretionary",
                    "metric": "Global Brand Revenue",
                    "latest_quarter": "Q3 2026: $1.92B",
                    "prior_year_quarter": "Q3 2025: $1.58B",
                    "analyst_view": "Global brand revenue grew 21% YoY driven by Coach and Kate Spade strength.",
                    "source": "IR/SEC",
                    "importance": "Tier 1 — Core",
                },
                {
                    "company": "Tapestry, Inc.",
                    "ticker": "TPR",
                    "sector": "Consumer Discretionary",
                    "metric": "Direct-to-Consumer Revenue",
                    "latest_quarter": "Q3 2026: $1.15B",
                    "prior_year_quarter": "Q3 2025: $0.92B",
                    "analyst_view": "DTC channel grew 25% YoY, outpacing wholesale and showing brand engagement.",
                    "source": "IR",
                    "importance": "Tier 1 — Core",
                },
                {
                    "company": "Tapestry, Inc.",
                    "ticker": "TPR",
                    "sector": "Consumer Discretionary",
                    "metric": "Operating Margin Expansion",
                    "latest_quarter": "Q3 2026: 22.3%",
                    "prior_year_quarter": "Q3 2025: 16.1%",
                    "analyst_view": "Operating margin expanded 620 bps YoY on scale and pricing power.",
                    "source": "SEC",
                    "importance": "Tier 2 — High",
                },
            ]
            
            # Populate the reference (simulates upsert_derived_kpis after manual derivation)
            upsert_derived_kpis(tpr_kpi_rows, path, added_on="2026-08-18")
            
            # Verify the reference was populated correctly
            stored = read_derived_kpis(path)
            tpr_rows = [r for r in stored if r["ticker"].casefold() == "tpr"]
            self.assertGreaterEqual(len(tpr_rows), 3)
            
            # Run build_business_kpis for the exact ticker/quarter the skill would analyze
            result = build_business_kpis(
                company="Tapestry, Inc.",
                ticker="TPR",
                sector="Consumer Discretionary",
                filing_url="https://www.sec.gov/filing",
                release_url="https://www.sec.gov/release",
                ir_url="https://ir.tapestry.com",
                fiscal_period="Q3",
                fiscal_year=2026,
                reference_path=path,
            )
            
            # Should now be INCOMPLETE with 3 rows (need 12 for COMPLETE)
            self.assertEqual(result["selection_status"], "INCOMPLETE")
            self.assertEqual(len(result["rows"]), 3)
            self.assertEqual(result["available_reference_rows"], 3)
            
            # Verify the data matches what was derived
            metrics_by_name = {row["metric"]: row for row in result["rows"]}
            self.assertIn("Global Brand Revenue", metrics_by_name)
            self.assertIn("Direct-to-Consumer Revenue", metrics_by_name)
            self.assertIn("Operating Margin Expansion", metrics_by_name)
            
            # Verify dashboard data structure includes the populated KPIs
            from create_interactive_dashboard import build_dashboard_data
            sample = sample_data()
            sample["business_kpis"] = result
            sample["ticker"] = "TPR"
            sample["fiscal_period"] = "Q3"
            sample["fiscal_year"] = 2026
            
            dashboard = build_dashboard_data(sample)
            kpi_section = dashboard["sections"]["business_kpis"]
            
            # Should be object format with rows
            self.assertIsInstance(kpi_section, dict)
            self.assertIn("rows", kpi_section)
            self.assertEqual(len(kpi_section["rows"]), 3)
            self.assertEqual(kpi_section["selection_status"], "INCOMPLETE")
            
            # Verify the note is not the generic one
            self.assertNotIn("business KPI catalogue was available", kpi_section.get("note", ""))


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

    def test_investor_relations_url_accepts_full_and_bare_official_hosts(self):
        self.assertEqual(
            _extract_investor_relations_url("Materials are available at https://ir.example.com."),
            "https://ir.example.com",
        )
        self.assertEqual(
            _extract_investor_relations_url("See ir.example.com/results for details."),
            "https://ir.example.com/results",
        )
        self.assertIsNone(_extract_investor_relations_url("https://example.com/about"))

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

    @patch("run_analysis.fetch_short_interest", side_effect=RuntimeError("not needed"))
    @patch("run_analysis.get_quote")
    @patch("run_analysis._now")
    def test_latest_completed_close_is_valid_production_data(self, now, quote, _short):
        from datetime import datetime, timezone
        now.return_value = datetime(2026, 8, 26, 20, 52, tzinfo=timezone.utc)
        quote.return_value = {
            "price": 345.73,
            "market_cap": 96_000_000_000,
            "updated_at": "2026-08-26T19:59:59+00:00",
            "source": "robinhood-trading MCP regular-session last trade",
        }
        analyzer = EarningsAnalyzer("TEST")
        analyzer.data["_xbrl"] = {
            "metrics": {"revenue": {"value": 100, "duration_days": 91}}
        }
        analyzer.quote_and_valuation()
        self.assertFalse(analyzer.data["test_run"])
        self.assertFalse(analyzer.data["valuation"]["quote_is_stale"])
        self.assertTrue(analyzer.data["valuation"]["quote_is_completed_close"])
        self.assertIn("latest completed", analyzer.data["warnings"][0])

    @patch("robinhood_mcp_get_quote._expected_account", return_value=None)
    @patch("robinhood_mcp_get_quote._call")
    def test_quote_requires_expected_account(self, call, expected):
        with self.assertRaisesRegex(RuntimeError, "ROBINHOOD_EXPECTED_ACCOUNT"):
            get_quote("TEST")
        call.assert_not_called()

class OutputTests(unittest.TestCase):
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
        # Create metrics that match the new tier1 structure - one metric per signal
        tier1_keys = ["revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "eps_diluted", "capex", "stock_based_compensation", "depreciation_amortization", "backlog", "cash", "total_assets", "total_liabilities", "total_equity", "long_term_debt", "shares_diluted"]
        data["financials"]["rows"] = []
        for i, (signal, emoji) in enumerate(spectrum.items()):
            key = tier1_keys[i % len(tier1_keys)]
            data["financials"]["rows"].append({
                "key": key, "label": f"Metric-{signal}", "display": "1", "comparison": "verified", "signal": signal
            })
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

    def test_unquantified_risks_do_not_render_na_placeholders(self):
        data = sample_data()
        data["risks"] = [{"risk": "Competition", "probability": None, "eps_impact": None,
                          "evidence": "Competition remains intense.", "signal": "caution"}]
        message = generate_dashboard_message(data)
        self.assertNotIn("N/A prob", message)
        self.assertIn("not quantified by the company", message)

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
                        ROOT / "scripts" / "telegram_notify.py", ROOT / "scripts" / "kpi_metrics.py"]
        source = "\n".join(path.read_text() for path in source_paths)
        for forbidden in ("if self.ticker ==", "META Q", "CAT Q", "ABNB Q", "CAVA", "Family of Apps", "Reality Labs"):
            self.assertNotIn(forbidden, source)

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

    def test_test_run_is_labeled_in_both_messages(self):
        data = sample_data(); data["test_run"] = True
        self.assertIn("TEST ONLY", generate_dashboard_message(data))
        self.assertIn("TEST ONLY", generate_call_message(data))

    def test_save_creates_nonempty_dashboard_zip_with_required_files(self):
        analyzer = EarningsAnalyzer("TEST", output_format="json")
        analyzer.data = sample_data()

        def create_dashboard(_data, output_dir, **_kwargs):
            root = Path(output_dir)
            files = {
                "index.html": "<html><body>dashboard</body></html>",
                "css/dashboard.css": "body { color: #111; }",
                "js/dashboard.js": "window.EARNINGS_REPORT = {};",
                "data/report.json": "{}",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            return str(root / "index.html")

        with tempfile.TemporaryDirectory() as directory, \
                patch("run_analysis.create_interactive_dashboard", side_effect=create_dashboard), \
                patch("run_analysis.render_dashboard_pdf", return_value="/tmp/dashboard.pdf"):
            paths = analyzer.save(directory, deliver=False)
            archive = Path(paths["dashboard_zip"])
            self.assertTrue(archive.is_file())
            self.assertGreater(archive.stat().st_size, 0)
            self.assertTrue(zipfile.is_zipfile(archive))
            with zipfile.ZipFile(archive) as zipped:
                names = set(zipped.namelist())
                prefix = "TEST_Q2_FY2026_Interactive_Dashboard/"
                required = {
                    prefix + "index.html",
                    prefix + "css/dashboard.css",
                    prefix + "js/dashboard.js",
                    prefix + "data/report.json",
                }
                self.assertTrue(required <= names)
                self.assertTrue(all(zipped.getinfo(name).file_size > 0 for name in required))

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

    def test_income_highlights_are_all_eight_tier_one_metrics_in_reference_order(self):
        data = sample_data()
        rows = [
            {"key": "cash", "label": "Cash", "value": 500, "display": "$500"},
            {"key": "net_income", "label": "Net Income", "value": 40, "display": "$40"},
            {"key": "revenue", "label": "Revenue", "value": 200, "display": "$200"},
            {"key": "operating_income", "label": "Operating Income", "value": 60, "display": "$60"},
            {"key": "gross_profit", "label": "Gross Profit", "value": 90, "display": "$90"},
            {"key": "eps_diluted", "label": "Diluted EPS", "value": 1, "display": "$1"},
            {"key": "operating_cash_flow", "label": "Operating Cash Flow", "value": 70, "display": "$70"},
            {"key": "free_cash_flow", "label": "Free Cash Flow", "value": 55, "display": "$55"},
            {"key": "capex", "label": "Capital Expenditures", "value": 15, "display": "$15"},
        ]
        data["financials"]["rows"] = rows
        keys = [card["key"] for card in build_dashboard_data(data)["sections"]["income_statement"]]
        self.assertEqual(keys, [
            "revenue", "gross_profit", "operating_income", "net_income",
            "free_cash_flow", "operating_cash_flow", "capex", "eps_diluted",
        ])
        comparisons = [card["comparison"] for card in build_dashboard_data(data)["sections"]["income_statement"]]
        self.assertTrue(all("YoY" in value and "QoQ" in value for value in comparisons))

    def test_key_ratios_keep_reference_metrics_and_add_yoy_qoq_to_tier_one(self):
        data = sample_data()
        data["financials"]["rows"] = [
            {"key": "revenue", "label": "Revenue", "value": 200, "prior_value": 160, "prior_q_value": 180},
            {"key": "gross_profit", "label": "Gross Profit", "value": 100, "prior_value": 72, "prior_q_value": 81},
            {"key": "operating_income", "label": "Operating Income", "value": 40, "prior_value": 24, "prior_q_value": 27},
            {"key": "net_income", "label": "Net Income", "value": 20, "prior_value": 8, "prior_q_value": 9},
            {"key": "stock_based_compensation", "label": "Stock-Based Compensation", "value": 10,
             "prior_value": 6.4, "prior_q_value": 7.2},
        ]
        data["financials"]["key_ratios"] = [
            {"key": "gross_margin", "label": "Gross Margin", "value": .5, "display": "50.0%", "signal": "positive"},
            {"key": "operating_margin", "label": "Operating Margin", "value": .2, "display": "20.0%", "signal": "positive"},
            {"key": "net_margin", "label": "Net Margin", "value": .1, "display": "10.0%", "signal": "positive"},
            {"key": "sbc_revenue", "label": "SBC / Revenue", "value": .05, "display": "5.0%", "signal": "neutral"},
            {"key": "revenue_growth", "label": "Revenue Growth", "display": "+25.0%", "signal": "positive"},
        ]
        cards = build_dashboard_data(data)["sections"]["key_ratios"]
        self.assertEqual([card["key"] for card in cards], [
            "gross_margin", "operating_margin", "net_margin", "sbc_revenue",
        ])
        self.assertTrue(all("YoY" in card["comparison"] and "QoQ" in card["comparison"] for card in cards))
        self.assertEqual(cards[0]["comparison"], "+5.0 pp YoY, +5.0 pp QoQ")

    def test_kpi_section_maps_top_twelve_source_derived_cards_and_telegram_fields(self):
        data = sample_data()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "KPI_derived_reference.json"
            upsert_derived_kpis(BusinessKpiTests()._rows(), path, added_on="2026-08-16")
            data["business_kpis"] = build_business_kpis(
                company="Example Corp", ticker="TEST", sector="Industrial Technology",
                filing_url=data["sources"]["filing_url"],
                release_url="https://www.sec.gov/Archives/edgar/data/1/ex99-1.htm",
                ir_url="https://ir.example.com/q2-2026",
                fiscal_period="Q2", fiscal_year=2026, reference_path=path,
            )
        cards = build_dashboard_data(data)["sections"]["business_kpis"]["rows"]
        self.assertEqual(len(cards), 12)
        required = {"name", "latest_value", "latest_period", "prior_value", "prior_period",
                    "analyst_view", "source", "importance", "status", "source_note"}
        self.assertTrue(all(required <= set(card) for card in cards))
        message = generate_dashboard_message(data)
        self.assertLess(message.index("🎯 **KPI**"), message.index("📊 **Key Ratios**"))
        self.assertIn("Q2 2026: **10%**", message)
        self.assertIn("Q2 2025: **8%**", message)
        self.assertIn("[IR · T1 — Core]", message)

    def test_reference_scorecard_structure_is_shared_and_data_driven(self):
        html = (ROOT / "earnings-dashboard" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "earnings-dashboard" / "css" / "dashboard.css").read_text(encoding="utf-8")
        script = (ROOT / "earnings-dashboard" / "js" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn('class="scorecard-section income-section"', html)
        self.assertIn('class="scorecard-section kpi-section"', html)
        self.assertIn('id="kpi-cards"', html)
        self.assertIn('class="scorecard-section ratio-section"', html)
        self.assertIn("Overview of key financial performance metrics", html)
        self.assertGreaterEqual(css.count("repeat(8, minmax(0, 1fr))"), 2)
        self.assertIn(".kpi-card-shell", css)
        self.assertIn("container-type: size", css)
        self.assertIn("--kpi-scale: clamp(", css)
        self.assertIn("min(1cqw, 1.15cqh)", css)
        self.assertIn("calc(var(--kpi-scale)", css)
        self.assertIn("minmax(calc(var(--kpi-scale)", css)
        self.assertNotIn("grid-template-rows: 6.2mm 2.8mm .2mm 1.7mm 5.8mm", css)
        self.assertIn(".kpi-grid--single .kpi-card-shell", css)
        self.assertIn("height: 28.5mm", css)
        self.assertIn(".kpi-grid--double .kpi-card-shell", css)
        self.assertIn("height: 23.75mm", css)
        self.assertIn("repeat(var(--kpi-columns, 8), minmax(0, 1fr))", css)
        self.assertIn("repeat(var(--ratio-columns, 8), minmax(0, 1fr))", css)
        self.assertIn("min-height: 8.5mm", css)
        self.assertIn("height: 10mm", css)
        self.assertIn("height: 9mm", css)
        self.assertIn(".bottom-grid section { height: 12mm;", css)
        self.assertIn("height: 10mm", css)
        self.assertIn("metric-card--income", css)
        self.assertIn(".kpi-card", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto", css)
        self.assertIn("flex-direction: column", css)
        self.assertIn(".kpi-divider", css)
        self.assertIn(".kpi-card-name", css)
        self.assertIn("font-size: calc(var(--kpi-scale)", css)
        self.assertIn(".kpi-latest strong.kpi-value--long", css)
        self.assertIn(".kpi-prior strong.kpi-value--long", css)
        self.assertIn("box-shadow: inset 0 0 0 calc(var(--kpi-scale)", css)
        self.assertIn("height: calc(var(--kpi-scale)", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("metric-card--ratio", css)
        self.assertIn('renderMetrics("income-cards", sections.income_statement, "income")', script)
        self.assertIn('header.className = "kpi-card-header"', script)
        self.assertIn('latestText.length > 12', script)
        self.assertIn('priorText.length > 12', script)
        self.assertIn('latestValue.classList.add("kpi-value--long")', script)
        self.assertIn('priorValue.classList.add("kpi-value--long")', script)
        self.assertIn('divider.className = "kpi-divider"', script)
        self.assertIn("button.append(header, latest, divider, prior, view)", script)
        self.assertIn('shell.className = "kpi-card-shell"', script)
        self.assertIn('shell.append(kpiCard(metric))', script)
        self.assertNotIn("kpiYoy", script)
        self.assertIn('row.className = "kpi-row"', script)
        self.assertIn('row.style.setProperty("--kpi-columns", String(rowItems.length))', script)
        self.assertIn("const split = Math.ceil(items.length / 2)", script)
        self.assertIn('container.classList.add(items.length <= 8 ? "kpi-grid--single" : "kpi-grid--double")', script)
        self.assertIn('container.style.setProperty("--ratio-columns", String(Math.max(items.length, 1)))', script)
        self.assertIn("renderKpis(sections.business_kpis)", script)
        self.assertIn('renderMetrics("ratio-cards", sections.key_ratios, "ratio")', script)

    def test_short_interest_sbc_keeps_tier_one_placeholders_and_selected_tier_two(self):
        data = sample_data()
        data["valuation"]["risk_rows"] = [{
            "key": "sbc_fcf", "label": "SBC / Free Cash Flow", "value": 12,
            "display": "12.0%", "assessment": "Strong", "signal": "positive", "tier": 2,
        }]
        rows = build_dashboard_data(data)["sections"]["short_interest_sbc"]
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["name"], "Short Interest % of Float")
        self.assertEqual(rows[0]["detail"], "N/A — Unavailable")
        self.assertEqual(rows[3]["name"], "SBC / Free Cash Flow")

    def test_valuation_one_row_limit_never_drops_applicable_tier_one_metrics(self):
        data = sample_data()
        data["valuation"]["rows"] = [
            {"key": f"metric_{index}", "label": f"Metric {index}", "value": index + 1,
             "display": f"{index + 1}.0x", "tier": 1 if index in {0, 7, 8, 9} else 2}
            for index in range(10)
        ]
        rows = build_dashboard_data(data)["sections"]["valuation"]
        self.assertEqual(len(rows), 8)
        self.assertTrue({"metric_0", "metric_7", "metric_8", "metric_9"} <= {row["key"] for row in rows})

    def test_narrative_sections_keep_complete_sentences_and_signal_colors(self):
        data = sample_data()
        data["channels"] = {"items": [
            {"name": "Growth", "desc": "A strong pipeline supports growth."},
            {"name": "Pressure", "desc": "Revenue recorded a 30% decrease."},
        ]}
        data["earnings_call_summary"] = {"insights": [{
            "topic": "Management Tone", "detail": "Demand remains durable.",
            "signal": "positive", "confidence_category": "Confident",
            "confidence_subcategory": "Assured",
        }]}
        report = build_dashboard_data(data)
        self.assertEqual([row["signal"] for row in report["sections"]["channels"]], ["positive", "negative"])
        self.assertEqual(
            report["sections"]["earnings_call"][0]["detail"],
            "Confident → Assured, Demand remains durable.",
        )

        css = (ROOT / "earnings-dashboard" / "css" / "dashboard.css").read_text(encoding="utf-8")
        script = (ROOT / "earnings-dashboard" / "js" / "dashboard.js").read_text(encoding="utf-8")
        for call in (
            'renderList("capital-content", sections.capital_liquidity, 8);',
            'renderList("guidance-content", sections.guidance, 6);',
            'renderList("call-content", sections.earnings_call, 8);',
        ):
            self.assertIn(call, script)
        self.assertIn('body.textContent = text(detailOf(item), "Not available")', script)
        self.assertIn("fitNarrativeSections", script)
        self.assertIn('document.body.dataset.layoutReady = "true"', script)
        self.assertIn(".channel-card { height: 10mm;", css)
        self.assertIn(".pillar-card { height: 9mm;", css)
        self.assertNotIn("color: var(--ink); font-size: 6.1px", css)
        self.assertIn(".dense-item > span:last-child { color: currentColor; }", css)
        self.assertIn(".channel-card > div { color: currentColor;", css)
        self.assertIn(".pillar-card > div { color: currentColor;", css)

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

    def test_latest_repository_dashboard_data_replaces_stale_ticker_json(self):
        import create_interactive_dashboard as dashboard_module
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "template"
            shutil.copytree(ROOT / "earnings-dashboard", template)
            stale = template / "data" / "STALE-2025-Q1.json"
            stale.write_text("{}", encoding="utf-8")
            output = Path(directory) / "output"
            with patch.object(dashboard_module, "TEMPLATE_DIR", template):
                dashboard_module.create_interactive_dashboard(
                    sample_data(), str(output), publish_template_data=True,
                )
            json_names = sorted(path.name for path in (template / "data").glob("*.json"))
            self.assertEqual(json_names, ["TEST-2026-Q2.json", "report.json"])
            self.assertFalse(stale.exists())

    def test_presentation_code_has_no_reference_ticker_or_fixed_metric_values(self):
        files = [ROOT / "earnings-dashboard" / "index.html",
                 ROOT / "earnings-dashboard" / "css" / "dashboard.css",
                 ROOT / "earnings-dashboard" / "css" / "print.css",
                 ROOT / "earnings-dashboard" / "js" / "dashboard.js",
                 ROOT / "scripts" / "create_interactive_dashboard.py"]
        source = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for forbidden in ("RKLB", "$234.1M", "57.9x", "$79.99", "$54.4B"):
            self.assertNotIn(forbidden, source)


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

    def test_browser_pdf_renderer_waits_for_final_cards_and_validates_output(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / "index.html"
            output = Path(directory) / "rendered.pdf"
            executable = Path(directory) / "playwright"
            html.write_text("<html></html>")
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o755)

            def completed(command, **_kwargs):
                Path(command[-1]).write_bytes(b"%PDF-1.7\n" + b"x" * 1200)
                return subprocess.CompletedProcess(command, 0, "rendered", "")

            with patch("render_interactive_dashboard_pdf.subprocess.run", side_effect=completed) as run, \
                    patch("render_interactive_dashboard_pdf.validate_pdf") as validate:
                result = render_dashboard_pdf(
                    str(html), str(output), ["https://www.sec.gov/filing"], str(executable)
                )
            self.assertEqual(result, str(output.resolve()))
            command = run.call_args.args[0]
            self.assertIn("--wait-for-selector", command)
            self.assertIn("body[data-layout-ready='true'] #valuation-cards .gauge-card", command)
            self.assertIn(html.resolve().as_uri(), command)
            # Interactive dashboard PDF validates structure only; clickable links
            # are verified on the one-pager PDF. Expect empty URL list.
            validate.assert_called_once_with(str(output.resolve()), [])

class ValuationGuideTests(unittest.TestCase):
    def _sections(self, positive=False):
        return build_valuation_sections(
            market_cap=10_000, enterprise_value=9_000, annual_revenue=2_000,
            annual_gross_profit=800, revenue_growth_pct=25, total_equity=4_000,
            backlog=3_000, annual_net_income=500 if positive else -500,
            annual_fcf=400 if positive else -400, annual_ebit=600 if positive else -600,
            annual_ebitda=800 if positive else None, trailing_pe=20 if positive else -20,
            forward_pe=18 if positive else None, peg_ratio=1.4 if positive else None,
            short_interest=100, public_float=1_000, days_to_cover=2.5,
            stock_compensation=50, period_revenue=2_000,
            period_fcf=400 if positive else -400,
            diluted_shares=110, prior_diluted_shares=100,
        )

    def test_negative_regime_keeps_main_metrics_then_unique_negative_metric(self):
        result = self._sections(False)
        keys = [row["key"] for row in result["rows"]]
        self.assertEqual(result["regime"], "negative_earnings_or_fcf")
        self.assertEqual(keys[:5], list(MAIN_ORDER))
        self.assertEqual(keys.count("ev_revenue"), 1)
        self.assertEqual(keys[-1], "ev_backlog")

    def test_positive_regime_uses_tier_order_and_omits_negative_only_metric(self):
        result = self._sections(True)
        keys = [row["key"] for row in result["rows"]]
        self.assertEqual(result["regime"], "positive_earnings_and_fcf")
        expected_profit = [key for key in PROFIT_ORDER if key in keys]
        actual_profit = [key for key in keys if key in PROFIT_ORDER]
        self.assertEqual(actual_profit, expected_profit)
        self.assertNotIn("ev_backlog", keys)

    def test_risk_metrics_follow_guide_order_and_require_meaningful_denominators(self):
        negative = self._sections(False)
        keys = [row["key"] for row in negative["risk_rows"]]
        self.assertEqual(keys, [key for key in RISK_ORDER if key in keys])
        self.assertNotIn("sbc_fcf", keys)
        self.assertIn("days_to_cover", keys)
        self.assertIn("net_share_dilution", keys)

    def test_reference_file_and_compact_eight_column_gauge_contract(self):
        reference = ROOT / "references" / "VALUATION_METRICS_REFERENCE_MAIN_METRICS_REVIEW.txt"
        self.assertTrue(reference.is_file())
        self.assertIn("MAIN VALUE METRICS", reference.read_text(encoding="utf-8"))
        html = (ROOT / "earnings-dashboard" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "earnings-dashboard" / "css" / "dashboard.css").read_text(encoding="utf-8")
        script = (ROOT / "earnings-dashboard" / "js" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn('id="short-interest-content"', html)
        self.assertIn("grid-template-columns: repeat(8, minmax(0, 1fr))", css)
        self.assertIn("(metrics || []).slice(0, 8)", script)
        self.assertIn("function gaugeCard(metric)", script)
        self.assertIn("gauge-segment", script)
        self.assertIn('renderList("short-interest-content", sections.short_interest_sbc, 6)', script)


if __name__ == "__main__": unittest.main()
