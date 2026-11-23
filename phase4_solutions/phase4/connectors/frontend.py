"""Phase 4 -> frontend: one compact, display-ready JSON for the manager view.

Every number comes as {"value": raw number, "display": "ready text"}, with a
range and the calculation ("math") where it helps, so the frontend only binds
fields and never formats money or works anything out.

    view = manager_view(output)

Types: contracts/phase4.d.ts (ManagerView). Schema: contracts/manager_view.schema.json.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..numbers import fmt_money, fmt_num, fmt_payback, fmt_pct, round_half_up

VIEW_VERSION = "phase4-manager-view/1.0"
BADGES = {
    "recommended": ("Recommended", "positive", "Part of the recommended mix"),
    "follow_on": ("Follow-on", "info", "Comes with a chosen fix; no extra savings counted"),
    "not_chosen": ("Not chosen", "neutral", "Eligible, but a better mix exists"),
    "deferred": ("Deferred", "warning", "Waits for a prerequisite"),
    "on_hold": ("Not now", "warning", "Governance risk too high until consent or policy exist"),
    "blocked": ("Blocked", "negative", "Depends on, or conflicts with, another fix"),
    "needs_input": ("Needs input", "attention", "A planning number is missing"),
}


def _money(cur: str, rng: Dict[str, Any], math: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": rng["base"], "display": fmt_money(rng["base"], cur)}
    if rng["low"] != rng["base"] or rng["high"] != rng["base"]:
        lo, hi = sorted((rng["low"], rng["high"]))
        out["range"] = {"low": lo, "high": hi, "display": f"{fmt_money(lo, cur)} to {fmt_money(hi, cur)}"}
    if math:
        out["math"] = math
    return out


def _hours(rng: Dict[str, Any], math: Optional[str] = None, unit: str = "h a week") -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": rng["base"], "display": f"{fmt_num(rng['base'])} {unit}"}
    if rng["low"] != rng["base"] or rng["high"] != rng["base"]:
        out["range"] = {"low": rng["low"], "high": rng["high"],
                        "display": f"{fmt_num(rng['low'])} to {fmt_num(rng['high'])} {unit}"}
    if math:
        out["math"] = math
    return out


def _payback(rng: Dict[str, Any], math: Optional[str] = None) -> Dict[str, Any]:
    base = rng["base"]
    text = fmt_payback(base)
    out: Dict[str, Any] = {"value": base, "display": text if base in (None, 0) else f"{text} months"}
    if rng["low"] != base or rng["high"] != base:
        fast, slow = rng["high"], rng["low"]  # the high case pays back fastest
        out["range"] = {"low": fast, "high": slow, "display": f"{fmt_payback(fast)} to {fmt_payback(slow)} months"}
    if math:
        out["math"] = math
    return out


def _badge(status: str) -> Dict[str, str]:
    label, tone, meaning = BADGES[status]
    return {"status": status, "label": label, "tone": tone, "meaning": meaning}


def manager_view(output: Dict[str, Any]) -> Dict[str, Any]:
    """The manager-view data: headline numbers, one card per bottleneck, governance and warnings."""
    cur = output["assumptions_used"]["currency"]
    p = output["program"]
    has_recs = p["recommendation_count"] > 0
    view: Dict[str, Any] = {
        "view_version": VIEW_VERSION,
        "client_name": output["run"]["client_name"],
        "scenario": output["run"]["scenario"],
        "generated_at": output["run"]["generated_at"],
        "engine": output["run"]["engine"],
        "headline": {
            "year_one_cost": _money(cur, p["year_one_cost"]),
            "annual_savings": _money(cur, p["annual_savings"]),
            "net_benefit_year_one": _money(cur, p["net_benefit_year_one"]),
            "payback": _payback(p["payback_months"]) if has_recs else {"value": None, "display": "n/a"},
            "hours_won_back_per_week": {
                "value": p["effective_hours_saved_per_week"]["base"],
                "display": f"{fmt_num(round_half_up(p['effective_hours_saved_per_week']['base'], 0))} hours",
                "math": f"{fmt_num(p['gross_hours_saved_per_week']['base'])} gross hours x "
                        f"{fmt_pct(p['adoption_rate_base'])} adoption",
            },
            "share_of_lost_time": {
                "value": p["share_of_lost_hours_recovered"],
                "display": fmt_pct(p["share_of_lost_hours_recovered"]),
                "math": f"of the {fmt_num(round_half_up(p['hours_lost_in_scope_per_week'], 0))} hours lost a week "
                        "to the bottlenecks in scope",
            },
        },
        "summary": p["summary"],
        "bottlenecks": [],
        "not_in_scope": [{"id": b["id"], "title": b["name"].split(":")[0].strip(), "reason": b["reason"]}
                         for b in output.get("bottlenecks_not_in_scope", [])],
        "governance_actions": [{"action": g["action"], "for": g["for"]} for g in p["governance_actions"]],
        "upside_not_counted": {
            "total": {"value": p["upside_not_counted_total"], "display": fmt_money(p["upside_not_counted_total"], cur)},
            "items": [{"label": u["label"], "value": u["amount"], "display": fmt_money(u["amount"], cur),
                       "basis": u.get("basis", "")} for u in p["upside_not_counted"]],
        },
        "warnings": list(output.get("warnings", [])),
        "badge_legend": [_badge(s) for s in BADGES],
    }
    for b in output["bottlenecks"]:
        r = b["recommendation"]
        card: Dict[str, Any] = {
            "id": b["id"],
            "rank": b["rank"],
            "title": b["name"].split(":")[0].strip(),
            "full_name": b["name"],
            "category": b.get("category"),
            "people_affected": b["employees_affected"],
            "hours_lost_per_week": _hours(b["hours_lost_per_week"]),
            "annual_cost": _money(cur, b["annual_cost"]) if b.get("annual_cost") else None,
            "recommendation": None,
            "options": [],
            "notes": list(b.get("notes", [])),
        }
        if r:
            card["recommendation"] = {
                "option_ids": r["option_ids"],
                "names": r["names"],
                "type_summary": r["type_summary"],
                "summary": r["summary"],
                "hours_saved_per_week": _hours(r["hours_saved_per_week"], r["trace"].get("hours_saved_per_week")),
                "annual_savings": _money(cur, r["annual_savings"], r["trace"].get("annual_time_savings")),
                "year_one_cost": _money(cur, r["year_one_cost"], r["trace"].get("year_one_cost")),
                "payback": _payback(r["payback_months"], r["trace"].get("payback_months")),
                "sequence": r["sequence"],
            }
        for o in b["options"]:
            card["options"].append({
                "option_id": o["option_id"],
                "number": o["option_number"],
                "label": o["label"],
                "name": o["name"],
                "type": o["fix_type"],
                "type_label": o["type_label"],
                "badge": _badge(o["status"]),
                "reason": o["status_reason"],
                "other_reasons": o["other_reasons"],
                "how_it_solves": o["how_it_solves"],
                "vendors": o["example_vendors"],
                "upfront_cost": _money(cur, o["upfront_cost"]),
                "ongoing_cost_per_year": _money(cur, o["ongoing_cost_per_year"]),
                "year_one_cost": _money(cur, o["year_one_cost"], o["trace"].get("year_one_cost")),
                "hours_saved_per_week": _hours(o["hours_saved_per_week"], o["trace"].get("hours_saved_per_week")),
                "annual_savings": _money(cur, o["annual_savings"], o["trace"].get("annual_time_savings")),
                "payback": _payback(o["payback_months"], o["trace"].get("payback_months")),
                "implementation": o["implementation"].get("label", ""),
                "effort": o["effort"]["note"],
                "governance": {"risk": o["governance"]["risk"], "label": o["governance"]["note"],
                               "is_ai": o["governance"]["is_ai"], "go_live_gates": o["governance"]["go_live_gates"]},
                "confidence": o["confidence"],
            })
        view["bottlenecks"].append(card)
    return view
