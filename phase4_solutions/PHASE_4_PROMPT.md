# Phase 4 prompt: the measured impact engine (workflow steps 4–9)

A standalone brief for a developer or coding agent. It consolidates the team's Phase 4 build prompt (`Claude_Code_Phase4_Prompt-2.md.txt`), the existing `phase4_solutions/` implementation, the architecture paper and the Colab notebook. Where they disagree, **§9 Decisions** records what was chosen and what still needs team approval.

---

## 1. Objective and scope

Build a deterministic engine that reads a company's work data and:

1. checks the data against a contract (§3)
2. measures KPIs per team and role (§4)
3. detects and sizes bottlenecks (§5)
4. estimates what each fix saves, as P10/P50/P90 ranges from published evidence and a seeded Monte Carlo (§6)
5. ranks the fixes and writes the outputs (§7)
6. grades itself against a planted answer key (§8)

**Demo:** Veloran, a fictional 50-person consulting firm, on Dec 9. Its reference report found three bottlenecks: staffing blind spots (129 hours lost a week), status reporting (112) and timesheets rebuilt from memory (42).

**Out of scope for this build:**

- LLM calls of any kind
- trained ML models
- what-if simulation (`engine/simulate.py`) and pilot proof (`engine/prove.py`), which stay as documented stubs
- live connectors
- pm4py

## 2. Context and integration

The team's 5-phase, 10-step workflow:

| Phase | Steps | Status |
| --- | --- | --- |
| 1 | 1–3: timelines, skills, tasks | other teammates |
| 2 | 4–6: measurement, cohorts, lifecycle | **this engine: step 4 KPIs** |
| 3 | 7–8: bottlenecks and their cost | **this engine: steps 7–8, measured** |
| 4 | 9: fixes | existing `phase4/` package (verified 75 of 75 against both reference reports) plus this engine's evidence-based fix ranking |
| 5 | 10: report | existing connectors (`phase4/connectors/phase5.py`, `frontend.py`) |

Rules for the integration:

- **Place it in the existing codebase.** The engine lives in `phase4_solutions/engine/`, beside `phase4/`. Do not change `phase4/`, its catalogs, contracts or reference numbers.
- **Connect, don't rewrite.** The engine writes `phase3_handoff.json`, a step 7–8 file that the existing adapter reads unchanged: `python -m phase4 pipeline <run>/phase3_handoff.json --profile <client>`. That file carries bottleneck name, teams, people affected, hours lost a week as `{low, base, high}`, and evidence.
- **Runtime:** Python 3.10+, standard library only (project rule in `AGENTS.md`). Use pytest and jsonschema for tests only.

## 3. Data contract (§A)

Every file is UTF-8 CSV with a header row.

- Timestamps are ISO 8601 with an offset, such as `2026-09-14T09:30:00-07:00`. Local time means the offset in the timestamp.
- IDs are strings. Each person keeps one `person_id` across all files.
- No names, emails or pay anywhere.

| File | Required | Columns |
| --- | --- | --- |
| `people.csv` | yes | `person_id, team, role, soc_code, weekly_hours` (float), `billable` (true/false) |
| `activity.csv` | yes | `event_id, person_id, start_ts, end_ts, source` (calendar/app/tracker/survey), `work_type`, `recurring`, `internal`; optional `work_item_id, tool` |
| `work_item_events.csv` | for flow KPIs | `event_id, work_item_id, ts, status, state` (active/waiting/done), `tool, team`; optional `person_id` |
| `time_entries.csv` | no | `entry_id, person_id, work_date` (YYYY-MM-DD), `hours, project, entered_ts` |
| `bookings.csv` | no | `booking_id, person_id, project, start_date, end_date, created_ts`; optional `allocation` from 0 to 1 (default 1.0) |
| `client_rates.csv` | no | `role, loaded_rate`. These are client-supplied role rates; when present they replace market rates. |
| `config_overrides.json` | no | Per-dataset overrides of assumptions, such as `{"min_weeks": 2}` for the fixture. Each override is recorded in the outputs. |
| `answer_key.json` | fake data only | See §8 |

`work_type` is one of `client_work, internal_meeting, status_update, admin, timesheet, search, proposal, rework, learning, other`.

