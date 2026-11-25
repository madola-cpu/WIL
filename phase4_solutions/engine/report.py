"""Run the engine and write its outputs (PHASE_4_PROMPT.md section 7).

analyze() returns findings (a JSON-ready dict); write_outputs() writes
outputs/<run_id>/. Every number in findings is {"value", "source"}. Nothing
here depends on the wall clock, so the same data and seed give byte-identical
findings.json.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from . import __version__
from .bottlenecks import detect, num
from .contract import Config, Dataset, load_config, load_dataset
from .impact import simulate
from .kpis import compute
from .prioritize import rank, react_first


def analyze(folder: Union[str, Path], draws: Optional[int] = None, seed: Optional[int] = None,
            cfg: Optional[Config] = None) -> Dict[str, Any]:
    ds = load_dataset(folder)
    cfg = cfg or load_config(folder)
    k = compute(ds, cfg)
    det = detect(ds, cfg, k)
    run_year = max(r["end_ts"] for r in ds.activity).year
    sim = simulate(det.bottlenecks, ds, cfg, run_year, draws=draws, seed=seed)
    names = {r["id"]: r["name"] for r in cfg.rules}
    ranked = rank(sim["fixes"], names)
    others = [f for f in sim["fixes"] if f["status"] != "computed"]
    records = []
    for b in det.bottlenecks:
        rec = b.to_record()
        if b.id in sim["hours_lost_ranges"]:
            rec["total_hours_lost_per_week_range"] = sim["hours_lost_ranges"][b.id]
        records.append(rec)
    measured = [r for r in records if not r["diagnostic"]]
    start = min(r["start_ts"] for r in ds.activity).date()
    end = max(r["end_ts"] for r in ds.activity).date()
    reported_teams = [t for t in sorted(k.team) if not k.suppressed_team(t)]
    findings = {
        "engine": {"name": "measured impact engine", "version": __version__},
        "run_id": f"{ds.folder_name}-{ds.digest[:10]}-seed{sim['seed']}",
        "data_profile": {
            "dataset": ds.folder_name, "files": ds.row_counts,
            "people": num(len(ds.people), "data", 0),
            "teams_reported": reported_teams, "teams_reported_count": num(len(reported_teams), "data", 0),
            "weeks": k.weeks, "weeks_count": num(len(k.weeks), "data", 0),
            "period": {"start": start.isoformat(), "end": end.isoformat()}, "run_year": run_year,
            "contract_warnings": [p.line() for p in ds.warnings],
            "has_answer_key": (Path(folder) / "answer_key.json").is_file(),
        },
        "assumptions_used": {key: val for key, val in cfg.assumptions.items()},
        "overrides": cfg.overridden,
        "rules": [{"id": r["id"], "name": r["name"], "kpi": r["kpi"], "comparator": r["comparator"],
                   "threshold": r.get("threshold"), "threshold_share_of_contracted": r.get("threshold_share_of_contracted"),
                   "or": r.get("or"), "source": r["source"]} for r in cfg.rules],
        "rule_results": det.rule_results,
        "summary": {
            "bottlenecks_detected": num(len(records), "data", 0),
            "total_hours_lost_per_week": num(sum(r["total_hours_lost_per_week"]["value"] for r in measured), "data"),
        },
        "bottlenecks": records,
        "fixes": ranked + others,
        "combined_by_bottleneck": sim["combined"],
        "react_first": react_first(ranked, names),
        "not_measured": k.not_measured + det.not_measured,
        "suppressed_groups": k.suppressed,
        "monte_carlo": {"draws": sim["draws"], "seed": sim["seed"]},
        "sources": _sources(cfg),
    }
    findings["_kpi_rows"] = k.rows  # written to kpis.csv, dropped from findings.json
    return findings


def _sources(cfg: Config) -> List[Dict[str, Any]]:
    out = [{"id": s["id"], "text": s["source"], "url": s.get("url"), "design": s["design"], "data_year": s["data_year"]}
           for s in cfg.studies]
    for key, val in cfg.assumptions.items():
        if isinstance(val, dict) and val.get("url"):
            out.append({"id": f"assumption:{key}", "text": val["source"], "url": val["url"]})
    if cfg.wages:
        out.append({"id": "reference:wages.csv", "text": "; ".join(sorted({w["source"] for w in cfg.wages.values()})),
                    "url": "https://www.bls.gov/oes/"})
    return out


def findings_json(findings: Dict[str, Any]) -> str:
    public = {k: v for k, v in findings.items() if not k.startswith("_")}
    return json.dumps(public, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def _safe(value: Any) -> Any:
    """Spreadsheet-safe cell: text starting with = + - @ is prefixed so it never runs as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({f: _safe(r.get(f, "")) for f in fields})


def _v(x: Optional[Dict[str, Any]]) -> Any:
    return "" if not x or x.get("value") is None else x["value"]


