"""Regression guard for the source-derived IREN Q4 FY2026 KPI reference."""
import json
from pathlib import Path

from scripts.kpi_metrics import build_business_kpis


REFERENCE = Path(__file__).resolve().parents[1] / "references" / "KPI_derived_reference.json"


def test_iren_q4_fy2026_reference_is_complete_and_not_annual_cost_data():
    rows = [row for row in json.loads(REFERENCE.read_text()) if row.get("TICKER") == "IREN"]
    assert len(rows) >= 12
    assert not any("electricity expense" in row["metric"].lower() for row in rows)
    assert not any("employee benefits expense" in row["metric"].lower() for row in rows)

    selected = build_business_kpis(
        company="IREN Limited",
        ticker="IREN",
        sector="Digital Infrastructure / AI Cloud & Bitcoin Mining",
        filing_text="",
        release_text="",
        filing_url="https://www.sec.gov/Archives/edgar/data/1878848/000187884826000052/iren-20260630.htm",
        release_url="https://www.sec.gov/Archives/edgar/data/1878848/000187884826000051/irenreportsfy26results.htm",
        ir_url="https://iren.com/investor/events-and-presentations",
        fiscal_period="Q4",
        fiscal_year=2026,
    )
    assert selected["selection_status"] == "COMPLETE"
    assert selected["available_reference_rows"] >= 12
    assert len(selected["rows"]) == 12
    assert all(row["latest_period"] == "Q4 2026" for row in selected["rows"])
