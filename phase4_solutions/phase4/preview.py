"""Render a Phase 4 output as Markdown, laid out like the reference reports.

Handy for checking results by eye, pasting into a doc, or showing teammates
what the JSON contains. The frontend should read the JSON, not this.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .numbers import fmt_money, fmt_num, fmt_payback


def _cell(text: Any) -> str:
    return str(text if text is not None else "").replace("|", "/").replace("\n", " ").strip()


def _rng_num(r: Optional[Dict[str, Any]]) -> str:
    if not r:
        return "n/a"
    if r["low"] == r["base"] == r["high"]:
        return fmt_num(r["base"])
    return f"{fmt_num(r['base'])} ({fmt_num(r['low'])} to {fmt_num(r['high'])})"


def _rng_money(r: Dict[str, Any], cur: str) -> str:
    if r["low"] == r["base"] == r["high"]:
        return fmt_money(r["base"], cur)
    return f"{fmt_money(r['base'], cur)} ({fmt_money(r['low'], cur)} to {fmt_money(r['high'], cur)})"


def _cost(o: Dict[str, Any], key: str, breakdown: str, cur: str) -> str:
    base = fmt_money(o[key]["base"], cur)
    if o.get("cost_shared_with"):
        return f"{base} (counted under {o['cost_shared_with']})"
    items = o.get(breakdown) or []
    if not items:
        return f"{base} ({o['cost_note']})" if o.get("cost_note") else base
    if len(items) == 1:
        item = items[0]
        if item["calc"] == fmt_money(item["amount"], cur):  # a flat amount: the label says enough
            return f"{base} ({item['item'].lower()})"
        return f"{base} ({item['item'].lower()}: {item['calc']})"
    return base + " (" + "; ".join(f"{i['item'].lower()} {fmt_money(i['amount'], cur)}" for i in items) + ")"


def _table(rows: List[List[str]]) -> List[str]:
    out = ["| " + " | ".join(_cell(c) for c in rows[0]) + " |",
           "|" + "|".join(" --- " for _ in rows[0]) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows[1:]]
    return out


def render_markdown(out: Dict[str, Any]) -> str:
    cur = out["assumptions_used"]["currency"]
    run = out["run"]
    cats = ", ".join(f"{c['catalog_id']} {c['catalog_version']}" for c in run["catalogs"])
    lines = [
        f"# Phase 4 fixes: {run['client_name']}",
        "",
        f"Scenario {run['scenario']} · {run['engine']} · catalog {cats} · generated {run['generated_at']}",
        "",
    ]
    p = out["program"]
    lines += ["## Summary", "", p["summary"], ""]
    rows = [["Bottleneck", "Recommended fixes", "Type", "Year-one cost", "Ongoing (per year)",
             "Hours saved per week", "Annual savings", "Payback (months)"]]
    for b in out["bottlenecks"]:
        r = b["recommendation"]
        if not r:
            rows.append([f"{b['rank']}. {b['name']}", "None yet", "", "", "", "", "", ""])
            continue
        rows.append([f"{b['rank']}. {b['name']}", " + ".join(r["names"]), r["type_summary"],
                     fmt_money(r["year_one_cost"]["base"], cur), fmt_money(r["ongoing_cost_per_year"]["base"], cur),
                     fmt_num(r["hours_saved_per_week"]["base"]), fmt_money(r["annual_savings"]["base"], cur),
                     fmt_payback(r["payback_months"]["base"])])
    rows.append(["Total", "", "", fmt_money(p["year_one_cost"]["base"], cur),
                 fmt_money(p["ongoing_cost_per_year"]["base"], cur), fmt_num(p["gross_hours_saved_per_week"]["base"]),
                 fmt_money(p["annual_savings"]["base"], cur), fmt_payback(p["payback_months"]["base"])])
    lines += _table(rows) + [""]
    lines.append(f"Low and high cases for total savings: {fmt_money(p['annual_savings']['low'], cur)} to "
                 f"{fmt_money(p['annual_savings']['high'], cur)} a year; payback "
                 f"{fmt_payback(p['payback_months']['high'])} to {fmt_payback(p['payback_months']['low'])} months.")
    lines.append("")

    for b in out["bottlenecks"]:
        lines.append(f"## {b['id']}: {b['name']}")
        lines.append("")
        facts = [f"{fmt_num(b['hours_lost_per_week']['base'])} hours lost a week",
                 f"{b['employees_affected']} people"]
        if b.get("annual_cost"):
            facts.append(f"{fmt_money(b['annual_cost']['base'], cur)} a year")
        facts.append(f"fix category: {b['category_label'] or 'none matched'}")
        lines += [" · ".join(facts), ""]
        if not b["options"]:
            lines += ["No fixes in the catalog for this bottleneck yet.", ""]
            continue
        has_deals = any(o.get("deals_recovered_per_year") for o in b["options"])
        header = [""] + [o["label"] for o in b["options"]]
        grid = [header,
                ["Type"] + [o["type_label"] for o in b["options"]],
                ["How it solves"] + [o["how_it_solves"] for o in b["options"]],
                ["Example vendors"] + ["; ".join(o["example_vendors"]) for o in b["options"]],
                ["Upfront cost"] + [_cost(o, "upfront_cost", "upfront_breakdown", cur) for o in b["options"]],
                ["Ongoing cost (per year)"] + [_cost(o, "ongoing_cost_per_year", "ongoing_breakdown", cur) for o in b["options"]],
                ["Implementation time"] + [o["implementation"].get("label", "") for o in b["options"]],
                ["Effort and disruption"] + [o["effort"]["note"] for o in b["options"]],
                ["Est. hours saved per week"] + [_rng_num(o["hours_saved_per_week"]) for o in b["options"]]]
        if has_deals:
            grid.append(["Est. deals recovered per year"] + [_rng_num(o["deals_recovered_per_year"]) for o in b["options"]])
        grid += [["Est. annual savings"] + [_rng_money(o["annual_savings"], cur) for o in b["options"]],
                 ["Payback (months)"] + [fmt_payback(o["payback_months"]["base"]) for o in b["options"]],
                 ["Data and AI governance risk"] + [o["governance"]["note"] for o in b["options"]],
                 ["Key risks and dependencies"] + ["; ".join(o["risks_and_dependencies"]) for o in b["options"]],
                 ["Status"] + [o["status_label"] for o in b["options"]]]
        lines += _table(grid) + [""]
        r = b["recommendation"]
        if r:
            lines += [f"**Recommendation.** {r['summary']}", ""]
        else:
            lines += ["**Recommendation.** None yet: " + " ".join(b["notes"]), ""]
        others = [o for o in b["options"] if o["status"] != "recommended"]
        if others:
            lines.append("**Options not chosen**")
            lines.append("")
            for o in others:
                extra = (" " + " ".join(o["other_reasons"])) if o["other_reasons"] else ""
                lines.append(f"- {o['label']}: {o['status_reason']}{extra}")
            lines.append("")
        if r:
            lines.append("**How the numbers were worked out**")
            lines.append("")
            for key, text in r["trace"].items():
                lines.append(f"- {key.replace('_', ' ')}: {text}")
            lines.append("")

    if p["governance_actions"]:
        lines += ["## Before any AI tool goes live", ""]
        lines += [f"- {g['action']} (for {', '.join(g['for'])})" for g in p["governance_actions"]]
        lines.append("")
    if p["upside_not_counted"]:
        lines += ["## Upside not counted in the savings", ""]
        rows = [["Source", "Estimate (per year)", "Basis"]]
        rows += [[u["label"], fmt_money(u["amount"], cur), u.get("basis", "")] for u in p["upside_not_counted"]]
        rows.append(["Total", fmt_money(p["upside_not_counted_total"], cur), ""])
        lines += _table(rows) + [""]
    if out["bottlenecks_not_in_scope"]:
        lines += ["## Bottlenecks not solved in this run", ""]
        lines += [f"- {b['id']} {b['name']}: {b['reason']}" for b in out["bottlenecks_not_in_scope"]]
        lines.append("")
    if out["warnings"]:
        lines += ["## Warnings", ""] + [f"- {w}" for w in out["warnings"]] + [""]
    return "\n".join(lines)
