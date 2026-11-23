# Phase 4 fixes: Veloran Consulting LLC

Scenario A · phase4 0.2.0 · catalog workplace 2026.11.1 · generated 2026-11-23T17:44:29+00:00

## Summary

The 3 recommendations cost $79,520 in year one and save an estimated $589,680 a year, a combined payback of 1.6 months. From year two, ongoing costs are $37,920 a year and the net benefit is about $551,760 a year. At 70% adoption, the 195 gross hours become about 137 effective hours a week: 48% of the 283 hours lost to the bottlenecks in scope.

| Bottleneck | Recommended fixes | Type | Year-one cost | Ongoing (per year) | Hours saved per week | Annual savings | Payback (months) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Staffing blind spots: unplanned bench time and last-minute assignments | Capacity council and bench-to-certification + PSA tool | Process and reskilling; non-AI software | $58,600 | $28,800 | 85 | $257,040 | 2.7 |
| 2. Status reporting repeated across four places and recurring meetings | Meeting and status reset + One system of record | Process; non-AI software | $9,800 | $0 | 75 | $226,800 | 0.5 |
| 3. Timesheets rebuilt from memory at the end of the week | Daily time rule + AI-drafted timesheets | Process; AI tool | $11,120 | $9,120 | 35 | $105,840 | 1.3 |
| Total |  |  | $79,520 | $37,920 | 195 | $589,680 | 1.6 |

Low and high cases for total savings: $285,120 to $965,736 a year; payback 1.0 to 3.8 months.

## BN-1: Staffing blind spots: unplanned bench time and last-minute assignments

129 hours lost a week · 43 people · $557,280 a year · fix category: Staffing and capacity blind spots

|  | Option 1: AI forecasting agent | Option 2: PSA tool | Option 3: Capacity council and bench-to-certification |
| --- | --- | --- | --- |
| Type | AI tool | Non-AI software | Process and reskilling |
| How it solves | An agent in the firm's own CRM predicts roll-offs and demand from pipeline and booking history, then proposes staffing moves for a person to approve | One system holds bookings, roll-offs, skills and pipeline demand on a single timeline, eight weeks out | A 30-minute weekly meeting books the next eight weeks; any unbooked day defaults to a certification plan or a reusable asset |
| Example vendors | Agentforce in the firm's own Salesforce org; AI features in PSA suites | Kantata; Rocketlane; BigTime; Certinia | Internal; Salesforce Trailhead and certification exams |
| Upfront cost | $40,000 (internal build and data clean-up) | $26,200 (vendor onboarding $10,000; configuration $12,600; training $3,600) | $3,600 (certification vouchers: 18 certification vouchers x $200 = $3,600) |
| Ongoing cost (per year) | $24,000 (run, monitor and retrain) | $28,800 (licences: 50 seats x $48 a month x 12 = $28,800) | $0 |
| Implementation time | 4 to 6 months | 6 to 8 weeks | 2 weeks |
| Effort and disruption | High: needs 12+ months of clean staffing data | Medium: data migration and new habits for 50 people | Low: one meeting and one rule |
| Est. hours saved per week | 45 (30 to 62) | 60 (40 to 83) | 30 (20 to 41) |
| Est. annual savings | $136,080 ($64,800 to $227,664) | $181,440 ($86,400 to $304,776) | $90,720 ($43,200 to $150,552) |
| Payback (months) | 5.6 | 3.6 | 0.5 |
| Data and AI governance risk | Medium: reads pipeline and staff data; every move needs human sign-off | Low: standard SaaS security review | None |
| Key risks and dependencies | Forecasts are only as good as the staffing history behind them | Adoption; Must sync with the CRM and replace the current time tool | Discipline; savings stall if leaders skip the meeting |
| Status | Deferred | Recommended | Recommended |

