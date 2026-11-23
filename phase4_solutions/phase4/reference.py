"""Check a Phase 4 output against a reference report's numbers.

reference/*.json hold the numbers printed in the reference reports. Step 10's
scorecard can use the same check: every row says what the report printed,
what the engine produced, and whether they match.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _same(expected: Any, got: Any) -> bool:
    if isinstance(expected, list):
        return list(expected) == list(got or [])
    if isinstance(expected, str) or isinstance(got, str) or got is None or expected is None:
        return expected == got
    return abs(float(expected) - float(got)) < 0.05  # payback is printed to 1 decimal


def _base(value: Any) -> Any:
    return value.get("base") if isinstance(value, dict) and "base" in value else value


def compare_to_reference(output: Dict[str, Any], expected: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return one row per checked number: where, expected, got, ok."""
    rows: List[Dict[str, Any]] = []

    def add(where: str, exp: Any, got: Any) -> None:
        rows.append({"where": where, "expected": exp, "got": got, "ok": _same(exp, got)})

    by_bn = {b["id"]: b for b in output.get("bottlenecks", [])}
    by_cat = {b.get("category"): b for b in output.get("bottlenecks", []) if b.get("category")}
    for bid, exp_bn in expected.get("bottlenecks", {}).items():
        # Match by id, else by fix category, so Phase 3 can use its own ids.
        bn = by_bn.get(bid) or by_cat.get(exp_bn.get("category"))
        if bn is None:
            add(f"{bid}", "present", "missing")
            continue
        opts = {o["fix_id"]: o for o in bn["options"]}
        if exp_bn.get("category") and bn.get("category") != exp_bn["category"]:
            add(f"{bid} category", exp_bn["category"], bn.get("category"))
        for fix_id, exp_opt in exp_bn.get("options", {}).items():
            opt = opts.get(fix_id)
            for key, exp in exp_opt.items():
                got = None if opt is None else _base(opt.get(key))
                add(f"{bid} {fix_id} {key}", exp, got)
        rec = bn.get("recommendation") or {}
        if "recommended" in exp_bn:
            add(f"{bid} recommended fixes", sorted(exp_bn["recommended"]), sorted(rec.get("fix_ids", [])))
        for key, exp in exp_bn.get("recommendation", {}).items():
            add(f"{bid} recommendation {key}", exp, _base(rec.get(key)))
    program = output.get("program", {})
    for key, exp in expected.get("program", {}).items():
        add(f"program {key}", exp, _base(program.get(key)))
    return rows


def format_rows(rows: List[Dict[str, Any]], only_failures: bool = False) -> str:
    shown = [r for r in rows if not (only_failures and r["ok"])]
    width = max([len(r["where"]) for r in shown] + [10])
    lines = [f"{'check'.ljust(width)}  {'report':>14}  {'engine':>14}  ok"]
    for r in shown:
        exp = ", ".join(r["expected"]) if isinstance(r["expected"], list) else r["expected"]
        got = ", ".join(r["got"]) if isinstance(r["got"], list) else r["got"]
        lines.append(f"{r['where'].ljust(width)}  {str(exp):>14}  {str(got):>14}  {'yes' if r['ok'] else 'NO'}")
    passed = sum(r["ok"] for r in rows)
    lines.append(f"{passed} of {len(rows)} checks match the reference report.")
    return "\n".join(lines)
