"""Phase 4 -> Phase 5 (step 10): report sections, an evidence index and the scorecard.

The sections follow the Veloran reference report, so step 10 can drop them in:
  * Recommended actions        (executive summary)
  * <bottleneck>: solution options + Recommendation   (one per bottleneck section)
  * Recommendations and ROI    (table, upside not counted, formulas)
  * Governance review of AI tools + governance actions
  * Calculation workbook       (appendix)
  * Evidence behind every Phase 4 number

    blocks = report_blocks(output)       # structured: sections -> blocks (heading, paragraph, table, list)
    text   = report_markdown(output)     # the same content as Markdown
    card   = scorecard(output, "veloran")
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from ..numbers import D, fmt_money, fmt_num, fmt_payback, fmt_pct, round_half_up
from ..preview import _cost, _rng_money
from ..reference import compare_to_reference
from ..resources import load_expected

REPORT_VERSION = "phase4-report/1.0"


def _short(name: str) -> str:
    return name.split(":")[0].strip()


def _pb(months: Optional[float]) -> str:
    text = fmt_payback(months)
    return text if months in (None, 0) else f"{text} months"


def _split(trace: str) -> List[str]:
    """'85 h x 48 weeks x $90 x 70% adoption = $257,040' -> ['85 h x ... adoption', '$257,040']."""
    if " = " in trace:
        working, result = trace.rsplit(" = ", 1)
        return [working, result]
    return [trace, ""]


def _formulas(output: Dict[str, Any]) -> List[str]:
    f = output["assumptions_used"].get("formulas", {})
    labels = {
        "hours_saved_per_week": "Hours saved per week",
        "annual_time_savings": "Annual savings",
        "annual_deal_margin": "Deal margin won back (scenario B)",
        "year_one_cost": "Year-one cost",
        "payback_months": "Payback (months)",
        "mix_of_fixes": "Two fixes together",
        "choice": "Which mix is recommended",
    }
    return [f"**{labels.get(k, k)}** = {v}" for k, v in f.items()]


def report_blocks(output: Dict[str, Any]) -> Dict[str, Any]:
    """Phase 4's part of the step 10 report, as sections of typed blocks."""
    cur = output["assumptions_used"]["currency"]
    money = lambda x: fmt_money(x, cur)  # noqa: E731
    p = output["program"]
    bns = output["bottlenecks"]
    sections: List[Dict[str, Any]] = []

    # 1. Recommended actions (executive summary)
    actions = []
    for b in bns:
        r = b["recommendation"]
        if r:
            actions.append(f"**{_short(b['name'])}: {' + '.join(r['names'])}.** Year-one cost "
                           f"{money(r['year_one_cost']['base'])}; saves {money(r['annual_savings']['base'])} a year; "
                           f"payback {_pb(r['payback_months']['base'])}.")
    blocks: List[Dict[str, Any]] = [{"type": "list", "ordered": True, "items": actions}] if actions else \
        [{"type": "paragraph", "text": "No fixes are recommended yet."}]
    if p["recommendation_count"]:
        blocks.append({"type": "paragraph", "text":
                       f"Together: {money(p['year_one_cost']['base'])} in year one against "
                       f"{money(p['annual_savings']['base'])} in annual savings, or "
                       f"{money(p['net_benefit_year_one']['base'])} net in the first year."})
    sections.append({"id": "recommended-actions", "title": "Recommended actions",
                     "report_section": "Executive summary", "blocks": blocks})

    # 2. One solution-options section per bottleneck
    for b in bns:
        blocks = []
        facts = [f"{fmt_num(b['hours_lost_per_week']['base'])} hours lost a week", f"{b['employees_affected']} people"]
        if b.get("annual_cost"):
            facts.append(f"{money(b['annual_cost']['base'])} a year")
        blocks.append({"type": "paragraph", "text": " · ".join(facts)})
        if not b["options"]:
            blocks.append({"type": "paragraph", "text": "No fixes in the catalog match this bottleneck yet."})
        else:
            opts = b["options"]
            rows = [
                ["Type"] + [o["type_label"] for o in opts],
                ["How it solves"] + [o["how_it_solves"] for o in opts],
                ["Example vendors"] + ["; ".join(o["example_vendors"]) for o in opts],
                ["Upfront cost"] + [_cost(o, "upfront_cost", "upfront_breakdown", cur) for o in opts],
                [f"Ongoing cost ({'$' if cur == 'USD' else cur}/yr)"] +
                [_cost(o, "ongoing_cost_per_year", "ongoing_breakdown", cur) for o in opts],
                ["Implementation time"] + [o["implementation"].get("label", "") for o in opts],
                ["Effort and disruption"] + [o["effort"]["note"] for o in opts],
                ["Est. hours saved per week"] + [fmt_num(o["hours_saved_per_week"]["base"]) for o in opts],
            ]
            if any(o.get("deals_recovered_per_year") for o in opts):
                rows.append(["Est. deals won back per year"] +
                            [fmt_num(o["deals_recovered_per_year"]["base"]) if o.get("deals_recovered_per_year") else "n/a"
                             for o in opts])
            rows += [
                ["Est. annual savings"] + [money(o["annual_savings"]["base"]) for o in opts],
                ["Payback (months)"] + [fmt_payback(o["payback_months"]["base"]) for o in opts],
                ["Data and AI governance risk"] + [o["governance"]["note"] for o in opts],
                ["Key risks and dependencies"] + ["; ".join(o["risks_and_dependencies"]) for o in opts],
                ["Status"] + [o["status_label"] for o in opts],
            ]
            blocks.append({"type": "table", "columns": [""] + [o["label"] for o in opts], "rows": rows})
            r = b["recommendation"]
            if r:
                blocks.append({"type": "paragraph", "label": "Recommendation", "text": r["summary"]})
            else:
                blocks.append({"type": "paragraph", "label": "Recommendation",
                               "text": "None yet. " + " ".join(b.get("notes", []))})
            for o in opts:
                if o["status"] != "recommended":
                    extra = (" " + " ".join(o["other_reasons"])) if o["other_reasons"] else ""
                    blocks.append({"type": "paragraph", "label": o["label"], "text": f"{o['status_reason']}{extra}"})
        sections.append({"id": f"{b['id']}-solution-options", "title": f"{_short(b['name'])}: solution options",
                         "report_section": f"Bottleneck {b['rank']}", "bottleneck_id": b["id"], "blocks": blocks})

    # 3. Recommendations and ROI
    roi_rows = []
    for b in bns:
        r = b["recommendation"]
        if r:
            roi_rows.append([f"{b['rank']}. {_short(b['name'])}", " + ".join(r["names"]), r["type_summary"],
                             money(r["year_one_cost"]["base"]), money(r["ongoing_cost_per_year"]["base"]),
                             fmt_num(r["hours_saved_per_week"]["base"]), money(r["annual_savings"]["base"]),
                             fmt_payback(r["payback_months"]["base"])])
    blocks = [{"type": "paragraph", "text": p["summary"]}]
    if roi_rows:
        roi_rows.append(["**Total**", "", "", f"**{money(p['year_one_cost']['base'])}**",
                         f"**{money(p['ongoing_cost_per_year']['base'])}**",
                         f"**{fmt_num(p['gross_hours_saved_per_week']['base'])}**",
                         f"**{money(p['annual_savings']['base'])}**", f"**{fmt_payback(p['payback_months']['base'])}**"])
        blocks.append({"type": "table", "columns": ["Bottleneck", "Recommended solution", "Type", "Year-one cost",
                                                    "Ongoing cost (per year)", "Hours saved per week (gross)",
                                                    "Annual savings", "Payback (months)"], "rows": roi_rows})
        blocks.append({"type": "paragraph", "text":
                       f"Range across the low and high cases: {_rng_money(p['annual_savings'], cur)} a year in savings; "
                       f"payback {fmt_payback(p['payback_months']['high'])} to {fmt_payback(p['payback_months']['low'])} months."})
    if p["upside_not_counted"]:
        rows = [[u["label"], money(u["amount"]), u.get("basis", "")] for u in p["upside_not_counted"]]
        rows.append(["**Total**", f"**{money(p['upside_not_counted_total'])}**", ""])
        blocks.append({"type": "heading", "level": 3, "text": "Upside not counted"})
        blocks.append({"type": "table", "columns": ["Source", "Estimate (per year)", "Basis"], "rows": rows})
        blocks.append({"type": "paragraph", "text": "These are revenue and licence effects that depend on clients and "
                       "pricing, so they are left out of the savings and the case stands on time saved alone."})
    blocks.append({"type": "heading", "level": 3, "text": "Formulas used"})
    blocks.append({"type": "list", "ordered": False, "items": _formulas(output)})
    sections.append({"id": "recommendations-and-roi", "title": "Recommendations and ROI",
                     "report_section": "Recommendations and ROI", "blocks": blocks})

    # 4. Governance review of AI tools
    ai_rows = []
    for b in bns:
        for o in b["options"]:
            if o["governance"]["is_ai"]:
                ai_rows.append([o["name"], _short(b["name"]), o["status_label"], o["governance"].get("data_accessed") or "",
                                o["governance"]["note"], "; ".join(o["governance"]["go_live_gates"]) or "None listed"])
    blocks = []
    if ai_rows:
        blocks.append({"type": "table", "columns": ["AI tool", "Bottleneck", "Status", "Data it will access",
                                                    "Governance risk", "Before it goes live"], "rows": ai_rows})
    else:
        blocks.append({"type": "paragraph", "text": "No AI tools are among the options."})
    if p["governance_actions"]:
        blocks.append({"type": "heading", "level": 3, "text": "Governance actions"})
        blocks.append({"type": "checklist", "items": [f"{g['action']} (for {', '.join(g['for'])})"
                                                      for g in p["governance_actions"]]})
    sections.append({"id": "ai-governance", "title": "Governance review of AI tools",
                     "report_section": "AI governance", "blocks": blocks})

    # 5. Calculation workbook
    work = []
    for b in bns:
        r = b["recommendation"]
        if not r:
            continue
        for key, label in (("hours_saved_per_week", "hours saved"), ("annual_time_savings", "savings"),
                           ("annual_deal_margin", "deal margin"), ("year_one_cost", "year-one cost"),
                           ("payback_months", "payback")):
            if key in r["trace"]:
                work.append([f"{_short(b['name'])} {label}"] + _split(r["trace"][key]))
    for row in _program_workings(output):
        work.append(row)
    sections.append({"id": "calculation-workbook", "title": "Calculation workbook (Phase 4)",
                     "report_section": "Appendix: calculation workbook",
                     "blocks": [{"type": "table", "columns": ["Calculation", "Working", "Result"], "rows": work}]})

    # 6. Evidence index
    ev = evidence_index(output)
    sections.append({"id": "evidence", "title": "Evidence behind every Phase 4 number",
                     "report_section": "Appendix: evidence map",
                     "blocks": [{"type": "table", "columns": ["Number", "What it is", "Where", "How it was worked out"],
                                 "rows": [[e["number"], e["what"], e["where"], e["how"]] for e in ev]}]})

    return {
        "report_version": REPORT_VERSION,
        "title": "Solutions and ROI (Phase 4)",
        "client_name": output["run"]["client_name"],
        "scenario": output["run"]["scenario"],
        "generated_at": output["run"]["generated_at"],
        "engine": output["run"]["engine"],
        "sections": sections,
        "warnings": list(output.get("warnings", [])),
    }