**Recommendation.** We recommend Option 3 (Capacity council and bench-to-certification) and Option 2 (PSA tool) together. The PSA makes capacity visible, the council turns it into decisions, and the certification rule gives every unplanned free day a use. Together they save an estimated 85 hours a week ($257,040 a year) for $58,600 in year one, a payback of 2.7 months.

**Options not chosen**

- Option 1: AI forecasting agent: Deferred: an AI forecast needs at least 12 months of clean booking data (current: 0). The recommended PSA tool creates this; revisit once the PSA holds 12 months of bookings.

**How the numbers were worked out**

- hours saved per week: 60 + 30 x (1 - 0.167 overlap) = 84.99 -> 85 h a week
- annual time savings: 85 h x 48 weeks x $90 x 70% adoption = $257,040
- year one cost: PSA tool $55,000 + Capacity council and bench-to-certification $3,600 = $58,600
- payback months: $58,600 / ($257,040 / 12) = 2.7 months

## BN-2: Status reporting repeated across four places and recurring meetings

112 hours lost a week · 40 people · $483,840 a year · fix category: Status reporting repeated across tools and meetings

|  | Option 1: AI meeting notes and status drafts | Option 2: One system of record | Option 3: Meeting and status reset |
| --- | --- | --- | --- |
| Type | AI tool | Non-AI software | Process |
| How it solves | AI joins calls, writes notes and drafts weekly status from transcripts and the work tracker | All delivery work moves into the one tracker the firm already licenses; client reports generate from it; the duplicate tools retire | Recurring internal status meetings end; a five-line written update per project every Friday and one 30-minute weekly risk review replace them |
| Example vendors | Zoom AI Companion; Gemini in Google Meet; Otter; Fireflies | Jira dashboards and a client report template (Jira is already licensed) | Internal; Written-update template |
| Upfront cost | $2,000 (set-up and recording policy) | $7,200 (migration and template build: 80 h x $90 = $7,200) | $2,600 (facilitation and templates) |
| Ongoing cost (per year) | $9,000 (seats: 30 seats x $25 a month x 12 = $9,000) | $0 | $0 |
| Implementation time | 2 weeks | 4 to 6 weeks | 1 week |
| Effort and disruption | Low | Medium: 23 active projects to migrate | Low, if leaders model it |
| Est. hours saved per week | 40 (27 to 55) | 35 (24 to 48) | 50 (34 to 69) |
| Est. annual savings | $120,960 ($58,320 to $201,960) | $105,840 ($51,840 to $176,256) | $151,200 ($73,440 to $253,368) |
| Payback (months) | 1.1 | 0.8 | 0.2 |
| Data and AI governance risk | High: records client calls that carry client data; some states require every party's consent to record | Low | None |
| Key risks and dependencies | Client contracts may bar recording; Notes still need human review; The duplicate tools remain | Clients used to other report formats need a new one | Meetings creep back without a named owner |
| Status | Not recommended now | Recommended | Recommended |

**Recommendation.** We recommend Option 3 (Meeting and status reset) and Option 2 (One system of record) together. The reset frees most of the time at once, and one system of record stops the copying behind the remaining updates. Together they save an estimated 75 hours a week ($226,800 a year) for $9,800 in year one, a payback of 0.5 months.

**Options not chosen**

- Option 1: AI meeting notes and status drafts: Not recommended now: recording client calls needs every party's consent and an approved AI policy first. Conflicts with Meeting and status reset: it would summarize meetings the reset cancels.

**How the numbers were worked out**

- hours saved per week: 50 + 35 x (1 - 0.286 overlap) = 74.99 -> 75 h a week
- annual time savings: 75 h x 48 weeks x $90 x 70% adoption = $226,800
- year one cost: One system of record $7,200 + Meeting and status reset $2,600 = $9,800
- payback months: $9,800 / ($226,800 / 12) = 0.5 months

## BN-3: Timesheets rebuilt from memory at the end of the week

42 hours lost a week · 42 people · $181,440 a year · fix category: Timesheets rebuilt from memory

