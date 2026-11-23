"""Phase 4 (step 9): turn priced bottlenecks into fix options and recommendations.

    from phase4 import run_phase4
    output = run_phase4(step8_json)            # dict in, dict out (JSON-ready)

Input format:  contracts/phase4_input.schema.json
Output format: contracts/phase4_output.schema.json
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .catalog import Catalog
from .contract import normalize_input
from .narrative import ClaudeWriter, not_chosen_list, program_summary, recommendation_summary
from .numbers import D, SCENARIOS, payback_months, round_half_up
from .selection import evaluate_bottleneck

ENGINE_VERSION = "0.2.0"
OUTPUT_SCHEMA_VERSION = "phase4-output/1.0"


@dataclass
class Phase4Options:
    top_n: Optional[int] = 3                 # bottlenecks to solve, by rank (None = all)
    max_fixes_per_bottleneck: int = 2        # largest mix of fixes to recommend per bottleneck
    min_group_size: int = 5                  # privacy rule: no group under 5 people
    max_payback_months: Optional[float] = None   # None = use assumptions.max_payback_months
    hours_rounding: float = 1                # hours saved are rounded to this step
    max_recoverable_share: float = 0.9       # a mix can never remove more than this share of lost hours
    cost_contingency: Dict[str, float] = field(
        default_factory=lambda: {"low": 0.15, "base": 0.0, "high": 0.0})  # low case assumes overruns
    count_deal_margin: bool = True           # scenario B: count recovered deal margin as savings
    ai_text: bool = False                    # let Claude write the recommendation paragraphs
    ai_model: Optional[str] = None
    max_passes: int = 3                      # re-run so cross-bottleneck dependencies settle


def run_phase4(raw_input: Dict[str, Any], options: Optional[Phase4Options] = None,
               catalog: Optional[Catalog] = None, ai_client: Any = None,
               now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run Phase 4 on one input. Raises Phase4InputError if the input is unusable."""
    norm, warnings = normalize_input(raw_input)
    opts = replace(options or Phase4Options())
    if opts.max_payback_months is None:
        opts.max_payback_months = float(norm["assumptions"]["max_payback_months"])
    catalog = catalog or Catalog.load(norm["scenario"])
    currency = norm["assumptions"]["currency"]

    # ------------------------------------------------ bottlenecks in scope
    ranked = sorted(enumerate(norm["bottlenecks"]), key=lambda ib: (ib[1]["rank"], ib[0]))
    in_scope, out_of_scope = [], []
    for _, bn in ranked:
        if bn["employees_affected"] < opts.min_group_size:
            warnings.append(f"{bn['id']} ({bn['name']}) affects fewer than {opts.min_group_size} people, "
                            "so it is left out to protect individuals.")
            out_of_scope.append({"id": bn["id"], "name": bn["name"], "rank": bn["rank"],
                                 "reason": f"group under {opts.min_group_size} people"})
        elif opts.top_n is not None and len(in_scope) >= opts.top_n:
            out_of_scope.append({"id": bn["id"], "name": bn["name"], "rank": bn["rank"],
                                 "reason": f"outside the top {opts.top_n}"})
        else:
            in_scope.append(bn)

    # ------------------------------------- choose fixes (repeat until stable)
    results: Dict[str, Dict[str, Any]] = {}
    previous: Optional[Dict[str, List[str]]] = None
    for _ in range(max(1, opts.max_passes)):
        chosen_by_bn: Dict[str, List[str]] = {}
        earlier: Dict[str, Dict[str, str]] = {}
        for bn in in_scope:
            other = dict(earlier)
            for bid, ids in (previous or {}).items():
                if bid != bn["id"] and bid not in chosen_by_bn:
                    name = next(b["name"] for b in in_scope if b["id"] == bid)
                    for fid in ids:
                        other.setdefault(fid, {"bottleneck_id": bid, "bottleneck_name": name})
            res = evaluate_bottleneck(bn, norm, catalog, opts, earlier_selected=earlier, other_selected=other)
            ids = res["recommendation"]["fix_ids"] if res["recommendation"] else []
            chosen_by_bn[bn["id"]] = ids
            for fid in ids:
                earlier.setdefault(fid, {"bottleneck_id": bn["id"], "bottleneck_name": bn["name"]})
            results[bn["id"]] = res
        if chosen_by_bn == previous:
            break
        previous = chosen_by_bn

    bottlenecks = [results[bn["id"]] for bn in in_scope]
    for res in bottlenecks:
        for note in res["notes"]:
            warnings.append(f"{res['id']}: {note}")

    # ------------------------------------------------------------- words
    writer = ClaudeWriter(client=ai_client, model=opts.ai_model) if opts.ai_text else None
    for res in bottlenecks:
        rec = res["recommendation"]
        if not rec:
            continue
        rec["summary"] = recommendation_summary(res, currency)
        rec["summary_template"] = rec["summary"]
        rec["not_chosen"] = not_chosen_list(res)
        if writer:
            text, warn = writer.recommendation(res)
            if text:
                rec["summary"], rec["summary_source"] = text, f"claude:{writer.model}"
            if warn:
                warnings.append(warn)

    _attach_skill_signals(bottlenecks, norm, opts)
    program = _program_totals(bottlenecks, norm, opts)
    program["summary"] = program_summary(program, currency)

    for res in bottlenecks:
        for o in res["options"]:
            for key in [k for k in o if k.startswith("_")]:
                del o[key]

    stamp = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    a = norm["assumptions"]
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "run": {
            **copy.deepcopy(norm["run"]),
            "scenario": norm["scenario"],
            "client_name": norm["company"]["name"],
            "engine": f"phase4 {ENGINE_VERSION}",
            "catalogs": catalog.versions,
            "input_schema_version": norm["schema_version"],
            "generated_at": stamp,
        },
        "assumptions_used": {
            "currency": currency,
            "loaded_hourly_rate": a["loaded_hourly_rate"],
            "working_weeks_per_year": a["working_weeks_per_year"],
            "adoption_rate": a["adoption_rate"],
            "max_payback_months": opts.max_payback_months,
            "max_fixes_per_bottleneck": opts.max_fixes_per_bottleneck,
            "top_n": opts.top_n,
            "min_group_size": opts.min_group_size,
            "hours_rounding": opts.hours_rounding,
            "max_recoverable_share": opts.max_recoverable_share,
            "cost_contingency": opts.cost_contingency,
            "count_deal_margin": opts.count_deal_margin,
            "sources": a["sources"],
            "formulas": {
                "hours_saved_per_week": "effect share x hours lost per week, rounded to whole hours",
                "annual_time_savings": "hours saved x working weeks x loaded hourly rate x adoption",
                "annual_deal_margin": "deals lost x recovery share x adoption x average deal value x contribution margin",
                "year_one_cost": "upfront cost + first year of ongoing cost",
                "payback_months": "year-one cost / (annual savings / 12)",
                "mix_of_fixes": "largest saving + each other saving x (1 - overlap); never more than the cap share of hours lost",
                "choice": "highest first-year net benefit among eligible mixes that pay back within the limit",
            },
        },
        "bottlenecks": bottlenecks,
        "bottlenecks_not_in_scope": out_of_scope,
        "program": program,
        "warnings": warnings,
    }