def _program_workings(output: Dict[str, Any]) -> List[List[str]]:
    cur = output["assumptions_used"]["currency"]
    money = lambda x: fmt_money(x, cur)  # noqa: E731
    p = output["program"]
    recs = [b["recommendation"] for b in output["bottlenecks"] if b["recommendation"]]
    if not recs:
        return []
    rows = [
        ["Program year-one cost", " + ".join(money(r["year_one_cost"]["base"]) for r in recs), money(p["year_one_cost"]["base"])],
        ["Program annual savings", " + ".join(money(r["annual_savings"]["base"]) for r in recs), money(p["annual_savings"]["base"])],
        ["Program payback", f"{money(p['year_one_cost']['base'])} / ({money(p['annual_savings']['base'])} / 12)",
         _pb(p["payback_months"]["base"])],
        ["Effective hours won back", f"{fmt_num(p['gross_hours_saved_per_week']['base'])} gross hours x "
         f"{fmt_pct(p['adoption_rate_base'])} adoption", f"{fmt_num(p['effective_hours_saved_per_week']['base'])} hours a week"],
        ["Net benefit, year one", f"{money(p['annual_savings']['base'])} - {money(p['year_one_cost']['base'])}",
         money(p["net_benefit_year_one"]["base"])],
    ]
    return rows


