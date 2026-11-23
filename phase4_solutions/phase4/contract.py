"""Read and check the Phase 4 input (what steps 7 and 8 hand over).

normalize_input() turns the raw JSON into one predictable shape: every range
becomes {"low", "base", "high"}, defaults are filled in, and anything that
would break pricing is reported as a clear error instead of a stack trace.
See contracts/phase4_input.schema.json for the documented format.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .numbers import D, SCENARIOS

INPUT_SCHEMA_PREFIX = "phase4-input/1."


class Phase4InputError(ValueError):
    """The input cannot be priced. .errors lists every problem found."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("Phase 4 input is not valid:\n- " + "\n- ".join(errors))


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def parse_range(value: Any, field: str, errors: List[str], *, share: bool = False,
                default: Any = None) -> Optional[Dict[str, float]]:
    """Accept a number or {low, base, high}; return all three cases."""
    if value is None:
        value = default
    if value is None:
        errors.append(f"{field} is required")
        return None
    if _is_number(value):
        out = {s: float(value) for s in SCENARIOS}
    elif isinstance(value, dict) and _is_number(value.get("base")):
        base = float(value["base"])
        out = {"base": base}
        for s in ("low", "high"):
            v = value.get(s, base)
            if not _is_number(v):
                errors.append(f"{field}.{s} must be a number")
                return None
            out[s] = float(v)
    else:
        errors.append(f"{field} must be a number or an object with low/base/high")
        return None
    for s, v in out.items():
        if v < 0:
            errors.append(f"{field}.{s} cannot be negative")
        if share and v > 1:
            errors.append(f"{field}.{s} is a share and must be between 0 and 1")
    if not (out["low"] <= out["base"] <= out["high"]):
        errors.append(f"{field} must satisfy low <= base <= high (got {out})")
    return {s: out[s] for s in SCENARIOS}


