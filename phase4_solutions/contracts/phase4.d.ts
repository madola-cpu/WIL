// TypeScript types for the Phase 4 data a frontend or a JS backend reads.
// Matches contracts/manager_view.schema.json and the report/pipeline shapes in phase4/connectors.
// Import with:  import type { ManagerView, PipelineResult } from "<path>/contracts/phase4";

export type Tone = "positive" | "info" | "neutral" | "warning" | "negative" | "attention";
export type OptionStatus =
  | "recommended"
  | "not_chosen"
  | "follow_on"
  | "deferred"
  | "on_hold"
  | "blocked"
  | "needs_input";
export type FixType = "ai_tool" | "software" | "process" | "reskilling";
export type Risk = "none" | "low" | "medium" | "high";

/** A number ready to show: raw value, display text, optional range and calculation. */
export interface Metric {
  value: number | null;
  display: string;
  range?: { low: number | null; high: number | null; display: string };
  /** How the number was worked out, e.g. "85 h x 48 weeks x $90 x 70% adoption = $257,040". */
  math?: string;
}

export interface Badge {
  status: OptionStatus;
  label: string;
  tone: Tone;
  meaning: string;
}

export interface SequenceStep {
  step: number;
  option_id: string;
  name: string;
  time_to_live: string;
}

export interface OptionCard {
  option_id: string;
  number: number;
  label: string;
  name: string;
  type: FixType;
  type_label: string;
  badge: Badge;
  reason: string;
  other_reasons: string[];
  how_it_solves: string;
  vendors: string[];
  upfront_cost: Metric;
  ongoing_cost_per_year: Metric;
  year_one_cost: Metric;
  hours_saved_per_week: Metric;
  annual_savings: Metric;
  payback: Metric;
  implementation: string;
  effort: string;
  governance: { risk: Risk; label: string; is_ai: boolean; go_live_gates: string[] };
  confidence: string;
}

export interface RecommendationCard {
  option_ids: string[];
  names: string[];
  type_summary: string;
  summary: string;
  hours_saved_per_week: Metric;
  annual_savings: Metric;
  year_one_cost: Metric;
  payback: Metric;
  sequence: SequenceStep[];
}

export interface BottleneckCard {
  id: string;
  rank: number;
  title: string;
  full_name: string;
  category: string | null;
  people_affected: number;
  hours_lost_per_week: Metric;
  annual_cost: Metric | null;
  recommendation: RecommendationCard | null;
  options: OptionCard[];
  notes: string[];
}

export interface ManagerView {
  view_version: string;
  client_name: string;
  scenario: "A" | "B";
  generated_at: string;
  engine: string;
  headline: {
    year_one_cost: Metric;
    annual_savings: Metric;
    net_benefit_year_one: Metric;
    payback: Metric;
    hours_won_back_per_week: Metric;
    share_of_lost_time: Metric;
  };
  summary: string;
  bottlenecks: BottleneckCard[];
  not_in_scope: { id: string; title: string; reason: string }[];
  governance_actions: { action: string; for: string[] }[];
  upside_not_counted: {
    total: Metric;
    items: { label: string; value: number; display: string; basis: string }[];
  };
  warnings: string[];
  badge_legend: Badge[];
}

// ------------------------------------------------------------------ step 10 report
export type ReportBlock =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string; label?: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "checklist"; items: string[] }
  | { type: "table"; columns: string[]; rows: string[][] };

export interface ReportSection {
  id: string;
  title: string;
  /** Which section of the consulting report this belongs in, e.g. "Recommendations and ROI". */
  report_section: string;
  bottleneck_id?: string;
  blocks: ReportBlock[];
}

export interface Phase5Report {
  report_version: string;
  title: string;
  client_name: string;
  scenario: "A" | "B";
  generated_at: string;
  engine: string;
  sections: ReportSection[];
  warnings: string[];
}

export interface Scorecard {
  reference: string;
  checks: number;
  matched: number;
  score_pct: number;
  passed: boolean;
  rows: { where: string; expected: unknown; got: unknown; ok: boolean }[];
  markdown: string;
}

export interface MappingReport {
  found: { bottlenecks_at: string; bottleneck_count: number; roi_at?: string; roi_matched?: number };
  client: Record<string, string>;
  bottlenecks: {
    id: string;
    name: string;
    fields: Record<string, string>;
    category: { value: string | null; from: string; matched_keywords: string[] };
    added_from_profile: string[];
    ignored_fields: string[];
  }[];
  notes: string[];
  errors: string[];
  scenario?: "A" | "B";
  engine_warnings?: string[];
}

/** POST /phase4/pipeline or `python -m phase4 pipeline - --json`. */
export interface PipelineResult {
  pipeline_version: string;
  /** Full shapes: contracts/phase4_input.schema.json and phase4_output.schema.json. */
  phase4_input: Record<string, unknown>;
  mapping_report: MappingReport;
  phase4_output: Record<string, unknown>;
  manager_view: ManagerView;
  report: Phase5Report;
  report_markdown: string;
  scorecard: Scorecard | null;
}

/** 422 error body from the HTTP service. */
export interface Phase4Error {
  errors: string[];
  mapping_report?: MappingReport;
}
