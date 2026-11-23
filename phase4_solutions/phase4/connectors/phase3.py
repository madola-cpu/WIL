"""Phase 3 -> Phase 4: build a Phase 4 input from whatever steps 7 and 8 already produce.

Steps 7 and 8 do not have to change. This adapter:
  * finds the list of bottlenecks (and a separate ROI list, if step 8 keeps one),
  * recognises common field names in any style (hoursLostPerWeek, hours_per_week, "Hours lost"...),
  * reads ranges written as {low, base, high}, {min, expected, max}, [low, base, high] or hours_low/hours_high,
  * fills the client facts Phase 4 needs (headcount, rate, capabilities...) from a client profile,
  * and returns a mapping report that says where every value came from.

    phase4_input, report = from_phase3(step7_8_output, profile="veloran")

Anything it cannot work out is an error that names the field, never a guess.
Only counts and totals are copied; lists of people are ignored.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ..catalog import Catalog
from ..contract import INPUT_SCHEMA_PREFIX, Phase4InputError, normalize_input
from ..resources import load_profile

SCHEMA_VERSION = INPUT_SCHEMA_PREFIX + "0"


class Phase3MappingError(Phase4InputError):
    """The Phase 3 output could not be turned into a valid Phase 4 input.

    .errors lists the problems; .report is the mapping report built so far.
    """

    def __init__(self, errors: List[str], report: Dict[str, Any]):
        super().__init__(errors)
        self.report = report


# ------------------------------------------------------------------ names
def _n(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


BOTTLENECK_FIELDS: Dict[str, List[str]] = {
    "id": ["id", "bottleneck_id", "key", "slug", "code", "ref"],
    "name": ["name", "title", "bottleneck", "bottleneck_name", "label", "issue", "problem"],
    "rank": ["rank", "priority_rank", "rank_order", "cost_rank", "order", "position"],
    "category": ["category", "category_id", "fix_category", "bottleneck_type", "bottleneck_category"],
    "description": ["description", "summary", "details", "what_happens", "explanation"],
    "departments": ["departments", "department", "teams", "team", "depts", "groups"],
    "employees_affected": ["employees_affected", "people_affected", "affected_employees", "staff_affected",
                           "headcount_affected", "num_affected", "affected", "headcount", "employees", "people",
                           "num_employees", "n_employees"],
    "hours_lost_per_week": ["hours_lost_per_week", "total_hours_per_week", "total_hours_lost_per_week",
                            "weekly_hours_lost", "hours_lost_weekly", "total_hours_lost", "hours_per_week",
                            "hours_lost", "lost_hours", "weekly_hours", "hours"],
    "hours_per_employee_per_week": ["hours_per_employee_per_week", "hours_per_person_per_week",
                                    "hours_per_person", "hours_per_employee", "per_person_hours"],
    "annual_cost": ["annual_cost", "annual_cost_usd", "cost_per_year", "yearly_cost", "annual_loss", "cost"],
    "feasibility": ["feasibility", "fix_feasibility"],
    "priority_score": ["priority_score", "priority", "score"],
    "root_causes": ["root_causes", "causes"],
    "evidence": ["evidence", "signals"],
    "deals_lost_per_year": ["deals_lost_per_year", "deals_lost", "lost_deals", "deals_at_risk"],
    "avg_deal_value": ["avg_deal_value", "average_deal_value", "deal_value", "avg_deal_size"],
    "contribution_margin": ["contribution_margin", "margin", "gross_margin"],
    "upside_not_counted": ["upside_not_counted", "upside"],
}
COMPANY_FIELDS: Dict[str, List[str]] = {
    "client_name": ["client_name", "client", "company_name", "company", "organization", "org"],
    "employees_total": ["employees_total", "total_employees", "employee_count", "headcount_total",
                        "company_size", "headcount", "employees"],
    "billable_employees": ["billable_employees", "billable_staff", "billable_headcount", "billable"],
}
ASSUMPTION_FIELDS: Dict[str, List[str]] = {
    "loaded_hourly_rate": ["loaded_hourly_rate", "loaded_rate", "hourly_rate", "rate_per_hour", "cost_per_hour", "rate"],
    "working_weeks_per_year": ["working_weeks_per_year", "weeks_per_year", "working_weeks", "weeks"],
    "adoption_rate": ["adoption_rate", "adoption"],
    "currency": ["currency"],
    "max_payback_months": ["max_payback_months", "payback_limit_months"],
    "realized_billing_rate": ["realized_billing_rate", "realized_rate", "billing_rate"],
}
LIST_KEYS = ["bottlenecks", "step7", "step_7", "bottleneck_list", "findings", "items", "results", "data", "output"]
ROI_KEYS = ["roi", "step8", "step_8", "roi_results", "bottleneck_costs", "costs", "pricing"]
ASSUMPTION_KEYS = ["assumptions", "inputs", "parameters", "params", "settings", "config"]
COMPANY_KEYS = ["company", "client", "organization", "org"]
RANGE_KEYS = {
    "low": ["low", "min", "minimum", "lower", "p10", "conservative", "worst"],
    "base": ["base", "expected", "mid", "median", "p50", "value", "point", "estimate", "best_estimate", "likely"],
    "high": ["high", "max", "maximum", "upper", "p90", "optimistic", "best"],
}
RANGED = {"hours_lost_per_week", "hours_per_employee_per_week", "annual_cost", "deals_lost_per_year"}
NUMERIC = RANGED | {"employees_affected", "priority_score", "rank", "avg_deal_value", "contribution_margin"}
STEP8_FIRST = RANGED | {"avg_deal_value", "contribution_margin"}   # step 8 owns the priced numbers


def _find(item: Any, target: str, table: Dict[str, List[str]],
          explicit: Optional[Dict[str, str]] = None) -> Tuple[Any, Optional[str]]:
    """Value and source key for a target field, by explicit path or by synonym."""
    if not isinstance(item, dict):
        return None, None
    if explicit and target in explicit:
        value = _dig(item, explicit[target])
        return (value, explicit[target]) if value not in (None, "") else (None, None)
    names = {_n(k): k for k in item}
    for syn in table[target]:
        key = names.get(_n(syn))
        if key is not None and item[key] not in (None, ""):
            return item[key], key
    return None, None


def _dig(obj: Any, path: str) -> Any:
    for part in [p for p in re.split(r"[.\[\]]", path) if p != ""]:
        if isinstance(obj, dict):
            names = {_n(k): k for k in obj}
            obj = obj[part] if part in obj else obj.get(names.get(_n(part), "\0"))
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return None
    return obj


# ------------------------------------------------------------------ values
_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = _NUM.search(value)
        if m:
            number = float(m.group(0).replace(",", ""))
            return number / 100 if value.strip().endswith("%") else number
    return None


def _clean(x: float) -> Union[int, float]:
    return int(x) if float(x).is_integer() else round(float(x), 6)


def _as_range(value: Any, notes: List[str], label: str) -> Any:
    """A number, or {low, base, high} built from the many ways ranges get written."""
    if isinstance(value, (list, tuple)):
        nums = [_num(v) for v in value]
        if len(nums) == 3 and all(n is not None for n in nums):
            return {"low": _clean(nums[0]), "base": _clean(nums[1]), "high": _clean(nums[2])}
        return None
    if isinstance(value, dict):
        names = {_n(k): k for k in value}
        found: Dict[str, float] = {}
        for case, syns in RANGE_KEYS.items():
            for syn in syns:
                key = names.get(_n(syn))
                if key is not None and _num(value[key]) is not None:
                    found[case] = _num(value[key])  # type: ignore[assignment]
                    break
        if "base" not in found:
            if "low" in found and "high" in found:
                found["base"] = (found["low"] + found["high"]) / 2
                notes.append(f"{label}: no base case given, used the midpoint of low and high")
            elif len(found) == 1:
                found["base"] = next(iter(found.values()))
            else:
                return None
        base = found["base"]
        return {"low": _clean(found.get("low", base)), "base": _clean(base), "high": _clean(found.get("high", base))}
    number = _num(value)
    return None if number is None else _clean(number)


LOW_SUFFIX = {"low", "min", "lower", "p10"}
HIGH_SUFFIX = {"high", "max", "upper", "p90"}


def _flat_range(item: Dict[str, Any], key: str, base: Any) -> Tuple[Any, List[str]]:
    """hours_lost_low / hours_lost_high next to hours_lost become one range. Returns (value, keys used)."""
    if base is None or isinstance(base, dict):
        return base, []
    root, low, high, used = _n(key), None, None, []
    for k, v in item.items():
        nk = _n(k)
        if any(nk in (root + s, s + root) for s in LOW_SUFFIX) and _num(v) is not None:
            low = _num(v)
            used.append(k)
        if any(nk in (root + s, s + root) for s in HIGH_SUFFIX) and _num(v) is not None:
            high = _num(v)
            used.append(k)
    if low is None and high is None:
        return base, []
    return {"low": _clean(low if low is not None else base), "base": base,
            "high": _clean(high if high is not None else base)}, used


def _feasibility(value: Any, notes: List[str], label: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or _NUM.fullmatch(value.strip()):
        number = _num(value)
        if number is not None:
            return "high" if number >= 0.8 else "medium" if number >= 0.45 else "low"
    text = str(value).strip().lower()
    for level in ("high", "medium", "low"):
        if text[:1] == level[0]:
            return level
    notes.append(f"{label}: feasibility {value!r} not understood, left out")
    return None


def _str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in re.split(r"[;|]", value) if p.strip()] if (";" in value or "|" in value) \
            else [p.strip() for p in value.split(",") if p.strip()]
    out = []
    for v in value if isinstance(value, list) else [value]:
        if isinstance(v, dict):
            v = v.get("text") or v.get("name") or v.get("title") or v.get("cause") or ""
        if str(v).strip():
            out.append(str(v).strip())
    return out


def _evidence(value: Any) -> List[Dict[str, str]]:
    out = []
    for v in value if isinstance(value, list) else ([value] if value else []):
        if isinstance(v, dict):
            table = {"signal": ["signal", "metric", "name", "finding", "what"],
                     "source": ["source", "system", "where", "tool"],
                     "value": ["value", "observed", "result", "amount"]}
            row = {k: _find(v, k, table)[0] for k in table}
            out.append({k: str(x) for k, x in row.items() if x is not None})
        elif v:
            out.append({"signal": str(v)})
    return out


# ------------------------------------------------------------------ locating lists
def _looks_like(items: Any, need_name: bool) -> bool:
    if not isinstance(items, list) or not items:
        return False
    dicts = [x for x in items if isinstance(x, dict)]
    if len(dicts) < 0.8 * len(items):
        return False
    good = 0
    for d in dicts:
        named = _find(d, "name", BOTTLENECK_FIELDS)[1] if need_name else \
            (_find(d, "name", BOTTLENECK_FIELDS)[1] or _find(d, "id", BOTTLENECK_FIELDS)[1])
        numbers = any(_find(d, f, BOTTLENECK_FIELDS)[1] for f in
                      ("hours_lost_per_week", "employees_affected", "hours_per_employee_per_week", "annual_cost"))
        good += bool(named and numbers)
    return good >= max(1, len(dicts) // 2)


def _dict_to_list(obj: Any) -> Optional[List[Dict[str, Any]]]:
    """{"staffing": {...}, "status": {...}} -> [{"id": "staffing", ...}, ...]."""
    if isinstance(obj, dict) and obj and all(isinstance(v, dict) for v in obj.values()):
        return [dict(v, **({} if _find(v, "id", BOTTLENECK_FIELDS)[1] else {"id": k})) for k, v in obj.items()]
    return None


def _locate(obj: Any, keys: List[str], need_name: bool, depth: int = 0) -> Tuple[Optional[List[Any]], Optional[str]]:
    if isinstance(obj, list):
        return (obj, "(top level)") if _looks_like(obj, need_name) else (None, None)
    if not isinstance(obj, dict) or depth > 3:
        return None, None
    names = {_n(k): k for k in obj}
    preferred = [names[_n(k)] for k in keys if _n(k) in names]
    for key in preferred + [k for k in obj if k not in preferred]:
        value = obj[key]
        as_list = value if isinstance(value, list) else _dict_to_list(value)
        if as_list is not None and _looks_like(as_list, need_name):
            return as_list, key
        if isinstance(value, dict):
            found, path = _locate(value, keys, need_name, depth + 1)
            if found is not None:
                return found, f"{key}.{path}"
    return None, None


def _section(obj: Any, keys: List[str]) -> Tuple[Dict[str, Any], Optional[str]]:
    if not isinstance(obj, dict):
        return {}, None
    names = {_n(k): k for k in obj}
    for k in keys:
        real = names.get(_n(k))
        if real is not None and isinstance(obj[real], dict):
            return obj[real], real
    return {}, None


# ------------------------------------------------------------------ main entry
def from_phase3(phase3: Any, profile: Union[str, Dict[str, Any], None] = None,
                mapping: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build a valid Phase 4 input from steps 7-8 output.

    phase3:  whatever steps 7 and 8 produce (dict or list), or the result of read_phase3_file().
    profile: client profile (a name such as "veloran", a path, or a dict) for facts Phase 3 does not have.
    mapping: optional explicit field paths, for names the adapter cannot recognise
             ({"bottlenecks_path": "...", "roi_path": "...", "fields": {...}, "roi_fields": {...}}).
    Returns (phase4_input, mapping_report). Raises Phase3MappingError naming anything required that is missing.
    """
    prof = load_profile(profile) if profile is not None else {}
    mapping = dict(prof.get("field_mapping") or {}, **(mapping or {}))
    item_paths = mapping.get("fields") or {}
    roi_paths = mapping.get("roi_fields") or item_paths
    errors: List[str] = []
    notes: List[str] = []
    report: Dict[str, Any] = {"found": {}, "client": {}, "bottlenecks": [], "notes": notes, "errors": errors}

    # ------------------------------------------------------- find the lists
    if mapping.get("bottlenecks_path"):
        items: Any = _dig(phase3, mapping["bottlenecks_path"])
        items = _dict_to_list(items) if isinstance(items, dict) else items
        where: Optional[str] = mapping["bottlenecks_path"]
    else:
        items, where = _locate(phase3, LIST_KEYS, need_name=True)
    if not isinstance(items, list) or not items:
        errors.append("could not find a list of bottlenecks with names and hours or people; set "
                      "field_mapping.bottlenecks_path in the profile (for example \"step7.bottlenecks\")")
        raise Phase3MappingError(errors, report)
    report["found"]["bottlenecks_at"] = where
    report["found"]["bottleneck_count"] = len(items)

    roi_items: List[Any] = []
    if mapping.get("roi_path"):
        roi_raw = _dig(phase3, mapping["roi_path"])
        roi_items = roi_raw if isinstance(roi_raw, list) else (_dict_to_list(roi_raw) or [])
        report["found"]["roi_at"] = mapping["roi_path"]
    elif isinstance(phase3, dict):
        roi_part = {k: v for k, v in phase3.items() if _n(k) in {_n(x) for x in ROI_KEYS}}
        found, roi_where = _locate(roi_part, ROI_KEYS, need_name=False)
        if found is not None and found is not items:
            roi_items, report["found"]["roi_at"] = found, roi_where

    # ------------------------------------------------------- client facts
    top = phase3 if isinstance(phase3, dict) else {}
    a_section, a_where = _section(top, ASSUMPTION_KEYS)
    c_section, c_where = _section(top, COMPANY_KEYS)
    overrides = prof.get("overrides") or {}
    p_company = dict(prof.get("company") or {})
    p_assumptions = dict(prof.get("assumptions") or {})

    def coerce(field: str, value: Any) -> Any:
        if field == "adoption_rate":
            return _as_range(value, notes, field)
        if field == "currency":
            return value if isinstance(value, str) and value.strip() else None
        if field == "client_name":
            if isinstance(value, dict):
                value = _find(value, "name", BOTTLENECK_FIELDS)[0]
            return str(value).strip() if isinstance(value, (str, int, float)) and str(value).strip() else None
        if isinstance(value, (list, dict, bool)):
            return None
        number = _num(value)
        return None if number is None else _clean(number)

    def pick(field: str, table: Dict[str, List[str]], sources: List[Tuple[str, Dict[str, Any]]],
             profile_value: Any, override: Any) -> Any:
        if override is not None:
            report["client"][field] = "profile override"
            return override
        for label, src in sources:
            raw_value, key = _find(src, field, table)
            value = coerce(field, raw_value) if raw_value is not None else None
            if value is not None:
                report["client"][field] = f"phase 3: {label}{key}"
                return value
        if profile_value is not None:
            report["client"][field] = "profile"
            return profile_value
        return None

    srcs_a = ([(f"{a_where}.", a_section)] if a_section else []) + [("", top)]
    srcs_c = ([(f"{c_where}.", c_section)] if c_section else []) + [("", top)]
    assumptions: Dict[str, Any] = {}
    for field in ASSUMPTION_FIELDS:
        value = pick(field, ASSUMPTION_FIELDS, srcs_a, p_assumptions.get(field),
                     (overrides.get("assumptions") or {}).get(field))
        if value is not None:
            assumptions[field] = value
    if p_assumptions.get("sources"):
        assumptions["sources"] = p_assumptions["sources"]
    company_name = pick("client_name", COMPANY_FIELDS, srcs_c, prof.get("client_name"), overrides.get("client_name"))
    company: Dict[str, Any] = {}
    for field in ("employees_total", "billable_employees"):
        value = pick(field, COMPANY_FIELDS, srcs_c, p_company.get(field), (overrides.get("company") or {}).get(field))
        if value is not None:
            company[field] = int(value)
    for field in ("short_name", "current_tools", "capabilities", "volumes"):
        if field in p_company:
            company[field] = p_company[field]
            report["client"][field] = "profile"
    if not company_name:
        errors.append("client name not found in the Phase 3 output or the profile (client_name)")
    if "employees_total" not in company:
        errors.append("company headcount not found: add company.employees_total to the client profile")
    if "loaded_hourly_rate" not in assumptions:
        errors.append("loaded hourly rate not found: add assumptions.loaded_hourly_rate to the client profile")

    top_scenario = top.get("scenario") if top.get("scenario") in ("A", "B") else None
    scenario = overrides.get("scenario") or top_scenario or prof.get("scenario") or "A"
    catalog = Catalog.load(scenario)

    # ------------------------------------------------------- ROI lookup
    roi_by_key: Dict[str, Dict[str, Any]] = {}
    for r in roi_items:
        for f in ("id", "name"):
            value, _ = _find(r, f, BOTTLENECK_FIELDS, roi_paths)
            if value is not None:
                roi_by_key.setdefault(_n(value), r)

    def read(item: Dict[str, Any], field: str, paths: Dict[str, str], label: str) -> Tuple[Any, Optional[str]]:
        value, key = _find(item, field, BOTTLENECK_FIELDS, paths)
        if value is None or key is None:
            return None, None
        if field in RANGED:
            rng = _as_range(value, notes, label)
            if rng is None:
                return None, None
            rng, siblings = _flat_range(item, key, rng)
            return rng, (f"{key} (+ {', '.join(siblings)})" if siblings else key)
        if field in NUMERIC:
            if isinstance(value, (list, dict, bool)):
                notes.append(f"{label}: '{key}' is a list or object, not a number, so it was ignored")
                return None, None
            number = _num(value)
            return (None, None) if number is None else (_clean(number), key)
        return value, key

    # ------------------------------------------------------- bottlenecks
    built: List[Dict[str, Any]] = []
    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            errors.append(f"bottleneck #{idx + 1} is not an object")
            continue
        roi = None
        for f in ("id", "name"):
            value, _ = _find(raw, f, BOTTLENECK_FIELDS, item_paths)
            if value is not None and _n(value) in roi_by_key:
                roi = roi_by_key[_n(value)]
                break
        rec: Dict[str, Any] = {}
        src: Dict[str, str] = {}
        used: set = set()
        label = f"bottleneck #{idx + 1}"
        for field in BOTTLENECK_FIELDS:
            order = [("step 8", roi, roi_paths), ("step 7", raw, item_paths)] if field in STEP8_FIRST else \
                [("step 7", raw, item_paths), ("step 8", roi, roi_paths)]
            for origin, item, paths in order:
                if item is None:
                    continue
                value, key = read(item, field, paths, f"{label} {field}")
                if value is not None:
                    rec[field], src[field] = value, f"{origin}: {key}"
                    if item is raw:
                        used.add(key)
                    break
        if rec.get("name") is None:
            errors.append(f"{label}: no name or title found")
            continue
        label = f"bottleneck '{rec['name']}'"
        if rec.get("hours_lost_per_week") is None and rec.get("hours_per_employee_per_week") is not None \
                and rec.get("employees_affected") is not None:
            per, people = rec["hours_per_employee_per_week"], rec["employees_affected"]
            rec["hours_lost_per_week"] = ({k: _clean(round(v * people, 4)) for k, v in per.items()}
                                          if isinstance(per, dict) else _clean(round(per * people, 4)))
            src["hours_lost_per_week"] = "hours per person x people affected"
        if rec.get("hours_lost_per_week") is None:
            errors.append(f"{label}: hours lost per week not found (or hours per person plus people affected)")
        if rec.get("employees_affected") is None:
            errors.append(f"{label}: number of people affected not found")
        built.append({"raw": raw, "rec": rec, "src": src, "used": used, "roi": roi})

    if errors:
        raise Phase3MappingError(errors, report)

    # ------------------------------------------------------- ranks
    missing_rank = [b for b in built if b["rec"].get("rank") is None]
    if missing_rank:
        def base(v: Any) -> float:
            return float(v["base"] if isinstance(v, dict) else (v or 0))

        basis = ("priority score" if any(b["rec"].get("priority_score") for b in built) else
                 "annual cost" if any(b["rec"].get("annual_cost") for b in built) else "hours lost")
        start = int(max((b["rec"]["rank"] for b in built if b["rec"].get("rank") is not None), default=0))
        ordered = sorted(missing_rank, key=lambda b: (-float(b["rec"].get("priority_score") or 0),
                                                      -base(b["rec"].get("annual_cost")),
                                                      -base(b["rec"].get("hours_lost_per_week"))))
        for i, b in enumerate(ordered):
            b["rec"]["rank"], b["src"]["rank"] = start + i + 1, f"ranked by {basis}"
        notes.append(f"ranks were missing for {len(missing_rank)} bottleneck(s), so they were ranked by {basis}")

    # ------------------------------------------------------- build each bottleneck
    category_map = {str(k).lower(): v for k, v in (prof.get("category_map") or {}).items()}
    extras = prof.get("bottleneck_extras") or {}
    default_margin = (prof.get("defaults") or {}).get("contribution_margin")
    bottlenecks: List[Dict[str, Any]] = []
    for b in sorted(built, key=lambda x: x["rec"]["rank"]):
        r, src = b["rec"], b["src"]
        bid = str(r["id"]) if r.get("id") is not None else f"BN-{int(r['rank'])}"
        if r.get("id") is None:
            src["id"] = "made from rank"
        out: Dict[str, Any] = {
            "id": bid,
            "rank": int(r["rank"]),
            "name": str(r["name"]),
            "employees_affected": int(round(float(r["employees_affected"]))),
            "hours_lost_per_week": r["hours_lost_per_week"],
        }
        explicit = r.get("category")
        cat_from = None
        if explicit in catalog.categories:
            out["category"], cat_from = explicit, src.get("category")
        else:
            name_l = out["name"].lower()
            hit = category_map.get(bid.lower()) or category_map.get(name_l)
            if hit is None:
                hit = next((v for k, v in category_map.items() if k and k in name_l), None)
            if hit:
                out["category"], cat_from = hit, "profile category_map"
            elif explicit is not None:
                out["category"] = str(explicit)
        for field in ("description", "annual_cost", "priority_score"):
            if r.get(field) is not None:
                out[field] = r[field]
        if r.get("departments") is not None:
            out["departments"] = _str_list(r["departments"])
        if r.get("root_causes") is not None:
            out["root_causes"] = _str_list(r["root_causes"])
        if r.get("evidence") is not None:
            out["evidence"] = _evidence(r["evidence"])
        feas = _feasibility(r.get("feasibility"), notes, f"bottleneck '{out['name']}'")
        if feas:
            out["feasibility"] = feas
        if r.get("deals_lost_per_year") is not None and r.get("avg_deal_value") is not None:
            margin = r.get("contribution_margin", default_margin)
            if margin is not None and margin > 1:
                margin = margin / 100
            if margin is None:
                errors.append(f"bottleneck '{out['name']}': deals are given but no contribution margin; "
                              "add one to step 8 or set defaults.contribution_margin in the profile")
            else:
                out["deal_impact"] = {"deals_lost_per_year": r["deals_lost_per_year"],
                                      "avg_deal_value": r["avg_deal_value"], "contribution_margin": margin}
        if isinstance(r.get("upside_not_counted"), list):
            out["upside_not_counted"] = r["upside_not_counted"]
        cat_id, match = catalog.match_category(out)
        extra = extras.get(bid) or (extras.get(cat_id) if cat_id else None) or {}
        added = [k for k in extra if k not in out]
        for k in added:
            out[k] = extra[k]
        bottlenecks.append(out)
        mapped = set()
        for v in src.values():
            if v.startswith("step 7: "):
                key_text = v.split(": ", 1)[1]
                mapped.add(key_text.split(" (+ ")[0])
                if " (+ " in key_text:
                    mapped.update(s.strip() for s in key_text.split(" (+ ", 1)[1].rstrip(")").split(","))
        report["bottlenecks"].append({
            "id": bid,
            "name": out["name"],
            "fields": src,
            "category": {"value": cat_id, "from": cat_from or (match["method"] if cat_id else "no match"),
                         "matched_keywords": match.get("matched_keywords", [])},
            "added_from_profile": added,
            "ignored_fields": sorted(str(k) for k in b["raw"] if k not in mapped),
        })
        if cat_id is None:
            notes.append(f"bottleneck '{out['name']}' matches no fix category; add it to the profile's "
                         "category_map, or add a category to the catalog")
    if errors:
        raise Phase3MappingError(errors, report)

    short = str(company.get("short_name") or company_name or "client").split()[0].lower()
    phase4_input: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": str(top.get("run_id") or prof.get("run_id") or
                          f"{re.sub(r'[^a-z0-9]+', '-', short).strip('-')}-{datetime.now(timezone.utc):%Y%m%d}"),
            "scenario": scenario,
            "client_name": company_name or "",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "source_steps": ["step7", "step8"],
            "synthetic": bool(prof.get("synthetic", False)),
            "notes": "Built from Phase 3 output by phase4.connectors.phase3",
        },
        "company": company,
        "assumptions": assumptions,
        "bottlenecks": bottlenecks,
    }
    if prof.get("upside_not_counted"):
        phase4_input["upside_not_counted"] = prof["upside_not_counted"]
    signals, _ = _find(top, "s", {"s": ["skill_signals", "skills", "step2"]})
    if isinstance(signals, list):
        phase4_input["skill_signals"] = signals
    report["found"]["roi_matched"] = sum(1 for b in built if b["roi"] is not None)
    report["scenario"] = scenario
    try:
        _, warnings = normalize_input(phase4_input)
    except Phase4InputError as exc:
        raise Phase3MappingError(exc.errors, report) from exc
    report["engine_warnings"] = warnings
    return phase4_input, report


# ------------------------------------------------------------------ files
def read_phase3_file(path: Union[str, Path], text: Optional[str] = None) -> Any:
    """Read Phase 3 output from .json or .csv (one row per bottleneck). Pass text to parse stdin."""
    p = Path(str(path))
    if text is None:
        text = p.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if p.suffix.lower() == ".csv" or (stripped[:1] not in ("{", "[") and "," in (stripped.splitlines() or [""])[0]):
        rows = list(csv.DictReader(io.StringIO(text)))
        return {"bottlenecks": [{k.strip(): (v.strip() if isinstance(v, str) else v)
                                 for k, v in row.items() if k} for row in rows]}
    return json.loads(text)
