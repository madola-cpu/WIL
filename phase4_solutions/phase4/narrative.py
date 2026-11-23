"""Words for the report: template sentences by default, Claude-written if enabled.

Numbers always come from the engine, never from the language model. When
Claude writes a paragraph, every number in it is checked against the facts it
was given. One unknown number, an empty answer or a failed call, and the
template text is used instead (with a warning), so the demo never breaks.
"""
from __future__ import annotations

import json
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .numbers import D, fmt_money, fmt_num, fmt_pct, round_half_up

DEFAULT_MODEL = "claude-sonnet-5-5"
MODEL_ENV = "PHASE4_CLAUDE_MODEL"


def _lower_first(name: str) -> str:
    if len(name) > 1 and name[1].islower():
        return name[0].lower() + name[1:]
    return name


def _join(items: List[str], word: str = "and") -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


# ----------------------------------------------------------- templates
def recommendation_summary(bn: Dict[str, Any], currency: str = "USD") -> str:
    rec = bn.get("recommendation")
    if not rec:
        return "No fix is recommended yet. " + " ".join(bn.get("notes", []))
    parts = [f"Option {n} ({name})" for n, name in zip(rec["option_numbers"], rec["names"])]
    many = len(parts) > 1
    head = f"We recommend {_join(parts)}{' together' if many else ''}."
    hours = rec["hours_saved_per_week"]["base"]
    savings = fmt_money(rec["annual_savings"]["base"], currency)
    cost = fmt_money(rec["year_one_cost"]["base"], currency)
    payback = rec["payback_months"]["base"]
    verb = "Together they save" if many else "It saves"
    deals = rec.get("deals_recovered_per_year")
    if deals:
        body = (f"{verb} an estimated {fmt_num(hours)} hours a week and recover about "
                f"{fmt_num(deals['base'])} deals a year, worth {savings} a year in time and margin, "
                f"for {cost} in year one")
    else:
        body = f"{verb} an estimated {fmt_num(hours)} hours a week ({savings} a year) for {cost} in year one"
    if payback == 0:
        body += ", with nothing to pay back."
    else:
        body += f", a payback of {payback:.1f} months."
    return " ".join(p for p in (head, rec.get("together_note") or "", body) if p)


def not_chosen_list(bn: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"option_id": o["option_id"], "option_number": o["option_number"], "name": o["name"],
         "status": o["status"], "status_label": o["status_label"], "reason": o["status_reason"]}
        for o in bn.get("options", []) if o["status"] != "recommended"
    ]


def program_summary(program: Dict[str, Any], currency: str = "USD") -> str:
    n = program["recommendation_count"]
    if not n:
        return "No fixes are recommended yet."
    y1 = fmt_money(program["year_one_cost"]["base"], currency)
    sav = fmt_money(program["annual_savings"]["base"], currency)
    pb = program["payback_months"]["base"]
    ongoing = fmt_money(program["ongoing_cost_per_year"]["base"], currency)
    net2 = fmt_money(program["net_benefit_year_two_onward"]["base"], currency)
    noun = "recommendation costs" if n == 1 else f"{n} recommendations cost"
    s1 = f"The {noun} {y1} in year one and save an estimated {sav} a year"
    s1 += ", with nothing to pay back." if pb == 0 else f", a combined payback of {pb:.1f} months."
    s2 = f"From year two, ongoing costs are {ongoing} a year and the net benefit is about {net2} a year."
    eff = program["effective_hours_saved_per_week"]["base"]
    gross = program["gross_hours_saved_per_week"]["base"]
    share = program["share_of_lost_hours_recovered"]
    adoption = program["adoption_rate_base"]
    s3 = (f"At {fmt_pct(adoption)} adoption, the {fmt_num(gross)} gross hours become about "
          f"{fmt_num(round_half_up(eff, 0))} effective hours a week: {fmt_pct(share)} of the "
          f"{fmt_num(round_half_up(program['hours_lost_in_scope_per_week'], 0))} hours lost to the "
          f"bottlenecks in scope.")
    return " ".join([s1, s2, s3])


# ------------------------------------------------------- number guard
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])\$?\d[\d,]*(?:\.\d+)?%?")