def ranked_rows(findings: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for f in findings["fixes"]:
        row = {"rank": f.get("priority", {}).get("rank", ""), "fix_id": f["id"], "name": f["name"],
               "bottleneck": f["bottleneck"], "status": f["status"], "effort": f["effort"],
               "time_to_value_weeks": _v(f["time_to_value_weeks"])}
        if f["status"] == "computed":
            p = f["priority"]
            row.update({"score": _v(p["score"]), "value_annual_hours_p50": _v(p["value_annual_hours_p50"]),
                        "confidence": _v(p["confidence"]),
                        "hours_week_p10": _v(f["hours_saved_per_week"]["p10"]),
                        "hours_week_p50": _v(f["hours_saved_per_week"]["p50"]),
                        "hours_week_p90": _v(f["hours_saved_per_week"]["p90"]),
                        "dollars_p10": _v(f["dollars"].get("p10")) if "p10" in f["dollars"] else "not computed",
                        "dollars_p50": _v(f["dollars"].get("p50")) if "p50" in f["dollars"] else "not computed",
                        "dollars_p90": _v(f["dollars"].get("p90")) if "p90" in f["dollars"] else "not computed",
                        "payback_months_p50": (_v(f["payback_months"]["p50"]) if "p50" in f["payback_months"]
                                               else "not computed"),
                        "top_driver": f["sensitivity"]["top_driver"],
                        "flags": "; ".join(fl for c in f["components"] for fl in c.get("flags", []))})
        else:
            row["flags"] = f.get("reason", "")
        rows.append(row)
    return rows


RANKED_FIELDS = ["rank", "fix_id", "name", "bottleneck", "status", "score", "value_annual_hours_p50", "confidence",
                 "effort", "time_to_value_weeks", "hours_week_p10", "hours_week_p50", "hours_week_p90",
                 "dollars_p10", "dollars_p50", "dollars_p90", "payback_months_p50", "top_driver", "flags"]
KPI_FIELDS = ["level", "team", "role", "week", "kpi", "value", "people"]


def phase3_handoff(findings: Dict[str, Any]) -> Dict[str, Any]:
    """Step 7-8 output in the shape the existing Phase 4 adapter reads (INTEGRATION.md)."""
    items = []
    for b in findings["bottlenecks"]:
        if b["diagnostic"]:
            continue
        rng = b.get("total_hours_lost_per_week_range", {})
        items.append({
            "id": b["id"], "name": b["name"], "teams": b["group"]["teams"],
            "people_affected": b["people_affected"]["value"],
            "hours_lost_per_week": {"low": _v(rng.get("p10")) or b["total_hours_lost_per_week"]["value"],
                                    "base": b["total_hours_lost_per_week"]["value"],
                                    "high": _v(rng.get("p90")) or b["total_hours_lost_per_week"]["value"]},
            "evidence": [{"metric": b["kpi"], "system": "measured impact engine",
                          "observed": str(b["kpi_value"]["value"])}],
        })
    return {"client": findings["data_profile"]["dataset"], "runId": findings["run_id"],
            "source": "measured impact engine (steps 7-8); low/high are bootstrap P10/P90 of weekly hours lost",
            "step7": {"bottlenecks": items}}


def write_outputs(findings: Dict[str, Any], out_root: Union[str, Path]) -> Path:
    from .preview import findings_html
    out = Path(out_root) / findings["run_id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "findings.json").write_text(findings_json(findings), encoding="utf-8")
    (out / "bottlenecks.json").write_text(json.dumps(findings["bottlenecks"], indent=2, sort_keys=True,
                                                     ensure_ascii=False) + "\n", encoding="utf-8")
    _csv(out / "kpis.csv", findings["_kpi_rows"], KPI_FIELDS)
    _csv(out / "fixes_ranked.csv", ranked_rows(findings), RANKED_FIELDS)
    (out / "report.md").write_text(render_markdown(findings), encoding="utf-8")
    (out / "phase3_handoff.json").write_text(json.dumps(phase3_handoff(findings), indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    (out / "preview.html").write_text(findings_html(findings), encoding="utf-8")
    return out


# ------------------------------------------------------------------ report.md


def fmt(x: Optional[Dict[str, Any]]) -> str:
    if not x or x.get("value") is None:
        return (x or {}).get("note", "n/a")
    v = x["value"]
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,}"


def pct(x: Optional[Dict[str, Any]]) -> str:
    return "n/a" if not x or x.get("value") is None else f"{x['value'] * 100:.2f}%"


def _range(r: Dict[str, Any], money: bool = False) -> str:
    if "p50" not in r:
        return "not computed"
    sign = "$" if money else ""
    return f"{sign}{fmt(r['p10'])} / {sign}{fmt(r['p50'])} / {sign}{fmt(r['p90'])}"


def render_markdown(f: Dict[str, Any]) -> str:
    dp, s = f["data_profile"], f["summary"]
    computed = [x for x in f["fixes"] if x["status"] == "computed"]
    names = {b["id"]: b["name"] for b in f["bottlenecks"]}
    out = [f"# Impact findings: {dp['dataset']}", "",
           f"Run `{f['run_id']}`, data from {dp['period']['start']} to {dp['period']['end']}. "
           f"Every number below comes from `findings.json`, where each one carries its source.", ""]
    s1 = (f"We measured {fmt(dp['people'])} people in {fmt(dp['teams_reported_count'])} reportable teams over "
          f"{fmt(dp['weeks_count'])} weeks and found {fmt(s['bottlenecks_detected'])} bottleneck(s), costing "
          f"{fmt(s['total_hours_lost_per_week'])} hours a week.")
    if computed:
        top = computed[0]
        h = top["hours_saved_per_week"]
        s2 = (f"The top fix is {top['name']}, saving {fmt(h['p50'])} hours a week (P10 {fmt(h['p10'])}, "
              f"P90 {fmt(h['p90'])}).")
    else:
        s2 = "No fix applies to the bottlenecks found in this data."
    money = [x for x in computed if "p50" in x["dollars"]]
    s3 = ("Dollar values are " + (f"a {money[0]['dollars']['label']}." if money else
          "not computed: " + (computed[0]["dollars"]["reason"] if computed else "no fix was priced") + "."))
    out += ["## Summary", "", f"{s1} {s2} {s3}", "", "## React first", ""]
    out += [f"{r['rank']}. {r['reason']}" for r in f["react_first"]] or ["No fix applies."]
    out += ["", "## Bottlenecks", ""]
    for b in f["bottlenecks"]:
        out += [f"### {b['name']}", "",
                f"- **KPI:** `{b['kpi']}` = {fmt(b['kpi_value'])} (rule: {b['comparator']} {fmt(b['threshold'])})",
                f"- **Teams:** {', '.join(b['group']['teams'])}",
                f"- **Sufficiency:** {b['sufficiency']['status']}: {b['sufficiency']['reason']}",
                f"- **After-hours share (guardrail):** {pct(b['after_hours_share'])}"]
        if b["diagnostic"]:
            for t in b["by_team"]:
                out.append(f"- **{t['team']}:** flow efficiency {fmt(t.get('flow_efficiency'))}, median cycle "
                           f"{fmt(t.get('cycle_days_median'))} days, P90 wait {fmt(t.get('wait_p90_days'))} days")
            out.append("- A diagnostic only: sized in days, not person-hours, and no fix is priced.")
        else:
            rng = b.get("total_hours_lost_per_week_range", {})
            out += [f"- **Size:** {fmt(b['total_hours_lost_per_week'])} hours lost a week "
                    f"(P10 {fmt(rng.get('p10'))}, P90 {fmt(rng.get('p90'))}), {fmt(b['people_affected'])} people, "
                    f"{fmt(b['hours_lost_per_person_week'])} hours per person-week"]
        out += [f"- **Evidence:** {b['evidence']['filter']}. Example rows: "
                f"{', '.join(b['evidence']['row_ids'][:5]) or 'none'}", ""]
        mine = [x for x in computed if x["bottleneck"] == b["id"]]
        if mine:
            out += ["| Fix | Hours a week P10 / P50 / P90 | Dollars a year P10 / P50 / P90 | Payback months P50 | Top driver |",
                    "| --- | --- | --- | --- | --- |"]
            for x in mine:
                pay = fmt(x["payback_months"]["p50"]) if "p50" in x["payback_months"] else "not computed"
                out.append(f"| {x['id']} {x['name']} | {_range(x['hours_saved_per_week'])} | "
                           f"{_range(x['dollars'], money=True)} | {pay} | {x['sensitivity']['top_driver']} |")
            out.append("")
    out += ["## Evidence check", "",
            "| Fix | Component | Effect P10 / P50 / P90 | Report estimate | Flags |", "| --- | --- | --- | --- | --- |"]
    for x in computed:
        for c in x["components"]:
            est = fmt(c.get("report_estimate")) if c.get("report_estimate") else "none"
            out.append(f"| {x['id']} | {c['component']} | {_range(c['effect'])} | {est} | "
                       f"{'; '.join(c['flags']) or 'none'} |")
    out += ["", "## Not applied", ""]
    out += [f"- {x['id']} {x['name']}: {x.get('reason', '')}" for x in f["fixes"] if x["status"] != "computed"] or ["- none"]
    out += ["", "## What we couldn't measure", ""]
    out += [f"- {m.get('item', m['kpi'])}: {m['reason']}" for m in f["not_measured"]] or ["- Everything in scope was measured."]
    out += [f"- {', '.join(f'{k}={v}' for k, v in g['group'].items())}: {g['status']}" for g in f["suppressed_groups"]]
    out += ["", "## Assumptions", "", "| Assumption | Value | Source |", "| --- | --- | --- |"]
    for key, val in sorted(f["assumptions_used"].items()):
        shown = {k: v for k, v in val.items() if k not in ("source", "url")}
        text = shown.get("value", shown) if list(shown) == ["value"] else shown
        out.append(f"| {key} | {json.dumps(text, sort_keys=True)} | {val.get('source', '').replace('|', '/')} |")
    out += ["", "## Sources", ""]
    out += [f"- {s['id']}: {s['text']}" + (f" ({s['url']})" if s.get("url") else "") for s in f["sources"]]
    out += ["", "Savings come from published effect sizes and assumptions, not from this data. "
            "Only a pilot can confirm them.", ""]
    return "\n".join(out)
