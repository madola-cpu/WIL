# AGENTS.md: Phase 4 (step 9, "Fixes")

These instructions are for coding agents (Codex and others) working in this folder.

## What this folder is

Phase 4 of the Team Tom AI consultant. It takes priced bottlenecks from Phase 3 (step 7 finds them, step 8 prices them). For each one it returns:

- AI, software, process and reskilling options, with cost, savings and payback
- a recommended mix
- the reasons behind each choice

Its output feeds Phase 5: the manager view (frontend) and the step 10 report and scorecard. Read `INTEGRATION.md` before wiring anything.

## Commands (run from this folder)

```bash
python -m pytest -q                       # must stay green: 50 tests
python -m phase4 check samples/veloran_input.json --expected veloran          # must print 75 of 75
python -m phase4 pipeline examples/phase3/veloran_step7_8.json --profile veloran --expected veloran --out-dir /tmp/p4
python -m phase4 adapt <phase3 output file> --profile veloran                 # shows how Phase 3 fields map
(cd examples/frontend && npx -y -p typescript tsc -p .)                       # type-check the frontend examples
```

## Rules

- **Python 3.10+, standard library only** at runtime. `anthropic` is optional; `pytest` and `jsonschema` are for tests.
- **Do not change** formulas in `phase4/pricing.py`, the selection rules in `phase4/selection.py`, or numbers in `phase4/data/catalog_*.json` unless asked. The reference tests reproduce the Veloran and Corlander & Vale reports exactly (75 of 75 each). If a requested change moves a number, explain why and update `reference/` only when the reference report itself changed.
- **The contracts are the API** between teammates: `contracts/*.schema.json` and `contracts/phase4.d.ts`. If you add or rename an output field, update the schema, the `.d.ts` and the tests in the same change. Never remove a field the frontend or step 10 may read.
- **Connect, don't rewrite.** To link Phase 3, call `phase4.pipeline.run_pipeline()` or `phase4.connectors.from_phase3()` on what steps 7 and 8 already produce. Fix field-name mismatches in `profiles/<client>.json` (`field_mapping`, `category_map`), not in the adapter and not by changing Phase 3's output.
- **Client facts live in profiles.** Headcount, rate, capabilities and volumes go in `profiles/<client>.json`. Don't hard-code them in Python.
- **Privacy.** Phase 4 works on team totals only. Never pass lists of people or per-person data into Phase 4. Groups under 5 people are dropped on purpose.
- **Numbers never come from a language model.** Optional Claude text goes through the number guard in `phase4/narrative.py`; keep it that way.
- Keep the folder self-contained: paths resolve relative to `phase4_solutions/`, so the folder can be moved as a unit.

## Where things are

- `phase4/engine.py` has `run_phase4()`. `phase4/pipeline.py` has `run_pipeline()`.
- `phase4/connectors/` holds the adapters: `phase3.py` is the input side; `phase5.py` and `frontend.py` are the output side.
- `phase4/server.py` is the HTTP service (`python -m phase4 serve`).
- Tests are in `tests/`. Reference numbers are in `reference/`. Example Phase 3 outputs are in `examples/phase3/`.
