#!/usr/bin/env python3
"""Build the crossover-week audit universe.

Enumerates every unique Bill_id in HISTORY.CSV with at least one action in
Feb 9-13, 2026. Output written to a flat text file for the fetch script.

Usage:
    python3 tools/crossover_audit/build_universe.py

Inputs:
    /tmp/lis_audit/history.csv  (HISTORY.CSV cached from LIS blob)

Outputs:
    /tmp/lis_audit/to_fetch.txt       — one bill id per line
    /tmp/lis_audit/universe_index.json — summary: {bill: [list of Feb 9-13 actions]}
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HISTORY_CSV = Path("/tmp/lis_audit/history.csv")
OUT_FETCH = Path("/tmp/lis_audit/to_fetch.txt")
OUT_INDEX = Path("/tmp/lis_audit/universe_index.json")

WINDOW_START = (2026, 2, 9)
WINDOW_END = (2026, 2, 13)
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
BILL_RE = re.compile(r"^(HB|SB|HJ|SJ|HR|SR)\d+$")


def in_window(date_str: str) -> bool:
    m = DATE_RE.match(date_str)
    if not m:
        return False
    mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (yr, mo, dy) >= WINDOW_START and (yr, mo, dy) <= WINDOW_END


def main() -> int:
    if not HISTORY_CSV.exists():
        print(f"ERROR: {HISTORY_CSV} not found. Download via:", file=sys.stderr)
        print("  curl -sL 'https://lis.blob.core.windows.net/lisfiles/20261/HISTORY.CSV' -o /tmp/lis_audit/history.csv", file=sys.stderr)
        return 1

    by_bill = defaultdict(list)
    with HISTORY_CSV.open() as f:
        for row in csv.DictReader(f):
            bill = row["Bill_id"].strip()
            if not BILL_RE.match(bill):
                continue
            if not in_window(row["History_date"]):
                continue
            by_bill[bill].append({
                "date": row["History_date"],
                "description": row["History_description"],
                "refid": row["History_refid"],
            })

    bills = sorted(by_bill)
    OUT_FETCH.write_text("\n".join(bills) + "\n")
    OUT_INDEX.write_text(json.dumps(by_bill, indent=2))
    print(f"Universe: {len(bills)} unique bills with Feb 9-13, 2026 activity.")
    print(f"  → wrote {OUT_FETCH}")
    print(f"  → wrote {OUT_INDEX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
