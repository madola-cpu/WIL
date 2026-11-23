"""Choose the fixes to recommend for one bottleneck, and say why not the others.

Rules, in order:
1. A fix that needs a missing planning number, a capability the client lacks,
   or a fix nobody chose is set aside, with the reason.
2. High governance risk is never recommended until its prerequisites exist.
3. Every mix of up to N eligible fixes (default 2) is priced with overlaps.
   Mixes with conflicting fixes, or a payback over the limit, are dropped.
4. The mix with the highest first-year net benefit wins
   (ties: faster payback, then fewer fixes, then lower governance risk).
"""
from __future__ import annotations

import operator
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

from .catalog import FIX_TYPES, Catalog, fill_template, template_missing
from .numbers import D, SCENARIOS, fmt_money
from .pricing import PricingContext, price_fix, price_mix

RISK_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
STATUS_LABELS = {
    "recommended": "Recommended",
    "not_chosen": "Not chosen",
    "follow_on": "Follow-on, no extra savings",
    "deferred": "Deferred",
    "on_hold": "Not recommended now",
    "blocked": "Blocked",
    "needs_input": "Needs input",
}
_OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt,
        "==": operator.eq, "!=": operator.ne}
FULL_OVERLAP = D("0.99")
HIGH_OVERLAP = D("0.75")


def requirement_met(req: Dict[str, Any], capabilities: Dict[str, Any]) -> Tuple[bool, Any]:
    current = capabilities.get(req["capability"])
    if current is None:
        return False, None
    try:
        return bool(_OPS[req.get("op", "==")](current, req.get("value", True))), current
    except TypeError:
        return False, current


def type_label(fix: Dict[str, Any]) -> str:
    if fix.get("type_label"):
        return fix["type_label"]
    labels = [FIX_TYPES[fix["fix_type"]]] + [FIX_TYPES[t].lower() for t in fix.get("also", [])]
    return " and ".join(labels)


def _join_types(labels: List[str]) -> str:
    out = []
    for i, label in enumerate(labels):
        if i and not label.startswith("AI"):
            label = label[0].lower() + label[1:]
        out.append(label)
    return "; ".join(out)


def _names(fix_ids: List[str], catalog: Catalog) -> str:
    names = [catalog.fixes[f]["name"] for f in fix_ids]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " + " + names[-1]


