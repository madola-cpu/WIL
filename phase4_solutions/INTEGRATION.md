# Connecting Phase 4 to Phase 3 and Phase 5

Phase 4 is ready to plug in. Phase 3 (steps 7 and 8) and Phase 5 (the manager view and the step 10 report) do not have to change how they work. You only add one call between them.

```
 Phase 3 (already built)          Phase 4 (this folder)                          Phase 5 (already built)
 ───────────────────────          ─────────────────────────────────────          ───────────────────────
 step 7 bottlenecks  ─┐                                                        ┌─► manager view (frontend)
                      ├─► adapter ─► engine ─► connectors ─────────────────────┤     manager_view.json
 step 8 ROI (costs)  ─┘   (reads any        (fixes, savings,                   └─► step 10 report + scorecard
                          field names)       payback, reasons)                       phase5_report.md / .json
                             ▲                                                       scorecard.json
                     client profile
                     (profiles/veloran.json)
```

One call does all of it:

```python
from phase4.pipeline import run_pipeline
result = run_pipeline(step7_8_output, profile="veloran", expected="veloran")
```

Or from the command line, with a file or stdin:

```bash
python -m phase4 pipeline step7_8_output.json --profile veloran --expected veloran --out-dir phase4_out
```

The pipeline writes these files into `phase4_out/`:

| File | Who uses it | What it is |
| --- | --- | --- |
| `manager_view.json` | Frontend | Headline numbers, one card per bottleneck, badges and the math for hover text. Every number already has display text. |
| `phase5_report.md` | Step 10 | The Phase 4 sections of the consulting report, laid out like the Veloran report |
| `phase5_report.json` | Step 10 | The same sections as typed blocks (heading, paragraph, table, list, checklist), for a report builder |
| `scorecard.json` | Step 10 | How many reference-report numbers we match (75 of 75 on Veloran) |
| `phase4_output.json` | Anyone | The full Phase 4 result: every option, status, reason and calculation |
| `phase4_input.json` | Debugging | What the adapter built from the Phase 3 output |
| `mapping_report.json` | Debugging | Which Phase 3 field fed which Phase 4 field, and what came from the profile |

---

## 1. Connect Phase 3 (steps 7 and 8)

### What Phase 3 needs to contain

You don't need to rename anything. The adapter recognises common names in any style: `peopleAffected`, `people_affected` and `People affected` all work. It needs three things for each bottleneck:

| Needed | Names it recognises (any case or style) |
| --- | --- |
| A name | `name`, `title`, `bottleneck`, `label` |
| People affected | `employees_affected`, `people_affected`, `affected`, `headcount`, `employees` (a number, never a list of people) |
| Hours lost per week | `hours_lost_per_week`, `total_hours_per_week`, `weekly_hours_lost`, `hours_per_week`, `hours_lost`, `hours`, or `hours_per_person` × people |

It uses these if they're there: `id`, `rank`, `priority_score`, `annual_cost`, `feasibility`, `departments`/`teams`, `root_causes`, `evidence`, `category`. For option B it also reads `deals_lost_per_year`, `avg_deal_value` and `contribution_margin`.

**Ranges.** Any of these work for low, base and high cases:

- `{"low", "base", "high"}`
- `{"min", "expected", "max"}`
- `[low, base, high]`
- separate `hours_low` / `hours_high` fields

**Where the list lives.** It finds the list on its own: at the top level, under `bottlenecks`, under `step7.bottlenecks`, and so on. If step 8 keeps its numbers in a separate list (`roi`, `step8.roi`, ...), those are matched to bottlenecks by id or name. Step 8's priced numbers win.

**CSV works too:** one row per bottleneck, with headers like `Bottleneck, People affected, Hours lost per week`.

### The client profile

Phase 3 doesn't know some facts Phase 4 needs: headcount, loaded rate, AI policy status, recording consent, planning volumes. These live in `profiles/<client>.json`. The Veloran one is filled in from the reference report. For a new client, copy it and change the values (`contracts/client_profile.schema.json` documents every field).

Values found in the Phase 3 output always win over the profile, except anything under `"overrides"`.

### Check the mapping before wiring anything

