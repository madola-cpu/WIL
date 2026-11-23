"""Connectors: Phase 3 -> Phase 4 adapter, Phase 5 report, manager view, pipeline, HTTP service, CLI."""
import copy
import json
import pathlib
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

from phase4 import run_phase4
from phase4.connectors import (Phase3MappingError, from_phase3, manager_view, read_phase3_file, report_blocks,
                               report_markdown, scorecard)
from phase4.pipeline import run_pipeline, write_pipeline_files

ROOT = pathlib.Path(__file__).resolve().parents[1]
EX = ROOT / "examples" / "phase3"


def phase3_json():
    return json.loads((EX / "veloran_step7_8.json").read_text())


# ------------------------------------------------------------------ Phase 3 -> Phase 4
def test_differently_shaped_phase3_output_still_reproduces_the_veloran_report():
    phase4_input, report = from_phase3(phase3_json(), profile="veloran")
    assert report["found"] == {"bottlenecks_at": "step7.bottlenecks", "bottleneck_count": 7,
                               "roi_at": "step8.roi", "roi_matched": 7}
    assert report["client"]["loaded_hourly_rate"] == "phase 3: assumptions.hourlyRate"
    assert report["client"]["employees_total"] == "profile"
    staffing = report["bottlenecks"][0]
    assert staffing["category"]["value"] == "staffing_visibility"
    assert staffing["fields"]["hours_lost_per_week"] == "step 8: hoursLostPerWeek"
    card = scorecard(run_phase4(phase4_input), "veloran")
    assert card["passed"] and card["matched"] == card["checks"] == 75, card["markdown"]


def test_csv_from_phase3_reproduces_the_veloran_report_and_reads_flat_ranges():
    phase4_input, report = from_phase3(read_phase3_file(EX / "veloran_bottlenecks.csv"), profile="veloran")
    first = phase4_input["bottlenecks"][0]
    assert first["hours_lost_per_week"] == {"low": 116, "base": 129, "high": 148}
    assert first["departments"][:2] == ["CRM Practice", "Data & AI Practice"]
    assert "Hours lost per week low" not in report["bottlenecks"][0]["ignored_fields"]
    assert scorecard(run_phase4(phase4_input), "veloran")["passed"]


def test_option_b_reads_deals_percent_margins_and_profile_defaults():
    phase4_input, _ = from_phase3(read_phase3_file(EX / "acquisition_step7_8.json"), profile="acquisition_example")
    b1, b2 = phase4_input["bottlenecks"]
    assert phase4_input["run"]["scenario"] == "B"
    assert b1["deal_impact"]["contribution_margin"] == 0.38  # "38%" in the file
    assert b2["deal_impact"]["contribution_margin"] == 0.38  # missing -> profile default
    out = run_phase4(phase4_input)
    assert out["program"]["annual_deal_margin"]["base"] > 0


def test_missing_required_fields_are_named():
    data = phase3_json()
    del data["step7"]["bottlenecks"][1]["peopleAffected"]
    with pytest.raises(Phase3MappingError) as err:
        from_phase3(data, profile="veloran")
    assert "Status reporting" in str(err.value) and "people affected" in str(err.value)
    assert err.value.report["found"]["bottleneck_count"] == 7


def test_no_bottleneck_list_says_how_to_point_at_it():
    with pytest.raises(Phase3MappingError) as err:
        from_phase3({"meta": {"week": 49}}, profile="veloran")
    assert "bottlenecks_path" in str(err.value)


def test_explicit_mapping_handles_unusual_names():
    data = {"weekly": {"problems": [
        {"label_text": "Timesheets rebuilt from memory", "n_staff": 42, "loss": {"hrs": 42}},
    ]}}
    mapping = {"bottlenecks_path": "weekly.problems",
               "fields": {"name": "label_text", "employees_affected": "n_staff", "hours_lost_per_week": "loss.hrs"}}
    phase4_input, report = from_phase3(data, profile="veloran", mapping=mapping)
    assert phase4_input["bottlenecks"][0]["hours_lost_per_week"] == 42
    assert report["bottlenecks"][0]["category"]["value"] == "time_capture"


def test_lists_of_people_are_never_copied():
    data = phase3_json()
    data["step7"]["bottlenecks"][0]["employees"] = ["Ana Ruiz", "Ben Cole"]
    phase4_input, report = from_phase3(data, profile="veloran")
    assert "Ana Ruiz" not in json.dumps(phase4_input)
    assert phase4_input["bottlenecks"][0]["employees_affected"] == 43
    assert "employees" in report["bottlenecks"][0]["ignored_fields"]


def test_phase3_values_win_over_the_profile_unless_overridden():
    data = phase3_json()
    data["assumptions"]["hourlyRate"] = 95
    phase4_input, _ = from_phase3(data, profile="veloran")
    assert phase4_input["assumptions"]["loaded_hourly_rate"] == 95
    prof = json.loads((ROOT / "profiles" / "veloran.json").read_text())
    prof["overrides"] = {"assumptions": {"loaded_hourly_rate": 90}}
    phase4_input, report = from_phase3(data, profile=prof)
    assert phase4_input["assumptions"]["loaded_hourly_rate"] == 90
    assert report["client"]["loaded_hourly_rate"] == "profile override"


def test_hours_per_person_times_people_when_no_total():
    data = {"bottlenecks": [{"title": "Timesheets rebuilt from memory", "peopleAffected": 42, "hoursPerPerson": 1.0}]}
    phase4_input, report = from_phase3(data, profile="veloran")
    assert phase4_input["bottlenecks"][0]["hours_lost_per_week"] == 42
    assert report["bottlenecks"][0]["fields"]["hours_lost_per_week"] == "hours per person x people affected"