def evaluate_bottleneck(bn: Dict[str, Any], norm: Dict[str, Any], catalog: Catalog, options: Any,
                        earlier_selected: Dict[str, Dict[str, str]],
                        other_selected: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """Return the bottleneck's options, the recommended mix and the reasons.

    earlier_selected: fixes already chosen for higher-ranked bottlenecks (their
        cost is counted there, so here they are free).
    other_selected: fixes chosen for any other bottleneck (satisfy dependencies).
    """
    ctx = PricingContext(norm, bn, options)
    company = norm["company"]
    caps = company["capabilities"]
    max_payback = options.max_payback_months
    result: Dict[str, Any] = {
        "id": bn["id"], "rank": bn["rank"], "name": bn["name"],
        "category": None, "category_label": None, "category_match": None,
        "departments": bn["departments"],
        "employees_affected": bn["employees_affected"],
        "hours_lost_per_week": bn["hours_lost_per_week"],
        "annual_cost": bn["annual_cost"],
        "deal_impact": bn["deal_impact"],
        "feasibility": bn["feasibility"],
        "priority_score": bn["priority_score"],
        "root_causes": bn["root_causes"],
        "options": [], "recommendation": None, "notes": [],
    }
    cat_id, match = catalog.match_category(bn)
    result["category_match"] = match
    if cat_id is None:
        result["notes"].append("No fix category in the catalog matches this bottleneck. "
                               "Add a category, or set a known category id in step 7.")
        return result
    category = catalog.categories[cat_id]
    result["category"], result["category_label"] = cat_id, category.get("label")
    in_category = set(category["fixes"])

    # ---------------------------------------------------------- 1. price
    opts: List[Dict[str, Any]] = []
    for number, fix_id in enumerate(category["fixes"], start=1):
        fix = catalog.fixes[fix_id]
        shared = earlier_selected.get(fix_id)
        shared_label = f"{shared['bottleneck_id']} ({shared['bottleneck_name']})" if shared else None
        priced = price_fix(fix, ctx, shared_from=shared_label)
        raw_vendors = fix.get("example_vendors", [])
        if fix.get("example_vendors_fallback") and any(template_missing(v, ctx.variables) for v in raw_vendors):
            vendors = list(fix["example_vendors_fallback"])
        else:
            vendors = [fill_template(v, ctx.variables) for v in raw_vendors]
        effort = fix.get("effort") or {}
        gov = fix.get("governance") or {}
        price_statuses = sorted({i["price_status"] for i in priced["upfront_breakdown"] + priced["ongoing_breakdown"]})
        opt = {
            "option_id": f"{bn['id']}.O{number}",
            "option_number": number,
            "label": f"Option {number}: {fix['name']}",
            "fix_id": fix_id,
            "name": fix["name"],
            "fix_type": fix["fix_type"],
            "also": list(fix.get("also", [])),
            "type_label": type_label(fix),
            "how_it_solves": fill_template(fix["how_it_solves"], ctx.variables, fix["how_it_solves"]),
            "example_vendors": vendors,
            "cost_note": fix.get("cost_note"),
            "implementation": dict(fix.get("implementation") or {}),
            "effort": {"level": effort.get("level", "low"),
                       "note": fill_template(effort.get("note"), ctx.variables, effort.get("note_fallback"))},
            "governance": {
                "risk": gov.get("risk", "none"),
                "note": gov.get("note", ""),
                "is_ai": fix["fix_type"] == "ai_tool",
                "data_accessed": gov.get("data_accessed"),
                "go_live_gates": list(gov.get("go_live_gates", [])),
            },
            "risks_and_dependencies": list(fix.get("risks", [])),
            "evidence": fix.get("evidence", ""),
            "confidence": fix.get("confidence", "estimate"),
            "price_statuses": price_statuses,
            "reskilling_focus": fix.get("reskilling_focus"),
            "status": "eligible", "status_label": None, "status_reason": "", "other_reasons": [],
        }
        for key in ("upfront_cost", "upfront_breakdown", "ongoing_cost_per_year", "ongoing_breakdown",
                    "year_one_cost", "hours_saved_per_week", "deals_recovered_per_year",
                    "annual_time_savings", "annual_deal_margin", "annual_savings", "payback_months",
                    "net_benefit_year_one", "missing_inputs", "cost_shared_with", "trace"):
            opt[key] = priced[key]
        opt["_priced"] = dict(priced, fix_id=fix_id, name=fix["name"])
        opt["_fix"] = fix

        # ------------------------------------------------- 2. pre-checks
        holds: List[Tuple[str, str]] = []   # (kind, reason)
        if priced["missing_inputs"]:
            holds.append(("needs_input", "Needs input: " + ", ".join(priced["missing_inputs"])
                          + " (add to company.volumes) before it can be priced."))
        has_hold_rule = False
        for req in fix.get("requires", []):
            kind = req.get("if_unmet", "block")
            has_hold_rule = has_hold_rule or kind == "hold"
            met, current = requirement_met(req, caps)
            if met:
                continue
            why = req.get("why", f"needs {req['capability']}")
            if kind == "defer":
                if current is None:
                    now = "none recorded"
                elif isinstance(current, bool):
                    now = "yes" if current else "no"
                else:
                    now = current
                text = f"Deferred: {why} (current: {now})."
                holds.append(("deferred", text))
                opt.setdefault("_defer", []).append((req, text))
            elif kind == "hold":
                holds.append(("on_hold", f"Not recommended now: {why}."))
            else:
                holds.append(("blocked", f"Blocked: {why}."))
        if gov.get("risk") == "high" and not has_hold_rule:
            holds.append(("on_hold", "Not recommended now: high governance risk; it needs an approved "
                                     "AI policy and a vendor review first."))
        for dep in fix.get("requires_fix", []):
            if dep not in other_selected and dep not in in_category:
                holds.append(("blocked", f"Blocked: depends on {catalog.fixes[dep]['name']}, "
                                         "which is not part of the recommendation."))
        if holds:
            order = ["needs_input", "blocked", "on_hold", "deferred"]
            holds.sort(key=lambda h: order.index(h[0]))
            opt["status"] = holds[0][0]
            opt["status_reason"] = holds[0][1]
            opt["other_reasons"] = [h[1] for h in holds[1:]]
        opts.append(opt)

    # ------------------------------------------------------ 3. try mixes
    eligible = [o for o in opts if o["status"] == "eligible"]
    max_k = max(1, int(options.max_fixes_per_bottleneck))
    mixes: List[Dict[str, Any]] = []
    rejected: Dict[Tuple[str, ...], str] = {}
    for k in range(1, min(max_k, len(eligible)) + 1):
        for combo in combinations(eligible, k):
            ids = tuple(o["fix_id"] for o in combo)
            reason = _mix_problem(combo, ids, other_selected, catalog)
            if reason:
                rejected[ids] = reason
                continue
            mix = price_mix([o["_priced"] for o in combo], ctx, catalog.overlap)
            pb = mix["payback_months"]["base"]
            if mix["annual_savings"]["base"] <= 0 or pb is None:
                rejected[ids] = "its savings do not cover its cost"
                continue
            if max_payback is not None and pb > max_payback:
                rejected[ids] = f"payback of {pb:.1f} months is over the {max_payback:g}-month limit"
                continue
            risk = sum(RISK_RANK.get(o["governance"]["risk"], 0) for o in combo)
            score = (mix["net_benefit_year_one"]["base"], -pb, -k, -risk)
            mixes.append({"ids": ids, "combo": combo, "mix": mix, "score": score})
    mixes.sort(key=lambda m: m["score"], reverse=True)
    best = mixes[0] if mixes else None

    # --------------------------------------------- 4. statuses and reasons
    chosen = set(best["ids"]) if best else set()
    selected_anywhere = dict(other_selected)
    for fid in chosen:
        selected_anywhere[fid] = {"bottleneck_id": bn["id"], "bottleneck_name": bn["name"]}
    for o in opts:
        fid = o["fix_id"]
        if fid in chosen:
            o["status"] = "recommended"
            o["status_reason"] = "Part of the recommended mix."
            continue
        conflicts = _conflicts_with_chosen(o["_fix"], chosen, catalog)
        if o["status"] == "eligible":
            full = [c for c in chosen if catalog.overlap_is_listed(fid, c) and catalog.overlap(fid, c) >= FULL_OVERLAP]
            if full:
                c = full[0]
                note = (catalog.pair(fid, c) or {}).get("overlap_note") or \
                    f"its savings overlap fully with {catalog.fixes[c]['name']}, so they are counted once."
                reason = f"Follow-on to {catalog.fixes[c]['name']}: {note}"
                for dep in o["_fix"].get("requires_fix", []):
                    if dep in other_selected:
                        where = other_selected[dep]
                        reason += (f" It arrives with the {catalog.fixes[dep]['name']} chosen for "
                                   f"{where['bottleneck_id']} ({where['bottleneck_name'].split(':')[0]}).")
                o["status"], o["status_reason"] = "follow_on", reason
            elif conflicts:
                o["status"], o["status_reason"] = "blocked", conflicts[0]
                o["other_reasons"].extend(conflicts[1:])
            else:
                o["status"] = "not_chosen"
                o["status_reason"] = _why_not_chosen(fid, best, mixes, rejected, chosen, catalog, ctx)
        else:
            o["other_reasons"].extend(conflicts)
        # Say when a recommended fix will create what a deferred fix is waiting for.
        for req, text in o.get("_defer", []):
            unlockers = [u for u in req.get("unlocked_by", []) if u in selected_anywhere]
            if not unlockers:
                continue
            extra = f" The recommended {catalog.fixes[unlockers[0]]['name']} creates this"
            extra += f"; revisit {req['revisit']}." if req.get("revisit") else "."
            if o["status_reason"] == text:
                o["status_reason"] += extra
            o["other_reasons"] = [r + extra if r == text else r for r in o["other_reasons"]]
    for o in opts:
        o["status_label"] = STATUS_LABELS[o["status"]]

    result["options"] = opts
    if best:
        result["recommendation"] = _recommendation(best, opts, catalog, bn, len(mixes))
    else:
        result["notes"].append(
            "No fix or mix of fixes is eligible and pays back within the limit; "
            "see each option's status for why.")
    return result


def _mix_problem(combo, ids, other_selected, catalog) -> Optional[str]:
    id_set = set(ids)
    for o in combo:
        for c in o["_fix"].get("conflicts_with", []):
            if c["fix"] in id_set:
                return f"{o['name']} conflicts with {catalog.fixes[c['fix']]['name']}: {c['why']}"
        for dep in o["_fix"].get("requires_fix", []):
            if dep not in other_selected and dep not in id_set:
                return f"{o['name']} needs {catalog.fixes[dep]['name']} in the same mix"
    return None


def _conflicts_with_chosen(fix: Dict[str, Any], chosen: set, catalog: Catalog) -> List[str]:
    out = []
    for c in fix.get("conflicts_with", []):
        if c["fix"] in chosen:
            out.append(f"Conflicts with {catalog.fixes[c['fix']]['name']}: {c['why']}.")
    for other in chosen:
        for c in catalog.fixes[other].get("conflicts_with", []):
            if c["fix"] == fix["id"]:
                out.append(f"Conflicts with {catalog.fixes[other]['name']}: {c['why']}.")
    return out


def _why_not_chosen(fid, best, mixes, rejected, chosen, catalog, ctx) -> str:
    parts = []
    for c in chosen:
        pair = catalog.pair(fid, c) or {}
        if catalog.overlap(fid, c) >= HIGH_OVERLAP and pair.get("overlap_note"):
            parts.append(f"Largely duplicates {catalog.fixes[c]['name']}: {pair['overlap_note']}")
            break
    with_it = [m for m in mixes if fid in m["ids"]]
    if with_it and best:
        alt = with_it[0]
        parts.append(
            f"The best mix that includes it ({_names(list(alt['ids']), catalog)}) nets "
            f"{ctx.money(alt['mix']['net_benefit_year_one']['base'])} in year one, against "
            f"{ctx.money(best['mix']['net_benefit_year_one']['base'])} for the recommended mix.")
    elif (fid,) in rejected:
        parts.append(f"On its own, its {rejected[(fid,)]}.")
    else:
        parts.append("It does not fit in any mix that pays back within the limit.")
    return " ".join(parts)


def _recommendation(best, opts, catalog, bn, n_mixes) -> Dict[str, Any]:
    combo = list(best["combo"])
    seq = sorted(combo, key=lambda o: (o["implementation"].get("weeks_min", 0),
                                       o["implementation"].get("weeks_max", 0), o["option_number"]))
    ids = [o["fix_id"] for o in seq]
    overlaps = []
    together = []
    for a, b in combinations(ids, 2):
        overlaps.append({"pair": [a, b], "overlap": float(catalog.overlap(a, b)),
                         "listed_in_catalog": catalog.overlap_is_listed(a, b)})
        note = (catalog.pair(a, b) or {}).get("together_note")
        if note:
            together.append(note)
    mix = best["mix"]
    return {
        "fix_ids": ids,
        "option_ids": [o["option_id"] for o in seq],
        "option_numbers": [o["option_number"] for o in seq],
        "names": [o["name"] for o in seq],
        "type_summary": _join_types([o["type_label"] for o in seq]),
        "sequence": [
            {"step": i + 1, "option_id": o["option_id"], "name": o["name"],
             "time_to_live": o["implementation"].get("label", "")}
            for i, o in enumerate(seq)
        ],
        "hours_saved_per_week": mix["hours_saved_per_week"],
        "deals_recovered_per_year": mix["deals_recovered_per_year"],
        "upfront_cost": mix["upfront_cost"],
        "ongoing_cost_per_year": mix["ongoing_cost_per_year"],
        "year_one_cost": mix["year_one_cost"],
        "annual_time_savings": mix["annual_time_savings"],
        "annual_deal_margin": mix["annual_deal_margin"],
        "annual_savings": mix["annual_savings"],
        "payback_months": mix["payback_months"],
        "net_benefit_year_one": mix["net_benefit_year_one"],
        "overlaps_applied": overlaps,
        "together_note": " ".join(together) or None,
        "mixes_compared": n_mixes,
        "summary": "",
        "summary_source": "template",
        "trace": mix["trace"],
    }
