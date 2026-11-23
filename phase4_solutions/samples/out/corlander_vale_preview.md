# Phase 4 fixes: Corlander & Vale CPAs

Scenario A · phase4 0.2.0 · catalog workplace 2026.11.1 · generated 2026-11-23T17:44:29+00:00

## Summary

The 3 recommendations cost $319,900 in year one and save an estimated $981,120 a year, a combined payback of 3.9 months. From year two, ongoing costs are $230,660 a year and the net benefit is about $750,460 a year. At 70% adoption, the 365 gross hours become about 256 effective hours a week: 43% of the 598 hours lost to the bottlenecks in scope.

| Bottleneck | Recommended fixes | Type | Year-one cost | Ongoing (per year) | Hours saved per week | Annual savings | Payback (months) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Client documents chased and re-requested by hand | Intake desk and document deadline + Client portal with automatic reminders | Process; non-AI software | $172,960 | $128,160 | 140 | $376,320 | 5.5 |
| 2. Returns and workpapers waiting in review, with rework | Tiered review and review-ready checklist + Review queues in the portal | Reskilling and process; non-AI software | $39,600 | $20,000 | 100 | $268,800 | 1.8 |
| 3. Source documents keyed into tax software by hand | Import-first standard and training + AI document extraction | Reskilling; AI tool | $107,340 | $82,500 | 125 | $336,000 | 3.8 |
| Total |  |  | $319,900 | $230,660 | 365 | $981,120 | 3.9 |

Low and high cases for total savings: $526,080 to $1,429,632 a year; payback 2.7 to 8.4 months.

## BN-1: Client documents chased and re-requested by hand

240.8 hours lost a week · 86 people · $924,672 a year · fix category: Client documents chased by hand

|  | Option 1: AI follow-up assistant | Option 2: Client portal with automatic reminders | Option 3: Intake desk and document deadline |
| --- | --- | --- | --- |
| Type | AI tool | Non-AI software | Process |
| How it solves | AI inside the email client drafts follow-up emails from each client thread and summarizes long threads; staff still send and track them | Every request becomes a tracked list in a portal; clients upload against each item; reminders go out automatically until the list is complete | One intake desk sends one combined request list per client, logs receipts and chases on a fixed schedule; anything incomplete on the deadline is extended by rule |
| Example vendors | Microsoft 365 Copilot Business (if the firm runs Microsoft 365) | Karbon (Business plan); TaxDome; Suralink for audit request lists | Internal; Engagement-letter clause; Standard request lists |
| Upfront cost | $3,000 (set-up and prompt library) | $38,400 (vendor onboarding $12,000; configuration $12,000; training $14,400) | $6,400 (request-list templates, engagement-letter wording and desk training: 80 h x $80 = $6,400) |
| Ongoing cost (per year) | $15,120 (seats: 60 seats x $21 a month x 12 = $15,120) | $128,160 (licences (annual list price): 120 seats x $89 a month x 12 = $128,160) | $0 |
| Implementation time | 2 weeks | 6 to 8 weeks | 3 weeks |
| Effort and disruption | Low | Medium: 120 staff and their clients learn a new portal | Medium: clients must hear the deadline in their engagement letters, and partners must hold it |
| Est. hours saved per week | 25 (19 to 30) | 100 (75 to 120) | 70 (53 to 84) |
| Est. annual savings | $67,200 ($36,480 to $97,920) | $268,800 ($144,000 to $391,680) | $188,160 ($101,760 to $274,176) |
| Payback (months) | 3.2 | 7.4 | 0.4 |
| Data and AI governance risk | Medium: reads client email that holds confidential data; needs the AI policy and consent language first | Low: standard security review | None |
| Key risks and dependencies | Drafts better emails but keeps no list, so nothing is tracked | Client adoption; Often the largest licence cost in the program | Clients who miss the cut-off; Partners making exceptions |
| Status | Not chosen | Recommended | Recommended |

**Recommendation.** We recommend Option 3 (Intake desk and document deadline) and Option 2 (Client portal with automatic reminders) together. The intake desk owns the chase, and the portal does the remembering. Together they save an estimated 140 hours a week ($376,320 a year) for $172,960 in year one, a payback of 5.5 months.

