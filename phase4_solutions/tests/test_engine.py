"""Behaviour checks: scenario B, validation, privacy, dependencies, AI text guard, CLI."""
import copy
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from phase4 import Catalog, CatalogError, Phase4InputError, Phase4Options, run_phase4
from phase4.narrative import check_numbers
from phase4.numbers import payback_months, round_to_step
from phase4.pricing import combine

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 22, tzinfo=timezone.utc)


def load(name):
    with open(ROOT / "samples" / name, encoding="utf-8") as fh:
        return json.load(fh)


def option(out, fix_id):
    return next(o for b in out["bottlenecks"] for o in b["options"] if o["fix_id"] == fix_id)


def bottleneck(out, bid):
    return next(b for b in out["bottlenecks"] if b["id"] == bid)


# ------------------------------------------------------------- scenario B
def test_scenario_b_gets_its_own_fix_list():
    out = run_phase4(load("acquisition_input.json"))
    assert out["run"]["catalogs"][0]["catalog_id"] == "acquisition"
    for b in out["bottlenecks"]:
        assert b["recommendation"], b["notes"]
        assert b["recommendation"]["annual_deal_margin"]["base"] > 0
        assert all(o["status"] for o in b["options"])
    assert "placeholder" in option(out, "approval_workflow")["price_statuses"]
    assert "deals a year" in bottleneck(out, "BN-B1")["recommendation"]["summary"]


def test_low_case_is_never_better_than_high_case():
    for name in ("veloran_input.json", "acquisition_input.json"):
        p = run_phase4(load(name))["program"]
        assert p["annual_savings"]["low"] <= p["annual_savings"]["base"] <= p["annual_savings"]["high"]
        assert p["year_one_cost"]["low"] >= p["year_one_cost"]["base"]


# ------------------------------------------------------------- contract
def test_output_matches_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema_in = json.loads((ROOT / "contracts" / "phase4_input.schema.json").read_text())
    schema_out = json.loads((ROOT / "contracts" / "phase4_output.schema.json").read_text())
    for name in ("veloran_input.json", "corlander_vale_input.json", "acquisition_input.json"):
        data = load(name)
        jsonschema.validate(data, schema_in)
        jsonschema.validate(json.loads(json.dumps(run_phase4(data))), schema_out)


def test_bad_input_lists_every_problem():
    data = load("veloran_input.json")
    data["run"]["scenario"] = "C"
    del data["company"]["employees_total"]
    data["bottlenecks"][0]["hours_lost_per_week"] = {"low": 200, "base": 129, "high": 140}
    with pytest.raises(Phase4InputError) as err:
        run_phase4(data)
    text = str(err.value)
    assert "run.scenario" in text and "employees_total" in text and "low <= base <= high" in text


def test_annual_cost_mismatch_is_a_warning_not_an_error():
    data = load("veloran_input.json")
    data["bottlenecks"][0]["annual_cost"] = 600000
    out = run_phase4(data)
    assert any("differs by more than 1%" in w for w in out["warnings"])


def test_runs_are_deterministic():
    data = load("veloran_input.json")
    assert run_phase4(copy.deepcopy(data), now=NOW) == run_phase4(copy.deepcopy(data), now=NOW)


# ------------------------------------------------------------- privacy and scope
def test_groups_under_five_are_left_out():
    data = load("veloran_input.json")
    data["bottlenecks"][2]["employees_affected"] = 4
    out = run_phase4(data)
    assert "BN-3" not in [b["id"] for b in out["bottlenecks"]]
    assert any(b["id"] == "BN-3" and "under 5" in b["reason"] for b in out["bottlenecks_not_in_scope"])
    assert any("fewer than 5" in w for w in out["warnings"])


def test_keyword_match_when_step7_sends_no_category():
    data = load("veloran_input.json")
    del data["bottlenecks"][2]["category"]
    b = bottleneck(run_phase4(data), "BN-3")
    assert b["category"] == "time_capture" and b["category_match"]["method"] == "keywords"


def test_one_shared_word_is_not_enough_to_match():
    data = load("veloran_input.json")
    out = run_phase4(data, Phase4Options(top_n=None))
    rework = bottleneck(out, "BN-7")  # "Data-migration rework" shares only "rework" with review queues
    assert rework["category"] is None and rework["recommendation"] is None
    assert any("BN-7" in w for w in out["warnings"])


# ------------------------------------------------------------- choosing
def test_follow_on_is_blocked_when_its_parent_fix_is_not_chosen():
    data = load("veloran_input.json")
    data["bottlenecks"] = [b for b in data["bottlenecks"] if b["id"] == "BN-3"]
    o = option(run_phase4(data), "psa_time_module")
    assert o["status"] == "blocked" and "PSA tool" in o["status_reason"]


def test_consent_lifts_the_hold_but_the_conflict_remains():
    data = load("veloran_input.json")
    data["company"]["capabilities"]["call_recording_consent"] = True
    out = run_phase4(data)
    o = option(out, "ai_meeting_notes")
    assert o["status"] == "blocked" and "summarize meetings the reset cancels" in o["status_reason"]
    assert bottleneck(out, "BN-2")["recommendation"]["fix_ids"] == ["meeting_reset", "system_of_record"]


def test_clean_history_makes_the_forecast_eligible_but_it_still_loses():
    data = load("veloran_input.json")
    data["company"]["capabilities"]["clean_staffing_history_months"] = 24
    o = option(run_phase4(data), "ai_capacity_forecasting")
    assert o["status"] == "not_chosen" and "nets" in o["status_reason"]


