"""Grade a run against answer_key.json (PHASE_4_PROMPT.md section 8).

Five checks: recovery, no false alarms, suppression, sensitivity, determinism.
This grades detection and sizing only; savings can only be graded by a pilot.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .bottlenecks import KPI_DEPENDS


def _teams(group: Dict[str, Any]) -> set:
    return set(group.get("teams") or ([group["team"]] if group.get("team") else []))


def score(findings: Dict[str, Any], key: Dict[str, Any], kpis_csv: Optional[Path] = None,
          rerun_json: Optional[str] = None, first_json: Optional[str] = None) -> Dict[str, Any]:
    found = [b for b in findings["bottlenecks"]]
    matched_ids, recovery = set(), []
    for kb in key.get("bottlenecks", []):
        cand = [b for b in found if b["kpi"] == kb["kpi"] and _teams(b["group"]) & _teams(kb["group"])]
        row = {"id": kb["id"], "name": kb["name"], "found": bool(cand)}
        if cand:
            b = cand[0]
            matched_ids.add(b["id"])
            tol = float(kb.get("tolerance", 0.15))
            hours, people = b["total_hours_lost_per_week"]["value"], b["people_affected"]["value"]
            he = abs(hours - kb["true_total_hours_lost_per_week"]) / kb["true_total_hours_lost_per_week"]
            pe = abs(people - kb["true_people_affected"]) / kb["true_people_affected"]
            row.update({"hours": hours, "true_hours": kb["true_total_hours_lost_per_week"], "hours_error": round(he, 4),
                        "people": people, "true_people": kb["true_people_affected"], "people_error": round(pe, 4),
                        "within_tolerance": he <= tol and pe <= tol})
        recovery.append(row)
    false_alarms = []
    for trap in key.get("traps", []):
        for b in found:
            kpis = {b["kpi"], *KPI_DEPENDS.get(b["kpi"], [])}
            if trap["kpi"] in kpis and _teams(b["group"]) & _teams(trap["group"]):
                false_alarms.append({"bottleneck": b["id"], "trap": trap})
    extras = [b["id"] for b in found if b["id"] not in matched_ids]
    small = [g["team"] for g in key.get("small_groups", [])]
    listed = {g["group"].get("team") for g in findings["suppressed_groups"]}
    in_csv = set()
    if kpis_csv and kpis_csv.is_file():
        with kpis_csv.open(encoding="utf-8") as fh:
            in_csv = {r["team"] for r in csv.DictReader(fh)}
    leaked = sorted(t for t in small if t in in_csv or any(t in b["group"]["teams"] for b in found))
    suppression_ok = not leaked and all(t in listed for t in small)
    computed = [f for f in findings["fixes"] if f["status"] == "computed"]
    sensitivity_ok = all(f.get("sensitivity", {}).get("top_driver") for f in computed)
    deterministic = None if rerun_json is None else rerun_json == first_json
    recovered = sum(1 for r in recovery if r.get("within_tolerance"))
    return {
        "recovery": recovery, "found": recovered, "expected": len(recovery),
        "false_alarms": false_alarms, "extra_detections": extras,
        "suppression": {"ok": suppression_ok, "leaked": leaked, "listed": sorted(t for t in listed if t)},
        "sensitivity_ok": sensitivity_ok, "deterministic": deterministic,
        "passed": recovered == len(recovery) and not false_alarms and suppression_ok and sensitivity_ok
                  and deterministic is not False,
    }


def render(card: Dict[str, Any], dataset: str) -> str:
    lines = [f"# Validation: {dataset}", "",
             f"- **Found:** {card['found']} of {card['expected']} planted bottlenecks within tolerance",
             f"- **False alarms:** {len(card['false_alarms'])}",
             f"- **Extra detections (not in the key, not failures):** {', '.join(card['extra_detections']) or 'none'}",
             f"- **Suppression:** {'pass' if card['suppression']['ok'] else 'FAIL'}"
             + (f" (leaked: {', '.join(card['suppression']['leaked'])})" if card['suppression']['leaked'] else ""),
             f"- **Sensitivity:** {'every fix has a top driver' if card['sensitivity_ok'] else 'FAIL'}",
             f"- **Determinism:** {'byte-identical findings.json' if card['deterministic'] else 'not checked' if card['deterministic'] is None else 'FAIL'}",
             f"- **Overall:** {'PASS' if card['passed'] else 'FAIL'}", "",
             "| Key | Found | Hours (true) | Hours error | People (true) | People error |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in card["recovery"]:
        if r["found"]:
            lines.append(f"| {r['id']} {r['name']} | yes | {r['hours']} ({r['true_hours']}) | {r['hours_error']:.1%} | "
                         f"{r['people']} ({r['true_people']}) | {r['people_error']:.1%} |")
        else:
            lines.append(f"| {r['id']} {r['name']} | no | | | | |")
    lines += ["", "Validation grades detection and sizing only. Savings can only be graded by a real pilot.", ""]
    return "\n".join(lines)


def load_key(folder: Union[str, Path]) -> Optional[Dict[str, Any]]:
    path = Path(folder) / "answer_key.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