**The validator** (`python -m engine.validate <folder>`) fails, showing up to 10 offending rows each, on any of these:

- a missing required column
- an unparseable timestamp, date, number or boolean
- an end before its start
- an unknown `person_id`
- a duplicate ID
- a column named like a name, email, phone, address or pay field, or a cell containing an email address

It warns, without failing, when a `work_type` is unknown, and maps it to `other`. It prints at most 30 lines and exits non-zero on failure.

**Never modify the input folder.**

## 4. KPIs (§B)

Compute KPIs per (team, role, ISO week), per (team, role) and per team.

- Activity rows belong to the ISO week of their local start.
- Weeks means the dataset's observed ISO weeks.
- Use contracted hours (`weekly_hours`) as the denominator where hours are shared.

| # | KPI | Definition |
| --- | --- | --- |
| 1 | `time_share[wt]` | hours of the work type ÷ all logged hours |
| 2 | `hours_per_person_week[wt]` | hours of the work type ÷ (people × weeks) |
| 3 | `internal_meeting_load` | hours of recurring internal `internal_meeting` ÷ contracted hours |
|   | `status_hours` | (those meeting hours + `status_update` hours) per person-week − `allowance_hours` |
| 4 | `duplicate_updates` | mean distinct tools with events, per active work item per week (team) |
| 5 | `wait_time` | median and P90 hours in `waiting` before the next `active`, grouped by the waited-in status (team) |
| 6 | `flow_efficiency` | active time ÷ (done − first event) per work item; median per team |
| 7 | `throughput` | items reaching `done` ÷ (team people × weeks) |
| 8 | `unplanned_bench` | per billable person-week, max(0, weekly_hours − weekly_hours × Σ allocation of the bookings overlapping that week) |
|   | `notice_days` | median of (start_date − created date) |
| 9 | `time_entry_lag_days` | median of (entered date − work date) |
|   | `share_entered_friday_or_later` | share of Monday–Thursday entries entered on or after that ISO week's Friday |
| 10 | `unlogged_share` | Σ over person-days of max(0, client_work hours − entry hours), ÷ client_work hours |
| 11 | `context_switches_per_hour` | tool changes between consecutive `source=app` blocks ÷ app hours. Without app data it is "not measured". |
| 12 | `after_hours_share` | share of activity hours starting outside 08:00–18:00 local, or on weekends. It is a guardrail, never a bottleneck. |

**Privacy:**

- Any group under `min_group_size` (5) is suppressed. It is listed as "not enough data" with no values.
- Per-person values exist in memory only.

## 5. Bottlenecks (§C)

`config/thresholds.json` sets, for each rule:

- the KPI, a comparator (`>` or `<`) and a threshold
- the work type
- the sizing rule
- who counts as affected

Rules are evaluated per team. The teams that trip a rule form one bottleneck record. Its size is the sum over those teams.

| Rule | Detected when | Sized as |
| --- | --- | --- |
| `status_reporting` | `status_hours` > 5% of the team's mean contracted hours | `status_hours` per person-week. Detection and size use the same measure. |
| `timesheets_from_memory` | `share_entered_friday_or_later` > 0.40 | `timesheet` hours per person-week |
| `staffing_blind_spots` | `unplanned_bench` > 1.0 h per billable person-week | bench hours per billable person-week. Only billable people are affected. |
| `flow_delays` | `flow_efficiency` < 0.30, or P90 wait > `p90_wait_days` | a diagnostic only: cycle days and throughput, no person-hours, no fixes |

Each record contains:

- `id, name, kpi, group{teams}, kpi_value, threshold`
- `hours_lost_per_person_week, people_affected, total_hours_lost_per_week`
- `weekly_values` (one per week, for the bootstrap)
- `by_team`
- `by_role`: a role split, suppressed when any role group is under 5
- `evidence`: up to 20 source row IDs, plus the filter text that reproduces them
- `sufficiency`: `ok`, `insufficient_weeks`, `not_measured` or `suppressed_small_group`, plus a reason
- `after_hours_share` of the group

A small team is never part of a record. Recurring external meetings (`internal=false`) never count toward `status_hours`.

## 6. Impact model (§D)

