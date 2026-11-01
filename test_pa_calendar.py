#!/usr/bin/env python3
"""Pennsylvania calendar — goldens on the REAL sample (tools/historical_cache/pa/2025_0/): the House + Senate
committee-schedule RSS (2026-10-31) and the Bill History export, written in the calendar subsystem's Sheet1 layout.

GOLDEN (goldens/pa_calendar_2025_0.json): a SHA-256 of every row + the stats, with spot rows checkable by eye.

INVARIANTS (from the sources, independent of the golden):
  * header == the calendar subsystem's Sheet1 header; every row is its width
  * every schedule meeting is on the calendar once (7 listed, 2 are the same agency meeting in both feeds)
  * a meeting whose Bills field is empty is written with no bill and the hint `no_bills_listed` (the screen says so)
  * "Call of Chair" is kept as the source's time, never turned into a clock time
  * a session day exists only where a chamber recorded floor business; an automatic Rule 71 tabling is not a sitting
    (2025-05-04, a Sunday, carried only one) — and no session day lies in the future
  * every session-day bill is a real record, and its Outcome is that action's own <fullAction>

Re-capture ONLY for an intended output change:  python3 test_pa_calendar.py --write
"""
import hashlib
import json
import os
import sys

from states import pa_adapter as A
from states import pa_calendar as C
from states import pa_roster as R
import test_pa_intake as S

GOLDEN = os.path.join(S.HERE, "goldens", "pa_calendar_2025_0.json")
FAILS = 0


def check(name, ok, detail=""):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    FAILS += 0 if ok else 1


fx = S.SampleFetcher()
records, comp, export, meetings = A.run_intake_full(fx, None, S.TODAY, S.NOW)
asked_by_intake = list(fx.asked)
roster, _ = R.run_roster(fx, S.PA.urls)
rows, st = C.build_calendar(export, meetings, roster, {r["bill"] for r in records})
check("the calendar reuses the intake's parse: no extra request", fx.asked[:len(asked_by_intake)] == asked_by_intake
      and all("schedule" not in u and "BillHistory" not in u for u in fx.asked[len(asked_by_intake):]))
head, body = rows[0], rows[1:]
check("Sheet1 header, every row its width", head == C.SHEET1_HEADER and all(len(r) == len(head) for r in body))
col = {k: i for i, k in enumerate(head)}

mt = [r for r in body if r[col["Origin"]] == C.ORIGIN_MEETING]
check("7 listed meetings -> 5 on the calendar (2 agency duplicates written once)",
      len(meetings) == 7 and st["calendar_meetings"] == 5 and st["calendar_meetings_duplicate"] == 2 and len(mt) == 5)
check("no meeting lists bills -> each says so (no_bills_listed, no bill)",
      st["calendar_meetings_without_bills"] == 5
      and all(r[col["Bill"]] == "" and r[col["DiagnosticHint"]] == "no_bills_listed" for r in mt))
check("Call of Chair kept as the source's time, no clock time invented",
      [(r[col["Date"]], r[col["Time"]], r[col["SortTime"]]) for r in mt if r[col["Committee"]] == "House Appropriations"]
      == [("2026-11-09", "Call of Chair", ""), ("2026-11-10", "Call of Chair", "")])
check("committee names from the roster; agencies keep their own names",
      sorted({r[col["Committee"]] for r in mt}) == ["CENTER FOR RURAL PENNSYLVANIA", "House Appropriations",
                                                   "INDEPENDENT REGULATORY REVIEW COMMISSION", "Senate Transportation"])

sd = [r for r in body if r[col["Origin"]] == C.ORIGIN_SESSION]
days = {(r[col["Committee"]], r[col["Date"]]) for r in sd}
check("214 past session days (House 119, Senate 95)",
      (st["calendar_session_days"], st["calendar_session_days_house"], st["calendar_session_days_senate"]) == (214, 119, 95))
check("a Rule 71 tabling alone is not a sitting (House 2025-05-04, a Sunday)", ("House Convened", "2025-05-04") not in days)
check("no session day in the future", max(d for _, d in days) <= S.TODAY.isoformat())
ids = {r["bill"] for r in records}
check("every session-day bill is a real record", all(r[col["Bill"]] in ids for r in sd))
full = {}
for b in export.iter("bill"):
    key = A.bill_key(*((b.findtext(k) or "").strip() for k in ("body", "type", "number")))
    for a in b.iter("action"):
        full.setdefault(key, set()).add((A._iso(a.findtext("date") or ""), (a.findtext("fullAction") or "").strip()))
check("each session-day Outcome is that bill's own <fullAction> on that date",
      all((r[col["Date"]], r[col["Outcome"]]) in full[r[col["Bill"]]] for r in sd))
oct21 = [(r[col["Bill"]], r[col["Outcome"]]) for r in sd if r[col["Date"]] == "2026-10-21" and r[col["Committee"]] == "House Convened"]
check("spot: House, 21 Oct 2026 — HB69 concurrence (203-0) first, bill-number order",
      oct21[0] == ("HB69", "House concurred in Senate amendments, Oct. 21, 2026 (203-0)"))

no_roster, st2 = C.build_calendar(export, meetings, None, ids)
check("without a roster the source's committee text is kept (never guessed)",
      any(r[col["Committee"]] == "HOUSE APPROPRIATIONS" for r in no_roster[1:]) and st2["calendar_roster_used"] is False)

digest = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
got = json.loads(json.dumps({"rows_sha256": digest, "stats": st, "spot_meetings": mt, "spot_oct21_house": oct21[:3]}))
if "--write" in sys.argv:
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump(got, f, indent=1, sort_keys=True)
    print(f"wrote {GOLDEN}")
else:
    with open(GOLDEN, encoding="utf-8") as f:
        want = json.load(f)
    check("golden: every calendar row + stats unchanged", got == want,
          "re-capture with --write ONLY for an intended output change")
sys.exit(1 if FAILS else 0)
