"""Self-contained HTML previews. All data text is escaped; nothing is fetched.

findings_html(findings)  - the engine's findings.json as a page (outputs/<run>/preview.html)
manager_view_html(view)  - the existing Phase 4 manager-view panel with a manager_view inlined
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

PANEL_JS = Path(__file__).resolve().parent.parent / "examples" / "frontend" / "phase4-panel.js"

CSS = """
:root{--bg:#f5f6f8;--card:#fff;--ink:#1d2433;--muted:#5b6474;--line:#e2e5ea;--accent:#2f5db3;--warn:#b45309;--warnbg:#fdf1e3}
@media (prefers-color-scheme: dark){:root{--bg:#14171c;--card:#1d2128;--ink:#e8ebf0;--muted:#a3abb8;--line:#2e343e;--accent:#8fb0f0;--warn:#f0b46a;--warnbg:#3a2a16}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.2rem;margin:28px 0 10px}
h3{font-size:1.05rem;margin:0 0 8px}.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.stat b{display:block;font-size:1.5rem}
.flag{display:inline-block;background:var(--warnbg);color:var(--warn);border-radius:6px;padding:1px 8px;margin:2px 4px 2px 0;font-size:13px}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:560px;font-size:14px}th,td{text-align:left;padding:7px 9px;border-top:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}ol li{margin:6px 0}code{font-size:13px;overflow-wrap:anywhere}
"""


def _v(x: Optional[Dict[str, Any]], money: bool = False) -> str:
    if not x or x.get("value") is None:
        return escape((x or {}).get("note", "n/a"))
    v = x["value"]
    text = f"{v:,.0f}" if float(v).is_integer() else f"{v:,}"
    return ("$" if money else "") + text


def _rng(r: Dict[str, Any], money: bool = False) -> str:
    if "p50" not in r:
        return f"<span class='flag'>not computed</span> <span class='muted'>{escape(r.get('reason', ''))}</span>"
    return f"{_v(r['p10'], money)} / <b>{_v(r['p50'], money)}</b> / {_v(r['p90'], money)}"


def findings_html(f: Dict[str, Any]) -> str:
    dp, s = f["data_profile"], f["summary"]
    computed = [x for x in f["fixes"] if x["status"] == "computed"]
    parts: List[str] = [
        f"<h1>Impact findings: {escape(dp['dataset'])}</h1>",
        f"<p class='muted'>Run <code>{escape(f['run_id'])}</code> · {escape(dp['period']['start'])} to "
        f"{escape(dp['period']['end'])} · {f['monte_carlo']['draws']:,} seeded draws · every number has a source tag "
        f"in findings.json</p>",
        "<div class='grid'>",
        f"<div class='card stat'><span class='muted'>People measured</span><b>{_v(dp['people'])}</b></div>",
        f"<div class='card stat'><span class='muted'>Reportable teams</span><b>{_v(dp['teams_reported_count'])}</b></div>",
        f"<div class='card stat'><span class='muted'>Bottlenecks found</span><b>{_v(s['bottlenecks_detected'])}</b></div>",
        f"<div class='card stat'><span class='muted'>Hours lost a week</span><b>{_v(s['total_hours_lost_per_week'])}</b></div>",
        "</div>", "<h2>React first</h2><div class='card'><ol>",
    ]
    parts += [f"<li>{escape(r['reason'])}</li>" for r in f["react_first"]] or ["<li>No fix applies.</li>"]
    parts.append("</ol></div><h2>Bottlenecks</h2>")
    for b in f["bottlenecks"]:
        parts.append(f"<div class='card'><h3>{escape(b['name'])}</h3>")
        parts.append(f"<p><code>{escape(b['kpi'])}</code> = {_v(b['kpi_value'])} (rule {escape(b['comparator'])} "
                     f"{_v(b['threshold'])}) · teams: {escape(', '.join(b['group']['teams']))} · sufficiency: "
                     f"{escape(b['sufficiency']['status'])}</p>")
        if not b["diagnostic"]:
            rng = b.get("total_hours_lost_per_week_range", {})
            parts.append(f"<p><b>{_v(b['total_hours_lost_per_week'])} hours lost a week</b> (P10 {_v(rng.get('p10'))}, "
                         f"P90 {_v(rng.get('p90'))}) across {_v(b['people_affected'])} people.</p>")
        else:
            parts.append("<p class='muted'>Diagnostic only: sized in days, not person-hours.</p>")
        parts.append(f"<p class='muted'>Evidence: {escape(b['evidence']['filter'])}</p>")
        mine = [x for x in computed if x["bottleneck"] == b["id"]]
        if mine:
            parts.append("<div class='scroll'><table><tr><th>Fix</th><th>Hours a week P10 / P50 / P90</th>"
                         "<th>Dollars a year P10 / P50 / P90</th><th>Top driver</th><th>Flags</th></tr>")
            for x in mine:
                flags = "".join(f"<span class='flag'>{escape(fl)}</span>" for c in x["components"] for fl in c["flags"])
                parts.append(f"<tr><td>{escape(x['id'] + ' ' + x['name'])}</td><td>{_rng(x['hours_saved_per_week'])}</td>"
                             f"<td>{_rng(x['dollars'], money=True)}</td><td>{escape(x['sensitivity']['top_driver'])}</td>"
                             f"<td>{flags or 'none'}</td></tr>")
            parts.append("</table></div>")
        parts.append("</div>")
    parts.append("<h2>What we couldn't measure</h2><div class='card'><ul>")
    items = [f"{m.get('item', m['kpi'])}: {m['reason']}" for m in f["not_measured"]]
    items += [", ".join(f"{k}={v}" for k, v in g["group"].items()) + ": " + g["status"] for g in f["suppressed_groups"]]
    items += [f"{x['id']} {x['name']}: {x.get('reason', '')}" for x in f["fixes"] if x["status"] != "computed"]
    parts += [f"<li>{escape(i)}</li>" for i in items] or ["<li>Everything in scope was measured.</li>"]
    parts.append("</ul></div><p class='muted'>Savings come from published effect sizes and assumptions, "
                 "not from this data. Only a pilot can confirm them.</p>")
    return _page("Impact findings", "".join(parts))


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'><title>{escape(title)}</title>"
            f"<style>{CSS}</style></head><body><main>{body}</main></body></html>\n")


def manager_view_html(view: Dict[str, Any]) -> str:
    """The existing Phase 4 panel (examples/frontend/phase4-panel.js) with the view inlined, as before."""
    js = PANEL_JS.read_text(encoding="utf-8").replace("export function renderPhase4Panel", "function renderPhase4Panel")
    data = json.dumps(view, indent=2, ensure_ascii=False).replace("</", "<\\/")
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "  <title>Phase 4 manager view demo</title>\n"
            "  <style>body{margin:0;padding:24px 16px;background:#F4F5F7}</style>\n</head>\n<body>\n"
            "  <main id=\"phase4\">Loading Phase 4 results…</main>\n  <script>\n" + js +
            "\nconst PHASE4_VIEW = " + data + ";\n(function () {\n  const target = document.getElementById(\"phase4\");\n"
            "  try {\n    renderPhase4Panel(target, PHASE4_VIEW);\n  } catch (err) {\n"
            "    target.textContent = \"Could not load the Phase 4 results: \" + err;\n  }\n})();\n</script>\n</body>\n</html>\n")
