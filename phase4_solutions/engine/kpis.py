"""KPIs (PHASE_4_PROMPT.md section 4), per (team, role, ISO week), (team, role) and team.

Per-person-week measures live in memory only (KpiResult.pw). Everything
written out is group-level, and groups under min_group_size are suppressed.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .contract import WORK_TYPES, Config, Dataset


def iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_bounds(label: str) -> Tuple[date, date]:
    y, w = label.split("-W")
    monday = date.fromisocalendar(int(y), int(w), 1)
    return monday, monday + timedelta(days=6)


def quantile(values: Iterable[float], q: float) -> Optional[float]:
    """Linear interpolation between order statistics (numpy's default)."""
    v = sorted(values)
    if not v:
        return None
    pos = (len(v) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def hours(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600.0


@dataclass
class KpiResult:
    weeks: List[str]
    team_size: Dict[str, int]
    role_size: Dict[Tuple[str, str], int]
    team_weeks: Dict[str, Set[str]]
    team: Dict[str, Dict[str, Any]]                    # every team, suppressed ones included (memory only)
    rows: List[Dict[str, Any]]                         # kpis.csv rows: unsuppressed groups only
    pw: Dict[Tuple[str, str], Counter]                 # (person_id, week) -> measures (memory only)
    not_measured: List[Dict[str, str]]
    suppressed: List[Dict[str, Any]]
    min_group: int = 5
    members: Dict[str, List[str]] = field(default_factory=dict)

    def suppressed_team(self, team: str) -> bool:
        return self.team_size.get(team, 0) < self.min_group


def _local_hm(t: str) -> time:
    h, m = t.split(":")
    return time(int(h), int(m))


def compute(ds: Dataset, cfg: Config) -> KpiResult:
    min_group = int(cfg.value("min_group_size"))
    allowance = float(cfg.value("allowance_hours"))
    wh = cfg.assumptions["work_hours_local"]
    day_start, day_end = _local_hm(wh["start"]), _local_hm(wh["end"])
    people = ds.people

    weeks = sorted({iso_week(r["start_ts"].date()) for r in ds.activity})
    members: Dict[str, List[str]] = defaultdict(list)
    for pid, p in sorted(people.items()):
        members[p["team"]].append(pid)
    team_size = {t: len(m) for t, m in members.items()}
    role_size = Counter((p["team"], p["role"]) for p in people.values())

    # ---- per person-week measures (memory only)
    pw: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    team_weeks: Dict[str, Set[str]] = defaultdict(set)
    app_blocks: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    client_by_day: Dict[Tuple[str, date], float] = defaultdict(float)
    for r in ds.activity:
        pid, start = r["person_id"], r["start_ts"]
        wk, h = iso_week(start.date()), hours(start, r["end_ts"])
        c = pw[(pid, wk)]
        team_weeks[people[pid]["team"]].add(wk)
        c["total"] += h
        c["wt:" + r["work_type"]] += h
        imeet = r["work_type"] == "internal_meeting" and r["recurring"] and r["internal"]
        if imeet:
            c["imeet"] += h
        if imeet or r["work_type"] == "status_update":
            c["status"] += h
        local = start.time().replace(tzinfo=None)
        if start.weekday() >= 5 or local < day_start or local >= day_end:
            c["after"] += h
        if r["source"] == "app":
            app_blocks[pid].append(r)
            c["app_hours"] += h
        if r["work_type"] == "client_work":
            client_by_day[(pid, start.date())] += h
    for pid, blocks in app_blocks.items():
        prev = None
        for r in blocks:  # activity is sorted by start
            if prev is not None and r["tool"] and prev["tool"] and r["tool"] != prev["tool"]:
                pw[(pid, iso_week(r["start_ts"].date()))]["switches"] += 1
            prev = r

    has_bookings = ds.bookings is not None
    if has_bookings:
        by_person: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for b in ds.bookings:
            by_person[b["person_id"]].append(b)
        for pid, p in people.items():
            if not p["billable"]:
                continue
            for wk in weeks:
                mon, sun = week_bounds(wk)
                alloc = sum(b["allocation"] for b in by_person[pid] if b["start_date"] <= sun and b["end_date"] >= mon)
                pw[(pid, wk)]["bench"] += max(0.0, p["weekly_hours"] - p["weekly_hours"] * alloc)
                pw[(pid, wk)]["billable_weeks"] += 1

    entries_by_person: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in ds.time_entries or []:
        entries_by_person[e["person_id"]].append(e)

    def group_kpis(pids: List[str], wks: List[str], flow_team: Optional[str] = None) -> Dict[str, Any]:
        n, nw = len(pids), len(wks)
        wkset = set(wks)
        tot: Counter = Counter()
        for pid in pids:
            for wk in wks:
                tot.update(pw.get((pid, wk), Counter()))
        k: Dict[str, Any] = {"people": n, "weeks": nw, "logged_hours": tot["total"]}
        contracted = sum(people[p]["weekly_hours"] for p in pids) * nw
        for wt in WORK_TYPES:
            k[f"time_share.{wt}"] = tot["wt:" + wt] / tot["total"] if tot["total"] else None
            k[f"hours_per_person_week.{wt}"] = tot["wt:" + wt] / (n * nw) if n and nw else None
        k["internal_meeting_load"] = tot["imeet"] / contracted if contracted else None
        k["status_hours"] = tot["status"] / (n * nw) - allowance if n and nw else None
        k["after_hours_share"] = tot["after"] / tot["total"] if tot["total"] else None
        k["context_switches_per_hour"] = tot["switches"] / tot["app_hours"] if tot["app_hours"] else None
        k["mean_weekly_hours"] = sum(people[p]["weekly_hours"] for p in pids) / n if n else None
        if has_bookings:
            k["unplanned_bench"] = tot["bench"] / tot["billable_weeks"] if tot["billable_weeks"] else None
            notice = [(b["start_date"] - b["created_ts"].date()).days for b in ds.bookings if b["person_id"] in pids]
            k["notice_days"] = quantile(notice, 0.5)
        if ds.time_entries is not None:
            ents = [e for p in pids for e in entries_by_person[p] if iso_week(e["work_date"]) in wkset]
            k["time_entry_lag_days"] = quantile([(e["entered_ts"].date() - e["work_date"]).days for e in ents], 0.5)
            early = [e for e in ents if e["work_date"].weekday() <= 3]
            late = [e for e in early
                    if e["entered_ts"].date() >= e["work_date"] + timedelta(days=4 - e["work_date"].weekday())]
            k["share_entered_friday_or_later"] = len(late) / len(early) if early else None
            logged: Dict[Tuple[str, date], float] = defaultdict(float)
            for e in ents:
                logged[(e["person_id"], e["work_date"])] += e["hours"]
            days = [(p, d) for (p, d) in client_by_day if p in pids and iso_week(d) in wkset]
            cw = sum(client_by_day[x] for x in days)
            k["unlogged_share"] = sum(max(0.0, client_by_day[x] - logged.get(x, 0.0)) for x in days) / cw if cw else None
        if flow_team is not None and ds.work_item_events is not None:
            k.update(_flow(ds.work_item_events, flow_team, n, wks))
        return k

    team: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []
    for t in sorted(members):
        team[t] = group_kpis(members[t], weeks, flow_team=t)
        if team_size[t] < min_group:
            suppressed.append({"group": {"team": t}, "status": f"not enough data (fewer than {min_group} people)"})
            continue
        rows += _rows("team", t, "", "", team[t])
        for (tt, role), size in sorted(role_size.items()):
            if tt != t:
                continue
            if size < min_group:
                suppressed.append({"group": {"team": t, "role": role},
                                   "status": f"not enough data (fewer than {min_group} people)"})
                continue
            rpids = [p for p in members[t] if people[p]["role"] == role]
            rows += _rows("team_role", t, role, "", group_kpis(rpids, weeks))
            for wk in weeks:
                rows += _rows("team_role_week", t, role, wk, group_kpis(rpids, [wk]))

    not_measured: List[Dict[str, str]] = []
    if not has_bookings:
        not_measured.append({"kpi": "unplanned_bench, notice_days", "reason": "bookings.csv not provided"})
    if ds.time_entries is None:
        not_measured.append({"kpi": "time_entry_lag_days, share_entered_friday_or_later, unlogged_share",
                             "reason": "time_entries.csv not provided"})
    if ds.work_item_events is None:
        not_measured.append({"kpi": "duplicate_updates, wait_time, flow_efficiency, throughput",
                             "reason": "work_item_events.csv not provided"})
    if not app_blocks:
        not_measured.append({"kpi": "context_switches_per_hour", "reason": "no activity rows with source=app"})
    return KpiResult(weeks=weeks, team_size=team_size, role_size=dict(role_size), team_weeks=dict(team_weeks),
                     team=team, rows=rows, pw=pw, not_measured=not_measured, suppressed=suppressed,
                     min_group=min_group, members=dict(members))


def _flow(events: List[Dict[str, Any]], team: str, n_people: int, wks: List[str]) -> Dict[str, Any]:
    items: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in events:
        if e["team"] == team:
            items[e["work_item_id"]].append(e)
    effs, cycles, waits_all, dup = [], [], [], []
    waits: Dict[str, List[float]] = defaultdict(list)
    done_count = 0
    for evs in items.values():
        evs.sort(key=lambda e: (e["ts"], e["event_id"]))
        tools_by_week: Dict[str, Set[str]] = defaultdict(set)
        for e in evs:
            tools_by_week[iso_week(e["ts"].date())].add(e["tool"])
        dup += [len(t) for t in tools_by_week.values()]
        active, wait_start = 0.0, None
        done = next((e for e in evs if e["state"] == "done"), None)
        for a, b in zip(evs, evs[1:]):
            if done is not None and a["ts"] >= done["ts"]:
                break
            if a["state"] == "active":
                active += hours(a["ts"], b["ts"])
        for prev, e in zip([None] + evs[:-1], evs):
            if e["state"] == "waiting" and (prev is None or prev["state"] != "waiting"):
                wait_start = e
            elif e["state"] == "active" and wait_start is not None:
                w = hours(wait_start["ts"], e["ts"])
                waits[wait_start["status"]].append(w)
                waits_all.append(w)
                wait_start = None
        if done is not None:
            done_count += 1
            span = hours(evs[0]["ts"], done["ts"])
            cycles.append(span / 24.0)
            if span > 0:
                effs.append(active / span)
    k: Dict[str, Any] = {
        "work_items": len(items),
        "duplicate_updates": sum(dup) / len(dup) if dup else None,
        "flow_efficiency": quantile(effs, 0.5),
        "cycle_days_median": quantile(cycles, 0.5),
        "throughput": done_count / (n_people * len(wks)) if n_people and wks else None,
        "wait_p90_days": (quantile(waits_all, 0.9) / 24.0) if waits_all else None,
    }
    for status, ws in sorted(waits.items()):
        k[f"wait_time.{status}.median_hours"] = quantile(ws, 0.5)
        k[f"wait_time.{status}.p90_hours"] = quantile(ws, 0.9)
    return k


def _rows(level: str, team: str, role: str, week: str, k: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for name, value in k.items():
        if name in ("people", "weeks") or value is None:
            continue
        out.append({"level": level, "team": team, "role": role, "week": week, "kpi": name,
                    "value": round(float(value), 4), "people": k["people"]})
    return out