def _program_totals(bottlenecks: List[Dict[str, Any]], norm: Dict[str, Any], opts: Phase4Options) -> Dict[str, Any]:
    recs = [(b, b["recommendation"]) for b in bottlenecks if b["recommendation"]]

    def total(key: str) -> Dict[str, Any]:
        return {s: sum(r[key][s] for _, r in recs) for s in SCENARIOS}

    adoption = norm["assumptions"]["adoption_rate"]
    year_one, ongoing, savings = total("year_one_cost"), total("ongoing_cost_per_year"), total("annual_savings")
    gross = {s: sum((D(r["hours_saved_per_week"][s]) for _, r in recs), Decimal(0)) for s in SCENARIOS}
    effective = {s: float(round_half_up(gross[s] * D(adoption[s]), 1)) for s in SCENARIOS}
    lost = sum((D(b["hours_lost_per_week"]["base"]) for b in bottlenecks), Decimal(0))
    share = float(round_half_up(D(effective["base"]) / lost, 4)) if lost else 0.0

    type_counts: Dict[str, int] = {}
    gates: Dict[str, List[str]] = {}
    recommended_ids = set()
    for b, r in recs:
        by_id = {o["option_id"]: o for o in b["options"]}
        for oid in r["option_ids"]:
            o = by_id[oid]
            recommended_ids.add(o["fix_id"])
            for t in [o["fix_type"]] + o["also"]:
                type_counts[t] = type_counts.get(t, 0) + 1
            for g in o["governance"]["go_live_gates"]:
                gates.setdefault(g, []).append(o["name"])

    upside = []
    for item in [u for b in bottlenecks for u in norm_upside(b, norm)] + list(norm["upside_not_counted"]):
        unlocked_by = item.get("unlocked_by") or []
        if not unlocked_by or set(unlocked_by) & recommended_ids:
            upside.append({k: item[k] for k in ("key", "label", "amount", "basis", "unlocked_by") if k in item})

    return {
        "recommendation_count": len(recs),
        "bottlenecks_with_recommendation": [b["id"] for b, _ in recs],
        "year_one_cost": year_one,
        "ongoing_cost_per_year": ongoing,
        "gross_hours_saved_per_week": {s: int(gross[s]) if gross[s] == gross[s].to_integral_value() else float(gross[s]) for s in SCENARIOS},
        "effective_hours_saved_per_week": effective,
        "adoption_rate_base": adoption["base"],
        "hours_lost_in_scope_per_week": float(lost) if lost != lost.to_integral_value() else int(lost),
        "share_of_lost_hours_recovered": share,
        "annual_time_savings": total("annual_time_savings"),
        "annual_deal_margin": total("annual_deal_margin"),
        "annual_savings": savings,
        "net_benefit_year_one": {s: savings[s] - year_one[s] for s in SCENARIOS},
        "net_benefit_year_two_onward": {s: savings[s] - ongoing[s] for s in SCENARIOS},
        "payback_months": {s: payback_months(year_one[s], savings[s]) if recs else None for s in SCENARIOS},
        "fix_type_counts": type_counts,
        "governance_actions": [{"action": g, "for": sorted(set(names))} for g, names in gates.items()],
        "upside_not_counted": upside,
        "upside_not_counted_total": sum(u["amount"] for u in upside),
        "summary": "",
    }


def norm_upside(bottleneck_result: Dict[str, Any], norm: Dict[str, Any]) -> List[Dict[str, Any]]:
    src = next(b for b in norm["bottlenecks"] if b["id"] == bottleneck_result["id"])
    return list(src.get("upside_not_counted") or [])


def _attach_skill_signals(bottlenecks: List[Dict[str, Any]], norm: Dict[str, Any], opts: Phase4Options) -> None:
    """Step 2 (after Dec 9) sends team-level skill signals; use them to aim reskilling fixes."""
    signals = [s for s in norm["skill_signals"]
               if s.get("signal") == "gap" and (s.get("people") is None or s["people"] >= opts.min_group_size)]
    for b in bottlenecks:
        teams = {d.lower() for d in b["departments"]}
        for o in b["options"]:
            if "reskilling" not in [o["fix_type"]] + o["also"]:
                continue
            matches = [s for s in signals if not teams or s["team"].lower() in teams]
            o["reskilling_targets"] = [
                {"team": s["team"], "skill": s["skill"], "evidence": s.get("evidence", "")} for s in matches
            ]
            if not norm["skill_signals"]:
                o["reskilling_targets_note"] = "Skill signals from step 2 are not available yet."
