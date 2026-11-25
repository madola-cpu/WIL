"""Command line for the measured impact engine.

  python -m engine.cli check tests/fixtures/mini            contract check (same as python -m engine.validate)
  python -m engine.cli run   tests/fixtures/mini            write outputs/<run_id>/
  python -m engine.cli run   tests/fixtures/mini --phase4-profile veloran
                                                            ...and feed phase3_handoff.json to the existing Phase 4 pipeline
  python -m engine.cli score tests/fixtures/mini            run, then grade against answer_key.json (validation.md)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .contract import DataContractError
from .report import analyze, findings_json, write_outputs
from .scorecard import load_key, render, score
from .validate import main as validate_main

ROOT = Path(__file__).resolve().parent.parent


def _run(args: argparse.Namespace):
    findings = analyze(args.data, draws=args.draws, seed=args.seed)
    out = write_outputs(findings, args.out)
    return findings, out


def _phase4(out: Path, profile: str) -> None:
    from phase4.pipeline import run_pipeline, write_pipeline_files
    from .preview import manager_view_html
    handoff = json.loads((out / "phase3_handoff.json").read_text(encoding="utf-8"))
    result = run_pipeline(handoff, profile=profile)
    target = out / "phase4"
    write_pipeline_files(result, target)
    (target / "preview.html").write_text(manager_view_html(result["manager_view"]), encoding="utf-8")
    print(f"step 9 (existing Phase 4 pipeline, profile {profile}): {target}")


def cmd_run(args: argparse.Namespace) -> int:
    findings, out = _run(args)
    print(f"{findings['run_id']}: {findings['summary']['bottlenecks_detected']['value']:g} bottleneck(s), "
          f"{findings['summary']['total_hours_lost_per_week']['value']:g} hours lost a week")
    for r in findings["react_first"]:
        print(f"  {r['rank']}. {r['reason']}")
    for m in findings["not_measured"]:
        print(f"  not measured: {m.get('item', m['kpi'])} ({m['reason']})")
    print(f"outputs: {out}")
    if args.phase4_profile:
        _phase4(out, args.phase4_profile)
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    key = load_key(args.data)
    if key is None:
        print("no answer_key.json in the data folder: nothing to grade")
        return 2
    findings, out = _run(args)
    again = findings_json(analyze(args.data, draws=args.draws, seed=args.seed))
    card = score(findings, key, out / "kpis.csv", rerun_json=again, first_json=(out / "findings.json").read_text(encoding="utf-8"))
    text = render(card, findings["data_profile"]["dataset"])
    (out / "validation.md").write_text(text, encoding="utf-8")
    print(text)
    return 0 if card["passed"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.cli", description="Measured impact engine (steps 4-9)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="check a data folder against the contract")
    p.add_argument("data")
    for name, helptext in (("run", "measure, size, price and rank; write outputs"),
                           ("score", "run, then grade against answer_key.json")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("data")
        p.add_argument("--out", default=str(ROOT / "outputs"))
        p.add_argument("--draws", type=int, default=None, help="Monte Carlo draws (default: config)")
        p.add_argument("--seed", type=int, default=None, help="seed (default: config)")
        if name == "run":
            p.add_argument("--phase4-profile", default=None,
                           help="also run the existing Phase 4 pipeline on phase3_handoff.json with this profile")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return validate_main([args.data])
    try:
        return cmd_run(args) if args.cmd == "run" else cmd_score(args)
    except DataContractError as exc:
        print("FAIL: the data does not meet the contract. Run: python -m engine.validate " + args.data)
        for p in exc.problems[:20]:
            print("  " + p.line())
        return 1


if __name__ == "__main__":
    sys.exit(main())
