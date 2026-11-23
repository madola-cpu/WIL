# Put Phase 4 on GitHub, then let Codex wire it in

## Part 1: Create the branch and add the files

Pick one of the three ways below. After any of them, the branch should contain:

```
<repo root>/
  phase4_solutions/                 <- this folder
  .github/workflows/phase4-tests.yml
```

### Way A: GitHub website (nothing to install)

1. **Create the branch.** Open the team repo on GitHub, click the branch menu (it says `main`), type `phase4_solutions`, and choose **Create branch phase4_solutions from main**.
2. **Unzip** `phase4_solutions.zip` on your computer.
3. **Upload the folder.** With the new branch selected, click **Add file → Upload files** and drag in the whole `phase4_solutions` folder. Write the message "Add Phase 4 (fixes) with Phase 3 and Phase 5 connectors" and choose **Commit directly to the phase4_solutions branch**.
4. **Add the test workflow.** Click **Add file → Create new file** and name it `.github/workflows/phase4-tests.yml`. Paste in the contents of that file from the zip, then commit. Folders starting with a dot are often hidden when you drag, which is why this file goes in separately.
5. **Open a pull request** from `phase4_solutions` into `main`. Don't merge until your teammates have looked.

### Way B: Command line

```bash
git clone https://github.com/madola-cpu/WIL.git && cd WIL          # skip if you already have it
git checkout main && git pull
git checkout -b phase4_solutions
# unzip phase4_solutions.zip here, so ./phase4_solutions and ./.github/workflows/phase4-tests.yml exist
(cd phase4_solutions && python -m pytest -q)      # 50 passed
git add phase4_solutions .github/workflows/phase4-tests.yml
git commit -m "Add Phase 4 (fixes) with Phase 3 and Phase 5 connectors"
git push -u origin phase4_solutions
```

If GitHub refuses to push the workflow file, your login token is missing the `workflow` permission. Add that file on the website instead (Way A, step 4).

### Way C: Codex CLI on your computer

Unzip into the repo root, run `codex` in a terminal there, and paste **Prompt 0**.

---

## Part 2: Prompts for Codex

**Codex cloud:** choose the team repo and the `phase4_solutions` branch, then paste one prompt per task.

**Codex CLI:** run `codex` from the repo root.

Each prompt tells Codex to read `phase4_solutions/AGENTS.md` first. Codex only picks up that file on its own when it works inside the folder.

Optional: paste the block from `ROOT_AGENTS_SNIPPET.md` into the repo's root `AGENTS.md`, so every Codex task knows about Phase 4.

### Prompt 0: add and check Phase 4 (Codex CLI only)

```text
The folder phase4_solutions/ and the file .github/workflows/phase4-tests.yml were just unzipped into this repo.
Read phase4_solutions/AGENTS.md. Then:
1. Create a branch phase4_solutions from main (git checkout main && git pull && git checkout -b phase4_solutions).
2. Run: cd phase4_solutions && python -m pytest -q   (expect 50 passed)
3. Run: python -m phase4 check samples/veloran_input.json --expected veloran   (expect 75 of 75)
4. If both pass, commit phase4_solutions/ and .github/workflows/phase4-tests.yml with the message
   "Add Phase 4 (fixes) with Phase 3 and Phase 5 connectors" and push the branch.
Do not change any file inside phase4_solutions/. If a check fails, stop and show me the output.
```

### Prompt 1: connect Phase 3 (steps 7 and 8) to Phase 4

```text
Read phase4_solutions/AGENTS.md and phase4_solutions/INTEGRATION.md (section 1) first.
Goal: feed our existing step 7 and step 8 output into Phase 4 WITHOUT changing how Phase 3 works.
1. Find the code that produces the step 7 (bottlenecks) and step 8 (ROI / costs) output. Tell me the files and show
   the shape of the output.
2. Save one real example of that output as phase4_solutions/examples/phase3/our_step7_8.json
   (team totals only, never names or per-person data).
3. Run: cd phase4_solutions && python -m phase4 adapt examples/phase3/our_step7_8.json --profile veloran
   If a field is not found or a bottleneck has no category, fix it ONLY in phase4_solutions/profiles/veloran.json
   (field_mapping, category_map). Do not edit phase4_solutions/phase4/ and do not change Phase 3's output.
4. Where Phase 3 finishes, call Phase 4 once:
   - Python code: from phase4.pipeline import run_pipeline, write_pipeline_files
     result = run_pipeline(output, profile="veloran"); write_pipeline_files(result, "<our output folder>/phase4")
   - Other languages: run `python -m phase4 pipeline - --profile veloran --json` with the output on stdin
     (see phase4_solutions/examples/node/phase4_client.mjs), or call the HTTP service (python -m phase4 serve).
   Put phase4_solutions on the import path (or pip install -e phase4_solutions). Add a flag or env var to switch it off.
5. Add a test that runs the pipeline on our_step7_8.json and asserts no mapping errors and at least one recommendation.
6. Run the Phase 4 tests (cd phase4_solutions && python -m pytest -q) and our own tests; all must pass.
Done = one call connects Phase 3 to Phase 4, the mapping report has no errors, all tests pass. Summarize the changes.
```

