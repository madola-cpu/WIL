"""Bottleneck detection and sizing (PHASE_4_PROMPT.md section 5).

Rules from config/thresholds.json run per team. Teams that trip a rule form
one bottleneck, sized as the sum over those teams. Suppressed (small) teams are
never evaluated. Per-person lost hours are kept in memory for the evidence
alignment and the role split, and are never written out.
"""
from __future__ import annotations

import operator
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional

from .contract import Config, Dataset
from .kpis import KpiResult

CMP = {">": operator.gt, "<": operator.lt}
SIZING_MEASURE = {"status_hours": "status", "timesheet_hours": "wt:timesheet", "bench_hours": "bench"}
# A detection on one of these KPIs counts as a detection on the KPIs it is built from (trap checks).
KPI_DEPENDS = {"status_hours": ["internal_meeting_load", "hours_per_person_week.status_update"]}


def num(value: Optional[float], source: str, nd: int = 2) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    return {"value": round(float(value), nd), "source": source}


@dataclass
class Bottleneck:
    rule: Dict[str, Any]
    teams: List[str]
    kpi_value: float
    threshold: float
    people_affected: int
    weekly_values: List[float]                      # group total hours lost, one per observed week
    weeks: List[str]
    by_team: List[Dict[str, Any]]
    person_lost: Dict[str, float] = field(repr=False)  # memory only: person_id -> lost hours a week
    role_lost: Dict[str, float] = field(repr=False)    # memory only: role -> lost hours a week
    evidence: Dict[str, Any] = field(default_factory=dict)
    sufficiency: Dict[str, str] = field(default_factory=dict)
    after_hours_share: Optional[float] = None
    mean_weekly_hours: Optional[float] = None
    by_role: List[Dict[str, Any]] = field(default_factory=list)
    by_role_note: str = ""

    @property
    def id(self) -> str:
        return self.rule["id"]

    @property
    def diagnostic(self) -> bool:
        return self.rule["sizing"] == "diagnostic"

    @property
    def total_hours(self) -> float:
        return sum(self.weekly_values) / len(self.weekly_values) if self.weekly_values else 0.0

    def to_record(self) -> Dict[str, Any]:
        thr_src = "assumption:thresholds." + self.id
        rec: Dict[str, Any] = {
            "id": self.id, "name": self.rule["name"], "kpi": self.rule["kpi"], "group": {"teams": self.teams},
            "kpi_value": num(self.kpi_value, "data", 4), "threshold": num(self.threshold, thr_src, 4),
            "comparator": self.rule["comparator"], "diagnostic": self.diagnostic,
            "by_team": self.by_team, "evidence": self.evidence, "sufficiency": self.sufficiency,
            "after_hours_share": num(self.after_hours_share, "data", 4),
        }
        if not self.diagnostic:
            rec.update({
                "hours_lost_per_person_week": num(self.total_hours / self.people_affected
                                                  if self.people_affected else 0.0, "data"),
                "people_affected": num(self.people_affected, "data", 0),
                "total_hours_lost_per_week": num(self.total_hours, "data"),
                "weekly_values": [{"week": w, "value": num(v, "data")} for w, v in zip(self.weeks, self.weekly_values)],
                "by_role": self.by_role, "by_role_note": self.by_role_note,
            })
        return rec


@dataclass
class Detection:
    bottlenecks: List[Bottleneck]
    rule_results: List[Dict[str, Any]]
    not_measured: List[Dict[str, str]]


def _threshold(rule: Dict[str, Any], kt: Dict[str, Any]) -> Optional[float]:
    if "threshold_share_of_contracted" in rule:
        mwh = kt.get("mean_weekly_hours")
        return rule["threshold_share_of_contracted"] * mwh if mwh else None
    return rule["threshold"]


