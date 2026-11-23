"""The fix catalog: which fixes exist for each kind of bottleneck.

The catalog is plain JSON (phase4/data/*.json) so teammates can add fixes
without touching Python. Each category lists its fixes in report order
(Option 1, 2, 3). Each fix says what it costs, how much of the bottleneck's
lost time it removes, what it needs first, and what could go wrong.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .numbers import D, round_to_step

DATA_DIR = Path(__file__).parent / "data"

FIX_TYPES = {
    "ai_tool": "AI tool",
    "software": "Non-AI software",
    "process": "Process",
    "reskilling": "Reskilling",
}
COST_BASES = {"flat", "per_unit", "per_seat_month", "internal_hours"}
REQUIRE_OPS = {">=", ">", "<=", "<", "==", "!="}
IF_UNMET = {"defer", "hold", "block"}
RISK_LEVELS = ["none", "low", "medium", "high"]
EFFORT_LEVELS = ["low", "medium", "high"]
DEFAULT_LOW_FACTOR = Decimal("0.75")
DEFAULT_HIGH_FACTOR = Decimal("1.2")


class CatalogError(ValueError):
    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__("Fix catalog has problems:\n- " + "\n- ".join(problems))


def _pair_key(a: str, b: str) -> frozenset:
    return frozenset((a, b))


class Catalog:
    """One or more catalog files merged together."""

    def __init__(self, documents: Iterable[Dict[str, Any]]):
        self.categories: Dict[str, Dict[str, Any]] = {}
        self.fixes: Dict[str, Dict[str, Any]] = {}
        self.pairs: Dict[frozenset, Dict[str, Any]] = {}
        self.default_overlap = Decimal("0.3")
        self.versions: List[Dict[str, str]] = []
        problems: List[str] = []
        for doc in documents:
            cid = doc.get("catalog_id", "unnamed")
            self.versions.append({"catalog_id": cid, "catalog_version": doc.get("catalog_version", "")})
            if "default_overlap" in doc:
                self.default_overlap = D(doc["default_overlap"])
            for cat_id, cat in (doc.get("categories") or {}).items():
                if cat_id in self.categories:
                    problems.append(f"category '{cat_id}' is defined twice")
                self.categories[cat_id] = dict(cat, catalog_id=cid)
            for fix_id, fix in (doc.get("fixes") or {}).items():
                if fix_id in self.fixes:
                    problems.append(f"fix '{fix_id}' is defined twice")
                self.fixes[fix_id] = dict(fix, id=fix_id, catalog_id=cid)
            for p in doc.get("pair_overlaps") or []:
                a, b = p.get("pair", [None, None])
                self.pairs[_pair_key(a, b)] = p
        problems.extend(self._validate())
        if problems:
            raise CatalogError(problems)

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, scenario: Optional[str] = None, paths: Optional[Iterable[str]] = None) -> "Catalog":
        """Load the shipped catalogs for a scenario, or explicit files."""
        if paths:
            files = [Path(p) for p in paths]
        else:
            files = sorted(DATA_DIR.glob("catalog_*.json"))
        docs = []
        for f in files:
            with open(f, encoding="utf-8") as fh:
                doc = json.load(fh)
            applies = doc.get("applies_to_scenarios")
            if paths or scenario is None or not applies or scenario in applies:
                docs.append(doc)
        if not docs:
            raise CatalogError([f"no catalog found for scenario {scenario!r}"])
        return cls(docs)

    # -------------------------------------------------------------- validate
    def _validate(self) -> List[str]:
        problems: List[str] = []
        for cat_id, cat in self.categories.items():
            if not cat.get("fixes"):
                problems.append(f"category '{cat_id}' lists no fixes")
            for fix_id in cat.get("fixes", []):
                if fix_id not in self.fixes:
                    problems.append(f"category '{cat_id}' lists unknown fix '{fix_id}'")
        for fix_id, fix in self.fixes.items():
            where = f"fix '{fix_id}'"
            if fix.get("fix_type") not in FIX_TYPES:
                problems.append(f"{where}: fix_type must be one of {sorted(FIX_TYPES)}")
            for extra in fix.get("also", []):
                if extra not in FIX_TYPES:
                    problems.append(f"{where}: 'also' has unknown type '{extra}'")
            for key in ("name", "how_it_solves"):
                if not fix.get(key):
                    problems.append(f"{where}: {key} is required")
            effect = fix.get("effect") or {}
            if "hours_share" not in effect and "deal_recovery_share" not in effect:
                problems.append(f"{where}: effect needs hours_share and/or deal_recovery_share")
            for key in ("hours_share", "deal_recovery_share"):
                if key in effect:
                    for s, v in _share_cases(effect[key]).items():
                        if not (0 <= v <= 1):
                            problems.append(f"{where}: effect.{key}.{s} must be between 0 and 1")
            for phase in ("upfront", "ongoing"):
                for item in (fix.get("costs") or {}).get(phase, []):
                    basis = item.get("basis")
                    if basis not in COST_BASES:
                        problems.append(f"{where}: cost basis '{basis}' must be one of {sorted(COST_BASES)}")
                    if basis == "per_seat_month" and phase == "upfront":
                        problems.append(f"{where}: per_seat_month only makes sense in ongoing costs")
            gov = fix.get("governance") or {}
            if gov.get("risk", "none") not in RISK_LEVELS:
                problems.append(f"{where}: governance.risk must be one of {RISK_LEVELS}")
            if (fix.get("effort") or {}).get("level", "low") not in EFFORT_LEVELS:
                problems.append(f"{where}: effort.level must be one of {EFFORT_LEVELS}")
            for req in fix.get("requires", []):
                if req.get("op", "==") not in REQUIRE_OPS:
                    problems.append(f"{where}: requires op '{req.get('op')}' is not supported")
                if req.get("if_unmet", "block") not in IF_UNMET:
                    problems.append(f"{where}: requires if_unmet must be one of {sorted(IF_UNMET)}")
                if not req.get("capability"):
                    problems.append(f"{where}: every requires entry needs a capability")
            for dep in fix.get("requires_fix", []):
                if dep not in self.fixes:
                    problems.append(f"{where}: requires_fix names unknown fix '{dep}'")
            for c in fix.get("conflicts_with", []):
                if c.get("fix") not in self.fixes:
                    problems.append(f"{where}: conflicts_with names unknown fix '{c.get('fix')}'")
        for key, p in self.pairs.items():
            names = sorted(key)
            for n in names:
                if n not in self.fixes:
                    problems.append(f"pair_overlaps names unknown fix '{n}'")
            if not (0 <= D(p.get("overlap", -1)) <= 1):
                problems.append(f"pair_overlaps {names}: overlap must be between 0 and 1")
        return problems

    # -------------------------------------------------------------- matching
    def match_category(self, bottleneck: Dict[str, Any], min_hits: int = 2) -> Tuple[Optional[str], Dict[str, Any]]:
        """Use the bottleneck's category if known, else match on keywords.

        A keyword match needs at least min_hits different keywords, so one
        shared word ("rework") cannot send a bottleneck to the wrong fixes.
        """
        cat = bottleneck.get("category")
        if cat in self.categories:
            return cat, {"method": "category_id", "matched_keywords": []}
        text = " ".join([bottleneck.get("name", ""), bottleneck.get("description", "")]
                        + list(bottleneck.get("root_causes", []))).lower()

        def found(words: List[str]) -> List[str]:
            return [k for k in words if re.search(r"\b" + re.escape(k.lower()), text)]

        best, best_hits, best_score = None, [], 0
        for cat_id, c in self.categories.items():
            anchors, hits = found(c.get("anchors", [])), found(c.get("keywords", []))
            # An anchor phrase ("timesheet", "staffing") is enough on its own;
            # ordinary keywords need at least min_hits different matches.
            if not anchors and len(hits) < min_hits:
                continue
            score = 2 * len(anchors) + len(hits)
            if score > best_score:
                best, best_hits, best_score = cat_id, sorted(set(anchors + hits)), score
        if best is None:
            return None, {"method": "none", "matched_keywords": []}
        method = "keywords" if cat is None else f"keywords (category '{cat}' not in catalog)"
        return best, {"method": method, "matched_keywords": best_hits}

    # ---------------------------------------------------------------- pairs
    def overlap(self, a: str, b: str) -> Decimal:
        p = self.pairs.get(_pair_key(a, b))
        return D(p["overlap"]) if p else self.default_overlap

    def pair(self, a: str, b: str) -> Optional[Dict[str, Any]]:
        return self.pairs.get(_pair_key(a, b))

    def overlap_is_listed(self, a: str, b: str) -> bool:
        return _pair_key(a, b) in self.pairs


# --------------------------------------------------------------- helpers
def _share_cases(spec: Any) -> Dict[str, float]:
    if isinstance(spec, (int, float)):
        return {"base": float(spec)}
    return {k: float(v) for k, v in spec.items() if k in ("low", "base", "high")}


def share_range(spec: Any, cap: Decimal) -> Dict[str, Decimal]:
    """Effect share for each case. Missing low/high default to x0.75 / x1.2."""
    cases = _share_cases(spec)
    base = D(cases["base"])
    low = D(cases["low"]) if "low" in cases else base * DEFAULT_LOW_FACTOR
    high = D(cases["high"]) if "high" in cases else base * DEFAULT_HIGH_FACTOR
    return {"low": min(low, cap), "base": min(base, cap), "high": min(high, cap)}


def resolve_qty(spec: Any, variables: Dict[str, Any]) -> Tuple[Decimal, str, List[str]]:
    """Turn a quantity spec into a number.

    Forms: 12 | "billable_employees" | {"var": "x", "mult": 0.5, "round": "nearest",
    "default": <spec>}. Returns (value, label, missing_variable_names).
    """
    if spec is None:
        return Decimal(1), "", []
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        return D(spec), "", []
    if isinstance(spec, str):
        spec = {"var": spec}
    name = spec.get("var")
    mult = D(spec.get("mult", 1))
    rounding = spec.get("round", "nearest")
    if name in variables and variables[name] is not None:
        raw = D(variables[name]) * mult
        value = round_to_step(raw, 1, rounding) if rounding != "none" else raw
        return value, name.replace("_", " "), []
    if "default" in spec:
        value, label, missing = resolve_qty(spec["default"], variables)
        return value, label or name.replace("_", " "), missing
    return Decimal(0), name.replace("_", " "), [name]


_PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def template_missing(text: Optional[str], variables: Dict[str, Any]) -> List[str]:
    """Placeholder names in text that have no value."""
    return [m for m in _PLACEHOLDER.findall(text or "") if variables.get(m) in (None, "")]


def fill_template(text: Optional[str], variables: Dict[str, Any], fallback: Optional[str] = None) -> str:
    """Fill {placeholders}; use the fallback text if any value is missing."""
    if not text:
        return fallback or ""
    missing = [m for m in _PLACEHOLDER.findall(text) if variables.get(m) in (None, "")]
    if missing:
        return fallback if fallback is not None else _PLACEHOLDER.sub("", text)

    def sub(m: "re.Match[str]") -> str:
        v = variables[m.group(1)]
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return f"{v:,}" if isinstance(v, int) and not isinstance(v, bool) else str(v)

    return _PLACEHOLDER.sub(sub, text)