|  | Option 1: AI-drafted timesheets | Option 2: PSA time module | Option 3: Daily time rule |
| --- | --- | --- | --- |
| Type | AI tool | Non-AI software | Process |
| How it solves | An app drafts each person's day from calendar, tracker and document activity; the person edits and submits. Drafts are visible only to the employee. | Time entry moves into the PSA chosen for staffing, next to bookings, with approvals in one place | Log time before leaving each day: a 4:30 p.m. chat nudge, a 15-minute end-of-day calendar block, and on-time rates shared by team, never by name |
| Example vendors | Timely; Memtime; Clockify | Same vendor as the PSA tool | Internal; Slack or Teams reminders |
| Upfront cost | $2,000 (set-up and pilot) | $0 ($0 extra once the PSA tool is approved) | $0 |
| Ongoing cost (per year) | $9,120 (licences: 38 seats x $20 a month x 12 = $9,120) | $0 ($0 extra once the PSA tool is approved) | $0 |
| Implementation time | 3 weeks | Arrives with the PSA, weeks 6 to 8 | 1 week |
| Effort and disruption | Low: install plus a privacy briefing | Low: new screen, same habit | Low |
| Est. hours saved per week | 25 (17 to 34) | 12 (8 to 16) | 15 (10 to 21) |
| Est. annual savings | $75,600 ($36,720 to $124,848) | $36,288 ($17,280 to $58,752) | $45,360 ($21,600 to $77,112) |
| Payback (months) | 1.8 | Immediate (no cost) | Immediate (no cost) |
| Data and AI governance risk | Medium: reads calendar and app activity. Mitigated by on-device processing, employee-only drafts and no manager access to raw activity | Low | None |
| Key risks and dependencies | Staff may fear surveillance; Must export to the PSA if one is chosen | Depends on the PSA decision; Moves the same manual entry to a new screen | The habit fades without the nudge and team-level feedback |
| Status | Recommended | Follow-on, no extra savings | Recommended |

**Recommendation.** We recommend Option 3 (Daily time rule) and Option 1 (AI-drafted timesheets) together. The rule fixes when time is logged; the drafts fix the effort and the forgetting. Together they save an estimated 35 hours a week ($105,840 a year) for $11,120 in year one, a payback of 1.3 months.

**Options not chosen**

- Option 2: PSA time module: Follow-on to AI-drafted timesheets: Once the PSA is live, drafts flow into it instead of the old time tool; no extra savings are counted, to avoid double counting. It arrives with the PSA tool chosen for BN-1 (Staffing blind spots).

**How the numbers were worked out**

- hours saved per week: 25 + 15 x (1 - 0.333 overlap) = 35.01 -> 35 h a week
- annual time savings: 35 h x 48 weeks x $90 x 70% adoption = $105,840
- year one cost: AI-drafted timesheets $11,120 + Daily time rule $0 = $11,120
- payback months: $11,120 / ($105,840 / 12) = 1.3 months

## Before any AI tool goes live

- Approve a one-page AI acceptable-use policy (for AI-drafted timesheets)
- Security and contract review of the timesheet tool, including no-training terms (for AI-drafted timesheets)
- Drafts stay employee-only; managers never see raw activity (for AI-drafted timesheets)

## Upside not counted in the savings

| Source | Estimate (per year) | Basis |
| --- | --- | --- |
| Half of unplanned bench becomes billable | $216,144 | 28.5 hours a week x 48 weeks x $158 realized rate |
| Asana and Smartsheet licences retired | $14,400 | Current licence invoices |
| Unlogged billable hours captured | $184,627 | 70% of 1,669 unlogged hours x $158 realized rate |
| Total | $415,171 |  |

## Bottlenecks not solved in this run

- BN-4 Tool switching and notifications: outside the top 3
- BN-5 Searching for past work: outside the top 3
- BN-6 Proposals rebuilt from scratch: outside the top 3
- BN-7 Data-migration rework: outside the top 3