def detect(ds: Dataset, cfg: Config, k: KpiResult) -> Detection:
    default_weeks = int(cfg.value("min_weeks"))
    allowance = float(cfg.value("allowance_hours"))
    nw = len(k.weeks)
    found: List[Bottleneck] = []
    results: List[Dict[str, Any]] = []
    not_measured: List[Dict[str, str]] = []
    for rule in cfg.rules:
        min_weeks = int(rule.get("min_weeks", default_weeks))
        tripped, checked = [], []
        for team in sorted(k.team):
            if k.suppressed_team(team):
                continue
            kt = k.team[team]
            value, thr = kt.get(rule["kpi"]), _threshold(rule, kt)
            hit = value is not None and thr is not None and CMP[rule["comparator"]](value, thr)
            alt = rule.get("or")
            if alt and kt.get(alt["kpi"]) is not None and CMP[alt["comparator"]](kt[alt["kpi"]], alt["threshold"]):
                hit = True
            if value is None and not (alt and kt.get(alt["kpi"]) is not None):
                continue
            checked.append({"team": team, "kpi_value": num(value, "data", 4), "threshold": num(thr, "assumption:thresholds." + rule["id"], 4),
                            "detected": hit})
            if hit:
                tripped.append(team)
        if not checked:
            reason = "; ".join(f"{m['kpi']}: {m['reason']}" for m in k.not_measured) or "no team with enough people and data"
            results.append({"rule": rule["id"], "name": rule["name"], "status": "not_measured", "teams": []})
            not_measured.append({"item": rule["name"], "kpi": rule["kpi"], "reason": reason})
            continue
        results.append({"rule": rule["id"], "name": rule["name"],
                        "status": "detected" if tripped else "not_detected", "teams": checked})
        if tripped:
            found.append(_size(ds, cfg, k, rule, tripped, min_weeks, allowance, nw))
    return Detection(found, results, not_measured)


def _size(ds: Dataset, cfg: Config, k: KpiResult, rule: Dict[str, Any], teams: List[str],
          min_weeks: int, allowance: float, nw: int) -> Bottleneck:
    people = ds.people
    affected = [p for t in teams for p in k.members[t]
                if rule["affected"] != "billable" or people[p]["billable"]]
    measure = SIZING_MEASURE.get(rule["sizing"])
    weekly, person_lost = [], {}
    if measure:
        for wk in k.weeks:
            total = sum(k.pw.get((p, wk), Counter())[measure] for p in affected)
            if rule["sizing"] == "status_hours":
                total -= allowance * len(affected)
            weekly.append(total)
        for p in affected:
            h = sum(k.pw.get((p, wk), Counter())[measure] for wk in k.weeks) / nw
            person_lost[p] = max(0.0, h - (allowance if rule["sizing"] == "status_hours" else 0.0))
    role_lost: Dict[str, float] = defaultdict(float)
    for p, h in person_lost.items():
        role_lost[people[p]["role"]] += h
    n_by_team = {t: sum(1 for p in affected if people[p]["team"] == t) for t in teams}
    weights = sum(n_by_team.values()) or 1
    kpi_value = sum(k.team[t][rule["kpi"]] * n_by_team[t] for t in teams if k.team[t].get(rule["kpi"]) is not None) / weights
    threshold = sum((_threshold(rule, k.team[t]) or 0.0) * n_by_team[t] for t in teams) / weights
    by_team = []
    for t in teams:
        kt = k.team[t]
        row = {"team": t, "kpi_value": num(kt.get(rule["kpi"]), "data", 4), "people_affected": num(n_by_team[t], "data", 0)}
        if measure:
            row["hours_lost_per_person_week"] = num(
                sum(person_lost[p] for p in affected if people[p]["team"] == t) / max(1, n_by_team[t]), "data")
        else:
            for key in ("flow_efficiency", "cycle_days_median", "throughput", "wait_p90_days"):
                row[key] = num(kt.get(key), "data", 4)
        by_team.append(row)
    short = [t for t in teams if len(k.team_weeks.get(t, ())) < min_weeks]
    sufficiency = ({"status": "insufficient_weeks",
                    "reason": f"{', '.join(short)}: fewer than {min_weeks} weeks of data"} if short
                   else {"status": "ok", "reason": f"{len(teams)} team(s), {nw} week(s), every group of at least {k.min_group} people"})
    tot = Counter()
    for p in affected:
        for wk in k.weeks:
            tot.update(k.pw.get((p, wk), Counter()))
    b = Bottleneck(rule=rule, teams=teams, kpi_value=kpi_value, threshold=threshold, people_affected=len(affected),
                   weekly_values=weekly, weeks=list(k.weeks), by_team=by_team, person_lost=person_lost,
                   role_lost=dict(role_lost), sufficiency=sufficiency,
                   after_hours_share=tot["after"] / tot["total"] if tot["total"] else None,
                   mean_weekly_hours=sum(people[p]["weekly_hours"] for p in affected) / len(affected) if affected else None)
    b.evidence = _evidence(ds, rule, teams, affected)
    _role_split(b, people, k.min_group)
    return b


