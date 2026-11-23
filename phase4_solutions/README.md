# Phase 4: Fixes (step 9)

Phase 4 takes each bottleneck from step 7, with what step 8 says it costs. It returns:

- **Three fix options** for each bottleneck: an AI tool, other software, and a process or reskilling change.
- **The numbers for each option:** cost, hours saved, annual savings and payback, in low, base and high cases.
- **A recommended mix** and the reason each other option was not chosen.
- **Program totals**, the governance steps needed before any AI tool goes live, and a calculation trail behind every number.

```
step 7 bottlenecks ─┐                                    ┌─► manager view (frontend)       manager_view.json
                    ├─► adapter ─► engine ─► connectors ─┤
step 8 ROI (costs) ─┘   (any field names)                └─► step 10 report + scorecard     phase5_report.md/.json, scorecard.json
```

**Ready to connect.** Phase 3 and Phase 5 don't have to change. Read **[INTEGRATION.md](INTEGRATION.md)** to wire it in, and **[CODEX_PROMPTS.md](CODEX_PROMPTS.md)** to put it on a GitHub branch and let Codex do the wiring.

Requirements: Python 3.10+, standard library only. `pip install anthropic` is needed only for the optional Claude-written text.

## Quick start

```bash
cd phase4_solutions
python -m pytest -q                                                    # 50 tests
python -m phase4 pipeline examples/phase3/veloran_step7_8.json \
       --profile veloran --expected veloran --out-dir phase4_out       # Phase 3 output -> every Phase 5 file
python -m phase4 adapt examples/phase3/veloran_bottlenecks.csv --profile veloran   # how Phase 3 fields map
python -m phase4 serve --port 8040                                     # HTTP service for any language
```

## Ways to use it

| From | Call |
| --- | --- |
| Python | `from phase4.pipeline import run_pipeline` then `run_pipeline(step7_8_output, profile="veloran")` |
| Any language, no server | `python -m phase4 pipeline - --profile veloran --json < step7_8_output.json` |
| Any language, HTTP | `POST http://127.0.0.1:8040/phase4/pipeline` with body `{"phase3": ..., "profile": "veloran"}` |
| Just the engine | `from phase4 import run_phase4` then `run_phase4(phase4_input)` (format: `contracts/phase4_input.schema.json`) |

A bad input exits with code 2 or returns HTTP 422, with a list of errors that name each field. A broken catalog exits with code 3.

## How it decides

1. **Match.** Each bottleneck is matched to a fix category: the category id from step 7, a phrase like "timesheet" in its name, or the profile's `category_map`.
2. **Price each fix** with the reference reports' formulas:
   - hours saved = effect share × hours lost per week
   - savings = hours × working weeks × loaded rate × adoption, plus recovered deal margin in scenario B
   - year-one cost = upfront cost + first-year ongoing cost
   - payback = year-one cost ÷ (savings ÷ 12)
3. **Set aside fixes that cannot go ahead yet:**
   - a missing planning number (`needs_input`)
   - a missing prerequisite (`deferred`)
   - high governance risk (`on_hold`)
   - a dependency on a fix nobody chose, or a conflict with a chosen fix (`blocked`)
4. **Try every mix** of up to 2 eligible fixes. Overlapping savings are discounted, never double counted.
5. **Pick a winner.** It is the mix with the **highest first-year net benefit** that pays back within 12 months. Every other option gets a written reason.
6. **Add up the program**, collect the AI go-live gates and the upside not counted. Groups under 5 people are always left out.

## Checked against the reference reports

| Report | Result |
| --- | --- |
| Veloran v1.0 (the Dec 9 demo case) | 75 of 75 numbers match: every option's cost, hours, savings and payback, the recommended mixes and the totals |
| Corlander & Vale v1.0 | 75 of 75 |
| Veloran, sent as differently shaped Phase 3 output (camelCase JSON with a separate ROI list, and CSV) | 75 of 75 through the adapter |

**What "calibrated" means.** The catalog's effect shares and cost models are set so the formulas reproduce both reports. The choosing rules are the same for every client. They defer Veloran's AI forecasting tool for missing data, hold AI meeting notes for recording consent, and drop Corlander & Vale's AI email assistant because the portal makes it redundant.

## Option B (acquisition)

`phase4/data/catalog_acquisition.json` covers stalled deals and shared customers, with three fixes each. `profiles/acquisition_example.json` and `examples/phase3/acquisition_step7_8.json` show the shapes.

**All B prices and effect sizes are placeholders** and are flagged in the output. When the Salesforce exports exist, step 8 should send:

- `deals_lost_per_year`, `avg_deal_value` and `contribution_margin` for each bottleneck
- the profile's `sales_reps`, `approval_seats` and capabilities

## Add or change a fix

The catalogs are JSON files in `phase4/data/`. Each category has:

- `anchors`: phrases strong enough to match on their own
- `keywords`: phrases that need two matches
- `fixes`: the option list, in order

Each fix has `costs`, `effect`, `governance`, `requires` and `conflicts_with`. Run `python -m phase4 catalog` to list them. `pytest` checks the catalog for mistakes.

## Claude-written text (optional)

`python -m phase4 run ... --ai-text`, with `ANTHROPIC_API_KEY` set, has Claude write each recommendation paragraph. The model defaults to `claude-sonnet-5-5`; change it with `PHASE4_CLAUDE_MODEL`. Claude never produces numbers. Any number in its paragraph that isn't in the computed facts brings back the template text.

## Files

```
INTEGRATION.md          how to connect Phase 3 and Phase 5 (start here)
CODEX_PROMPTS.md        GitHub branch steps and copy-paste Codex prompts
AGENTS.md               rules for coding agents working in this folder
ROOT_AGENTS_SNIPPET.md  block to paste into the repo's root AGENTS.md
phase4/engine.py        run_phase4(): the engine and program totals
phase4/pipeline.py      run_pipeline(): Phase 3 output -> every Phase 5 output
phase4/connectors/      phase3.py (adapter), phase5.py (report, evidence, scorecard), frontend.py (manager view)
phase4/server.py        HTTP service (python -m phase4 serve)
phase4/selection.py     eligibility, mixes, the choice and the reasons
phase4/pricing.py       costs, hours, savings, payback, overlaps, traces
phase4/data/            fix catalogs (A: workplace, B: acquisition)
profiles/               client facts Phase 3 doesn't have (Veloran, Corlander & Vale, option B starter)
contracts/              JSON Schemas (input, output, manager view, profile) and phase4.d.ts
examples/               Phase 3 output examples, frontend (React and plain JS), Node and Python callers
samples/, reference/    engine inputs and outputs, and the numbers printed in the two reference reports
tests/                  50 tests
```
