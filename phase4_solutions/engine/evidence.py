"""Effect of each fix component from alignment-weighted evidence (PHASE_4_PROMPT.md 6.1).

Each study that applies to a component is put on one scale (time reduction),
scored for how closely it matches the client (alignment), given a transfer
uncertainty that grows with poor alignment and age, and pooled. The result is
a predictive distribution for one new client: Normal(mu, sigma).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

Z90 = 1.2815515655446004  # standard normal quantile at 0.90


def adjusted_effect(study: Dict[str, Any], design_discount: Dict[str, float]) -> float:
    effect = float(study["effect"])
    if study["metric"] == "productivity_gain":
        effect = 1.0 - 1.0 / (1.0 + effect)
    elif study["metric"] != "time_reduction":
        raise ValueError(f"{study['id']}: unknown metric {study['metric']!r}")
    return effect * float(design_discount[study["design"]])


def sampling_se(study: Dict[str, Any]) -> Tuple[float, Optional[str]]:
    if study.get("se") is not None:
        return float(study["se"]), None
    if study.get("ci_low") is not None and study.get("ci_high") is not None:
        return (float(study["ci_high"]) - float(study["ci_low"])) / 3.92, None
    return 1.0 / math.sqrt(float(study["n"])), "se approximated"


def task_score(study_task: str, work_type: Optional[str], families: Dict[str, List[str]]) -> int:
    if work_type is None:
        return 0
    if study_task == work_type:
        return 2
    return 1 if any(study_task in members and work_type in members for members in families.values()) else 0


def people_score(study: Dict[str, Any], affected: Dict[str, Tuple[str, float]]) -> float:
    """affected: person_id -> (soc_code, lost hours a week). Weighted by lost hours (equal if all zero)."""
    if not affected:
        return 0.0
    codes, majors = set(study.get("soc_codes") or []), set(study.get("soc_major_groups") or [])
    total = sum(h for _, h in affected.values())
    score = 0.0
    for soc, h in affected.values():
        s = 2 if soc in codes else 1 if soc[:2] in majors else 0
        score += s * (h / total if total > 0 else 1.0 / len(affected))
    return round(score, 6)


def transfer_sd(alignment: float, sd_at_zero: float, drift: float, age: float) -> float:
    return math.sqrt(((1.0 - alignment) * sd_at_zero) ** 2 + (drift * age) ** 2)


def dersimonian_laird(ys: List[float], variances: List[float]) -> float:
    w = [1.0 / v for v in variances]
    sw = sum(w)
    mu = sum(wi * yi for wi, yi in zip(w, ys)) / sw
    q = sum(wi * (yi - mu) ** 2 for wi, yi in zip(w, ys))
    c = sw - sum(wi * wi for wi in w) / sw
    return max(0.0, (q - (len(ys) - 1)) / c) if c > 0 else 0.0


def pool(entries: List[Dict[str, float]], tau_min: float) -> Dict[str, float]:
    """entries: dicts with y, se, t. Transfer error is treated as shared, so it is averaged, not shrunk."""
    w = [1.0 / (e["se"] ** 2 + e["t"] ** 2) for e in entries]
    sw = sum(w)
    mu = sum(wi * e["y"] for wi, e in zip(w, entries)) / sw
    v = sum(wi * wi * e["se"] ** 2 for wi, e in zip(w, entries)) / sw ** 2
    t = sum(wi * e["t"] for wi, e in zip(w, entries)) / sw
    tau2 = tau_min ** 2
    if len(entries) >= 3:
        tau2 = max(tau2, dersimonian_laird([e["y"] for e in entries], [e["se"] ** 2 + e["t"] ** 2 for e in entries]))
    return {"mu": mu, "sigma": math.sqrt(v + t * t + tau2), "V": v, "T": t, "tau2": tau2,
            "weights": [wi / sw for wi in w]}


def effect_quantiles(mu: float, sigma: float) -> Dict[str, float]:
    return {"p10": min(1.0, mu - Z90 * sigma), "p50": min(1.0, mu), "p90": min(1.0, mu + Z90 * sigma)}


def component_effect(component: Dict[str, Any], work_type: Optional[str], affected: Dict[str, Tuple[str, float]],
                     studies: List[Dict[str, Any]], assumptions: Dict[str, Dict[str, Any]],
                     families: Dict[str, List[str]], run_year: int) -> Dict[str, Any]:
    """Pool the studies that apply to one component; fall back to its report estimate."""
    a = assumptions
    discounts = {k: v for k, v in a["design_discount"].items() if k not in ("source", "url")}
    s0 = float(a["transfer_sd_at_zero_alignment"]["value"])
    drift = float(a["drift_per_year"][component["kind"]])
    tau_min = float(a["tau_min"]["value"])
    flags: List[str] = []
    rows: List[Dict[str, Any]] = []
    for st in studies:
        entry = next((x for x in st.get("applies_to", []) if x["component"] == component["id"]), None)
        if entry is None:
            continue
        scores = {"task": task_score(st["task"], work_type, families), "people": people_score(st, affected),
                  "setting": int(st["setting"]), "outcome": int(st["outcome"]), "tool": int(entry["tool"])}
        align = sum(scores.values()) / 10.0
        age = max(0, run_year - int(st["data_year"]))
        se, se_flag = sampling_se(st)
        rows.append({"id": st["id"], "source": st["source"], "url": st.get("url"), "design": st["design"],
                     "data_year": st["data_year"], "scores": scores, "alignment": align, "age": age,
                     "y": adjusted_effect(st, discounts), "se": se, "t": transfer_sd(align, s0, drift, age),
                     "flags": [se_flag] if se_flag else [], "caution": st.get("caution")})
    estimate = component.get("report_estimate")
    if not rows:
        if estimate is None:
            return {"component": component["id"], "kind": component["kind"], "studies": [], "flags": ["no evidence and no estimate"],
                    "mu": None, "sigma": None, "effect": None}
        flags.append("no matching study")
        align = 0.9
        rows.append({"id": f"report_estimate.{component['id']}", "source": component.get("note") or "reference report estimate",
                     "url": None, "design": "expert_estimate", "data_year": run_year,
                     "scores": None, "alignment": align, "age": 0,
                     "y": float(estimate) * float(discounts["expert_estimate"]),
                     "se": float(a["expert_se_share"]["value"]) * float(estimate),
                     "t": transfer_sd(align, s0, drift, 0), "flags": [], "caution": None})
    pooled = pool(rows, tau_min)
    for r, share in zip(rows, pooled["weights"]):
        r["weight_share"] = share
    for r in rows:
        flags += [f"{r['id']}: {f}" for f in r["flags"]]
    q = effect_quantiles(pooled["mu"], pooled["sigma"])
    position = None
    if estimate is not None and "no matching study" not in flags:
        position = "above" if estimate > q["p90"] else "below" if estimate < q["p10"] else "within"
        if position != "within":
            flags.append(f"report assumption {position} the evidence range")
    return {"component": component["id"], "kind": component["kind"], "studies": rows, "flags": flags,
            "mu": pooled["mu"], "sigma": pooled["sigma"], "V": pooled["V"], "T": pooled["T"], "tau2": pooled["tau2"],
            "effect": q, "report_estimate": estimate, "report_estimate_position": position}
