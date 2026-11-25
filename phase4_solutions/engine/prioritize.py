"""Rank fixes (PHASE_4_PROMPT.md section 7): score = value x confidence / effort.

value      = P50 annual hours saved
confidence = P10 / P50 of annual hours, clipped to 0-1, halved unless sufficiency is ok
effort     = low 1, medium 2, high 3
Ties go to the shorter time to value. React first = the top 3.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .bottlenecks import num

EFFORT = {"low": 1, "medium": 2, "high": 3}


def rank(fixes: List[Dict[str, Any]], names: Dict[str, str]) -> List[Dict[str, Any]]:
    ranked = []
    for f in fixes:
        if f["status"] != "computed":
            continue
        p10, p50 = f["annual_hours"]["p10"]["value"], f["annual_hours"]["p50"]["value"]
        conf = min(1.0, max(0.0, p10 / p50)) if p50 > 0 else 0.0
        if f["sufficiency"] != "ok":
            conf /= 2.0
        effort = EFFORT[f["effort"]]
        score = p50 * conf / effort
        src = f["annual_hours"]["p50"]["source"]
        f["priority"] = {"value_annual_hours_p50": num(p50, src, 2), "confidence": num(conf, src, 3),
                         "effort_score": num(effort, f"assumption:fixes.{f['id']}", 0), "score": num(score, src, 2)}
        ranked.append(f)
    ranked.sort(key=lambda f: (-f["priority"]["score"]["value"], f["time_to_value_weeks"]["value"], f["id"]))
    for i, f in enumerate(ranked, start=1):
        f["priority"]["rank"] = i
    return ranked


def reason(f: Dict[str, Any], bottleneck_name: str) -> str:
    h = f["hours_saved_per_week"]
    money = ""
    if "p50" in f["dollars"]:
        money = f", about ${f['dollars']['p50']['value']:,.0f} a year ({f['dollars']['label']})"
    return (f"{f['name']}: saves {h['p50']['value']:g} hours a week (P10 {h['p10']['value']:g}, "
            f"P90 {h['p90']['value']:g}) on {bottleneck_name.lower()}{money}; {f['effort']} effort, "
            f"value in about {f['time_to_value_weeks']['value']:g} weeks; top driver: {f['sensitivity']['top_driver']}.")


def react_first(ranked: List[Dict[str, Any]], names: Dict[str, str], n: int = 3) -> List[Dict[str, Any]]:
    return [{"rank": f["priority"]["rank"], "fix": f["id"], "name": f["name"], "reason": reason(f, names[f["bottleneck"]])}
            for f in ranked[:n]]
