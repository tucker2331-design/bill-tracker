#!/usr/bin/env python3
"""Goldens for the outcome-provenance work (W0c/W0d) — the fix for the 2026-07-25 false RED accuracy ring.

WHAT WENT WRONG, so the tests below are read as consequences and not trivia:
LIS batch-marked interim carryover in its structural FLAGS while leaving its status STRINGS untouched. Our
adjudicator did the right thing — published the flag (the oracle, Standard #3) — but then recorded only
"they disagreed", discarding the fact that the published value WAS the authoritative one. Downstream, a bare
mismatch rate (12.2%, 443/3,633) tripped an accuracy threshold while every published value was correct.

Three things are pinned here:
  1. the delta guard on the genuinely UNVERIFIED population (the alarm that should have existed),
  2. the outcome-origin vocabulary (a CLOSED set — a typo must not invent a rung),
  3. the alert wire format, which is a CONTRACT with web/src/data/history.ts. That regex lives in another
     language in another file; nothing but a test keeps them in step.

Pure — no network, no Sheets, no credentials.
    python3 test_bill_outcome_provenance.py
"""
import re
import sys

import bill_tracker as bt

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}\n     got:  {got!r}\n     want: {want!r}")
        print(f"  ✗ {name}")
    else:
        print(f"  ✓ {name}")


# ── 1. the UNVERIFIED delta guard ───────────────────────────────────────────────────────────────────────
print("unverified_jump_is_alarming — a DELTA guard, never an absolute floor")
J = bt.unverified_jump_is_alarming

check("no baseline (first run) never alarms — no comparison beats a fabricated one", J(None, 5000), False)
check("steady state is silent", J(12, 12), False)
check("a FALL is good news, not an alarm (LIS started flagging more)", J(400, 12), False)
check("a small in-session drift does not alarm", J(12, 20), False)
check("a +25 jump alarms", J(100, 125), True)
check("a doubling from a meaningful base alarms", J(60, 120), True)
check("doubling from a TINY base is noise, not signal (2 -> 4)", J(2, 4), False)
check("but crossing the small-base floor does alarm (2 -> 12)", J(2, 12), True)
check("the 2026-07-25 shape: 443 disagreements moved ZERO unverified bills", J(12, 12), False)
check("a BILLS.CSV collapse (everything loses its flag) alarms loudly", J(12, 3645), True)

# The calibration that pre-push #14 exists to force: growth the UNIVERSE explains is not an anomaly.
print("\n  …and the session-start calibration (raw deltas would false-alarm every January)")
check("SESSION START: +3,000 new bills, all unflagged -> silent (the universe explains it)",
      J(12, 3012, 3645, 6645), False)
check("same influx, slightly more unverified than new bills -> still within tolerance",
      J(12, 3020, 3645, 6645), False)
check("LIS DROPS FLAGS on existing bills: +500 unverified, universe flat -> LOUD",
      J(12, 512, 3645, 3645), True)
check("partial: universe +100 but unverified +400 -> the unexplained 300 alarms",
      J(12, 412, 3645, 3745), True)
check("a SHRINKING universe cannot manufacture a negative allowance",
      J(12, 14, 3645, 3600), False)
check("universe figures absent -> falls back to the raw delta (unchanged behaviour)",
      J(100, 125, None, None), True)

# ── 2. the origin vocabulary is a CLOSED set ────────────────────────────────────────────────────────────
print("\noutcome-origin vocabulary")
check("closed set, exact", tuple(bt.OUTCOME_ORIGINS), ("structural_flag", "keyword_fallback", "unresolved"))
check("'unresolved' exists for the future tie case (measured 0 today, must not be an invented winner)",
      "unresolved" in bt.OUTCOME_ORIGINS, True)

# ── 3. the alert wire format is a CROSS-LANGUAGE contract with the front end ────────────────────────────
print("\nalert wire format — parsed by web/src/data/history.ts")
# The exact regex the front end applies to the Outcome cell (kept in sync BY THIS TEST):
FRONTEND_RE = re.compile(r"^\[([A-Z]+):([A-Z_]+)\]\s*(.*)$", re.S)

bt._ALERT_BUFFER.clear()
try:
    bt.notify_slack = lambda *_a, **_k: None      # keep the golden offline