def _norm(token: str) -> Optional[str]:
    t = token.replace("$", "").replace(",", "").rstrip("%")
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    d = d.normalize()
    return format(d, "f")


def numbers_in_text(text: str) -> Set[str]:
    out = set()
    for tok in _NUMBER.findall(text or ""):
        n = _norm(tok.rstrip("."))
        if n is not None:
            out.add(n)
    return out


def allowed_numbers(facts: Any) -> Set[str]:
    """Every number that appears anywhere in the facts, in the forms a writer may use."""
    out: Set[str] = set()

    def add(value: Any) -> None:
        d = D(value)
        for form in (d, round_half_up(d, 0), round_half_up(d, 1)):
            n = _norm(str(form))
            if n is not None:
                out.add(n)
        if 0 < d < 1:  # shares may be written as percentages
            out.add(_norm(str(round_half_up(d * 100, 0))))

    def walk(x: Any) -> None:
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float, Decimal)):
            add(x)
        elif isinstance(x, str):
            out.update(numbers_in_text(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(facts)
    return out


def check_numbers(text: str, facts: Any) -> Tuple[bool, List[str]]:
    unknown = sorted(numbers_in_text(text) - allowed_numbers(facts))
    return (not unknown), unknown


# ------------------------------------------------------ Claude writer
SYSTEM_PROMPT = (
    "You write one paragraph for a workflow consulting report that managers will read. "
    "Style: plain words, short sentences, active voice, no hype, no lists, no headings. "
    "Use only the facts in the JSON you are given. Every number you write must appear in the facts; "
    "you may format money like $257,040, but never round, estimate, convert or add numbers. "
    "Cover, in order: which option or options we recommend and how they work together; the combined result "
    "(hours a week, savings a year, year-one cost, payback); then one sentence on the most important option "
    "not chosen and why. At most 110 words. Return only the paragraph."
)


def recommendation_facts(bn: Dict[str, Any]) -> Dict[str, Any]:
    rec = bn["recommendation"]
    by_id = {o["option_id"]: o for o in bn["options"]}
    return {
        "bottleneck": bn["name"],
        "hours_lost_per_week": bn["hours_lost_per_week"]["base"],
        "recommended_options": [
            {"option_number": by_id[i]["option_number"], "name": by_id[i]["name"],
             "type": by_id[i]["type_label"], "how_it_solves": by_id[i]["how_it_solves"]}
            for i in rec["option_ids"]
        ],
        "how_they_work_together": rec.get("together_note"),
        "hours_saved_per_week": rec["hours_saved_per_week"]["base"],
        "deals_recovered_per_year": (rec.get("deals_recovered_per_year") or {}).get("base"),
        "annual_savings": rec["annual_savings"]["base"],
        "year_one_cost": rec["year_one_cost"]["base"],
        "payback_months": rec["payback_months"]["base"],
        "options_not_chosen": [
            {"option_number": o["option_number"], "name": o["name"], "status": o["status_label"],
             "reason": o["status_reason"]}
            for o in bn["options"] if o["status"] != "recommended"
        ],
    }


class ClaudeWriter:
    """Optional: Claude drafts the recommendation paragraph; the guard checks it."""

    def __init__(self, client: Any = None, model: Optional[str] = None):
        self.model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic  # optional dependency: pip install anthropic
            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        return self._client

    def write(self, facts: Dict[str, Any]) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(facts, ensure_ascii=False)}],
        )
        return "".join(getattr(b, "text", "") for b in message.content).strip()

    def recommendation(self, bn: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Return (text, None) if accepted, or (None, warning) to fall back."""
        facts = recommendation_facts(bn)
        try:
            text = self.write(facts)
        except Exception as exc:  # network, key, model name... never break the run
            return None, f"{bn['id']}: Claude text skipped ({type(exc).__name__}: {exc}); template used."
        if not text:
            return None, f"{bn['id']}: Claude returned no text; template used."
        ok, unknown = check_numbers(text, facts)
        if not ok:
            return None, (f"{bn['id']}: Claude text rejected because it used numbers not in the facts "
                          f"({', '.join(unknown)}); template used.")
        return text, None