### 6.1 Effect of each fix component: alignment-weighted evidence

Each study *i* in `config/evidence.json` that `applies_to` a component goes through four steps:

1. **Adjusted effect.** `y_i` = effect on the time-reduction scale (a productivity gain g becomes 1 − 1/(1+g)) × `design_discount[design]`.
2. **Sampling error.** `se_i` = the paper's SE, or (ci_high − ci_low)/3.92, or else 1/√n with the flag "se approximated".
3. **Alignment.** `a_i` = (task + people + setting + outcome + tool)/10, each scored 0–2:
   - **task:** 2 if the study task equals the bottleneck's work type; 1 if it is in the same family in `task_families.json`
   - **people:** per affected person, 2 if their soc_code is in `soc_codes`, 1 if its 2-digit major group is in `soc_major_groups`; averaged with lost-hour weights
   - **setting** and **outcome:** the study's tags
   - **tool:** the study's `applies_to` entry
4. **Transfer uncertainty.** `t_i` = √[((1 − a_i)·S)² + (d·age_i)²]. Here:
   - S is `transfer_sd_at_zero_alignment`
   - d is `drift_per_year[kind]`
   - age = run year − `data_year`; the run year is the year of the last observed activity, which keeps reruns identical

Pool the studies:

- Weight: w = 1/(se² + t²)
- Middle: μ = Σwy/Σw
- Sampling variance: V = Σw²se²/(Σw)²
- Shared transfer: T = Σwt/Σw. It is shared, so loose duplicates never narrow the range.
- Between-firm spread: τ² = DerSimonian–Laird on the y_i, with variances se² + t², when k ≥ 3, never below `tau_min`²; otherwise `tau_min`²
- Predictive SD: σ = √(V + T² + τ²). Report μ, σ and the effect's P10/P50/P90 (normal quantiles, capped at 1).

Two special cases:

- **No study applies.** Use the component's `report_estimate` as one entry: design `expert_estimate`, se = `expert_se_share` × estimate, age 0, alignment 0.9. Flag "no matching study".
- **Studies apply and a `report_estimate` exists.** Don't pool the estimate. Report where it falls against P10/P90, and flag it if it is outside ("report assumption above the evidence range").

Output every study with its five scores, a, age, y, se, t and share of weight.

### 6.2 Monte Carlo

Use `monte_carlo.draws` draws (10,000) with a fixed seed. Each bottleneck and each fix gets its own stable sub-seed.

**Draws:**

- **Hours lost, H_b:** bootstrap mean of the bottleneck's weekly totals
- **Effect of each component, e_c:** Normal(μ_c, σ_c), capped at 1. Negative draws are allowed, because a fix can backfire.
- **Adoption, a:** Triangular(low, base, high). One draw per fix, shared by its components.

**Combining:**

- Hours saved = H_b × (1 − Π_c(1 − e_c·a)).
- Several fixes on one bottleneck combine the same way, on shared H_b draws, and are never added.

**Outputs per fix,** each as P10/P50/P90:

- **Hours saved a week:** split by role in proportion to lost hours (subject to suppression)
- **FTE:** hours ÷ the affected group's mean `weekly_hours`
- **Annual hours:** weekly × `weeks_per_year`
- **Dollars:** Σ over roles of annual hours × the role's loaded rate
  - The loaded rate is `mean_hourly_wage` for the role's soc_code (`data/reference/wages.csv`) ÷ `wage_share_of_compensation` (0.70), labeled "market-rate estimate".
  - If the data folder has `client_rates.csv`, use it instead, labeled "client rate".
  - If any affected soc_code has no wage, write "not computed" with the reason. Never guess a wage.
- **Payback months:** year-one cost ÷ (dollars/12), per draw. A draw that saves nothing never pays back. P10 savings pair with P90 payback.
- **Sensitivity:** set each input (H_b, each effect, adoption, wage, weeks) to its P10 and then its P90, holding the others at their medians. Rank the inputs by their swing in the P50 value (dollars if computed, else annual hours) and report the top driver. Fixed inputs have zero swing.
- **Guardrail:** the affected group's `after_hours_share`.

## 7. Prioritization and outputs (§E)

**Ranking:**