```bash
python -m phase4 adapt path/to/your_step7_8_output.json --profile veloran
```

It prints, for every bottleneck, which of your fields fed which Phase 4 field. It also lists anything it didn't use.

**If it can't find a field,** add an explicit path to the profile:

```json
"field_mapping": {
  "bottlenecks_path": "results.week49.bottlenecks",
  "roi_path": "results.week49.costs",
  "fields": {"hours_lost_per_week": "loss.weekly_hours", "employees_affected": "n_staff"}
}
```

**If a bottleneck matches no fix category,** map it in the profile's `category_map`. It takes a word from the name, an id or the exact name:

```json
"category_map": {"staffing": "staffing_visibility", "timesheet": "time_capture"}
```

`python -m phase4 catalog --scenario A` lists the category ids.

### Three ways to call it from the backend

**Python backend:** import the function.

```python
from phase4.pipeline import run_pipeline           # put phase4_solutions on the path, or: pip install -e phase4_solutions
result = run_pipeline(step7_8_output, profile="veloran")
save_for_frontend(result["manager_view"])           # your code
save_for_report(result["report"], result["report_markdown"])
```

**Any language, no server:** pipe JSON through the CLI. `examples/node/phase4_client.mjs` does this for Node.

```bash
python -m phase4 pipeline - --profile veloran --json < step7_8_output.json > phase4_result.json
```

**Any language, over HTTP:**

```bash
python -m phase4 serve --port 8040            # add --cors-origin http://localhost:3000 for a browser frontend
```

```bash
curl -s -X POST http://127.0.0.1:8040/phase4/pipeline \
  -H "Content-Type: application/json" \
  -d '{"phase3": <step 7-8 output>, "profile": "veloran", "expected": "veloran"}'
```

| Endpoint | Body | Returns |
| --- | --- | --- |
| `GET /health` | — | Engine version, catalogs, profiles |
| `POST /phase4/pipeline` | `{phase3, profile, mapping?, expected?}` | Everything (same as the CLI `--json`) |
| `POST /phase4/from-phase3` | `{phase3, profile, mapping?}` | `{phase4_input, mapping_report}` |
| `POST /phase4/run` | A Phase 4 input | The Phase 4 output (`?view=manager` for the manager view) |
| `POST /phase4/report` | A Phase 4 output | `{report, report_markdown}` |
| `POST /phase4/manager-view` | A Phase 4 output | The manager view |
| `GET /schemas/{input,output,manager-view,phase3-profile}` | — | The JSON Schemas |

**Errors** come back as JSON:

- **400:** the body isn't valid JSON.
- **422:** the input can't be used. The body is `{"errors": [...], "mapping_report": {...}}`, and each error names the field.

The service binds to `127.0.0.1` by default. It's for local use and the demo, not the open internet.

---

## 2. Connect Phase 5

### The manager view (frontend)

Read `manager_view.json`, or `result.manager_view` from the pipeline or the HTTP service. The frontend only binds fields and never formats or calculates anything:

```jsonc
{
  "headline": {
    "annual_savings": {"value": 589680, "display": "$589,680", "range": {"display": "$285,120 to $965,736"}},
    "payback":        {"value": 1.6,    "display": "1.6 months"}
    // ...
  },
  "bottlenecks": [{
    "title": "Staffing blind spots",
    "recommendation": {"names": ["Capacity council and bench-to-certification", "PSA tool"], "summary": "We recommend ..."},
    "options": [{
      "label": "Option 1: AI forecasting agent",
      "badge": {"label": "Deferred", "tone": "warning"},
      "reason": "Deferred: an AI forecast needs at least 12 months of clean booking data ...",
      "annual_savings": {"display": "$136,080", "math": "45 h x 48 weeks x $90 x 70% adoption = $136,080"}
    }]
  }]
}
```

**Types:** `contracts/phase4.d.ts`, for example `import type { ManagerView } from ".../contracts/phase4"`. The Python tests check real output against these types.

**Ready-made views you can copy:**

- `examples/frontend/Phase4Panel.tsx` is a React component: `<Phase4Panel view={managerView} />`.
- `examples/frontend/phase4-panel.js` is plain JavaScript: `renderPhase4Panel(element, managerView)`. Open `examples/frontend/demo.html` through `python -m http.server` to see it.

