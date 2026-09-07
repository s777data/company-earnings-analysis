"""Focused cross-skill contract tests for company_valuation_score integration."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

import run_analysis


def _stdout(payload: dict) -> str:
    return "MACHINE-READABLE JSON OUTPUT\n" + json.dumps(payload)


def _valid_payload() -> dict:
    return {
        "contract_version": run_analysis.EXPECTED_VALUATION_CONTRACT_VERSION,
        "methodology_version": run_analysis.EXPECTED_VALUATION_METHODOLOGY_VERSION,
        "run_id": "run-1",
        "ticker": "IREN",
        "status": "ok",
        "final_score": 78.95,
        "grade": "B+",
        "classification": "Fair / Attractive",
        "confidence": "low",
        "business_quality": {
            "status": "ok",
            "score": 26.5,
            "grade": "F",
            "classification": "Very Weak Business Quality",
            "confidence": "medium",
        },
    }


def test_parse_valuation_output_accepts_expected_contract():
    result = run_analysis._parse_company_valuation_score_output(_stdout(_valid_payload()), "IREN")
    assert result["valuation"]["status"] == "ok"
    assert result["valuation"]["grade"] == "B+"
    assert result["business_quality"]["status"] == "ok"


def test_parse_valuation_output_rejects_contract_mismatch():
    payload = _valid_payload()
    payload["contract_version"] = "0.9"
    with pytest.raises(RuntimeError, match="VALUATION_CONTRACT_MISMATCH"):
        run_analysis._parse_company_valuation_score_output(_stdout(payload), "IREN")


def test_parse_valuation_output_fails_closed_on_insufficient_data():
    payload = _valid_payload()
    payload["status"] = "insufficient_data"
    with pytest.raises(RuntimeError, match="analytical status"):
        run_analysis._parse_company_valuation_score_output(_stdout(payload), "IREN")


def test_canonical_valuation_preflight_runs_without_pythonpath():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["COMPANY_VALUATION_EXPECTED_PACKAGE"] = str(run_analysis.VALUATION_SKILL_DIR.resolve())
    result = subprocess.run(
        [sys.executable, "-m", "company_valuation_score", "IREN", "--preflight"],
        cwd=run_analysis.VALUATION_SKILL_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    marker = "MACHINE-READABLE PREFLIGHT JSON OUTPUT"
    payload = json.loads(result.stdout.split(marker, 1)[1])
    assert payload["ready"] is True
    assert payload["contract_version"] == run_analysis.EXPECTED_VALUATION_CONTRACT_VERSION
    assert len(payload["cache"]["usable_peers"]) >= 5