### Prompt 2: connect Phase 4 to the manager view (frontend)

```text
Read phase4_solutions/AGENTS.md and phase4_solutions/INTEGRATION.md (section "The manager view") first.
Goal: show Phase 4 results in our existing manager view without breaking current pages.
1. Find the manager-view frontend code: framework, components, and where it gets its data today.
2. Load the Phase 4 manager view the same way the frontend already gets data: from the manager_view.json the pipeline
   writes, from our backend API, or from POST /phase4/pipeline on the Phase 4 service.
3. Use the ManagerView types from phase4_solutions/contracts/phase4.d.ts (import or copy; do not hand-write new ones).
4. Show: the headline numbers; one card per bottleneck with the recommended fixes and the summary; every option with
   its badge (label and tone), reason, savings, year-one cost and payback; each number's `math` as a tooltip;
   and governance_actions. Start from phase4_solutions/examples/frontend/Phase4Panel.tsx (React) or
   phase4-panel.js (plain JS) and match our existing styles.
5. Never calculate or reformat numbers in the frontend. Use the `display` fields.
6. Test with phase4_solutions/examples/frontend/sample_manager_view.json, then run the frontend build, lint and tests.
Done = the manager view shows the sample results, the build passes, existing pages are unchanged.
```

### Prompt 3: connect Phase 4 to the step 10 report and scorecard

```text
Read phase4_solutions/AGENTS.md and phase4_solutions/INTEGRATION.md (section "The step 10 report and scorecard").
Goal: put Phase 4's sections into our step 10 consulting report and add the scorecard.
1. Find the step 10 report code and how it builds sections.
2. Input: result["report"] (typed blocks) or phase5_report.json / phase5_report.md from the pipeline. Each section has
   `report_section` saying where it belongs: Executive summary, Bottleneck N, Recommendations and ROI, AI governance,
   or an appendix.
3. Insert each section in that place, rendering blocks (paragraph, table, list, checklist, heading; text may contain
   **bold**) with the report's existing styles. Keep the calculation workbook and evidence sections.
4. Scorecard: show result["scorecard"] (or scorecard.json): matched of checks, score_pct and the rows table.
5. Do not change Phase 4 numbers or wording in the report code; if something reads wrong, tell me instead.
6. Build the report from: python -m phase4 pipeline examples/phase3/veloran_step7_8.json --profile veloran
   --expected veloran. Check that $79,520 (year one), $589,680 (a year), 1.6 months (payback) and 75 of 75 appear.
   Run all tests.
```

### Prompt 4: one command for the Dec 9 demo

```text
Read phase4_solutions/AGENTS.md. Create ONE command for the Dec 9 demo that:
1. runs our steps 7 and 8 on the Veloran data,
2. runs Phase 4: python -m phase4 pipeline <step 7-8 output> --profile veloran --expected veloran --out-dir <folder>,
3. builds the step 10 report and refreshes the data the manager view reads,
4. prints the scorecard line at the end (it must say 75 of 75).
Use a Makefile target or npm script if the repo already uses one, and document it in the root README.
It must work from a fresh clone with Python 3.10+ (and Node only if the frontend needs it).
```

### Prompt 5: review before merging

```text
Review all changes on this branch against phase4_solutions/AGENTS.md and report problems with file and line:
- cd phase4_solutions && python -m pytest -q passes, and
  python -m phase4 check samples/veloran_input.json --expected veloran prints 75 of 75.
- No Phase 4 formulas, selection rules or catalog numbers changed.
- No personal or per-person data is passed into Phase 4 (team totals only).
- Any new or renamed output field is also in contracts/*.schema.json and contracts/phase4.d.ts.
- Phase 3 and Phase 5 code changed only to call Phase 4 or to display its output.
```

---

## Part 3: Message for your teammates

> Phase 4 is on the `phase4_solutions` branch and ready to connect. You don't need to change what your code outputs.
>
> **Backend (steps 7–8):** Phase 4 reads your output as it is. Run `python -m phase4 adapt <your output file> --profile veloran` to see how your fields map. One call connects it: `run_pipeline(output, profile="veloran")`.
>
> **Frontend:** read `manager_view.json`. The types are in `contracts/phase4.d.ts`, and there are React and plain-JS examples in `examples/frontend/`.
>
> **Step 10:** `phase5_report.md` / `phase5_report.json` are laid out like the Veloran report, and `scorecard.json` shows 75 of 75.
>
> Instructions are in `phase4_solutions/INTEGRATION.md`. If you'd like Codex to do the wiring, the prompts are in `CODEX_PROMPTS.md`.