def evidence_index(output: Dict[str, Any]) -> List[Dict[str, str]]:
    """Every headline Phase 4 number with the calculation behind it."""
    cur = output["assumptions_used"]["currency"]
    money = lambda x: fmt_money(x, cur)  # noqa: E731
    shown = {
        "hours_saved_per_week": ("hours saved a week", lambda v: f"{fmt_num(v)} h"),
        "annual_time_savings": ("time savings a year", money),
        "annual_deal_margin": ("deal margin won back a year", money),
        "year_one_cost": ("year-one cost", money),
        "payback_months": ("payback", _pb),
    }
    rows: List[Dict[str, str]] = []
    for b in output["bottlenecks"]:
        for o in b["options"]:
            for key, (what, fmt) in shown.items():
                if key in o["trace"]:
                    rows.append({"number": fmt(o[key]["base"]), "what": what, "where": f"{b['id']} · {o['label']}",
                                 "how": o["trace"][key]})
        r = b["recommendation"]
        if r:
            for key, (what, fmt) in shown.items():
                if key in r["trace"]:
                    rows.append({"number": fmt(r[key]["base"]), "what": what,
                                 "where": f"{b['id']} · recommended mix", "how": r["trace"][key]})
    for name, working, result in _program_workings(output):
        rows.append({"number": result, "what": name.lower(), "where": "program", "how": f"{working} = {result}"})
    return rows