**Options not chosen**

- Option 1: AI follow-up assistant: Largely duplicates Client portal with automatic reminders: The portal sends reminders without anyone writing them. The best mix that includes it (AI follow-up assistant + Intake desk and document deadline) nets $190,520 in year one, against $203,360 for the recommended mix.

**How the numbers were worked out**

- hours saved per week: 100 + 70 x (1 - 0.429 overlap) = 140 -> 140 h a week
- annual time savings: 140 h x 48 weeks x $80 x 70% adoption = $376,320
- year one cost: Client portal with automatic reminders $166,560 + Intake desk and document deadline $6,400 = $172,960
- payback months: $172,960 / ($376,320 / 12) = 5.5 months

## BN-2: Returns and workpapers waiting in review, with rework

180.3 hours lost a week · 80 people · $692,352 a year · fix category: Work waiting in review, with rework

|  | Option 1: AI pre-review agent | Option 2: Review queues in the portal | Option 3: Tiered review and review-ready checklist |
| --- | --- | --- | --- |
| Type | AI tool | Non-AI software | Reskilling and process |
| How it solves | An agent reconciles each prepared return with its source documents and the prior year, and flags differences and risky items before a person reviews | Every item carries a status, a named reviewer and a due date; reviewers see their queue and its age; review notes are logged per item | Preparers clear a one-page checklist before review; work is tiered by complexity so trained seniors sign off the simplest third and partners review only the complex third; a monthly debrief fixes the most repeated notes |
| Example vendors | TaxGPT review agent; Thomson Reuters CoCounsel tools | Same vendor as the client portal | Internal checklist; Review-skills courses from professional bodies |
| Upfront cost | $10,000 (pilot set-up and integration testing) | $0 ($0 extra once the client portal is approved) | $19,600 (checklist design $3,200; reviewer training $10,240; outside facilitator $6,160) |
| Ongoing cost (per year) | $36,000 (subscription) | $0 ($0 extra once the client portal is approved) | $20,000 (review stipend: 8 reviewers to train x $2,500 = $20,000) |
| Implementation time | 8 to 10 weeks | Arrives with the client portal | 6 weeks |
| Effort and disruption | Medium: integration and client consent work | Low: same tool, new screens | Medium: senior reviewers must let go of simple work |
| Est. hours saved per week | 45 (34 to 54) | 40 (30 to 48) | 75 (56 to 90) |
| Est. annual savings | $120,960 ($65,280 to $176,256) | $107,520 ($57,600 to $156,672) | $201,600 ($107,520 to $293,760) |
| Payback (months) | 4.6 | Immediate (no cost) | 2.4 |
| Data and AI governance risk | High: full returns and source documents go to a third-party AI; needs signed client consent and a vendor review | Low | None |
| Key risks and dependencies | The vendor may not support the firm's software version; A clean AI check can breed false comfort | Depends on the client portal decision | Partner habits; Quality must hold under peer review |
| Status | Not recommended now | Recommended | Recommended |

**Recommendation.** We recommend Option 3 (Tiered review and review-ready checklist) and Option 2 (Review queues in the portal) together. The checklist cuts second reviews at the source, tiering moves simple work off senior desks, and the queue shows everyone what is waiting. Together they save an estimated 100 hours a week ($268,800 a year) for $39,600 in year one, a payback of 1.8 months.

**Options not chosen**

- Option 1: AI pre-review agent: Not recommended now: full client files would go to a third-party AI, which needs signed client consent and a vendor review first. Deferred: an AI pre-review works best on work that arrives complete through a tracked queue (current: no). The recommended Client portal with automatic reminders creates this; revisit after one season on the portal.

**How the numbers were worked out**

- hours saved per week: 75 + 40 x (1 - 0.375 overlap) = 100 -> 100 h a week
- annual time savings: 100 h x 48 weeks x $80 x 70% adoption = $268,800
- year one cost: Review queues in the portal $0 + Tiered review and review-ready checklist $39,600 = $39,600
- payback months: $39,600 / ($268,800 / 12) = 1.8 months