# ------------------------------------------------------------------ Phase 4 -> Phase 5
@pytest.fixture(scope="module")
def veloran_output():
    phase4_input, _ = from_phase3(phase3_json(), profile="veloran")
    return run_phase4(phase4_input)


def test_report_follows_the_reference_report_structure(veloran_output):
    blocks = report_blocks(veloran_output)
    ids = [s["id"] for s in blocks["sections"]]
    assert ids[0] == "recommended-actions" and ids[-3:] == ["ai-governance", "calculation-workbook", "evidence"]
    assert "recommendations-and-roi" in ids and "staffing-solution-options" in ids
    text = report_markdown(veloran_output)
    for needle in ("$257,040", "$79,520", "Upside not counted", "$415,171", "Governance review of AI tools",
                   "AI-drafted timesheets", "**Option 1: AI forecasting agent.** Deferred"):
        assert needle in text, needle


def test_every_headline_number_has_evidence(veloran_output):
    evidence = [r for s in report_blocks(veloran_output)["sections"] if s["id"] == "evidence"
                for b in s["blocks"] for r in b["rows"]]
    assert len(evidence) > 40
    assert any(row[0] == "$257,040" and "85 h x 48 weeks" in row[3] for row in evidence)


def test_manager_view_matches_its_schema_and_numbers(veloran_output):
    jsonschema = pytest.importorskip("jsonschema")
    view = manager_view(veloran_output)
    jsonschema.validate(view, json.loads((ROOT / "contracts" / "manager_view.schema.json").read_text()))
    assert view["headline"]["annual_savings"]["display"] == "$589,680"
    assert view["headline"]["payback"]["display"] == "1.6 months"
    deferred = view["bottlenecks"][0]["options"][0]
    assert deferred["badge"] == {"status": "deferred", "label": "Deferred", "tone": "warning",
                                 "meaning": "Waits for a prerequisite"}
    assert "85 h x 48 weeks" in view["bottlenecks"][0]["recommendation"]["annual_savings"]["math"]


def test_pipeline_writes_every_file(tmp_path):
    result = run_pipeline(phase3_json(), profile="veloran", expected="veloran")
    names = sorted(p.name for p in write_pipeline_files(result, tmp_path))
    assert names == sorted(["phase4_input.json", "mapping_report.json", "phase4_output.json", "manager_view.json",
                            "phase5_report.json", "phase5_report.md", "scorecard.json"])
    assert json.loads((tmp_path / "scorecard.json").read_text())["matched"] == 75


# ------------------------------------------------------------------ HTTP service
@pytest.fixture(scope="module")
def service():
    from phase4.server import make_server
    server = make_server(port=0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _call(url, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read()), res.headers
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read()), err.headers


def test_service_health_and_schemas(service):
    status, body, headers = _call(f"{service}/health")
    assert status == 200 and body["ok"] and "veloran" in body["profiles"]
    assert headers["Access-Control-Allow-Origin"] == "*"
    status, body, _ = _call(f"{service}/schemas/manager-view")
    assert status == 200 and body["title"].startswith("Phase 4 manager view")
    assert _call(f"{service}/nope")[0] == 404


def test_service_pipeline_and_run(service):
    status, body, _ = _call(f"{service}/phase4/pipeline", {"phase3": phase3_json(), "profile": "veloran",
                                                           "expected": "veloran"})
    assert status == 200 and body["scorecard"]["matched"] == 75
    assert body["manager_view"]["headline"]["year_one_cost"]["display"] == "$79,520"
    sample = json.loads((ROOT / "samples" / "veloran_input.json").read_text())
    status, view, _ = _call(f"{service}/phase4/run?view=manager", sample)
    assert status == 200 and view["view_version"].startswith("phase4-manager-view/")


def test_service_errors_are_clear(service):
    status, body, _ = _call(f"{service}/phase4/run", raw=b"{not json")
    assert status == 400 and "not valid JSON" in body["error"]
    bad = phase3_json()
    del bad["step7"]["bottlenecks"][0]["peopleAffected"]
    status, body, _ = _call(f"{service}/phase4/from-phase3", {"phase3": bad, "profile": "veloran"})
    assert status == 422 and any("people affected" in e for e in body["errors"]) and "mapping_report" in body


# ------------------------------------------------------------------ CLI
def _cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-m", "phase4", *args], cwd=ROOT, input=stdin,
                          capture_output=True, text=True, timeout=120)


def test_cli_pipeline_json_from_stdin():
    res = _cli("pipeline", "-", "--profile", "veloran", "--expected", "veloran", "--json",
               stdin=(EX / "veloran_step7_8.json").read_text())
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["scorecard"]["passed"]


def test_cli_adapt_explains_the_mapping():
    res = _cli("adapt", "examples/phase3/veloran_step7_8.json", "--profile", "veloran")
    assert res.returncode == 0, res.stderr
    assert "hours_lost_per_week" in res.stdout and "step 8: hoursLostPerWeek" in res.stdout


def test_cli_mapping_error_exit_code():
    bad = phase3_json()
    del bad["step7"]["bottlenecks"][0]["peopleAffected"]
    res = _cli("pipeline", "-", "--profile", "veloran", "--json", stdin=json.dumps(bad))
    assert res.returncode == 2 and "could not be mapped" in res.stderr
