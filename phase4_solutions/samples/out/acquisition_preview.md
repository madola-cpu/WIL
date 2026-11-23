# Phase 4 fixes: Acquisition sample: Acquirer Co. and Target Co. (synthetic)

Scenario B · phase4 0.2.0 · catalog acquisition 2026.11.1-starter · generated 2026-11-23T17:44:29+00:00

## Summary

The 2 recommendations cost $83,560 in year one and save an estimated $257,668 a year, a combined payback of 3.9 months. From year two, ongoing costs are $29,280 a year and the net benefit is about $228,388 a year. At 70% adoption, the 45 gross hours become about 32 effective hours a week: 44% of the 72 hours lost to the bottlenecks in scope.

| Bottleneck | Recommended fixes | Type | Year-one cost | Ongoing (per year) | Hours saved per week | Annual savings | Payback (months) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Stalled deals waiting on approvals | Stage exit rules and a weekly stalled-deal review + One approval workflow with response targets | Process; non-AI software | $34,120 | $17,280 | 24 | $145,184 | 2.8 |
| 2. Shared customers worked by both teams | Rules of engagement, a conflict desk and cross-sell training + One account master and territory rules | Process and reskilling; non-AI software | $49,440 | $12,000 | 21 | $112,484 | 5.3 |
| Total |  |  | $83,560 | $29,280 | 45 | $257,668 | 3.9 |

Low and high cases for total savings: $106,068 to $470,739 a year; payback 2.1 to 10.9 months.

## BN-B1: Stalled deals waiting on approvals

40.8 hours lost a week · 34 people · $389,904 a year · fix category: Stalled deals and slow approvals

|  | Option 1: AI deal-risk alerts | Option 2: One approval workflow with response targets | Option 3: Stage exit rules and a weekly stalled-deal review |
| --- | --- | --- | --- |
| Type | AI tool | Non-AI software | Process |
| How it solves | Predictive scoring reads stage history and activity, flags deals that have gone quiet, slipped their close date or wait on an approval, and drafts the next step for the owner | One approval matrix for both companies; discount, pricing and legal approvals route automatically, can be approved from chat, and escalate after 24 hours | Clear exit criteria for every stage, a 14-day no-activity flag, a 24-hour approval target and a 30-minute weekly review of every stalled deal |
| Example vendors | Agentforce Sales and Einstein pipeline insights (Salesforce); Oracle Deal Advisor; Pega deal-risk scoring | Salesforce Advanced Approvals or Revenue Cloud; DealHub; Slack workflow approvals | Internal; CRM list views and reports already licensed |
| Upfront cost | $3,400 (set-up and field mapping: 40 h x $85 = $3,400) | $14,800 (approval matrix and configuration $6,800; implementation partner $8,000) | $2,040 (rules design and manager briefing: 24 h x $85 = $2,040) |
| Ongoing cost (per year) | $24,000 (licences: 40 seats x $50 a month x 12 = $24,000) | $17,280 (licences: 48 seats x $30 a month x 12 = $17,280) | $0 |
| Implementation time | 4 to 6 weeks | 6 to 8 weeks | 2 weeks |
| Effort and disruption | Medium: needs clean stage history in one place | Medium: both companies must agree one approval matrix | Low: one meeting and a shared list |
| Est. hours saved per week | 10 (6 to 14) | 16 (10 to 23) | 12 (8 to 17) |
| Est. deals recovered per year | 2.9 (1.1 to 5.5) | 3.4 (1.3 to 6.4) | 2 (0.8 to 3.7) |
| Est. annual savings | $75,482 ($30,195 to $136,460) | $100,439 ($41,348 to $182,323) | $65,554 ($28,290 to $117,561) |
| Payback (months) | 4.4 | 3.8 | 0.4 |
| Data and AI governance risk | Medium: reads opportunity and activity data; a person decides every action | Low: standard security review | None |
| Key risks and dependencies | Alerts get ignored without a weekly review; Two orgs mean two data models until they are joined | Leaders must agree who approves what across both companies; Exceptions creep back into email | The review turns into a status read-out unless it ends in decisions |
| Status | Not chosen | Recommended | Recommended |

**Recommendation.** We recommend Option 3 (Stage exit rules and a weekly stalled-deal review) and Option 2 (One approval workflow with response targets) together. The workflow routes and times every approval; the weekly review deals with the stalls a workflow can't see. Together they save an estimated 24 hours a week and recover about 4.8 deals a year, worth $145,184 a year in time and margin, for $34,120 in year one, a payback of 2.8 months.

