"""Monte Carlo savings per fix (PHASE_4_PROMPT.md 6.2).

hours saved = H_b x (1 - prod_c(1 - e_c x a)). H_b is a bootstrap mean of the
bottleneck's weekly totals, e_c ~ Normal(mu_c, sigma_c) capped at 1 (from
engine.evidence), and a ~ Triangular(adoption). Fixes on one bottleneck share
the H_b draws and combine multiplicatively, never additively. Every draw is
seeded, so the same seed gives the same output.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .bottlenecks import Bottleneck, num
from .contract import Config, Dataset
from .evidence import component_effect
from .kpis import quantile

INF = float("inf")
QS = (("p10", 0.10), ("p50", 0.50), ("p90", 0.90))


def q_inf(values: List[float], q: float) -> float:
    """Quantile that tolerates infinite values (draws that never pay back)."""
    v = sorted(values)
    pos = (len(v) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if v[lo] == INF or v[hi] == INF:
        return INF
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def triple(draws: List[float], source: str, nd: int = 2) -> Dict[str, Any]:
    return {name: num(quantile(draws, q), source, nd) for name, q in QS}


def bootstrap_hours(weekly: List[float], draws: int, rng: random.Random) -> List[float]:
    n = len(weekly)
    return [sum(rng.choice(weekly) for _ in range(n)) / n for _ in range(draws)]


def loaded_rate(b: Bottleneck, ds: Dataset, cfg: Config) -> Tuple[Optional[float], str, str, str]:
    """Blended loaded hourly rate over the bottleneck's roles, weighted by lost hours.

    Returns (rate or None, label, source tag, reason). Never guesses a missing wage.
    """
    people = ds.people
    total = sum(b.person_lost.values())
    weight = {p: (h / total if total > 0 else 1.0 / len(b.person_lost)) for p, h in b.person_lost.items()}
    if ds.client_rates is not None:
        missing = sorted({people[p]["role"] for p in weight if people[p]["role"] not in ds.client_rates})
        if missing:
            return None, "not computed", "", "client_rates.csv has no rate for role(s): " + ", ".join(missing)
        rate = sum(w * ds.client_rates[people[p]["role"]] for p, w in weight.items())
        return rate, "client rate", "client:client_rates.csv", ""
    missing = sorted({people[p]["soc_code"] for p in weight if people[p]["soc_code"] not in cfg.wages})
    if missing:
        return None, "not computed", "", ("no mean_hourly_wage in data/reference/wages.csv for soc_code(s): "
                                          + ", ".join(missing))
    share = float(cfg.value("wage_share_of_compensation"))
    rate = sum(w * cfg.wages[people[p]["soc_code"]]["mean_hourly_wage"] / share for p, w in weight.items())
    return rate, "market-rate estimate", "reference:wages.csv+assumption:wage_share_of_compensation", ""


def _sources(components: List[Dict[str, Any]]) -> str:
    tags = ["data"]
    for c in components:
        for s in c["studies"]:
            tags.append(("assumption:" if s["id"].startswith("report_estimate.") else "evidence:") + s["id"])
    tags.append("assumption:adoption")
    return "+".join(dict.fromkeys(tags))


def _saving(h: float, effects: List[float], a: float) -> float:
    keep = 1.0
    for e in effects:
        keep *= 1.0 - e * a
    return h * (1.0 - keep)


def simulate(bottlenecks: List[Bottleneck], ds: Dataset, cfg: Config, run_year: int,
             draws: Optional[int] = None, seed: Optional[int] = None) -> Dict[str, Any]:
    mc = cfg.assumptions["monte_carlo"]
    draws = int(draws or mc["draws"])
    seed = int(mc["seed"] if seed is None else seed)
    adopt = cfg.assumptions["adoption"]
    weeks_per_year = float(cfg.value("weeks_per_year"))
    by_id = {b.id: b for b in bottlenecks if not b.diagnostic}
    h_draws = {bid: bootstrap_hours(b.weekly_values, draws, random.Random(f"{seed}:hours:{bid}"))
               for bid, b in by_id.items()}
    keep_by_bottleneck: Dict[str, List[List[float]]] = defaultdict(list)
    fixes: List[Dict[str, Any]] = []
    for fix in cfg.fixes:
        base = {"id": fix["id"], "name": fix["name"], "bottleneck": fix["bottleneck"],
                "effort": fix["effort"],
                "time_to_value_weeks": num(fix["time_to_value_weeks"], f"assumption:fixes.{fix['id']}", 0),
                "year_one_cost": num(fix["year_one_cost"], f"assumption:fixes.{fix['id']}", 0),
                "ongoing_cost": num(fix["ongoing_cost"], f"assumption:fixes.{fix['id']}", 0)}
        b = by_id.get(fix["bottleneck"])
        if b is None:
            fixes.append({**base, "status": "not_applicable",
                          "reason": f"bottleneck {fix['bottleneck']} was not detected in this data"})
            continue
        affected = {p: (ds.people[p]["soc_code"], h) for p, h in b.person_lost.items()}
        comps = [component_effect(c, b.rule.get("work_type"), affected, cfg.studies, cfg.assumptions,
                                  cfg.families, run_year) for c in fix["components"]]
        if any(c["mu"] is None for c in comps):
            fixes.append({**base, "status": "not_computed", "reason": "a component has no evidence and no estimate",
                          "components": [_component_out(c) for c in comps]})
            continue
        rng = random.Random(f"{seed}:fix:{fix['id']}")
        hd = h_draws[b.id]
        saved, adoption, keep = [], [], []
        for i in range(draws):
            a = rng.triangular(adopt["low"], adopt["high"], adopt["base"])
            effects = [min(1.0, rng.gauss(c["mu"], c["sigma"])) for c in comps]
            k = 1.0
            for e in effects:
                k *= 1.0 - e * a
            adoption.append(a)
            keep.append(k)
            saved.append(hd[i] * (1.0 - k))
        keep_by_bottleneck[b.id].append(keep)
        src = _sources(comps)
        fte_div = b.mean_weekly_hours or 40.0
        annual = [s * weeks_per_year for s in saved]
        rate, label, rate_src, reason = loaded_rate(b, ds, cfg)
        out = {**base, "status": "computed", "sufficiency": b.sufficiency["status"],
               "components": [_component_out(c) for c in comps],
               "hours_saved_per_week": triple(saved, src),
               "fte": triple([s / fte_div for s in saved], src + "+data", 3),
               "annual_hours": triple(annual, src + "+assumption:weeks_per_year"),
               "rate_label": label,
               "guardrail": {"after_hours_share": num(b.after_hours_share, "data", 4),
                             "note": "share of the affected group's activity outside core hours or on weekends"}}
        if b.by_role:
            out["by_role"] = [{"role": r["role"], "hours_saved_per_week": {
                k: num(out["hours_saved_per_week"][k]["value"] * r["share_of_lost_hours"]["value"], src, 2)
                for k, _ in QS}} for r in b.by_role]
        else:
            out["by_role_note"] = b.by_role_note
        if rate is None:
            out["dollars"] = {"status": "not computed", "reason": reason}
            out["payback_months"] = {"status": "not computed", "reason": reason}
        else:
            dollars = [h * rate for h in annual]
            cost = float(fix["year_one_cost"])
            payback = [cost / (d / 12.0) if d > 0 else INF for d in dollars]
            dsrc = src + "+assumption:weeks_per_year+" + rate_src
            out["dollars"] = triple(dollars, dsrc, 0)
            out["dollars"]["label"] = label
            out["payback_months"] = {name: _months(q_inf(payback, q), dsrc + f"+assumption:fixes.{fix['id']}")
                                     for name, q in QS}
            out["payback_months"]["never_share"] = num(sum(p == INF for p in payback) / draws, dsrc, 4)
            out["payback_months"]["pairing"] = "P10 savings pair with P90 payback"
        out["sensitivity"] = _sensitivity(hd, comps, adoption, weeks_per_year, rate)
        fixes.append(out)
    combined = []
    for bid, keeps in keep_by_bottleneck.items():
        if len(keeps) < 2:
            continue
        hd = h_draws[bid]
        tot = [hd[i] * (1.0 - math.prod(k[i] for k in keeps)) for i in range(draws)]
        combined.append({"bottleneck": bid, "fixes": [f["id"] for f in fixes if f["bottleneck"] == bid and f["status"] == "computed"],
                         "hours_saved_per_week": triple(tot, "data+assumption:adoption"),
                         "note": "fixes on one bottleneck combine multiplicatively, never added"})
    hours_ranges = {bid: {name: num(quantile(h_draws[bid], q), "data", 2) for name, q in QS} for bid in h_draws}
    return {"fixes": fixes, "combined": combined, "hours_lost_ranges": hours_ranges, "draws": draws, "seed": seed}


def _months(value: float, source: str) -> Dict[str, Any]:
    if value == INF:
        return {"value": None, "source": source, "note": "never pays back"}
    return num(value, source, 1)


def _component_out(c: Dict[str, Any]) -> Dict[str, Any]:
    if c["mu"] is None:
        return {"component": c["component"], "kind": c["kind"], "flags": c["flags"]}
    tags = "+".join(("assumption:" if s["id"].startswith("report_estimate.") else "evidence:") + s["id"]
                    for s in c["studies"])
    model = tags + "+assumption:transfer_sd_at_zero_alignment+assumption:drift_per_year+assumption:tau_min"
    studies = []
    for s in c["studies"]:
        sid = ("assumption:" if s["id"].startswith("report_estimate.") else "evidence:") + s["id"]
        studies.append({"id": s["id"], "source_text": s["source"], "url": s["url"], "design": s["design"],
                        "scores": s["scores"], "alignment": num(s["alignment"], sid + "+data", 3),
                        "age_years": num(s["age"], sid, 0), "y": num(s["y"], sid + "+assumption:design_discount", 4),
                        "se": num(s["se"], sid, 4),
                        "t": num(s["t"], sid + "+assumption:transfer_sd_at_zero_alignment+assumption:drift_per_year", 4),
                        "weight_share": num(s["weight_share"], model, 4), "flags": s["flags"], "caution": s["caution"]})
    out = {"component": c["component"], "kind": c["kind"], "studies": studies,
           "mu": num(c["mu"], model, 4), "sigma": num(c["sigma"], model, 4),
           "effect": {k: num(v, model, 4) for k, v in c["effect"].items()}, "flags": c["flags"]}
    if c.get("report_estimate") is not None:
        out["report_estimate"] = num(c["report_estimate"], f"assumption:report_estimate.{c['component']}", 3)
        out["report_estimate_position"] = c["report_estimate_position"]
    return out


def _sensitivity(hd: List[float], comps: List[Dict[str, Any]], adoption: List[float],
                 weeks: float, rate: Optional[float]) -> Dict[str, Any]:
    """One at a time: each input at its P10 then P90, others at their medians."""
    med_h, med_a = quantile(hd, 0.5), quantile(adoption, 0.5)
    med_e = [c["effect"]["p50"] for c in comps]

    def value(h: float, es: List[float], a: float, w: float, r: Optional[float]) -> float:
        return _saving(h, es, a) * w * (r if r is not None else 1.0)

    rows = [("hours_lost (H_b)", value(quantile(hd, 0.1), med_e, med_a, weeks, rate),
             value(quantile(hd, 0.9), med_e, med_a, weeks, rate), "")]
    for i, c in enumerate(comps):
        lo, hi = list(med_e), list(med_e)
        lo[i], hi[i] = c["effect"]["p10"], c["effect"]["p90"]
        rows.append((f"effect: {c['component']}", value(med_h, lo, med_a, weeks, rate),
                     value(med_h, hi, med_a, weeks, rate), ""))
    rows.append(("adoption", value(med_h, med_e, quantile(adoption, 0.1), weeks, rate),
                 value(med_h, med_e, quantile(adoption, 0.9), weeks, rate), ""))
    mid = value(med_h, med_e, med_a, weeks, rate)
    rows.append(("wage", mid, mid, "fixed input: no range in config" if rate is not None else "dollars not computed"))
    rows.append(("weeks_per_year", mid, mid, "fixed input: no range in config"))
    metric = "annual dollars" if rate is not None else "annual hours"
    src = "data+assumption:adoption+" + "+".join(f"evidence:{s['id']}" if not s["id"].startswith("report_estimate.")
                                                 else f"assumption:{s['id']}" for c in comps for s in c["studies"])
    nd = 0 if rate is not None else 1
    inputs = [{"input": name, "at_p10": num(lo, src, nd), "at_p90": num(hi, src, nd),
               "swing": num(abs(hi - lo), src, nd), "note": note} for name, lo, hi, note in rows]
    top = max(inputs, key=lambda r: r["swing"]["value"])
    return {"metric": metric, "at_medians": num(mid, src, nd), "inputs": inputs, "top_driver": top["input"]}