except Exception:
    pass
bt._alert("WARN", "DATA_ANOMALY", "UNVERIFIED outcomes jumped 12 → 400 of 3,645 bills")
bt._alert("CRITICAL", "API_FAILURE", "BILLS.CSV fetched/parsed to 0 rows")

check("every alert is buffered for Metrics_History (it used to reach ONLY stdout+Slack)",
      len(bt._ALERT_BUFFER), 2)
for sev, msg in bt._ALERT_BUFFER:
    m = FRONTEND_RE.match(msg)
    check(f"front end can parse {sev} row", bool(m), True)
    if m:
        check(f"  severity survives the wire ({sev})", m.group(1), sev)
        check("  category is a known Standard #4 class",
              m.group(2) in {"TIMING_LAG", "PARENT_CHILD", "COMMITTEE_DRIFT", "API_FAILURE",
                             "DATA_ANOMALY", "UNKNOWN"}, True)
        check("  the human message is not swallowed", len(m.group(3)) > 10, True)

check("origins are DISTINCT from the calendar worker's, so each is judged on its own cadence",
      (bt.BILL_ALERT_ORIGIN, bt.BILL_METRICS_ORIGIN) != ("system_alert", "system_metrics"), True)
check("Metrics_History header matches the calendar worker's schema",
      bt.METRICS_HISTORY_HEADER, ["RunTimestampUTC", "Status", "Origin", "Outcome"])
bt._ALERT_BUFFER.clear()

# ── ABSENT vs UNVERIFIED: the split must be STRUCTURAL, never clock-based (owner 2026-07-26) ───────────
# A flagless bill that is still in progress is ABSENT (LIS has no terminal fact to flag yet) and must never
# alarm — otherwise every session opening, when thousands of new bills arrive unflagged, screams. A flagless
# bill whose own status says it is SETTLED is the real anomaly. These goldens pin that boundary so nobody
# "fixes" a noisy January by muting alerts for the first N days instead.
print("\n— absent-vs-unverified split —")
check("_TERMINAL_OUTCOMES is a closed frozenset (a typo can't silently widen it)",
      isinstance(bt._TERMINAL_OUTCOMES, frozenset), True)

# Every value _derive_outcome can EMIT must land deliberately on one side of the split — this is the guard
# the module comment promises. A new outcome added upstream fails here instead of defaulting to "not
# terminal" (which would silently stop alarming on a real settled-but-flagless bill).
emitted = {bt._derive_outcome(s) for s in
           ("", "Introduced", "In Committee", "Passed", "Failed", "Incorporated", "Continued",
            "Acts of Assembly Chapter", "Governor's Veto", "Approved", "Awaiting Governor")}
known = bt._TERMINAL_OUTCOMES | {"in_progress"}
check("every outcome _derive_outcome emits is classified by the split (no silent default)",
      sorted(emitted - known), [])

# The specific shapes that matter, asserted by NAME so the intent survives a refactor.
check("an in-progress bill is ABSENT, not unverified-terminal",
      bt._derive_outcome("In Committee") in bt._TERMINAL_OUTCOMES, False)
check("a freshly introduced bill is ABSENT (this is the session-opening wave)",
      bt._derive_outcome("Introduced") in bt._TERMINAL_OUTCOMES, False)
check("a dead bill is TERMINAL (settled → a flag is owed)",
      bt._derive_outcome("Failed") in bt._TERMINAL_OUTCOMES, True)
check("a signed bill is TERMINAL",
      bt._derive_outcome("Acts of Assembly Chapter") in bt._TERMINAL_OUTCOMES, True)
check("a vetoed bill is TERMINAL",
      bt._derive_outcome("Governor's Veto") in bt._TERMINAL_OUTCOMES, True)
check("a carried-over bill is TERMINAL (deferred is still a disposition)",
      bt._derive_outcome("Continued") in bt._TERMINAL_OUTCOMES, True)
check("'in_progress' is deliberately NOT terminal",
      "in_progress" in bt._TERMINAL_OUTCOMES, False)

print()
if FAILURES:
    print(f"❌ {len(FAILURES)} failure(s):")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("✅ all outcome-provenance goldens pass")