- Score = value × confidence ÷ effort.
  - **Value:** P50 annual hours (dollars shown beside it)
  - **Confidence:** P10/P50 of annual hours, clipped to 0–1, halved if the bottleneck's sufficiency is not `ok`
  - **Effort:** low 1, medium 2, high 3
- Ties go to the shorter time to value.
- "React first" is the top 3, each with a one-line templated reason.
- Fixes whose bottleneck was not detected are listed as not applicable.

**Files written to `outputs/<run_id>/`.** The run_id comes from the dataset hash and the seed. There is no wall-clock time in any output.

| File | Content |
| --- | --- |
| `findings.json` | The single file a front end reads: `run_id, data_profile, assumptions_used, bottlenecks, fixes, react_first, not_measured, suppressed_groups, rule_results`. Every number is `{"value", "source"}`. The source is `data`, `evidence:<id>`, `assumption:<key>`, `client:<file>` or `+`-joined combinations for derived numbers. |
| `bottlenecks.json` | The bottleneck records |
| `kpis.csv` | Group-level KPIs only, with suppressed groups omitted and cells made spreadsheet-safe |
| `fixes_ranked.csv` | The ranking |
| `report.md` | A 3-sentence summary, react first, one section per bottleneck (KPI, size, evidence filter, fixes with P10/P50/P90 hours and dollars), what we couldn't measure, an assumptions table and sources. Every number in it must appear in `findings.json`. |
| `phase3_handoff.json` | The step 7–8 file for the existing Phase 4 pipeline (§2) |
| `preview.html` | A self-contained view of `findings.json`, with all text escaped |
| `validation.md` | Only when an answer key is present |

## 8. Validation (§F)

The answer key looks like this:

```json
{"dataset": "...",
 "bottlenecks": [{"id": "B2", "name": "status reporting", "kpi": "status_hours",
   "group": {"teams": ["..."]}, "true_total_hours_lost_per_week": 112, "true_people_affected": 40, "tolerance": 0.15}],
 "traps": [{"kpi": "internal_meeting_load", "group": {"team": "..."}, "reason": "..."}],
 "small_groups": [{"team": "...", "size": 4}]}
```

Write true values in the engine's own units (§5 sizing).

**The scorecard** (`python -m engine.cli score <folder>`) checks five things:

1. **Recovery.** Each key bottleneck is matched on the same KPI with an overlapping group. Total hours and people must each be within the tolerance.
2. **No false alarms.** Nothing is detected on a trap's KPI, or on a KPI built from it, in that group. Extra detections are listed but don't fail.
3. **Suppression.** No small group appears in `kpis.csv`, and each one is listed as suppressed.
4. **Sensitivity.** Every fix has a top driver.
5. **Determinism.** The same seed gives byte-identical `findings.json`.

Validation grades detection and sizing only. Savings can only be graded by a real pilot.

**The mini fixture** (`tests/fixtures/make_mini.py`, seeded) has:

- three teams: A (6 people), B (5) and C (3, which must be suppressed)
- three ISO weeks, with `min_weeks` overridden to 2
- team A planted with 3 status-update hours per person-week, timesheet hours and late time entries
- team B planted with heavy recurring external client meetings, as the trap
- its own `answer_key.json`

## 9. Decisions, exclusions and open items

**Decided** (documented project rules win):

1. **Location and naming.** The prompt's "Phase 4 engine" spans steps 4–9, but the project defines Phase 4 as step 9. It is built as `engine/` inside `phase4_solutions/`, feeding the existing step-9 engine through `phase3_handoff.json`. Nothing in `phase4/` changes.
2. **Standard library only.** There is no pandas, numpy or PyYAML, and config is JSON. The team prompt asked for YAML and pandas, but the existing `AGENTS.md` rule is standard library only.
3. **Adoption range.** It is 0.5/0.7/0.85, from the Veloran reference report and `profiles/veloran.json`. The prompt's starter config said high 0.9.
4. **Run year.** It is the year of the last observed activity, not the wall clock, which keeps reruns identical.
5. **Excluded:**
   - Multi-agent build instructions, `.claude/agents/*` and PROGRESS.md: these are process, not product.
   - A separate SPEC.md: it is merged into this file to avoid two copies of the spec.
   - The optional pm4py `dfg` target (AGPL licence, not needed for the demo).
   - From the notebook and the architecture paper: Qwen/vLLM inference, OCEL export, Splink, Leiden, RAG and license audits. They are beyond the Dec 9 scope or conflict with "no LLM calls".

