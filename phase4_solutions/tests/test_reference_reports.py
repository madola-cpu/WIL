"""Phase 4 must reproduce the fix tables of both reference reports exactly."""
import json
import pathlib

import pytest

from phase4 import run_phase4
from phase4.reference import compare_to_reference, format_rows

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("sample,expected", [
    ("veloran_input.json", "veloran_expected.json"),
    ("corlander_vale_input.json", "corlander_vale_expected.json"),
])
def test_matches_reference_report(sample, expected):
    out = run_phase4(load(ROOT / "samples" / sample))
    rows = compare_to_reference(out, load(ROOT / "reference" / expected))
    assert len(rows) >= 70
    assert all(r["ok"] for r in rows), format_rows(rows, only_failures=True)


def test_veloran_program_totals():
    p = run_phase4(load(ROOT / "samples" / "veloran_input.json"))["program"]
    assert p["year_one_cost"]["base"] == 79520
    assert p["annual_savings"]["base"] == 589680
    assert p["payback_months"]["base"] == 1.6
    assert p["net_benefit_year_one"]["base"] == 510160
    assert p["effective_hours_saved_per_week"]["base"] == 136.5
    assert round(p["share_of_lost_hours_recovered"], 2) == 0.48
    assert "1.6 months" in p["summary"] and "$589,680" in p["summary"]


def test_veloran_reasons_match_the_report():
    out = run_phase4(load(ROOT / "samples" / "veloran_input.json"))
    opts = {o["fix_id"]: o for b in out["bottlenecks"] for o in b["options"]}

    forecast = opts["ai_capacity_forecasting"]
    assert forecast["status"] == "deferred"
    assert "12 months" in forecast["status_reason"] and "PSA tool creates this" in forecast["status_reason"]

    notes = opts["ai_meeting_notes"]
    assert notes["status"] == "on_hold"
    assert "consent" in notes["status_reason"]
    assert any("Meeting and status reset" in r for r in notes["other_reasons"])

    psa_time = opts["psa_time_module"]
    assert psa_time["status"] == "follow_on"
    assert "double counting" in psa_time["status_reason"]
    assert "BN-1" in psa_time["status_reason"]


def test_corlander_reasons_match_the_report():
    out = run_phase4(load(ROOT / "samples" / "corlander_vale_input.json"))
    opts = {o["fix_id"]: o for b in out["bottlenecks"] for o in b["options"]}
    assert "portal sends reminders" in opts["ai_followup_assistant"]["status_reason"]
    assert opts["ai_pre_review"]["status"] == "on_hold"
    assert any("Client portal" in r for r in opts["ai_pre_review"]["other_reasons"])
    assert opts["offshore_data_entry"]["status"] == "on_hold"
    gates = [g["action"] for g in out["program"]["governance_actions"]]
    assert any("no training on client data" in g for g in gates)
