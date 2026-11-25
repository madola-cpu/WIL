"""Build the seeded mini fixture: python tests/fixtures/make_mini.py [out_dir]

The data is synthetic, with three teams over three ISO weeks:
  Team A (6 people): 3 status-update hours per person-week, 1 timesheet hour per
                     person-week, and Monday-Thursday time entered on Friday.
  Team B (5 people): the trap. Heavy recurring external client meetings, some
                     labeled internal_meeting with internal=false. Only 1 status
                     hour per person-week, and time entered the same day.
  Team C (3 people): it would trip the status rule but must be suppressed.
answer_key.json holds the planted truths in the engine's own units.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

SEED = 7
TZ = timezone(timedelta(hours=-7))
MONDAYS = [date(2026, 9, 14), date(2026, 9, 21), date(2026, 9, 28)]  # ISO weeks 38-40
HERE = Path(__file__).resolve().parent

TEAMS = [  # team, role, soc_code, size, billable
    ("Team A", "consultant", "13-1111", 6, True),
    ("Team B", "account_manager", "11-2022", 5, True),
    ("Team C", "analyst", "15-2051", 3, False),
]

# A day plan is a list of blocks: (work_type, hours, source, recurring, internal).


def _plan(team: str, weekday: int, rng: random.Random) -> list:
    def b(wt, h, src="tracker", rec=False, internal=True):
        return (wt, h, src, rec, internal)
    filler = "learning" if rng.random() < 0.3 else "admin"
    if team == "Team A":
        status = b("status_update", 1.0, rec=True)
        days = {0: [status, b("client_work", 6.0, "app"), b(filler, 1.0)],
                1: [b("client_work", 7.0, "app"), b(filler, 1.0)],
                2: [status, b("client_work", 6.0, "app"), b(filler, 1.0)],
                3: [b("client_work", 7.0, "app"), b(filler, 1.0)],
                4: [status, b("client_work", 5.0, "app"), b(filler, 1.0), b("timesheet", 1.0)]}
        return days[weekday]
    if team == "Team B":
        client_meeting = b("client_work", 2.0, "calendar", rec=True, internal=False)
        days = {0: [b("status_update", 0.5, rec=True), client_meeting, b("client_work", 5.5, "app")],
                1: [client_meeting, b("client_work", 6.0, "app")],
                2: [b("internal_meeting", 0.5, "calendar", rec=True, internal=True), client_meeting,
                    b("client_work", 5.5, "app")],
                3: [client_meeting, b("client_work", 6.0, "app")],
                # The trap: a standing client call that the calendar labels internal_meeting, but internal=false.
                4: [b("internal_meeting", 1.5, "calendar", rec=True, internal=False), b("client_work", 5.5, "app"),
                    b(filler, 1.0)]}
        return days[weekday]
    status = b("status_update", 2.0, rec=True)  # Team C: 4 status hours a week, but only 3 people
    days = {1: [status, b("client_work", 6.0, "app")], 3: [status, b("client_work", 6.0, "app")]}
    return days.get(weekday, [b("client_work", 7.0, "app"), b(filler, 1.0)])


def _ts(d: date, hours_after_nine: float) -> str:
    return (datetime.combine(d, time(9, 0), TZ) + timedelta(hours=hours_after_nine)).isoformat()


def build(out_dir: Path = HERE / "mini") -> Path:
    rng = random.Random(SEED)
    out_dir.mkdir(parents=True, exist_ok=True)
    people, activity, entries, bookings, items = [], [], [], [], []
    for team, role, soc, size, billable in TEAMS:
        letter = team[-1]
        for i in range(1, size + 1):
            people.append({"person_id": f"{letter}{i:02d}", "team": team, "role": role, "soc_code": soc,
                           "weekly_hours": "40", "billable": "true" if billable else "false"})
    tools = ["excel", "powerpoint", "salesforce"]
    for p in people:
        team, pid = p["team"], p["person_id"]
        for monday in MONDAYS:
            for wd in range(5):
                day = monday + timedelta(days=wd)
                offset, client_hours = 0.0, 0.0
                for wt, hours, src, rec, internal in _plan(team, wd, rng):
                    if src == "app":  # app blocks come in up to 2-hour chunks with alternating tools
                        chunks = [2.0] * int(hours // 2) + ([hours % 2] if hours % 2 else [])
                    else:
                        chunks = [hours]
                    for h in chunks:
                        activity.append({"event_id": f"act-{len(activity) + 1:05d}", "person_id": pid,
                                         "start_ts": _ts(day, offset), "end_ts": _ts(day, offset + h),
                                         "source": src, "work_type": wt,
                                         "recurring": str(rec).lower(), "internal": str(internal).lower(),
                                         "work_item_id": "", "tool": rng.choice(tools) if src == "app" else ""})
                        offset += h
                    if wt == "client_work":
                        client_hours += hours
                if team == "Team B" and wd == 1 and rng.random() < 0.4:  # some evening work, for the guardrail
                    activity.append({"event_id": f"act-{len(activity) + 1:05d}", "person_id": pid,
                                     "start_ts": _ts(day, 10.0), "end_ts": _ts(day, 11.0), "source": "tracker",
                                     "work_type": "admin", "recurring": "false", "internal": "true",
                                     "work_item_id": "", "tool": ""})
                friday = monday + timedelta(days=4)
                if team == "Team B":
                    entered = datetime.combine(day, time(17, 10), TZ)
                elif team == "Team A":
                    entered = datetime.combine(friday, time(16, 30), TZ)
                else:
                    entered = datetime.combine(monday + timedelta(days=7), time(9, 30), TZ)
                logged = client_hours - (0.5 if team == "Team A" else 0.0)
                entries.append({"entry_id": f"te-{len(entries) + 1:05d}", "person_id": pid,
                                "work_date": day.isoformat(), "hours": f"{logged:g}",
                                "project": f"P{rng.randint(1, 4)}", "entered_ts": entered.isoformat()})
        if p["billable"] == "true":
            bookings.append({"booking_id": f"bk-{len(bookings) + 1:04d}", "person_id": pid,
                             "project": f"P{rng.randint(1, 4)}", "start_date": MONDAYS[0].isoformat(),
                             "end_date": (MONDAYS[-1] + timedelta(days=4)).isoformat(),
                             "created_ts": datetime.combine(MONDAYS[0] - timedelta(days=10), time(10), TZ).isoformat(),
                             "allocation": "1.0"})
    for team, *_ in TEAMS:
        for n, monday in enumerate(MONDAYS):
            wid = f"WI-{team[-1]}{n + 1}"
            two_tools = team == "Team A"
            steps = [(0, 0.0, "in_progress", "active", "jira"),
                     (1, 0.0, "review", "waiting", "sheets" if two_tools else "jira"),
                     (1, 6.0, "in_progress", "active", "jira"),
                     (3, 3.0, "done", "done", "jira")]
            for day_off, h, status, state, tool in steps:
                items.append({"event_id": f"wi-{len(items) + 1:04d}", "work_item_id": wid,
                              "ts": _ts(monday + timedelta(days=day_off), h), "status": status, "state": state,
                              "tool": tool, "team": team, "person_id": ""})
    _write(out_dir / "people.csv", people)
    _write(out_dir / "activity.csv", activity)
    _write(out_dir / "time_entries.csv", entries)
    _write(out_dir / "bookings.csv", bookings)
    _write(out_dir / "work_item_events.csv", items)
    (out_dir / "config_overrides.json").write_text(json.dumps({"min_weeks": 2}, indent=2) + "\n", encoding="utf-8")
    key = {
        "dataset": "mini_v1 (synthetic)",
        "bottlenecks": [
            {"id": "K1", "name": "status reporting", "kpi": "status_hours", "group": {"teams": ["Team A"]},
             "true_total_hours_lost_per_week": 18, "true_people_affected": 6, "tolerance": 0.15},
            {"id": "K2", "name": "timesheets rebuilt from memory", "kpi": "share_entered_friday_or_later",
             "group": {"teams": ["Team A"]}, "true_total_hours_lost_per_week": 6, "true_people_affected": 6,
             "tolerance": 0.15},
        ],
        "traps": [{"kpi": "internal_meeting_load", "group": {"team": "Team B"},
                   "reason": "recurring external client meetings, not internal status"}],
        "small_groups": [{"team": "Team C", "size": 3}],
    }
    (out_dir / "answer_key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    return out_dir


def _write(path: Path, rows: list) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    target = build(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "mini")
    print(f"wrote {target}")
