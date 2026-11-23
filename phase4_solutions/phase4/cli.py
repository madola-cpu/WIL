"""Command line for Phase 4.

  python -m phase4 pipeline examples/phase3/veloran_step7_8.json --profile veloran --expected veloran --out-dir out
  python -m phase4 pipeline - --profile veloran --json < step7_8.json      (JSON in on stdin, everything out on stdout)
  python -m phase4 adapt examples/phase3/veloran_bottlenecks.csv --profile veloran   (show how Phase 3 fields map)
  python -m phase4 run samples/veloran_input.json -o out.json --md out.md
  python -m phase4 check samples/veloran_input.json --expected veloran
  python -m phase4 serve --port 8040
  python -m phase4 validate samples/acquisition_input.json
  python -m phase4 catalog --scenario B
  python -m phase4 profiles
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional

from .catalog import Catalog, CatalogError
from .connectors.phase3 import Phase3MappingError, from_phase3, read_phase3_file
from .contract import Phase4InputError, normalize_input
from .engine import Phase4Options, run_phase4
from .numbers import fmt_money, fmt_payback
from .preview import render_markdown
from .reference import compare_to_reference, format_rows
from .resources import list_profiles, load_expected


def _load(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _load_phase3(path: str) -> Any:
    if path == "-":
        return read_phase3_file("stdin.json", text=sys.stdin.read())
    return read_phase3_file(path)


def _options(args: argparse.Namespace) -> Phase4Options:
    return Phase4Options(
        top_n=None if getattr(args, "all", False) else getattr(args, "top", 3),
        max_fixes_per_bottleneck=getattr(args, "max_fixes", 2),
        ai_text=getattr(args, "ai_text", False),
        ai_model=getattr(args, "model", None),
    )


def _catalog(args: argparse.Namespace) -> Optional[Catalog]:
    return Catalog.load(paths=args.catalog) if getattr(args, "catalog", None) else None


def _mapping(args: argparse.Namespace) -> Optional[dict]:
    return _load(args.mapping) if getattr(args, "mapping", None) else None


def _print_summary(out: dict, target: Any = sys.stdout) -> None:
    cur = out["assumptions_used"]["currency"]
    print(f"{out['run']['client_name']}: {len(out['bottlenecks'])} bottlenecks solved", file=target)
    for b in out["bottlenecks"]:
        r = b["recommendation"]
        if r:
            print(f"  {b['id']} {b['name'][:50]}: {' + '.join(r['names'])} | "
                  f"{fmt_money(r['annual_savings']['base'], cur)} a year | payback "
                  f"{fmt_payback(r['payback_months']['base'])}", file=target)
        else:
            print(f"  {b['id']} {b['name'][:50]}: no recommendation", file=target)
    print(out["program"]["summary"], file=target)
    for w in out["warnings"]:
        print(f"  warning: {w}", file=target)


def cmd_run(args: argparse.Namespace) -> int:
    out = run_phase4(_load(args.input), options=_options(args), catalog=_catalog(args))
    text = json.dumps(out, indent=2, ensure_ascii=False)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(out))
    if not args.output:
        print(text)
        return 0
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    _print_summary(out)
    print(f"Wrote {args.output}" + (f" and {args.md}" if args.md else ""))
    return 0


def cmd_adapt(args: argparse.Namespace) -> int:
    phase4_input, report = from_phase3(_load_phase3(args.input), profile=args.profile, mapping=_mapping(args))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(phase4_input, indent=2, ensure_ascii=False) + "\n")
    print(f"Found {report['found']['bottleneck_count']} bottlenecks at '{report['found']['bottlenecks_at']}'"
          + (f", ROI at '{report['found']['roi_at']}' ({report['found']['roi_matched']} matched)"
             if report["found"].get("roi_at") else ", no separate ROI list"))
    print("Client facts:")
    for field, source in report["client"].items():
        print(f"  {field:<24} <- {source}")
    for b in report["bottlenecks"]:
        cat = b["category"]
        print(f"\n{b['id']}  {b['name']}")
        print(f"  category: {cat['value'] or 'NONE'} ({cat['from']})")
        for field, source in b["fields"].items():
            print(f"  {field:<28} <- {source}")
        if b["added_from_profile"]:
            print(f"  from profile: {', '.join(b['added_from_profile'])}")
        if b["ignored_fields"]:
            print(f"  not used: {', '.join(b['ignored_fields'])}")
    for n in report["notes"]:
        print(f"note: {n}")
    if args.output:
        print(f"\nWrote {args.output}")
    return 0


def cmd_pipeline(args: argparse.Namespace) -> int:
    from .pipeline import run_pipeline, write_pipeline_files
    result = run_pipeline(_load_phase3(args.input), profile=args.profile, mapping=_mapping(args),
                          expected=args.expected, options=_options(args))
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    paths = write_pipeline_files(result, args.out_dir)
    _print_summary(result["phase4_output"])
    if result["scorecard"]:
        sc = result["scorecard"]
        print(f"Scorecard: {sc['matched']} of {sc['checks']} numbers match the reference ({sc['score_pct']:g}%).")
    print("Wrote:")
    for p in paths:
        print(f"  {p}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    data = _load(args.input)
    out = data if str(data.get("schema_version", "")).startswith("phase4-output/") else run_phase4(data, options=_options(args))
    rows = compare_to_reference(out, load_expected(args.expected))
    print(format_rows(rows, only_failures=args.failures_only))
    return 0 if all(r["ok"] for r in rows) else 1


def cmd_validate(args: argparse.Namespace) -> int:
    norm, warnings = normalize_input(_load(args.input))
    catalog = _catalog(args) or Catalog.load(norm["scenario"])
    print(f"Valid: {len(norm['bottlenecks'])} bottlenecks, scenario {norm['scenario']}.")
    for b in norm["bottlenecks"]:
        cat, match = catalog.match_category(b)
        print(f"  {b['id']} {b['name'][:50]} -> {cat or 'NO CATEGORY'} ({match['method']})")
    for w in warnings:
        print(f"  warning: {w}")
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    catalog = _catalog(args) or Catalog.load(args.scenario)
    for v in catalog.versions:
        print(f"{v['catalog_id']} {v['catalog_version']}")
    for cat_id, cat in catalog.categories.items():
        print(f"\n{cat_id}: {cat.get('label', '')}")
        for n, fix_id in enumerate(cat["fixes"], start=1):
            f = catalog.fixes[fix_id]
            print(f"  Option {n}: {f['name']} [{f['fix_type']}] ({fix_id})")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    for name in list_profiles():
        print(name)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve
    serve(host=args.host, port=args.port, cors_origin=args.cors_origin)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m phase4", description="Phase 4 (step 9): fixes per bottleneck")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--top", type=int, default=3, help="solve the top N bottlenecks by rank (default 3)")
        p.add_argument("--all", action="store_true", help="solve every bottleneck")
        p.add_argument("--max-fixes", type=int, default=2, help="largest mix of fixes per bottleneck (default 2)")

    p = sub.add_parser("pipeline", help="Phase 3 output -> Phase 4 -> every Phase 5 file")
    p.add_argument("input", help="Phase 3 output: .json, .csv, or '-' for stdin")
    p.add_argument("--profile", help="client profile name (see `profiles`) or a path to one")
    p.add_argument("--mapping", help="JSON file with explicit field paths, if the adapter cannot find a field")
    p.add_argument("--expected", help="reference to score against: a name such as 'veloran' or a path")
    p.add_argument("--out-dir", default="phase4_out", help="folder for the output files (default phase4_out)")
    p.add_argument("--json", action="store_true", help="print everything as one JSON object instead of writing files")
    common(p)
    p.set_defaults(func=cmd_pipeline)

    p = sub.add_parser("adapt", help="show how Phase 3 output maps into a Phase 4 input")
    p.add_argument("input", help="Phase 3 output: .json, .csv, or '-' for stdin")
    p.add_argument("--profile", help="client profile name or path")
    p.add_argument("--mapping", help="JSON file with explicit field paths")
    p.add_argument("-o", "--output", help="also write the Phase 4 input here")
    p.set_defaults(func=cmd_adapt)

    p = sub.add_parser("run", help="run Phase 4 on a Phase 4 input file ('-' for stdin)")
    p.add_argument("input")
    p.add_argument("-o", "--output", help="write JSON here (default: print JSON to stdout)")
    p.add_argument("--md", help="also write a Markdown preview here")
    p.add_argument("--ai-text", action="store_true", help="let Claude write the recommendation paragraphs")
    p.add_argument("--model", help="Claude model id (default: $PHASE4_CLAUDE_MODEL or claude-sonnet-5-5)")
    p.add_argument("--catalog", nargs="+", help="use these catalog files instead of the shipped ones")
    common(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("check", help="compare results with a reference report")
    p.add_argument("input", help="a Phase 4 input or output file")
    p.add_argument("--expected", required=True, help="a reference name such as 'veloran', or a path")
    p.add_argument("--failures-only", action="store_true")
    common(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("serve", help="run the Phase 4 HTTP service")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8040)
    p.add_argument("--cors-origin", default="*", help="allowed browser origin, e.g. http://localhost:3000")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("validate", help="check a Phase 4 input file and show category matches")
    p.add_argument("input")
    p.add_argument("--catalog", nargs="+")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("catalog", help="list the fixes in the catalog")
    p.add_argument("--scenario", choices=["A", "B"])
    p.add_argument("--catalog", nargs="+")
    p.set_defaults(func=cmd_catalog)

    p = sub.add_parser("profiles", help="list the client profiles")
    p.set_defaults(func=cmd_profiles)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:  # output piped into `head` and closed early
        return 0
    except Phase3MappingError as exc:
        print(str(exc).replace("Phase 4 input is not valid", "Phase 3 output could not be mapped"), file=sys.stderr)
        return 2
    except Phase4InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read input: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