**Badge tones:**

| Tone | Statuses |
| --- | --- |
| `positive` | recommended |
| `info` | follow-on |
| `neutral` | not chosen |
| `warning` | deferred, not now |
| `negative` | blocked |
| `attention` | needs input |

**Hover text:** put each number's `math` field in a tooltip. That's the "evidence behind every number".

### The step 10 report and scorecard

`phase5_report.json` (or `result.report`) has sections in report order. Each one says where it belongs:

| Section id | Goes in the report under | Contains |
| --- | --- | --- |
| `recommended-actions` | Executive summary | Numbered actions with year-one cost, savings and payback |
| `<bottleneck id>-solution-options` | That bottleneck's section | The options table (the same rows as the Veloran report), the recommendation, and why the others weren't chosen |
| `recommendations-and-roi` | Recommendations and ROI | Summary, ROI table with totals, range, upside not counted, formulas |
| `ai-governance` | AI governance | AI tools table and the governance checklist |
| `calculation-workbook` | Appendix: calculation workbook | Every calculation and its result |
| `evidence` | Appendix: evidence map | Every Phase 4 number with how it was worked out |

Each section has `blocks`:

- `{"type": "paragraph", "text", "label"?}`
- `{"type": "table", "columns", "rows"}`
- `{"type": "list", "ordered", "items"}`
- `{"type": "checklist", "items"}`
- `{"type": "heading", "level", "text"}`

Text can contain `**bold**`.

If the report is Markdown, paste `phase5_report.md` as is, or render single sections with `phase4.connectors.phase5.render_markdown`.

**Scorecard:** `scorecard.json` holds one row per reference number, with what the report printed, what Phase 4 produced, and whether they match. Its `markdown` field is a ready table. Bottlenecks are matched by fix category, so Phase 3 can use any ids.

---

## 3. Run it for the Dec 9 demo

```bash
cd phase4_solutions
python -m pytest -q                                                   # 50 tests, about 2 seconds
python -m phase4 pipeline examples/phase3/veloran_step7_8.json \
       --profile veloran --expected veloran --out-dir phase4_out      # swap in the real step 7-8 output
python -m phase4 serve --port 8040 --cors-origin http://localhost:3000  # if the frontend calls over HTTP
```

**What the demo should show:**

- $79,520 in year one and $589,680 a year in savings
- A payback of 1.6 months
- 137 hours a week won back (48% of the lost time)
- A scorecard of 75 of 75

## Troubleshooting

| Message | Fix |
| --- | --- |
| `could not find a list of bottlenecks` | Set `field_mapping.bottlenecks_path` in the profile |
| `hours lost per week not found` | Map the field in `field_mapping.fields`, or make step 8 send hours (a total, or per person) |
| `company headcount not found` | Add `company.employees_total` to the profile |
| `matches no fix category` | Add the bottleneck to `category_map`, or add a category to `phase4/data/catalog_*.json` |
| Numbers differ from the report | Run `python -m phase4 adapt ...` and check the rate, weeks and hours it picked up |
| Browser says CORS | Start the service with `--cors-origin <your frontend URL>` |
| `Address already in use` | Use another port, e.g. `--port 8041` |

## Where things are

| Path | What |
| --- | --- |
| `phase4/pipeline.py` | `run_pipeline()` and `write_pipeline_files()` |
| `phase4/connectors/phase3.py` | The Phase 3 adapter, `from_phase3()` |
| `phase4/connectors/phase5.py` | Report blocks, Markdown, evidence index, scorecard |
| `phase4/connectors/frontend.py` | `manager_view()` |
| `phase4/server.py` | The HTTP service |
| `profiles/` | Client profiles (Veloran, Corlander & Vale, option B starter) |
| `contracts/` | JSON Schemas and `phase4.d.ts` |
| `examples/phase3/` | Example Phase 3 outputs in different shapes (JSON with a separate ROI list, CSV, option B) |
| `examples/frontend/`, `examples/node/`, `examples/python/` | Ready-to-copy connections |
