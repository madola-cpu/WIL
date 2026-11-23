// React version of the Phase 4 manager view. Drop it into the existing frontend and pass it the
// manager view (from the backend, from manager_view.json, or from POST /phase4/pipeline).
//
//   <Phase4Panel view={managerView} />
//
// Styling uses the same class names as phase4-panel.js; restyle freely.
import type { BottleneckCard, ManagerView, Metric, OptionCard, Tone } from "../../contracts/phase4";

const TONES: Record<Tone, { background: string; color: string }> = {
  positive: { background: "#E7F5EC", color: "#15803D" },
  info: { background: "#E6EEF9", color: "#2F5DB3" },
  neutral: { background: "#EEF0F3", color: "#4B5563" },
  warning: { background: "#FDF1E3", color: "#B45309" },
  negative: { background: "#FDE8E8", color: "#B42318" },
  attention: { background: "#FDF6D8", color: "#8A6100" },
};

function tip(m: Metric): string {
  return [m.math, m.range ? `Range: ${m.range.display}` : ""].filter(Boolean).join("\n");
}

function Kpi({ label, metric }: { label: string; metric: Metric }) {
  return (
    <div className="p4-kpi" title={tip(metric)}>
      <strong>{metric.display}</strong>
      <span>{label}</span>
    </div>
  );
}

function OptionRow({ option }: { option: OptionCard }) {
  return (
    <div className="p4-opt">
      <div>
        <strong>{option.label}</strong>
        <span className="p4-badge" style={TONES[option.badge.tone]} title={option.badge.meaning}>
          {option.badge.label}
        </span>
        <div className="p4-meta">{option.type_label}</div>
      </div>
      <span className="p4-nums" title={`${tip(option.annual_savings)}\n${tip(option.payback)}`}>
        {option.annual_savings.display} a year · {option.year_one_cost.display} year one · payback {option.payback.display}
      </span>
      <small>{option.badge.status === "recommended" ? option.how_it_solves : option.reason}</small>
    </div>
  );
}

function Bottleneck({ card }: { card: BottleneckCard }) {
  const meta = [`Loses ${card.hours_lost_per_week.display}`, `${card.people_affected} people`];
  if (card.annual_cost) meta.push(`${card.annual_cost.display} a year`);
  return (
    <article className="p4-card">
      <h3>
        {card.rank}. {card.title}
      </h3>
      <div className="p4-meta">{meta.join(" · ")}</div>
      <div className="p4-rec">
        {card.recommendation ? (
          <>
            <strong>Recommended: {card.recommendation.names.join(" + ")}</strong>
            <p>{card.recommendation.summary}</p>
          </>
        ) : (
          <span>No recommendation yet. {card.notes.join(" ")}</span>
        )}
      </div>
      {card.options.map((o) => (
        <OptionRow key={o.option_id} option={o} />
      ))}
    </article>
  );
}

export function Phase4Panel({ view }: { view: ManagerView }) {
  const h = view.headline;
  return (
    <section className="p4">
      <h2>{view.client_name}: recommended fixes</h2>
      <p className="p4-sub">{view.summary}</p>
      <div className="p4-kpis">
        <Kpi label="year-one cost" metric={h.year_one_cost} />
        <Kpi label="saved a year" metric={h.annual_savings} />
        <Kpi label="to pay back" metric={h.payback} />
        <Kpi label={`won back a week (${h.share_of_lost_time.display} of lost time)`} metric={h.hours_won_back_per_week} />
      </div>
      {view.bottlenecks.map((b) => (
        <Bottleneck key={b.id} card={b} />
      ))}
      {view.governance_actions.length > 0 && (
        <article className="p4-card p4-gov">
          <h3>Before any AI tool goes live</h3>
          <ul>
            {view.governance_actions.map((g) => (
              <li key={g.action}>
                {g.action} ({g.for.join(", ")})
              </li>
            ))}
          </ul>
        </article>
      )}
    </section>
  );
}

/** Fetch the manager view from the Phase 4 service (python -m phase4 serve). */
export async function fetchManagerView(
  phase3: unknown,
  profile = "veloran",
  baseUrl = "http://127.0.0.1:8040",
): Promise<ManagerView> {
  const res = await fetch(`${baseUrl}/phase4/pipeline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phase3, profile }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error((body.errors ?? [body.error]).join("\n"));
  return body.manager_view as ManagerView;
}