def normalize_input(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and normalize. Returns (normalized_input, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(raw, dict):
        raise Phase4InputError(["input must be a JSON object"])

    version = raw.get("schema_version")
    if not isinstance(version, str) or not version.startswith(INPUT_SCHEMA_PREFIX):
        errors.append(f"schema_version must start with '{INPUT_SCHEMA_PREFIX}' (got {version!r})")

    run = raw.get("run") or {}
    scenario = run.get("scenario")
    if scenario not in ("A", "B"):
        errors.append("run.scenario must be 'A' (workplace data) or 'B' (acquisition)")
    if not run.get("client_name"):
        errors.append("run.client_name is required")

    company_raw = raw.get("company") or {}
    employees_total = company_raw.get("employees_total")
    if not isinstance(employees_total, int) or isinstance(employees_total, bool) or employees_total < 1:
        errors.append("company.employees_total must be a whole number of 1 or more")
        employees_total = None
    billable = company_raw.get("billable_employees", employees_total)
    capabilities = company_raw.get("capabilities") or {}
    volumes = company_raw.get("volumes") or {}
    if not isinstance(capabilities, dict):
        errors.append("company.capabilities must be an object")
        capabilities = {}
    if not isinstance(volumes, dict) or not all(_is_number(v) for v in volumes.values()):
        errors.append("company.volumes must be an object of numbers")
        volumes = {}
    client_name = run.get("client_name") or ""
    company = {
        "name": client_name,
        "short_name": company_raw.get("short_name") or (client_name.split()[0] if client_name else ""),
        "employees_total": employees_total,
        "billable_employees": billable,
        "current_tools": list(company_raw.get("current_tools") or []),
        "capabilities": dict(capabilities),
        "volumes": {k: float(v) for k, v in volumes.items()},
    }

    a_raw = raw.get("assumptions") or {}
    assumptions = {
        "currency": a_raw.get("currency", "USD"),
        "loaded_hourly_rate": parse_range(a_raw.get("loaded_hourly_rate"),
                                          "assumptions.loaded_hourly_rate", errors),
        "working_weeks_per_year": a_raw.get("working_weeks_per_year", 48),
        "max_payback_months": a_raw.get("max_payback_months", 12),
        "realized_billing_rate": a_raw.get("realized_billing_rate"),
        "sources": dict(a_raw.get("sources") or {}),
    }
    adoption = a_raw.get("adoption_rate", 0.7)
    if _is_number(adoption):
        # One number given: widen it into a range so low/high cases mean something.
        base = float(adoption)
        adoption = {"low": max(0.0, round(base - 0.2, 4)), "base": base,
                    "high": min(0.95, round(base + 0.15, 4))}
        if adoption["high"] < base:
            adoption["high"] = base
    assumptions["adoption_rate"] = parse_range(adoption, "assumptions.adoption_rate", errors, share=True)
    weeks = assumptions["working_weeks_per_year"]
    if not _is_number(weeks) or not (1 <= weeks <= 52):
        errors.append("assumptions.working_weeks_per_year must be between 1 and 52")
    if not _is_number(assumptions["max_payback_months"]) or assumptions["max_payback_months"] < 0:
        errors.append("assumptions.max_payback_months must be a number of 0 or more")

    bottlenecks_raw = raw.get("bottlenecks")
    bottlenecks: List[Dict[str, Any]] = []
    if not isinstance(bottlenecks_raw, list) or not bottlenecks_raw:
        errors.append("bottlenecks must be a non-empty list")
        bottlenecks_raw = []
    seen_ids = set()
    for i, b in enumerate(bottlenecks_raw):
        where = f"bottlenecks[{i}]"
        if not isinstance(b, dict):
            errors.append(f"{where} must be an object")
            continue
        bid = b.get("id")
        if not bid or not isinstance(bid, str):
            errors.append(f"{where}.id is required")
            bid = f"#{i + 1}"
        elif bid in seen_ids:
            errors.append(f"{where}.id '{bid}' is used twice")
        seen_ids.add(bid)
        where = f"bottleneck {bid}"
        if not b.get("name"):
            errors.append(f"{where}: name is required")
        affected = b.get("employees_affected")
        if not isinstance(affected, int) or isinstance(affected, bool) or affected < 0:
            errors.append(f"{where}: employees_affected must be a whole number")
            affected = 0
        hours = parse_range(b.get("hours_lost_per_week"), f"{where}: hours_lost_per_week", errors)
        annual_cost = None
        if b.get("annual_cost") is not None:
            annual_cost = parse_range(b.get("annual_cost"), f"{where}: annual_cost", errors)
        deal_impact = None
        if b.get("deal_impact") is not None:
            di = b["deal_impact"]
            deals = parse_range(di.get("deals_lost_per_year"), f"{where}: deal_impact.deals_lost_per_year", errors)
            avg = di.get("avg_deal_value")
            margin = di.get("contribution_margin")
            if not _is_number(avg) or avg < 0:
                errors.append(f"{where}: deal_impact.avg_deal_value must be a number")
            if not _is_number(margin) or not (0 <= margin <= 1):
                errors.append(f"{where}: deal_impact.contribution_margin must be between 0 and 1")
            deal_impact = {"deals_lost_per_year": deals, "avg_deal_value": avg,
                           "contribution_margin": margin, "source": di.get("source", "")}
        feasibility = b.get("feasibility")
        if feasibility is not None and feasibility not in ("low", "medium", "high"):
            errors.append(f"{where}: feasibility must be low, medium or high")
        rank = b.get("rank", i + 1)
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            errors.append(f"{where}: rank must be a whole number of 1 or more")
            rank = i + 1
        bottlenecks.append({
            "id": bid,
            "rank": rank,
            "name": b.get("name", ""),
            "category": b.get("category"),
            "description": b.get("description", ""),
            "departments": list(b.get("departments") or []),
            "employees_affected": affected,
            "hours_lost_per_week": hours,
            "annual_cost": annual_cost,
            "feasibility": feasibility,
            "priority_score": b.get("priority_score"),
            "root_causes": list(b.get("root_causes") or []),
            "evidence": list(b.get("evidence") or []),
            "deal_impact": deal_impact,
            "upside_not_counted": list(b.get("upside_not_counted") or []),
        })

    if errors:
        raise Phase4InputError(errors)

    # Cross-checks that are worth a warning but should not stop the run.
    rate = assumptions["loaded_hourly_rate"]["base"]
    for b in bottlenecks:
        if b["annual_cost"] is not None and b["deal_impact"] is None:
            expected = D(b["hours_lost_per_week"]["base"]) * D(weeks) * D(rate)
            given = D(b["annual_cost"]["base"])
            if expected > 0 and abs(given - expected) / expected > D("0.01"):
                warnings.append(
                    f"{b['id']}: annual_cost {given:,.0f} differs by more than 1% from "
                    f"hours x weeks x rate = {expected:,.0f}; Phase 4 prices from the hours."
                )
    if isinstance(billable, int) and employees_total is not None and billable > employees_total:
        warnings.append("company.billable_employees is larger than employees_total")

    normalized = {
        "schema_version": version,
        "run": dict(run),
        "scenario": scenario,
        "company": company,
        "assumptions": assumptions,
        "bottlenecks": bottlenecks,
        "upside_not_counted": list(raw.get("upside_not_counted") or []),
        "skill_signals": list(raw.get("skill_signals") or []),
    }
    return normalized, warnings
