#!/usr/bin/env python3
"""Diff Sheet1 (worker output) against LIS website ground truth.

Emits a categorized discrepancy list for the crossover-week audit.

Usage:
    python3 tools/crossover_audit/diff_sheet1.py \
        --sheet1 /tmp/lis_audit/sheet1.csv \
        --truth docs/testing/crossover_lis_truth.json \
        --history /tmp/lis_audit/history.csv \
        --out docs/testing/crossover_audit_findings.json

Categories emitted (see docs/testing/crossover_audit.md for taxonomy):
    missing_bill        — HISTORY has Feb 9-13 activity but Sheet1 has no rows for this bill
    meeting_in_ledger   — Sheet1 row in Ledger Updates but LIS shows meeting-verb action
    subcommittee_miss   — Sheet1 committee is parent; LIS shows subcommittee
    no_schedule_match   — Sheet1 tagged NO_SCHEDULE_MATCH; root cause traced via LIS
    phantom_row         — Sheet1 has row for (bill, date) with no LIS counterpart
    action_count_drift  — Sheet1 row count ≠ LIS action count for (bill, date); needs review

The diff_sheet1 output is intentionally compact — one entry per discrepancy,
with enough context for a human to triage. Full-text outcomes are truncated
at 150 chars.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BILL_RE = re.compile(r"^(HB|SB|HJ|SJ|HR|SR)\d+$")
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
WINDOW_START = (2026, 2, 9)
WINDOW_END = (2026, 2, 13)

# Meeting-verb patterns: if the action description contains one of these, it's
# a real committee/floor vote or substantive action that *must* carry a time.
# Not a definitive list — biased toward high-recall for audit purposes.
MEETING_VERBS = [
    "reported from",
    "recommends reporting",
    "recommends continuing",
    "recommends passing",
    "recommends laying",
    "recommends defeating",
    "recommends striking",
    "committee amendment offered",
    "committee substitute offered",
    "subcommittee substitute offered",
    "subcommittee amendment offered",
    "committee offered",
    "subcommittee offered",
    "continued to next session",
    "continued to 2027",
    "passed by for the day",
    "passed by indefinitely",
    "engrossed",
    "read first time",
    "read second time",
    "read third time",
    "constitutional reading dispensed",
    "taken up",
    "laid on the table",
    "stricken from docket",
    "block vote",
    "voice vote",
    "rules suspended",
]

# Admin verbs — these correctly live in Ledger Updates with no time.
ADMIN_VERBS = [
    "placed on ",
    "assigned ",
    "referred to",
    "rereferred",
    "transmitted to",
    "enrolled",
    "approved by",
    "signed by",
    "fiscal impact statement",  # all-day admin; never a meeting action
    "fiscal impact statement from",
    "prefiled",
    "printed for",
    "committee substitute printed",  # borderline — the printing is admin even though coincident with committee meeting
    "incorporates",
    "communicated",
    "enrolled bill",
    "scheduled",  # pre-meeting schedule entries ("Scheduled") are not actions
    "continued to 2027 in",  # this IS a meeting action, but always paired with a real committee row elsewhere
]

# Sheet1 outcomes that are not real actions (pre-meeting placeholders, etc.)
NON_ACTION_OUTCOMES = {"", "scheduled"}


def has_meeting_verb(text: str) -> bool:
    """True iff the text contains a meeting-verb substring AND no admin-verb
    override. Admin wins when both match (e.g. "Fiscal Impact Statement ... Engrossed"
    mentions "engrossed" as metadata, not as the action).
    """
    t = text.lower()
    if not any(v in t for v in MEETING_VERBS):
        return False
    return not any(v in t for v in ADMIN_VERBS)


def has_admin_verb(text: str) -> bool:
    t = text.lower()
    return any(v in t for v in ADMIN_VERBS)


def in_window(date_str: str) -> bool:
    m = DATE_RE.match(date_str)
    if not m:
        return False
    mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return WINDOW_START <= (yr, mo, dy) <= WINDOW_END


def normalize_committee(s: str) -> str:
    """Normalize committee name for fuzzy matching."""
    s = s.lower()
    s = re.sub(r"^(house|h-)\s*", "", s)
    s = re.sub(r"^(senate|s-)\s*", "", s)
    s = re.sub(r"[-\s,]+", " ", s)
    s = s.strip()
    return s


def short(s: str, n: int = 150) -> str:
    s = s.replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")


def load_sheet1(path: Path):
    by_bill = defaultdict(list)
    with path.open() as f:
        for r in csv.DictReader(f):
            bill = r["Bill"].strip()
            if not BILL_RE.match(bill):
                continue
            by_bill[bill].append(r)
    return by_bill


def load_lis_truth(path: Path):
    return json.loads(path.read_text())


def load_history(path: Path):
    by_bill = defaultdict(list)
    with path.open() as f:
        for r in csv.DictReader(f):
            bill = r["Bill_id"].strip()
            if not BILL_RE.match(bill):
                continue
            if not in_window(r["History_date"]):
                continue
            m = DATE_RE.match(r["History_date"])
            iso = f"{int(m.group(3)):04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            by_bill[bill].append({
                "date": iso,
                "description": r["History_description"],
                "refid": r["History_refid"],
            })
    return by_bill


def diff(sheet1, truth, history):
    findings = {
        "missing_bill": [],
        "meeting_in_ledger": [],
        "no_schedule_match_meeting": [],
        "no_schedule_match_admin": [],
        "phantom_row": [],
        "action_count_drift": [],
        "subcommittee_miss": [],
    }

    universe = set(history.keys())
    sheet_bills = set(sheet1.keys())

    # --- Check 1: bills entirely missing from Sheet1 ---
    # Only flag if HISTORY has ≥1 meeting-verb action; bills with only
    # fiscal-impact-statement entries are correctly noise-filtered.
    for bill in sorted(universe - sheet_bills):
        meeting_actions = [a for a in history[bill] if has_meeting_verb(a["description"])]
        if not meeting_actions:
            continue
        admin_actions = [a for a in history[bill] if not has_meeting_verb(a["description"])]
        findings["missing_bill"].append({
            "bill": bill,
            "history_meeting_count": len(meeting_actions),
            "history_admin_count": len(admin_actions),
            "sample_action": short(meeting_actions[0]["description"]),
        })

    # --- Check 2/3: per-(bill, date) comparison ---
    for bill in sorted(universe & sheet_bills):
        sheet_rows = sheet1[bill]
        hist_rows = history[bill]
        lis_rows = truth.get(bill, [])

        # Group by date
        sheet_by_date = defaultdict(list)
        for r in sheet_rows:
            sheet_by_date[r["Date"]].append(r)
        lis_by_date = defaultdict(list)
        for r in lis_rows:
            lis_by_date[r["date"]].append(r)
        hist_by_date = defaultdict(list)
        for r in hist_rows:
            hist_by_date[r["date"]].append(r)

        all_dates = set(sheet_by_date) | set(lis_by_date) | set(hist_by_date)
        for d in all_dates:
            sheet_rows_d = sheet_by_date.get(d, [])
            lis_rows_d = lis_by_date.get(d, [])

            # Per-row checks on Sheet1
            for sr in sheet_rows_d:
                outcome = sr["Outcome"]
                origin = sr["Origin"]
                committee = sr["Committee"]
                time_val = sr["Time"]
                is_ledger = committee == "📋 Ledger Updates"
                is_no_sched = "NO_SCHEDULE_MATCH" in time_val or "NO_CONVENE_ANCHOR" in time_val

                # Class 4: meeting verb routed to Ledger
                if is_ledger and has_meeting_verb(outcome):
                    # Look for the LIS committee attribution
                    lis_com = ""
                    for lr in lis_rows_d:
                        if has_meeting_verb(lr["action"]):
                            lis_com = lr["committee_name"] or lis_com
                            break
                    findings["meeting_in_ledger"].append({
                        "bill": bill,
                        "date": d,
                        "sheet1_outcome": short(outcome),
                        "sheet1_origin": origin,
                        "sheet1_time": short(time_val, 50),
                        "diagnostic_hint": short(sr.get("DiagnosticHint", ""), 200),
                        "lis_committee_match": lis_com,
                    })

                # NO_SCHEDULE_MATCH rows — separate meeting vs admin
                elif is_no_sched:
                    bucket = "no_schedule_match_meeting" if has_meeting_verb(outcome) else "no_schedule_match_admin"
                    findings[bucket].append({
                        "bill": bill,
                        "date": d,
                        "sheet1_outcome": short(outcome),
                        "sheet1_origin": origin,
                        "sheet1_committee": committee,
                        "diagnostic_hint": short(sr.get("DiagnosticHint", ""), 200),
                    })

            # Phantom row check: Sheet1 has row (real outcome) but LIS + HISTORY have no action for this bill/date
            real_sheet_rows = [
                sr for sr in sheet_rows_d
                if sr["Outcome"].strip().lower() not in NON_ACTION_OUTCOMES
            ]
            if real_sheet_rows and not lis_rows_d and not hist_by_date.get(d):
                for sr in real_sheet_rows:
                    findings["phantom_row"].append({
                        "bill": bill,
                        "date": d,
                        "sheet1_outcome": short(sr["Outcome"]),
                        "sheet1_committee": sr["Committee"],
                        "sheet1_origin": sr["Origin"],
                    })

            # Missing-meeting-action: LIS shows a meeting action, Sheet1 has
            # NO row for this bill/date at all. Stronger signal than count drift.
            if lis_rows_d and not sheet_rows_d:
                lis_meeting = [r for r in lis_rows_d if has_meeting_verb(r["action"])]
                if lis_meeting:
                    findings["action_count_drift"].append({
                        "bill": bill,
                        "date": d,
                        "lis_meeting_actions": len(lis_meeting),
                        "sheet1_meeting_rows": 0,
                        "lis_sample": [short(r["action"], 80) for r in lis_meeting[:3]],
                    })

    # --- Summary stats ---
    summary = {k: len(v) for k, v in findings.items()}
    summary["universe_size"] = len(universe)
    summary["sheet1_bills"] = len(sheet_bills)
    summary["overlap"] = len(universe & sheet_bills)
    return findings, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet1", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--history", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sheet1 = load_sheet1(Path(args.sheet1))
    truth = load_lis_truth(Path(args.truth))
    history = load_history(Path(args.history))

    findings, summary = diff(sheet1, truth, history)

    out = {"summary": summary, "findings": findings}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))

    print("=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    for k, v in summary.items():
        print(f"  {k:35} {v}")
    print(f"\n→ wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
