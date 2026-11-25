"""Tests for the measured impact engine (engine/). Spec: PHASE_4_PROMPT.md section 11."""
from __future__ import annotations

import copy
import csv
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

import make_mini  # noqa: E402
from engine import evidence  # noqa: E402
from engine.contract import check_folder, load_config, load_dataset  # noqa: E402
from engine.impact import simulate  # noqa: E402
from engine.kpis import compute  # noqa: E402
from engine.bottlenecks import detect  # noqa: E402
from engine.report import analyze, findings_json, phase3_handoff, render_markdown, write_outputs  # noqa: E402
from engine.scorecard import score  # noqa: E402

DRAWS = 2000


@pytest.fixture(scope="module")
def mini(tmp_path_factory) -> Path:
    return make_mini.build(tmp_path_factory.mktemp("mini") / "mini")


@pytest.fixture(scope="module")
def findings(mini):
    return analyze(mini, draws=DRAWS)


def _copy(mini: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "data"
    shutil.copytree(mini, dst)
    return dst


def _edit_csv(path: Path, fn) -> None:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows, fields = fn(rows)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# ------------------------------------------------------------------ contract


def test_fixture_passes_contract_and_is_reproducible(mini, tmp_path):
    assert not check_folder(mini).errors
    again = make_mini.build(tmp_path / "again")
    for name in ("people.csv", "activity.csv", "time_entries.csv", "answer_key.json"):
        assert (mini / name).read_bytes() == (again / name).read_bytes()


@pytest.mark.parametrize("change,message", [
    (lambda rows: ([{k: v for k, v in r.items() if k != "work_type"} for r in rows],
                   [k for k in rows[0] if k != "work_type"]), "missing required column"),
    (lambda rows: ([{**r, "start_ts": "yesterday"} if i == 0 else r for i, r in enumerate(rows)], list(rows[0])),
     "unparseable start_ts"),
    (lambda rows: ([{**r, "start_ts": "2026-09-14T09:00:00"} if i == 0 else r for i, r in enumerate(rows)], list(rows[0])),
     "unparseable start_ts"),  # no UTC offset
    (lambda rows: ([{**r, "end_ts": "2026-09-01T09:00:00-07:00"} if i == 0 else r for i, r in enumerate(rows)],
                   list(rows[0])), "end_ts before start_ts"),
    (lambda rows: ([{**r, "person_id": "ZZ99"} if i == 0 else r for i, r in enumerate(rows)], list(rows[0])),
     "unknown person_id"),
    (lambda rows: ([{**r, "event_id": rows[0]["event_id"]} if i == 1 else r for i, r in enumerate(rows)], list(rows[0])),
     "duplicate event_id"),
    (lambda rows: ([{**r, "tool": "someone@example.com"} if i == 0 else r for i, r in enumerate(rows)], list(rows[0])),
     "email address"),
    (lambda rows: ([{**r, "employee_name": "x"} for r in rows], list(rows[0]) + ["employee_name"]),
     "personal or pay data"),
])
def test_validator_failures(mini, tmp_path, change, message):
    data = _copy(mini, tmp_path)
    _edit_csv(data / "activity.csv", change)
    errors = check_folder(data).errors
    assert any(message in p.message for p in errors), [p.line() for p in errors]


def test_unknown_work_type_warns_and_maps_to_other(mini, tmp_path):
    data = _copy(mini, tmp_path)
    _edit_csv(data / "activity.csv",
              lambda rows: ([{**r, "work_type": "gardening"} if i == 0 else r for i, r in enumerate(rows)], list(rows[0])))
    res = check_folder(data)
    assert not res.errors and res.warnings
    assert res.tables["activity.csv"][0]["work_type"] == "other"


def test_validator_cli_output_is_short(mini, tmp_path):
    from engine.validate import report_lines
    data = _copy(mini, tmp_path)
    _edit_csv(data / "activity.csv",
              lambda rows: ([{**r, "start_ts": "bad", "person_id": "ZZ"} for r in rows], list(rows[0])))
    lines = report_lines(str(data))
    assert lines[0].startswith("FAIL") and len(lines) <= 30


# ------------------------------------------------------------------ KPIs and bottlenecks


def test_planted_kpis_and_trap(mini):
    ds, cfg = load_dataset(mini), load_config(mini)
    k = compute(ds, cfg)
    assert k.team["Team A"]["status_hours"] == pytest.approx(3.0)
    assert k.team["Team A"]["share_entered_friday_or_later"] == pytest.approx(1.0)
    assert k.team["Team B"]["status_hours"] == pytest.approx(1.0)  # external meetings excluded by the internal flag
    det = detect(ds, cfg, k)
    status = next(b for b in det.bottlenecks if b.id == "status_reporting")
    assert status.teams == ["Team A"] and status.total_hours == pytest.approx(18.0)
    assert len(status.evidence["row_ids"]) <= 20 and status.evidence["filter"]


def test_trap_would_trip_without_the_internal_flag(mini, tmp_path):
    data = _copy(mini, tmp_path)
    _edit_csv(data / "activity.csv", lambda rows: ([{**r, "internal": "true"} for r in rows], list(rows[0])))
    ds, cfg = load_dataset(data), load_config(data)
    det = detect(ds, cfg, compute(ds, cfg))
    status = next(b for b in det.bottlenecks if b.id == "status_reporting")
    assert "Team B" in status.teams  # so the fixture really tests the flag


def test_scorecard_passes_on_fixture(mini, findings, tmp_path):
    out = write_outputs(findings, tmp_path / "out")
    key = json.loads((mini / "answer_key.json").read_text(encoding="utf-8"))
    card = score(findings, key, out / "kpis.csv", rerun_json=findings_json(analyze(mini, draws=DRAWS)),
                 first_json=(out / "findings.json").read_text(encoding="utf-8"))
    assert card["found"] == 2 and not card["false_alarms"]
    assert card["suppression"]["ok"] and card["sensitivity_ok"] and card["deterministic"] and card["passed"]


# ------------------------------------------------------------------ D1 evidence pooling


def _study(**kw):
    base = {"id": "s", "source": "test", "design": "field_rct", "data_year": 2026, "n": 400, "metric": "time_reduction",
            "effect": 0.3, "se": 0.05, "task": "timesheet", "soc_codes": [], "soc_major_groups": [], "setting": 1,
            "outcome": 2, "applies_to": [{"component": "c", "tool": 1}]}
    base.update(kw)
    return base


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _effect(cfg, studies, kind="ai_tool", estimate=None, affected=None, run_year=2026, work_type="timesheet"):
    comp = {"id": "c", "kind": kind, "report_estimate": estimate}
    return evidence.component_effect(comp, work_type, affected or {"p1": ("13-1111", 1.0)}, studies,
                                     cfg.assumptions, cfg.families, run_year)


def test_alignment_matches_hand_computed_values(mini, findings):
    f3 = next(f for f in findings["fixes"] if f["id"] == "F3")
    ai = next(c for c in f3["components"] if c["component"] == "ai_timesheet_drafts")
    got = {s["id"]: (s["scores"], s["alignment"]["value"]) for s in ai["studies"]}
    # Team A: soc 13-1111, bottleneck work type timesheet.
    assert got["noy_zhang_2023"] == ({"task": 1, "people": 1.0, "setting": 1, "outcome": 2, "tool": 1}, 0.6)
    assert got["dellacqua_2023"] == ({"task": 0, "people": 2.0, "setting": 1, "outcome": 2, "tool": 1}, 0.6)
    assert got["brynjolfsson_li_raymond_2025"] == ({"task": 0, "people": 0.0, "setting": 2, "outcome": 1, "tool": 1}, 0.4)
    assert findings_json(analyze(mini, draws=DRAWS)) == findings_json(findings)  # identical on every run


def test_higher_alignment_raises_weight_and_narrows_sigma(cfg):
    loose = [_study(id="a", setting=0), _study(id="b", setting=0, effect=0.2)]
    tight = [_study(id="a", setting=2, soc_codes=["13-1111"]), _study(id="b", setting=0, effect=0.2)]
    r_loose, r_tight = _effect(cfg, loose), _effect(cfg, tight)
    assert r_tight["studies"][0]["weight_share"] > r_loose["studies"][0]["weight_share"]
    assert r_tight["sigma"] < r_loose["sigma"]


def test_duplicate_loose_study_does_not_narrow_transfer(cfg):
    # With the spec's formulas a duplicate halves sampling variance V, but the shared transfer
    # term T is unchanged, so sigma can never fall below the transfer floor sqrt(T^2 + tau^2).
    # (Flagged for the team: the prompt's test said "does not narrow sigma" at all.)
    one = [_study(id="a", setting=0, task="customer_support")]
    two = one + [_study(id="a2", setting=0, task="customer_support")]
    r1, r2 = _effect(cfg, one), _effect(cfg, two)
    assert r2["T"] == pytest.approx(r1["T"])
    assert r2["sigma"] >= (r1["T"] ** 2 + r1["tau2"]) ** 0.5
    assert r2["sigma"] > 0.95 * r1["sigma"]


def test_older_ai_study_widens_sigma(cfg):
    assert _effect(cfg, [_study(data_year=2019)])["sigma"] > _effect(cfg, [_study(data_year=2025)])["sigma"]


def test_fallback_and_report_flag(cfg):
    fb = _effect(cfg, [], kind="process", estimate=0.5)
    assert "no matching study" in fb["flags"] and fb["mu"] == pytest.approx(0.5)
    flagged = _effect(cfg, [_study(effect=0.1)], estimate=0.9)
    assert "report assumption above the evidence range" in flagged["flags"]
    assert flagged["report_estimate_position"] == "above"


def test_productivity_gain_is_converted():
    assert evidence.adjusted_effect(_study(metric="productivity_gain", effect=0.25), {"field_rct": 1.0}) == pytest.approx(0.2)


# ------------------------------------------------------------------ D2 Monte Carlo


def test_same_seed_same_output_and_different_seed_differs(mini, findings):
    other = analyze(mini, draws=DRAWS, seed=7)
    assert findings_json(other) != findings_json(findings)


def test_components_combine_multiplicatively(mini):
    ds, cfg = load_dataset(mini), load_config(mini)
    det = detect(ds, cfg, compute(ds, cfg))
    one = copy.deepcopy(cfg)
    one.studies = []  # deterministic effects: make sigma tiny via a near-certain report estimate
    for f in one.fixes:
        for c in f["components"]:
            c["report_estimate"] = 0.5
    one.assumptions["expert_se_share"]["value"] = 1e-9
    one.assumptions["transfer_sd_at_zero_alignment"]["value"] = 1e-9
    one.assumptions["tau_min"]["value"] = 1e-9
    one.assumptions["adoption"].update(low=1.0, base=1.0, high=1.0)
    sim = simulate(det.bottlenecks, ds, one, 2026, draws=200)
    f3 = next(f for f in sim["fixes"] if f["id"] == "F3")  # two components at 0.5 each on 6 hours
    assert f3["hours_saved_per_week"]["p50"]["value"] == pytest.approx(6 * (1 - 0.5 * 0.5), abs=0.01)  # not 6


def test_missing_wage_is_not_computed(findings):
    f2 = next(f for f in findings["fixes"] if f["id"] == "F2")
    assert f2["dollars"]["status"] == "not computed" and "13-1111" in f2["dollars"]["reason"]


def test_client_rates_and_payback_pairing(mini, tmp_path):
    data = _copy(mini, tmp_path)
    (data / "client_rates.csv").write_text("role,loaded_rate\nconsultant,100\naccount_manager,100\n", encoding="utf-8")
    f = analyze(data, draws=DRAWS)
    f2 = next(x for x in f["fixes"] if x["id"] == "F2")
    assert f2["dollars"]["label"] == "client rate" and "client:client_rates.csv" in f2["dollars"]["p50"]["source"]
    d, p = f2["dollars"], f2["payback_months"]
    assert d["p10"]["value"] < d["p50"]["value"] < d["p90"]["value"]
    # P10 savings pair with P90 payback: payback quantiles run the other way.
    assert p["p90"]["value"] is None or p["p90"]["value"] >= p["p50"]["value"] >= p["p10"]["value"]
    expected = 9800 / (d["p10"]["value"] / 12)
    assert p["p90"]["value"] == pytest.approx(expected, rel=0.02)


def test_wages_file_is_used_with_wage_share(mini, tmp_path):
    wages = tmp_path / "wages.csv"
    wages.write_text("soc_code,title,mean_hourly_wage,source\n13-1111,t,70,test only\n11-2022,t,70,test only\n",
                     encoding="utf-8")
    c = load_config(mini, wages_path=wages)
    f = analyze(mini, draws=DRAWS, cfg=c)
    f2 = next(x for x in f["fixes"] if x["id"] == "F2")
    assert f2["dollars"]["label"] == "market-rate estimate"
    assert f2["dollars"]["p50"]["value"] == pytest.approx(f2["annual_hours"]["p50"]["value"] * 100, rel=0.01)


def test_every_fix_has_a_top_driver_and_guardrail(findings):
    for f in findings["fixes"]:
        if f["status"] == "computed":
            assert f["sensitivity"]["top_driver"]
            assert "after_hours_share" in f["guardrail"]


# ------------------------------------------------------------------ outputs and privacy


def _numbers(obj, path=""):
    if isinstance(obj, dict):
        if "value" in obj and isinstance(obj["value"], (int, float)) and not isinstance(obj["value"], bool):
            yield path, obj
        for k, v in obj.items():
            yield from _numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _numbers(v, f"{path}[{i}]")


def test_every_number_has_a_source_tag(findings):
    public = json.loads(findings_json(findings))
    for key in ("bottlenecks", "fixes", "summary", "react_first", "combined_by_bottleneck"):
        for path, obj in _numbers(public[key], key):
            assert obj.get("source"), path
            assert re.match(r"^(data|evidence:|assumption:|client:|reference:)", obj["source"]), path


NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?(?![\w])")


def _vals(text):
    out = set()
    for tok in NUM.findall(text):
        v = float(tok.rstrip("%").replace(",", ""))
        out.add(round(v / 100, 6) if tok.endswith("%") else round(v, 6))
    return out


def test_every_number_in_report_md_is_in_findings(findings):
    report = render_markdown(findings)
    source = findings_json(findings)
    known = {round(float(t.replace(",", "")), 6) for t in NUM.findall(source) if not t.endswith("%")}
    missing = [v for v in _vals(report) if not any(abs(v - k) < 1e-6 for k in known)]
    assert not missing, missing


def test_small_team_never_appears_in_outputs(findings, tmp_path):
    out = write_outputs(findings, tmp_path / "out")
    for name in ("kpis.csv", "bottlenecks.json", "fixes_ranked.csv", "report.md", "phase3_handoff.json"):
        text = (out / name).read_text(encoding="utf-8")
        if name == "report.md":  # listed once as suppressed, with no values
            assert text.count("Team C") == 1 and "team=Team C: not enough data" in text
        else:
            assert "Team C" not in text, name
    public = json.loads(findings_json(findings))
    assert "Team C" not in json.dumps({k: v for k, v in public.items() if k != "suppressed_groups"})
    assert "C01" not in (out / "findings.json").read_text(encoding="utf-8")  # no person IDs


def test_outputs_written_and_spreadsheet_safe(findings, tmp_path):
    out = write_outputs(findings, tmp_path / "out")
    for name in ("findings.json", "bottlenecks.json", "kpis.csv", "fixes_ranked.csv", "report.md",
                 "phase3_handoff.json", "preview.html"):
        assert (out / name).is_file(), name
    from engine.report import _safe
    assert _safe("=HYPERLINK()") == "'=HYPERLINK()" and _safe("Team A") == "Team A"


def test_handoff_feeds_existing_phase4_pipeline(findings):
    from phase4.pipeline import run_pipeline
    result = run_pipeline(phase3_handoff(findings), profile="veloran")
    names = {b["name"] for b in result["phase4_output"]["bottlenecks"]}
    assert {"Status reporting", "Timesheets rebuilt from memory"} <= names
    assert result["manager_view"]


def test_stubs_raise():
    from engine import prove, simulate as sim
    with pytest.raises(NotImplementedError):
        sim.simulate()
    with pytest.raises(NotImplementedError):
        prove.prove()
