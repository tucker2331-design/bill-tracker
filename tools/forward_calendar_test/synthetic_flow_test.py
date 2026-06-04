#!/usr/bin/env python3
"""Forward-calendar synthetic validation harness (PR-FC Step 4).

The forward-calendar producer (`schedule_meeting_origin`, PR-FC1b) and the X-Ray
"Upcoming meetings" consumer (PR-FC2) are a verified NO-OP on the adjourned 2026
session — there are no future-dated meetings to exercise them. This harness
INJECTS synthetic future meetings to validate the full flow end-to-end before the
2027 session goes live, with NO network and NO Google Sheets:

  producer tags a future meeting `scheduled_future`
    → the X-Ray filter surfaces it in "Upcoming meetings (Date >= today)"
      → as days pass, the SAME meeting re-tags `api_schedule` (date <= today)
        → and is correctly EXCLUDED from the upcoming view (reconciliation).

Extracts the real functions from source via AST (avoids importing gspread). Run:
    python3 tools/forward_calendar_test/synthetic_flow_test.py
Exit 0 = all pass.
"""
import ast
import os
import sys
from datetime import datetime, date, timedelta

import pandas as pd  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _extract(path, names):
    """Exec only the named top-level functions from a module (no gspread import)."""
    src = open(os.path.join(_ROOT, path)).read()
    tree = ast.parse(src)
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {"datetime": datetime, "date": date, "timedelta": timedelta, "pd": pd}
    exec(compile(ast.Module(body, []), path, "exec"), ns)
    return ns


def _upcoming_view(sheet_df, today_str):
    """The exact filter the X-Ray Section 11 (PR-FC2) applies."""
    return sheet_df[
        (sheet_df["Origin"].astype(str) == "scheduled_future")
        & (sheet_df["Date"].astype(str) >= today_str)
    ].copy()


def main():
    cw = _extract("calendar_worker.py", {"schedule_meeting_origin"})
    origin = cw["schedule_meeting_origin"]
    fails = []

    def check(cond, msg):
        print(f"  {'PASS' if cond else 'FAIL'}: {msg}")
        if not cond:
            fails.append(msg)

    today = datetime(2026, 6, 4, 9, 0)  # a fixed "today" for reproducibility
    print("1) PRODUCER — schedule_meeting_origin tags by date")
    check(origin(datetime(2026, 6, 18), today) == "scheduled_future", "meeting 14d ahead → scheduled_future")
    check(origin(datetime(2026, 6, 4, 23, 0), today) == "api_schedule", "a meeting later TODAY is NOT future")
    check(origin(datetime(2026, 6, 3), today) == "api_schedule", "yesterday → api_schedule")
    check(origin(date(2026, 6, 18), date(2026, 6, 4)) == "scheduled_future", "bare date objects work (Gemini #80)")
    check(origin(None, today) == "api_schedule", "malformed → safe fallback")

    print("\n2) END-TO-END — synthetic schedule rows through the producer")
    # Two future committee meetings + one past, as the worker's row dicts.
    synth = [
        {"Bill": "HB1001", "Date": "2026-06-18", "Committee": "Senate Finance", "Time": "2:00 PM",
         "Outcome": "Scheduled", "_md": datetime(2026, 6, 18)},
        {"Bill": "HB1002", "Date": "2026-06-11", "Committee": "House Courts of Justice", "Time": "9:00 AM",
         "Outcome": "Scheduled", "_md": datetime(2026, 6, 11)},
        {"Bill": "HB1003", "Date": "2026-05-30", "Committee": "Senate Finance", "Time": "10:00 AM",
         "Outcome": "Reported from Finance (15-Y 0-N)", "_md": datetime(2026, 5, 30)},
    ]
    for r in synth:
        r["Origin"] = origin(r.pop("_md"), today)
    df = pd.DataFrame(synth)
    fut = df[df["Origin"] == "scheduled_future"]
    check(set(fut["Bill"]) == {"HB1001", "HB1002"}, "2 future meetings → scheduled_future")
    check((df[df["Bill"] == "HB1003"]["Origin"] == "api_schedule").all(), "past meeting → api_schedule (not future)")

    print("\n3) X-RAY CONSUMER — Section 11 'Upcoming meetings (Date >= today)' filter")
    up = _upcoming_view(df, today.strftime("%Y-%m-%d"))
    check(set(up["Bill"]) == {"HB1001", "HB1002"}, "upcoming view shows exactly the 2 future meetings")
    check("HB1003" not in set(up["Bill"]), "past meeting excluded from upcoming view")

    print("\n4) RECONCILIATION — same meeting, time advances past it")
    later = datetime(2026, 6, 12, 9, 0)  # now HB1002 (6/11) is in the past
    df2 = df.copy()
    # re-derive origin at the later 'today' (what the next cycle does)
    md = {"HB1001": datetime(2026, 6, 18), "HB1002": datetime(2026, 6, 11), "HB1003": datetime(2026, 5, 30)}
    df2["Origin"] = df2["Bill"].map(lambda b: origin(md[b], later))
    up2 = _upcoming_view(df2, later.strftime("%Y-%m-%d"))
    check(set(up2["Bill"]) == {"HB1001"}, "after 'today' passes HB1002, only HB1001 remains upcoming")
    check((df2[df2["Bill"] == "HB1002"]["Origin"] == "api_schedule").all(),
          "HB1002 transitioned scheduled_future → api_schedule (reconciliation)")

    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAILURE(S)'} — forward-calendar flow validated end-to-end (producer → X-Ray → reconciliation)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
