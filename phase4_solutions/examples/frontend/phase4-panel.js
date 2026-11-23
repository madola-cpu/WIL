// @ts-check
// Plain-JavaScript renderer for the Phase 4 manager view. No framework, no build step:
//   import { renderPhase4Panel } from "./phase4-panel.js";
//   renderPhase4Panel(document.getElementById("phase4"), managerView);
// All text goes in with textContent, so data can never inject HTML.

/** @typedef {import("../../contracts/phase4").ManagerView} ManagerView */
/** @typedef {import("../../contracts/phase4").BottleneckCard} BottleneckCard */
/** @typedef {import("../../contracts/phase4").OptionCard} OptionCard */
/** @typedef {import("../../contracts/phase4").Metric} Metric */
/** @typedef {import("../../contracts/phase4").Tone} Tone */

/** @type {Record<Tone, [string, string]>} background, text */
const TONES = {
  positive: ["#E7F5EC", "#15803D"],
  info: ["#E6EEF9", "#2F5DB3"],
  neutral: ["#EEF0F3", "#4B5563"],
  warning: ["#FDF1E3", "#B45309"],
  negative: ["#FDE8E8", "#B42318"],
  attention: ["#FDF6D8", "#8A6100"],
};

const CSS = `
.p4{font:15px/1.45 system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color:#111827;max-width:1100px}
.p4 h2{font-size:22px;margin:0 0 4px}.p4 h3{font-size:17px;margin:0}
.p4-sub{color:#4B5563;margin:0 0 16px}
.p4-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:18px}
.p4-kpi{background:#fff;border:1px solid #CBD5E1;border-radius:12px;padding:12px 14px}
.p4-kpi strong{display:block;font-size:24px;color:#2F5DB3}.p4-kpi span{color:#4B5563;font-size:13px}
.p4-card{background:#fff;border:1px solid #CBD5E1;border-radius:12px;padding:16px;margin-bottom:14px}
.p4-meta{color:#4B5563;font-size:13px;margin:2px 0 10px}
.p4-rec{background:#F4F7FC;border-radius:10px;padding:10px 12px;margin-bottom:10px}
.p4-rec p{margin:6px 0 0}
.p4-opt{display:grid;grid-template-columns:1fr auto;gap:4px 12px;padding:10px 0;border-top:1px solid #E5E7EB}
.p4-opt small{color:#4B5563;grid-column:1/-1}
.p4-nums{color:#111827;font-size:13px;white-space:nowrap}
.p4-badge{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600;margin-left:8px}
.p4-gov li{margin:3px 0}
`;

/**
 * @param {string} tag
 * @param {{className?: string, title?: string}} [attrs]
 * @param {(Node | string | null | undefined)[]} [children]
 */
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  if (attrs.className) node.className = attrs.className;
  if (attrs.title) node.title = attrs.title;
  for (const child of children) {
    if (child === null || child === undefined) continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

/** @param {Metric} m */
function tip(m) {
  return [m.math, m.range ? `Range: ${m.range.display}` : ""].filter(Boolean).join("\n");
}

/** @param {string} label @param {Metric} m */
function kpi(label, m) {
  return el("div", { className: "p4-kpi", title: tip(m) }, [el("strong", {}, [m.display]), el("span", {}, [label])]);
}

/** @param {OptionCard} o */
function option(o) {
  const [bg, fg] = TONES[o.badge.tone];
  const badge = el("span", { className: "p4-badge", title: o.badge.meaning }, [o.badge.label]);
  badge.style.background = bg;
  badge.style.color = fg;
  const nums = el("span", { className: "p4-nums", title: [tip(o.annual_savings), tip(o.payback)].join("\n") }, [
    `${o.annual_savings.display} a year · ${o.year_one_cost.display} year one · payback ${o.payback.display}`,
  ]);
  return el("div", { className: "p4-opt" }, [
    el("div", {}, [el("strong", {}, [o.label]), badge, el("div", { className: "p4-meta" }, [o.type_label])]),
    nums,
    el("small", {}, [o.badge.status === "recommended" ? o.how_it_solves : o.reason]),
  ]);
}

/** @param {BottleneckCard} b */
function card(b) {
  const meta = [`Loses ${b.hours_lost_per_week.display}`, `${b.people_affected} people`];
  if (b.annual_cost) meta.push(`${b.annual_cost.display} a year`);
  const rec = b.recommendation
    ? el("div", { className: "p4-rec" }, [
        el("strong", {}, [`Recommended: ${b.recommendation.names.join(" + ")}`]),
        el("p", {}, [b.recommendation.summary]),
      ])
    : el("div", { className: "p4-rec" }, ["No recommendation yet. ", ...b.notes]);
  return el("article", { className: "p4-card" }, [
    el("h3", {}, [`${b.rank}. ${b.title}`]),
    el("div", { className: "p4-meta" }, [meta.join(" · ")]),
    rec,
    ...b.options.map(option),
  ]);
}

/**
 * Render the Phase 4 manager view into a container.
 * @param {HTMLElement} container
 * @param {ManagerView} view
 */
export function renderPhase4Panel(container, view) {
  container.replaceChildren();
  container.classList.add("p4");
  const style = document.createElement("style");
  style.textContent = CSS;
  const h = view.headline;
  container.append(
    style,
    el("h2", {}, [`${view.client_name}: recommended fixes`]),
    el("p", { className: "p4-sub" }, [view.summary]),
    el("div", { className: "p4-kpis" }, [
      kpi("year-one cost", h.year_one_cost),
      kpi("saved a year", h.annual_savings),
      kpi("to pay back", h.payback),
      kpi(`won back a week (${h.share_of_lost_time.display} of lost time)`, h.hours_won_back_per_week),
    ]),
    ...view.bottlenecks.map(card),
  );
  if (view.governance_actions.length) {
    container.append(
      el("article", { className: "p4-card p4-gov" }, [
        el("h3", {}, ["Before any AI tool goes live"]),
        el("ul", {}, view.governance_actions.map((g) => el("li", {}, [`${g.action} (${g.for.join(", ")})`]))),
      ]),
    );
  }
}