**Options not chosen**

- Option 1: AI deal-risk alerts: The best mix that includes it (AI deal-risk alerts + One approval workflow with response targets) nets $93,796 in year one, against $111,064 for the recommended mix.

**How the numbers were worked out**

- hours saved per week: 16 + 12 x (1 - 0.3 overlap) = 24.4 -> 24 h a week
- annual time savings: 24 h x 48 weeks x $85 x 70% adoption = $68,544
- year one cost: One approval workflow with response targets $32,080 + Stage exit rules and a weekly stalled-deal review $2,040 = $34,120
- payback months: $34,120 / ($145,184 / 12) = 2.8 months
- annual deal margin: 14 deals lost x combined recovery share x 70% adoption = 4.8 deals x $42,000 x 38% margin = $76,640

## BN-B2: Shared customers worked by both teams

30.8 hours lost a week · 28 people · $253,344 a year · fix category: Shared customers worked by both teams

|  | Option 1: AI account matching across both CRMs | Option 2: One account master and territory rules | Option 3: Rules of engagement, a conflict desk and cross-sell training |
| --- | --- | --- | --- |
| Type | AI tool | Non-AI software | Process and reskilling |
| How it solves | Matches the same customer across both companies' records despite different names and domains, flags collisions before anyone reaches out, and suggests one owner for a person to confirm | Connect or merge the two CRM orgs so every customer has one account record, one owner and one territory, with both companies' open deals visible on it | Written rules say who owns a shared account, a referral split rewards both teams for cross-selling, a 30-minute weekly desk settles conflicts, and each team learns the other's offers |
| Example vendors | Salesforce Data Cloud identity resolution; Leadspace account matching | Salesforce Enterprise Territory Management; MuleSoft or Salesforce Connect for org-to-org sync; Org merge with a Salesforce partner | Internal; Compensation plan update; Cross-training sessions |
| Upfront cost | $5,100 (data mapping and match-rule tuning: 60 h x $85 = $5,100) | $28,600 (integration build and data migration $13,600; implementation partner $15,000) | $8,840 (rules and referral-split design $2,040; cross-sell training $6,800) |
| Ongoing cost (per year) | $18,000 (subscription) | $12,000 (integration licence) | $0 |
| Implementation time | 4 to 6 weeks | 10 to 14 weeks | 3 weeks |
| Effort and disruption | Medium: two customer databases to map | High: two orgs, two data models and every rep's accounts | Medium: compensation rules must change |
| Est. hours saved per week | 11 (7 to 15) | 14 (8 to 19) | 9 (6 to 13) |
| Est. deals recovered per year | 1.7 (0.6 to 3.4) | 2.2 (0.8 to 4.5) | 1.4 (0.5 to 2.8) |
| Est. annual savings | $58,229 ($23,258 to $105,741) | $75,734 ($28,290 to $137,520) | $48,048 ($19,721 to $89,852) |
| Payback (months) | 4.8 | 6.4 | 2.2 |
| Data and AI governance risk | Medium: reads customer records from both companies; merges need human approval | Low: standard security review | None |
| Key risks and dependencies | False matches; Matching alone does not settle who owns the account | Long project; collisions continue until it is live; Ownership disputes surface during the merge | Rules fail if leaders make exceptions for big accounts |
| Status | Not chosen | Recommended | Recommended |

**Recommendation.** We recommend Option 3 (Rules of engagement, a conflict desk and cross-sell training) and Option 2 (One account master and territory rules) together. The account master shows who owns what; the rules settle what a system can't. Together they save an estimated 21 hours a week and recover about 3.3 deals a year, worth $112,484 a year in time and margin, for $49,440 in year one, a payback of 5.3 months.

**Options not chosen**

- Option 1: AI account matching across both CRMs: The best mix that includes it (AI account matching across both CRMs + Rules of engagement, a conflict desk and cross-sell training) nets $59,066 in year one, against $63,044 for the recommended mix.

**How the numbers were worked out**

- hours saved per week: 14 + 9 x (1 - 0.25 overlap) = 20.75 -> 21 h a week
- annual time savings: 21 h x 48 weeks x $85 x 70% adoption = $59,976
- year one cost: One account master and territory rules $40,600 + Rules of engagement, a conflict desk and cross-sell training $8,840 = $49,440
- payback months: $49,440 / ($112,484 / 12) = 5.3 months
- annual deal margin: 8 deals lost x combined recovery share x 70% adoption = 3.3 deals x $42,000 x 38% margin = $52,508
