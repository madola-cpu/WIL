# Snippet for the repo's root AGENTS.md

Codex reads AGENTS.md files from the repo root down to the folder it is working in. A task that runs from the repo root, such as wiring Phase 3 code in another folder, will not see `phase4_solutions/AGENTS.md`.

Paste the block below into the root `AGENTS.md`. If the repo has none, create one with this block.

---

```markdown
## Phase 4 (step 9: fixes) lives in phase4_solutions/

- Before touching Phase 4 or wiring it to other phases, read phase4_solutions/AGENTS.md and phase4_solutions/INTEGRATION.md.
- Phase 3 -> Phase 4: call phase4.pipeline.run_pipeline(step7_8_output, profile="<client>") on what steps 7-8 already produce;
  fix field-name mismatches in phase4_solutions/profiles/<client>.json, not by changing Phase 3.
- Phase 4 -> Phase 5: the frontend reads result["manager_view"] (types: phase4_solutions/contracts/phase4.d.ts);
  step 10 reads result["report"] / result["report_markdown"] and result["scorecard"].
- Tests: cd phase4_solutions && python -m pytest -q   (must stay green; Veloran check must stay 75 of 75)
```
