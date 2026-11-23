"""Price one fix, or a mix of fixes, against one bottleneck.

Formulas (same as the reference reports):
  hours saved per week = effect share x hours lost per week   (rounded to whole hours)
  annual time savings  = hours saved x working weeks x loaded rate x adoption
  annual deal margin   = deals lost x recovery share x adoption x avg deal value x margin  (scenario B)
  year-one cost        = upfront cost + first year of ongoing cost
  payback (months)     = year-one cost / (annual savings / 12)
Fixes in a mix never simply add up: the smaller one is discounted by how much
the two overlap (catalog pair_overlaps), so nothing is double counted.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .catalog import resolve_qty, share_range
from .numbers import (D, SCENARIOS, fmt_money, fmt_num, fmt_pct, payback_months,
                      round_half_up, round_to_step, to_int)


def _fmt_unit_money(x: Decimal) -> str:
    """$48 or $37.50 (keeps cents when there are any)."""
    if x == x.to_integral_value():
        return f"${int(x):,}"
    return f"${x:,.2f}"


def _fmt_dec(x: Decimal, places: int = 2) -> str:
    """Up to `places` decimals, trailing zeros dropped: 0.465, 59.99, 60."""
    text = f"{round_half_up(x, places):,.{places}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


class PricingContext:
    """Everything pricing needs to know about one bottleneck and the client."""

    def __init__(self, norm: Dict[str, Any], bottleneck: Dict[str, Any], options: Any):
        a = norm["assumptions"]
        self.currency = a["currency"]
        self.rate = {s: D(a["loaded_hourly_rate"][s]) for s in SCENARIOS}
        self.weeks = D(a["working_weeks_per_year"])
        self.adoption = {s: D(a["adoption_rate"][s]) for s in SCENARIOS}
        self.contingency = {s: D(options.cost_contingency.get(s, 0)) for s in SCENARIOS}
        self.cap = D(options.max_recoverable_share)
        self.hours_step = D(options.hours_rounding)
        self.bottleneck = bottleneck
        self.hours_lost = {s: D(bottleneck["hours_lost_per_week"][s]) for s in SCENARIOS}
        self.deal = bottleneck.get("deal_impact") if options.count_deal_margin else None
        company = norm["company"]
        variables: Dict[str, Any] = {}
        variables.update({k: v for k, v in company["capabilities"].items()})
        variables.update(company["volumes"])
        variables.update({
            "employees_total": company["employees_total"],
            "billable_employees": company["billable_employees"],
            "employees_affected": bottleneck["employees_affected"],
            "hours_lost_per_week": bottleneck["hours_lost_per_week"]["base"],
            "short_name": company["short_name"],
            "client_name": company["name"],
        })
        self.variables = variables

    def money(self, x: Any) -> str:
        return fmt_money(x, self.currency)


# ------------------------------------------------------------------ costs
def price_cost_item(item: Dict[str, Any], ctx: PricingContext) -> Dict[str, Any]:
    basis = item["basis"]
    qty, qty_label, missing = resolve_qty(item.get("qty"), ctx.variables)
    rate = ctx.rate["base"]
    if basis == "flat":
        amount = D(item["amount"])
        calc = ctx.money(amount)
    elif basis == "per_unit":
        unit = D(item["unit_cost"])
        amount = qty * unit
        calc = f"{fmt_num(qty)} {qty_label or 'units'} x {_fmt_unit_money(unit)}"
    elif basis == "per_seat_month":
        unit = D(item["unit_cost"])
        amount = qty * unit * 12
        calc = f"{fmt_num(qty)} seats x {_fmt_unit_money(unit)} a month x 12"
    elif basis == "internal_hours":
        hours = D(item["hours"])
        if item.get("qty") is not None:
            amount = qty * hours * rate
            calc = f"{fmt_num(qty)} {qty_label or 'people'} x {fmt_num(hours)} h x {_fmt_unit_money(rate)}"
        else:
            amount = hours * rate
            calc = f"{fmt_num(hours)} h x {_fmt_unit_money(rate)}"
    else:  # validated in the catalog, kept for safety
        raise ValueError(f"unknown cost basis {basis!r}")
    amount_int = to_int(amount)
    if basis != "flat":
        calc = f"{calc} = {ctx.money(amount_int)}"
    return {
        "item": item.get("item", ""),
        "amount": amount_int,
        "calc": calc,
        "price_status": item.get("price_status", "estimate"),
        "missing_inputs": missing,
    }


# ------------------------------------------------------------- one fix
def price_fix(fix: Dict[str, Any], ctx: PricingContext, shared_from: Optional[str] = None) -> Dict[str, Any]:
    """Price a single fix in all three cases (low, base, high)."""
    costs = fix.get("costs") or {}
    upfront_items = [price_cost_item(i, ctx) for i in costs.get("upfront", [])]
    ongoing_items = [price_cost_item(i, ctx) for i in costs.get("ongoing", [])]
    missing = sorted({m for i in upfront_items + ongoing_items for m in i["missing_inputs"]})
    for i in upfront_items + ongoing_items:
        del i["missing_inputs"]
    upfront_base = sum(i["amount"] for i in upfront_items)
    ongoing_base = sum(i["amount"] for i in ongoing_items)
    if shared_from:
        upfront_base = ongoing_base = 0

    upfront = {s: to_int(D(upfront_base) * (1 + ctx.contingency[s])) for s in SCENARIOS}
    ongoing = {s: to_int(D(ongoing_base) * (1 + ctx.contingency[s])) for s in SCENARIOS}
    year_one = {s: upfront[s] + ongoing[s] for s in SCENARIOS}

    effect = fix.get("effect") or {}
    zero = {s: Decimal(0) for s in SCENARIOS}
    hshare = share_range(effect["hours_share"], ctx.cap) if "hours_share" in effect else dict(zero)
    raw_hours = {s: hshare[s] * ctx.hours_lost[s] for s in SCENARIOS}
    hours = {s: round_to_step(raw_hours[s], ctx.hours_step) for s in SCENARIOS}
    time_sav = {s: to_int(hours[s] * ctx.weeks * ctx.rate[s] * ctx.adoption[s]) for s in SCENARIOS}

    dshare = dict(zero)
    deals = None
    deal_margin = {s: 0 for s in SCENARIOS}
    if ctx.deal and "deal_recovery_share" in effect:
        dshare = share_range(effect["deal_recovery_share"], ctx.cap)
        deals, deal_margin = _deal_value(dshare, ctx)

    savings = {s: time_sav[s] + deal_margin[s] for s in SCENARIOS}
    payback = {s: payback_months(year_one[s], savings[s]) for s in SCENARIOS}
    net = {s: savings[s] - year_one[s] for s in SCENARIOS}

    adoption_txt = fmt_pct(ctx.adoption["base"])
    trace = {
        "hours_saved_per_week": (
            f"{_fmt_dec(hshare['base'], 3)} share x {fmt_num(ctx.hours_lost['base'])} h lost = "
            f"{_fmt_dec(raw_hours['base'])} -> {fmt_num(hours['base'])} h a week"
        ),
        "annual_time_savings": (
            f"{fmt_num(hours['base'])} h x {fmt_num(ctx.weeks)} weeks x {_fmt_unit_money(ctx.rate['base'])} "
            f"x {adoption_txt} adoption = {ctx.money(time_sav['base'])}"
        ),
        "year_one_cost": (
            f"{ctx.money(upfront['base'])} upfront + {ctx.money(ongoing['base'])} first-year ongoing = "
            f"{ctx.money(year_one['base'])}"
        ),
        "payback_months": _payback_trace(year_one["base"], savings["base"], payback["base"], ctx),
    }
    if deals is not None:
        trace["annual_deal_margin"] = (
            f"{fmt_num(ctx.deal['deals_lost_per_year']['base'])} deals lost x {_fmt_dec(dshare['base'], 3)} "
            f"recovered x {adoption_txt} adoption x {ctx.money(ctx.deal['avg_deal_value'])} x "
            f"{fmt_pct(ctx.deal['contribution_margin'])} margin = {ctx.money(deal_margin['base'])}"
        )
    if shared_from:
        trace["year_one_cost"] = f"Cost already counted under {shared_from}; no extra cost here"

    return {
        "upfront_cost": upfront,
        "upfront_breakdown": upfront_items,
        "ongoing_cost_per_year": ongoing,
        "ongoing_breakdown": ongoing_items,
        "year_one_cost": year_one,
        "hours_saved_per_week": {s: int(hours[s]) if hours[s] == hours[s].to_integral_value() else float(hours[s]) for s in SCENARIOS},
        "deals_recovered_per_year": None if deals is None else {s: float(round_half_up(deals[s], 1)) for s in SCENARIOS},
        "annual_time_savings": time_sav,
        "annual_deal_margin": deal_margin,
        "annual_savings": savings,
        "payback_months": payback,
        "net_benefit_year_one": net,
        "missing_inputs": missing,
        "cost_shared_with": shared_from,
        "trace": trace,
        "_hours": hours,
        "_dshare": dshare,
    }


def _deal_value(dshare: Dict[str, Decimal], ctx: PricingContext) -> Tuple[Dict[str, Decimal], Dict[str, int]]:
    lost = ctx.deal["deals_lost_per_year"]
    avg = D(ctx.deal["avg_deal_value"])
    margin = D(ctx.deal["contribution_margin"])
    deals = {s: D(lost[s]) * dshare[s] * ctx.adoption[s] for s in SCENARIOS}
    value = {s: to_int(deals[s] * avg * margin) for s in SCENARIOS}
    return deals, value


def _payback_trace(cost: int, savings: int, months: Optional[float], ctx: PricingContext) -> str:
    if months == 0:
        return "No year-one cost: pays back immediately"
    if months is None:
        return "Savings do not cover the cost"
    return f"{ctx.money(cost)} / ({ctx.money(savings)} / 12) = {months:.1f} months"


# -------------------------------------------------------------- a mix
def combine(values: Sequence[Tuple[str, Decimal]], overlap: Callable[[str, str], Decimal]) -> Tuple[Decimal, str]:
    """Largest first; each next fix is discounted by its biggest overlap with those before it.

    For two fixes this is a + b - overlap x min(a, b).
    """
    ordered = sorted(values, key=lambda kv: kv[1], reverse=True)
    if not ordered:
        return Decimal(0), "0"
    total = ordered[0][1]
    parts = [_fmt_dec(ordered[0][1])]
    for i, (fid, v) in enumerate(ordered[1:], start=1):
        ov = max(overlap(fid, prev) for prev, _ in ordered[:i])
        total += v * (1 - ov)
        parts.append(f"{_fmt_dec(v)} x (1 - {_fmt_dec(ov, 3)} overlap)")
    return total, " + ".join(parts)


def price_mix(members: List[Dict[str, Any]], ctx: PricingContext,
              overlap: Callable[[str, str], Decimal]) -> Dict[str, Any]:
    """Price several fixes chosen together for one bottleneck."""
    cap_hours = {s: ctx.cap * ctx.hours_lost[s] for s in SCENARIOS}
    hours, hours_expr, raw_hours = {}, "", {}
    capped = False
    for s in SCENARIOS:
        total, expr = combine([(m["fix_id"], m["_hours"][s]) for m in members], overlap)
        raw_hours[s] = min(total, cap_hours[s])
        hours[s] = round_to_step(raw_hours[s], ctx.hours_step)
        if s == "base":
            hours_expr = expr
            capped = total > cap_hours[s]
    time_sav = {s: to_int(hours[s] * ctx.weeks * ctx.rate[s] * ctx.adoption[s]) for s in SCENARIOS}

    deals = None
    deal_margin = {s: 0 for s in SCENARIOS}
    if ctx.deal and any(m["_dshare"]["base"] > 0 for m in members):
        dshare = {}
        for s in SCENARIOS:
            total, _ = combine([(m["fix_id"], m["_dshare"][s]) for m in members], overlap)
            dshare[s] = min(total, ctx.cap)
        deals, deal_margin = _deal_value(dshare, ctx)

    upfront = {s: sum(m["upfront_cost"][s] for m in members) for s in SCENARIOS}
    ongoing = {s: sum(m["ongoing_cost_per_year"][s] for m in members) for s in SCENARIOS}
    year_one = {s: upfront[s] + ongoing[s] for s in SCENARIOS}
    savings = {s: time_sav[s] + deal_margin[s] for s in SCENARIOS}
    payback = {s: payback_months(year_one[s], savings[s]) for s in SCENARIOS}
    net = {s: savings[s] - year_one[s] for s in SCENARIOS}

    trace = {
        "hours_saved_per_week": (
            f"{hours_expr} = {_fmt_dec(raw_hours['base'])} -> {fmt_num(hours['base'])} h a week"
            + (f" (capped at {fmt_pct(ctx.cap)} of hours lost)" if capped else "")
        ),
        "annual_time_savings": (
            f"{fmt_num(hours['base'])} h x {fmt_num(ctx.weeks)} weeks x {_fmt_unit_money(ctx.rate['base'])} "
            f"x {fmt_pct(ctx.adoption['base'])} adoption = {ctx.money(time_sav['base'])}"
        ),
        "year_one_cost": " + ".join(f"{m['name']} {ctx.money(m['year_one_cost']['base'])}" for m in members)
        + f" = {ctx.money(year_one['base'])}",
        "payback_months": _payback_trace(year_one["base"], savings["base"], payback["base"], ctx),
    }
    if deals is not None:
        trace["annual_deal_margin"] = (
            f"{fmt_num(ctx.deal['deals_lost_per_year']['base'])} deals lost x combined recovery share x "
            f"{fmt_pct(ctx.adoption['base'])} adoption = {fmt_num(round_half_up(deals['base'], 1))} deals x "
            f"{ctx.money(ctx.deal['avg_deal_value'])} x {fmt_pct(ctx.deal['contribution_margin'])} margin = "
            f"{ctx.money(deal_margin['base'])}"
        )
    return {
        "hours_saved_per_week": {s: int(hours[s]) if hours[s] == hours[s].to_integral_value() else float(hours[s]) for s in SCENARIOS},
        "deals_recovered_per_year": None if deals is None else {s: float(round_half_up(deals[s], 1)) for s in SCENARIOS},
        "upfront_cost": upfront,
        "ongoing_cost_per_year": ongoing,
        "year_one_cost": year_one,
        "annual_time_savings": time_sav,
        "annual_deal_margin": deal_margin,
        "annual_savings": savings,
        "payback_months": payback,
        "net_benefit_year_one": net,
        "trace": trace,
    }