# ------------------------------------------------------------------ markdown
def _esc(text: Any) -> str:
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: Dict[str, Any], top_level: int = 2) -> str:
    h = "#" * top_level
    lines = [f"{h} {report['title']}", "",
             f"{report['client_name']} · scenario {report['scenario']} · {report['engine']} · generated {report['generated_at']}", ""]
    for s in report["sections"]:
        lines += [f"{h}# {s['title']}", ""]
        for blk in s["blocks"]:
            t = blk["type"]
            if t == "heading":
                lines += [f"{'#' * (top_level + blk.get('level', 3) - 1)} {blk['text']}", ""]
            elif t == "paragraph":
                label = f"**{blk['label']}.** " if blk.get("label") else ""
                lines += [label + blk["text"], ""]
            elif t == "list":
                lines += [(f"{i}. " if blk.get("ordered") else "- ") + item for i, item in enumerate(blk["items"], 1)] + [""]
            elif t == "checklist":
                lines += [f"- [ ] {item}" for item in blk["items"]] + [""]
            elif t == "table":
                lines.append("| " + " | ".join(_esc(c) for c in blk["columns"]) + " |")
                lines.append("|" + "|".join(" --- " for _ in blk["columns"]) + "|")
                lines += ["| " + " | ".join(_esc(c) for c in row) + " |" for row in blk["rows"]]
                lines.append("")
    if report.get("warnings"):
        lines += [f"{h}# Warnings", ""] + [f"- {w}" for w in report["warnings"]] + [""]
    return "\n".join(lines)


def report_markdown(output: Dict[str, Any], top_level: int = 2) -> str:
    return render_markdown(report_blocks(output), top_level)


# ------------------------------------------------------------------ scorecard
def scorecard(output: Dict[str, Any], expected: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """How many of the reference report's numbers Phase 4 reproduces (for step 10's scorecard)."""
    exp = load_expected(expected)
    rows = compare_to_reference(output, exp)
    matched = sum(1 for r in rows if r["ok"])
    pct = float(round_half_up(D(matched) * 100 / D(len(rows)), 1)) if rows else 0.0
    table = ["| Check | Report | Phase 4 | Match |", "| --- | --- | --- | --- |"]
    for r in rows:
        e = ", ".join(r["expected"]) if isinstance(r["expected"], list) else r["expected"]
        g = ", ".join(r["got"]) if isinstance(r["got"], list) else r["got"]
        table.append(f"| {_esc(r['where'])} | {_esc(e)} | {_esc(g)} | {'yes' if r['ok'] else '**no**'} |")
    return {
        "reference": exp.get("reference", ""),
        "checks": len(rows),
        "matched": matched,
        "score_pct": pct,
        "passed": bool(rows) and matched == len(rows),
        "rows": rows,
        "markdown": f"**{matched} of {len(rows)} numbers match the reference report ({pct:g}%).**\n\n" + "\n".join(table),
    }
