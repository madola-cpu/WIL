"""Check a data folder against the contract: python -m engine.validate <folder>

Prints at most 30 lines: PASS/FAIL, row counts, then each problem with up to
10 example rows. Exits 1 on any error. Never prints cell values beyond IDs.
"""
from __future__ import annotations

import sys
from typing import List, Optional

from .contract import check_folder

MAX_LINES = 30


def report_lines(folder: str) -> List[str]:
    res = check_folder(folder)
    lines = [("FAIL" if res.errors else "PASS") + f": {folder}"]
    if res.row_counts:
        lines.append("rows: " + ", ".join(f"{k} {v}" for k, v in res.row_counts.items()))
    lines += ["error   " + p.line() for p in res.errors]
    lines += ["warning " + p.line() for p in res.warnings]
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [f"... {len(lines) - MAX_LINES + 1} more lines not shown"]
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m engine.validate <data folder>")
        return 2
    lines = report_lines(argv[0])
    print("\n".join(lines))
    return 1 if lines[0].startswith("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
