"""Data contract and config loading (PHASE_4_PROMPT.md sections 3 and 6).

check_folder() applies every contract rule and returns typed rows plus the
problems found. load_dataset() refuses a folder with any error. Input files are
only ever read, never written.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
WAGES_PATH = ROOT / "data" / "reference" / "wages.csv"
OVERRIDES_FILE = "config_overrides.json"

WORK_TYPES = ("client_work", "internal_meeting", "status_update", "admin", "timesheet",
              "search", "proposal", "rework", "learning", "other")
SOURCES = ("calendar", "app", "tracker", "survey")
STATES = ("active", "waiting", "done")

SPECS: Dict[str, Dict[str, Any]] = {
    "people.csv": {"required": True, "id": "person_id",
                   "columns": ("person_id", "team", "role", "soc_code", "weekly_hours", "billable"),
                   "optional": ()},
    "activity.csv": {"required": True, "id": "event_id",
                     "columns": ("event_id", "person_id", "start_ts", "end_ts", "source", "work_type",
                                 "recurring", "internal"),
                     "optional": ("work_item_id", "tool")},
    "work_item_events.csv": {"required": False, "id": "event_id",
                             "columns": ("event_id", "work_item_id", "ts", "status", "state", "tool", "team"),
                             "optional": ("person_id",)},
    "time_entries.csv": {"required": False, "id": "entry_id",
                         "columns": ("entry_id", "person_id", "work_date", "hours", "project", "entered_ts"),
                         "optional": ()},
    "bookings.csv": {"required": False, "id": "booking_id",
                     "columns": ("booking_id", "person_id", "project", "start_date", "end_date", "created_ts"),
                     "optional": ("allocation",)},
    "client_rates.csv": {"required": False, "id": "role", "columns": ("role", "loaded_rate"), "optional": ()},
}
TIMESTAMPS = {"start_ts", "end_ts", "ts", "entered_ts", "created_ts"}
DATES = {"work_date", "start_date", "end_date"}
FLOATS = {"weekly_hours": (0.0, 168.0), "hours": (0.0, 24.0), "allocation": (0.0, 1.0),
          "loaded_rate": (0.01, 10000.0)}
BOOLS = {"billable", "recurring", "internal"}
ENUMS = {"source": SOURCES, "state": STATES}
PERSON_FILES = ("activity.csv", "work_item_events.csv", "time_entries.csv", "bookings.csv")

# Privacy: no names, emails, phone numbers, addresses or pay in the inputs (role rates excepted).
FORBIDDEN_HEADER = re.compile(
    r"(^|_)(name|firstname|lastname|fullname|email|e_mail|phone|address|salary|pay|wage|compensation)($|_)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
MAX_EXAMPLES = 10


@dataclass
class Problem:
    file: str
    message: str
    examples: List[str] = field(default_factory=list)
    count: int = 0

    def line(self) -> str:
        shown = ", ".join(self.examples[:MAX_EXAMPLES])
        more = f" (+{self.count - MAX_EXAMPLES} more)" if self.count > MAX_EXAMPLES else ""
        rows = f": {shown}{more}" if shown else ""
        return f"{self.file}: {self.message} [{self.count}]{rows}"


class _Problems:
    def __init__(self) -> None:
        self.items: Dict[Tuple[str, str], Problem] = {}

    def add(self, file: str, message: str, example: str = "") -> None:
        p = self.items.setdefault((file, message), Problem(file, message))
        p.count += 1
        if example and len(p.examples) < MAX_EXAMPLES:
            p.examples.append(example)

    def list(self) -> List[Problem]:
        return list(self.items.values())


@dataclass
class CheckResult:
    errors: List[Problem]
    warnings: List[Problem]
    tables: Dict[str, List[Dict[str, Any]]]
    row_counts: Dict[str, int]
    digest: str


class DataContractError(ValueError):
    def __init__(self, problems: List[Problem]):
        self.problems = problems
        super().__init__("data contract failed: " + "; ".join(p.line() for p in problems[:5]))


def parse_ts(text: str) -> datetime:
    t = text.strip()
    if t.endswith(("Z", "z")):
        t = t[:-1] + "+00:00"
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        raise ValueError("timestamp needs a UTC offset")
    return dt


def parse_bool(text: str) -> bool:
    t = text.strip().lower()
    if t in ("true", "1", "yes"):
        return True
    if t in ("false", "0", "no"):
        return False
    raise ValueError("not a boolean")


def _parse(col: str, raw: str) -> Any:
    if col in TIMESTAMPS:
        return parse_ts(raw)
    if col in DATES:
        return date.fromisoformat(raw.strip())
    if col in FLOATS:
        lo, hi = FLOATS[col]
        v = float(raw)
        if not lo <= v <= hi:
            raise ValueError(f"outside {lo}-{hi}")
        return v
    if col in BOOLS:
        return parse_bool(raw)
    if col in ENUMS:
        v = raw.strip().lower()
        if v not in ENUMS[col]:
            raise ValueError("unknown value")
        return v
    return raw.strip()


def _read(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = [h.strip() for h in (reader.fieldnames or [])]
        rows = [{(k or "").strip(): (v or "") for k, v in row.items()} for row in reader]
    return header, rows


def check_folder(folder: Union[str, Path]) -> CheckResult:
    """Apply every contract rule to a data folder. Never modifies it."""
    folder = Path(folder)
    errors, warnings = _Problems(), _Problems()
    tables: Dict[str, List[Dict[str, Any]]] = {}
    counts: Dict[str, int] = {}
    hasher = hashlib.sha256()
    if not folder.is_dir():
        errors.add(str(folder), "data folder not found")
        return CheckResult(errors.list(), [], {}, {}, "")
    for name, spec in SPECS.items():
        path = folder / name
        if not path.is_file():
            if spec["required"]:
                errors.add(name, "missing required file")
            continue
        hasher.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
        header, raw_rows = _read(path)
        counts[name] = len(raw_rows)
        missing = [c for c in spec["columns"] if c not in header]
        if missing:
            errors.add(name, "missing required column(s) " + ", ".join(missing))
            continue
        if name != "client_rates.csv":
            for h in header:
                if FORBIDDEN_HEADER.search(h.replace(" ", "_")):
                    errors.add(name, f"column '{h}' looks like personal or pay data; remove it")
        id_col, seen, parsed = spec["id"], set(), []
        for i, raw in enumerate(raw_rows, start=2):  # line 1 is the header
            label = f"line {i} ({id_col}={raw.get(id_col, '')[:40]})"
            if any(EMAIL.search(v) for v in raw.values()):
                errors.add(name, "cell contains an email address", label)
            row: Dict[str, Any] = {"_line": i}
            ok = True
            for col in spec["columns"] + spec["optional"]:
                value = raw.get(col, "")
                if col in spec["optional"] and not value.strip():
                    row[col] = 1.0 if col == "allocation" else None
                    continue
                if col == "work_type":
                    wt = value.strip().lower()
                    if wt not in WORK_TYPES:
                        warnings.add(name, f"unknown work_type '{wt[:30]}' mapped to other", label)
                        wt = "other"
                    row[col] = wt
                    continue
                try:
                    row[col] = _parse(col, value)
                except (ValueError, TypeError):
                    errors.add(name, f"unparseable {col}", label)
                    ok = False
                    continue
                if col == id_col or col == "person_id":
                    if not row[col]:
                        errors.add(name, f"empty {col}", label)
                        ok = False
            key = row.get(id_col)
            if key in seen:
                errors.add(name, f"duplicate {id_col}", label)
                ok = False
            seen.add(key)
            if ok and name == "activity.csv" and row["end_ts"] < row["start_ts"]:
                errors.add(name, "end_ts before start_ts", label)
                ok = False
            if ok and name == "bookings.csv" and row["end_date"] < row["start_date"]:
                errors.add(name, "end_date before start_date", label)
                ok = False
            if ok:
                parsed.append(row)
        tables[name] = parsed
    people = {r["person_id"] for r in tables.get("people.csv", [])}
    for name in PERSON_FILES:
        for row in tables.get(name, []):
            pid = row.get("person_id")
            if pid and pid not in people:
                errors.add(name, "unknown person_id",
                           f"line {row['_line']} ({SPECS[name]['id']}={row[SPECS[name]['id']]})")
    return CheckResult(errors.list(), warnings.list(), tables, counts, hasher.hexdigest())


@dataclass
class Dataset:
    folder_name: str
    people: Dict[str, Dict[str, Any]]
    activity: List[Dict[str, Any]]
    work_item_events: Optional[List[Dict[str, Any]]]
    time_entries: Optional[List[Dict[str, Any]]]
    bookings: Optional[List[Dict[str, Any]]]
    client_rates: Optional[Dict[str, float]]
    row_counts: Dict[str, int]
    digest: str
    warnings: List[Problem]


def load_dataset(folder: Union[str, Path]) -> Dataset:
    res = check_folder(folder)
    if res.errors:
        raise DataContractError(res.errors)
    t = res.tables
    rates = t.get("client_rates.csv")
    return Dataset(
        folder_name=Path(folder).resolve().name,  # never the full path: it can contain a user name
        people={r["person_id"]: r for r in t["people.csv"]},
        activity=sorted(t["activity.csv"], key=lambda r: (r["start_ts"], r["event_id"])),
        work_item_events=t.get("work_item_events.csv"),
        time_entries=t.get("time_entries.csv"),
        bookings=t.get("bookings.csv"),
        client_rates={r["role"]: r["loaded_rate"] for r in rates} if rates else None,
        row_counts=res.row_counts,
        digest=res.digest,
        warnings=res.warnings,
    )


# ---------------------------------------------------------------- config


@dataclass
class Config:
    assumptions: Dict[str, Dict[str, Any]]
    rules: List[Dict[str, Any]]
    fixes: List[Dict[str, Any]]
    studies: List[Dict[str, Any]]
    families: Dict[str, List[str]]
    wages: Dict[str, Dict[str, Any]]
    overridden: List[str]

    def value(self, key: str) -> Any:
        return self.assumptions[key]["value"]


def _json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def read_wages(path: Path = WAGES_PATH) -> Dict[str, Dict[str, Any]]:
    wages: Dict[str, Dict[str, Any]] = {}
    if not path.is_file():
        return wages
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            code, wage = (row.get("soc_code") or "").strip(), (row.get("mean_hourly_wage") or "").strip()
            if code and wage:
                wages[code] = {"title": (row.get("title") or "").strip(), "mean_hourly_wage": float(wage),
                               "source": (row.get("source") or "").strip()}
    return wages


def load_config(data_folder: Union[str, Path, None] = None, config_dir: Path = CONFIG_DIR,
                wages_path: Path = WAGES_PATH, overrides: Optional[Dict[str, Any]] = None) -> Config:
    """Read config/*.json. Optional per-dataset overrides come from <data>/config_overrides.json."""
    assumptions = _json(config_dir / "assumptions.json")
    merged: Dict[str, Any] = {}
    if data_folder is not None and (Path(data_folder) / OVERRIDES_FILE).is_file():
        merged.update(_json(Path(data_folder) / OVERRIDES_FILE))
    merged.update(overrides or {})
    for key, val in merged.items():
        if key not in assumptions:
            raise ValueError(f"{OVERRIDES_FILE}: unknown assumption '{key}'")
        entry = copy.deepcopy(assumptions[key])
        if isinstance(val, dict):
            entry.update(val)
        else:
            entry["value"] = val
        entry["source"] = f"override in {OVERRIDES_FILE} (was: {assumptions[key].get('source', '')})"
        assumptions[key] = entry
    return Config(
        assumptions=assumptions,
        rules=_json(config_dir / "thresholds.json")["rules"],
        fixes=_json(config_dir / "fixes.json"),
        studies=_json(config_dir / "evidence.json")["studies"],
        families=_json(config_dir / "task_families.json"),
        wages=read_wages(wages_path),
        overridden=sorted(merged),
    )