def _role_split(b: Bottleneck, people: Dict[str, Dict[str, Any]], min_group: int) -> None:
    """Share of lost hours by role. Roles under min_group people are merged into
    'other roles'; if that merged group is still too small, no split is shown."""
    total = sum(b.role_lost.values())
    if not total:
        b.by_role_note = "no lost hours to split"
        return
    sizes = Counter(people[p]["role"] for p in b.person_lost)
    big = sorted(r for r, n in sizes.items() if n >= min_group)
    small = [r for r in sizes if r not in big]
    small_n = sum(sizes[r] for r in small)
    if small and small_n < min_group:
        b.by_role_note = f"role split suppressed: a role group would have fewer than {min_group} people"
        return
    rows = [(r, b.role_lost[r], sizes[r]) for r in big]
    if small:
        rows.append(("other roles", sum(b.role_lost[r] for r in small), small_n))
        b.by_role_note = f"roles with fewer than {min_group} people are combined"
    b.by_role = [{"role": r, "people": num(n, "data", 0), "share_of_lost_hours": num(h / total, "data", 4)}
                 for r, h, n in rows]


def _evidence(ds: Dataset, rule: Dict[str, Any], teams: List[str], affected: List[str]) -> Dict[str, Any]:
    who = set(affected)
    tl = ", ".join(teams)
    sizing = rule["sizing"]
    if sizing == "status_hours":
        ids = [r["event_id"] for r in ds.activity if r["person_id"] in who and (
            r["work_type"] == "status_update" or
            (r["work_type"] == "internal_meeting" and r["recurring"] and r["internal"]))]
        text = (f"activity.csv where the person's team is in [{tl}] and (work_type = status_update or "
                f"(work_type = internal_meeting and recurring = true and internal = true))")
    elif sizing == "timesheet_hours":
        ids = [e["entry_id"] for e in ds.time_entries or [] if e["person_id"] in who and e["work_date"].weekday() <= 3
               and e["entered_ts"].date() >= e["work_date"] + timedelta(days=4 - e["work_date"].weekday())]
        ids += [r["event_id"] for r in ds.activity if r["person_id"] in who and r["work_type"] == "timesheet"]
        text = (f"time_entries.csv where the person's team is in [{tl}], work_date is Monday-Thursday and "
                f"entered_ts is on or after that week's Friday; plus activity.csv rows with work_type = timesheet")
    elif sizing == "bench_hours":
        ids = [b["booking_id"] for b in ds.bookings or [] if b["person_id"] in who]
        text = (f"people.csv billable = true in [{tl}], joined to bookings.csv; bench = weekly_hours minus "
                f"weekly_hours x allocation of bookings overlapping each ISO week")
    else:
        ids = [e["event_id"] for e in ds.work_item_events or [] if e["team"] in teams]
        text = f"work_item_events.csv where team is in [{tl}], ordered by work_item_id then ts"
    return {"row_ids": sorted(ids)[:20], "rows_matching": len(ids), "filter": text}