def test_single_fix_mode():
    out = run_phase4(load("veloran_input.json"), Phase4Options(max_fixes_per_bottleneck=1))
    assert bottleneck(out, "BN-1")["recommendation"]["fix_ids"] == ["psa_tool"]


def test_payback_limit_can_leave_a_bottleneck_without_a_recommendation():
    data = load("veloran_input.json")
    data["assumptions"]["max_payback_months"] = 0.4
    b = bottleneck(run_phase4(data), "BN-1")
    assert b["recommendation"] is None and b["notes"]


def test_missing_planning_number_sets_fix_aside():
    data = load("corlander_vale_input.json")
    del data["company"]["volumes"]["complex_returns_per_year"]
    out = run_phase4(data)
    o = option(out, "ai_document_extraction")
    assert o["status"] == "needs_input" and "complex_returns_per_year" in o["status_reason"]
    assert bottleneck(out, "BN-3")["recommendation"]["fix_ids"] == ["import_first"]


def test_skill_signals_aim_reskilling_fixes():
    data = load("veloran_input.json")
    data["skill_signals"] = [
        {"team": "Data & AI Practice", "skill": "Salesforce Data Cloud", "signal": "gap", "people": 9},
        {"team": "Growth", "skill": "Proposal writing", "signal": "gap", "people": 3},
    ]
    o = option(run_phase4(data), "capacity_council")
    assert [t["skill"] for t in o["reskilling_targets"]] == ["Salesforce Data Cloud"]  # group of 3 is dropped


# ------------------------------------------------------------- maths
def test_rounding_is_half_up_like_a_spreadsheet():
    assert round_to_step(Decimal("2.5")) == 3
    assert round_to_step(Decimal("84.99")) == 85
    assert payback_months(3600, 90720) == 0.5
    assert payback_months(0, 1000) == 0.0
    assert payback_months(1000, 0) is None


def test_two_fixes_combine_symmetrically():
    def overlap(_a, _b):
        return Decimal("0.25")

    a, _ = combine([("x", Decimal(60)), ("y", Decimal(30))], overlap)
    b, _ = combine([("y", Decimal(30)), ("x", Decimal(60))], overlap)
    assert a == b == Decimal("82.5")  # 60 + 30 - 0.25 x 30


def test_broken_catalog_is_reported():
    doc = json.loads((ROOT / "phase4" / "data" / "catalog_workplace.json").read_text())
    doc["categories"]["time_capture"]["fixes"].append("no_such_fix")
    doc["fixes"]["daily_time_rule"]["fix_type"] = "magic"
    with pytest.raises(CatalogError) as err:
        Catalog([doc])
    assert "no_such_fix" in str(err.value) and "fix_type" in str(err.value)


# ------------------------------------------------------------- AI text guard
class FakeClaude:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


def _run_with(client):
    data = load("veloran_input.json")
    data["bottlenecks"] = data["bottlenecks"][:1]
    return run_phase4(data, Phase4Options(ai_text=True, ai_model="test-model"), ai_client=client)


def test_claude_text_is_used_when_every_number_checks_out():
    reply = ("We recommend Options 2 and 3 together. The PSA shows capacity eight weeks out and the council "
             "acts on it. Together they save 85 hours a week, or $257,040 a year, for $58,600 in year one, "
             "a payback of 2.7 months. Option 1 waits for 12 months of clean booking data.")
    rec = _run_with(FakeClaude(reply))["bottlenecks"][0]["recommendation"]
    assert rec["summary"] == reply and rec["summary_source"] == "claude:test-model"


def test_claude_text_with_an_invented_number_falls_back():
    out = _run_with(FakeClaude("Together they save 85 hours a week and $300,000 a year."))
    rec = out["bottlenecks"][0]["recommendation"]
    assert rec["summary_source"] == "template" and rec["summary"] == rec["summary_template"]
    assert any("300000" in w for w in out["warnings"])


def test_claude_failure_never_breaks_the_run():
    out = _run_with(FakeClaude(error=RuntimeError("no API key")))
    assert out["bottlenecks"][0]["recommendation"]["summary_source"] == "template"
    assert any("no API key" in w for w in out["warnings"])


def test_number_guard_accepts_formatting_but_not_new_numbers():
    facts = {"annual_savings": 257040, "payback_months": 2.7, "adoption": 0.7}
    assert check_numbers("$257,040 a year, 2.7 months, at 70% adoption", facts)[0]
    assert not check_numbers("about $260,000 a year", facts)[0]


# ------------------------------------------------------------- CLI
def _cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-m", "phase4", *args], cwd=ROOT, input=stdin,
                          capture_output=True, text=True, timeout=60)


def test_cli_check_passes_for_both_reports():
    for sample, expected in (("veloran", "veloran"), ("corlander_vale", "corlander_vale")):
        res = _cli("check", f"samples/{sample}_input.json", "--expected", f"reference/{expected}_expected.json")
        assert res.returncode == 0, res.stdout + res.stderr
        assert "75 of 75 checks match" in res.stdout


def test_cli_reads_stdin_and_writes_json():
    res = _cli("run", "-", stdin=(ROOT / "samples" / "acquisition_input.json").read_text())
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["schema_version"].startswith("phase4-output/")


def test_cli_reports_bad_input_with_exit_code_2():
    res = _cli("run", "-", stdin=json.dumps({"schema_version": "phase4-input/1.0"}))
    assert res.returncode == 2 and "not valid" in res.stderr