**Needs team input:**

1. **Which savings figure goes in the demo.** `phase4/` reproduces the reference report's fix effects (for example, timesheets: 40 of 42 hours). The evidence engine pools published studies and flags report assumptions that fall outside the evidence range. Both are shown; the team must pick one for Dec 9.
2. **Wages.** `data/reference/wages.csv` must be built by hand from BLS OEWS May 2025 national estimates (bls.gov/oes), because bls.gov refuses automated download. Until then, dollars are "not computed". Alternatively, supply `client_rates.csv`: Veloran's $90 loaded rate is company-wide, not per role.
3. **Loaded-rate method.** The options are BLS wage ÷ 0.70 (this prompt), ×1.35 (the architecture paper and the notebook) or the client's finance figure ($90, `phase4/`).
4. **`flow_delays.p90_wait_days`.** It is unspecified; the placeholder is 5 days.
5. **Inputs that are missing.** Veloran's fake data (`data/lev/`) doesn't exist yet. `Claude Code Measurement Engine Prompt.md.txt` is empty.
6. **Two pipelines.** The Colab notebook is a parallel pipeline: a different company, input contract and LLM use. Decide which one is the Dec 9 demo path.

## 10. Implementation steps

1. Write config (`config/*.json`) and the contract and validator (`engine/contract.py`, `engine/validate.py`).
2. Write the fixture generator and answer key (`tests/fixtures/make_mini.py`).
3. Write KPIs and bottlenecks (`engine/kpis.py`, `engine/bottlenecks.py`).
4. Write evidence pooling, the Monte Carlo and ranking (`engine/evidence.py`, `engine/impact.py`, `engine/prioritize.py`).
5. Write outputs, the preview, the scorecard and the CLI (`engine/report.py`, `engine/preview.py`, `engine/scorecard.py`, `engine/cli.py`), plus stubs for `simulate.py` and `prove.py`.
6. Write tests (§11), the Makefile, and the README and AGENTS.md updates.
7. Run everything (§11), then run the existing Phase 4 pipeline on the fixture's handoff.

## 11. Acceptance criteria

```bash
cd phase4_solutions
python tests/fixtures/make_mini.py                     # writes tests/fixtures/mini/
python -m engine.validate tests/fixtures/mini          # PASS
python -m engine.cli run tests/fixtures/mini           # writes every §7 file
python -m engine.cli score tests/fixtures/mini         # found 2 of 2, no false alarms, suppression and determinism pass
python -m pytest -q                                    # all green: the existing 50 plus the engine tests
python -m phase4 check samples/veloran_input.json --expected veloran              # still 75 of 75
python -m phase4 pipeline outputs/<run_id>/phase3_handoff.json --profile veloran --out-dir outputs/<run_id>/phase4
```

The engine tests must cover:

- the validator's failure and warning rules
- every D1 test:
  - alignment matches hand-computed values and is stable
  - higher alignment raises a study's weight share and narrows σ
  - a duplicate loose study doesn't narrow σ
  - an older AI study widens σ
  - the fallback and report-assumption flags fire
- the Monte Carlo:
  - the same seed gives identical output
  - fixes and components combine multiplicatively
  - P10 savings pair with P90 payback
  - a missing wage gives "not computed"
- privacy: no suppressed group appears in any output
- every number in `report.md` appears in `findings.json`

## 12. Dependencies and known limitations

- **Dependencies:** Python 3.10+, standard library. pytest and jsonschema for tests.
- **No trained ML.** Savings rest on published effect sizes and assumptions. Only a pilot can grade them.
- **The data is fake.** The demo fixture is synthetic, and real exports need mapping into §3.
- **Evidence entries are copied from the team prompt.** Their SEs are approximated (1/√n) until the papers' SEs are entered.
- **Sensitivity is one-at-a-time.** Wage and weeks have no range, so their swing is 0.