## BN-3: Source documents keyed into tax software by hand

176.5 hours lost a week · 41 people · $677,760 a year · fix category: Source documents keyed in by hand

|  | Option 1: AI document extraction | Option 2: Import-first standard and training | Option 3: Offshore data-entry partner |
| --- | --- | --- | --- |
| Type | AI tool | Reskilling | Process (outsourcing) |
| How it solves | Software reads scanned documents, bookmarks them, extracts the data and fills the return; the preparer checks flagged fields instead of typing | Everything that can be imported is imported; staff get short training and a one-page import checklist | Scanned documents go to an outsourced team that keys them overnight; staff check the result |
| Example vendors | SurePrep 1040SCAN (Thomson Reuters); Thomson Reuters Ready to Review; GruntWorx | Import features already licensed in the firm's software | US-managed offshore preparation providers |
| Upfront cost | $12,000 (set-up, scanning standards and a pilot) | $12,840 (trainer $3,000; staff training time $9,840) | $8,000 (onboarding and a consent campaign) |
| Ongoing cost (per year) | $82,500 (per-document fee: 2,200 complex returns per year x $37.50 = $82,500) | $0 | $66,000 (per-document fee: 1,650 offshore returns per year x $40 = $66,000) |
| Implementation time | 6 weeks | 3 weeks | 8 weeks plus consent collection |
| Effort and disruption | Medium: new scanning habits and a verification step | Low | High: signed consent from every client in scope; quality control across time zones |
| Est. hours saved per week | 105 (79 to 126) | 35 (26 to 42) | 90 (68 to 108) |
| Est. annual savings | $282,240 ($151,680 to $411,264) | $94,080 ($49,920 to $137,088) | $241,920 ($130,560 to $352,512) |
| Payback (months) | 4.0 | 1.6 | 3.7 |
| Data and AI governance risk | Medium: documents are processed by a vendor; confirm US-only processing, no training on client data and deletion terms | None | High: sending client data outside the US needs each client's signed consent |
| Key risks and dependencies | Scan quality; Per-unit price creep; Staff over-trusting extracted figures | The habit fades without spot checks | Consent refusals; Client perception; Quality |
| Status | Recommended | Recommended | Not recommended now |

**Recommendation.** We recommend Option 2 (Import-first standard and training) and Option 1 (AI document extraction) together. Extraction removes most typing on complex documents; the standard stops anyone typing what already exists as data. Together they save an estimated 125 hours a week ($336,000 a year) for $107,340 in year one, a payback of 3.8 months.

**Options not chosen**

- Option 3: Offshore data-entry partner: Not recommended now: sending client information outside the US needs every client's signed consent first.

**How the numbers were worked out**

- hours saved per week: 105 + 35 x (1 - 0.429 overlap) = 125 -> 125 h a week
- annual time savings: 125 h x 48 weeks x $80 x 70% adoption = $336,000
- year one cost: AI document extraction $94,500 + Import-first standard and training $12,840 = $107,340
- payback months: $107,340 / ($336,000 / 12) = 3.8 months

## Before any AI tool goes live

- Vendor security and contract review: US-only processing, no training on client data, deletion terms (for AI document extraction)
- Client consent for AI processing in engagement letters (for AI document extraction)

## Upside not counted in the savings

| Source | Estimate (per year) | Basis |
| --- | --- | --- |
| Fewer review write-downs | $205,000 | Half of the $410,000 of FY2026 write-downs coded to review rework |
| Less busy-season overtime | $30,500 | Half of the $61,000 of overtime paid in the 2026 season |
| Lower professional turnover | $160,000 | Four fewer departures a year (17.9% toward 13%) x $40,000 replacement cost |
| Total | $395,500 |  |

## Bottlenecks not solved in this run

- BN-4 Status questions answered by hand: outside the top 3
- BN-5 CAS transaction coding and reconciliations: outside the top 3
- BN-6 Audit tie-outs and confirmations by hand: outside the top 3
- BN-7 Bills drafted from WIP by hand: outside the top 3
