"""Unit tests for cadence.py (LIS-safety guardrail #5). Pure logic, no I/O — runnable with plain python:

    python3 cadence_test.py        # -> prints "ALL N cadence tests passed" or raises

Covers the decision layer AND every fail-toward-safe default (Standard #7: measured, not vibed). No pytest
dependency so it runs anywhere the workers run.
"""
from datetime import datetime, timedelta, timezone

import cadence as c

ET = c.ET
_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


def et(y, mo, d, h, mi):
    return ET.localize(datetime(y, mo, d, h, mi))


def utc(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


# --- parse_state: total function, safe empty on garbage -------------------------------------------------
for bad in [None, "", "not json", "[]", "123", '{"win": "nope"}', '{"lfr": 42}']:
    st = c.parse_state(bad)
    ok(st == {"lfr": None, "windows": []}, f"garbage {bad!r} must parse to empty state, got {st}")

st = c.parse_state('{"lfr":"2026-02-09T14:03:11Z","win":[["2026-02-09T08:30:00","2026-02-09T11:00:00"]]}')
ok(st["lfr"] == datetime(2026, 2, 9, 14, 3, 11, tzinfo=timezone.utc), "lfr should parse to UTC")
ok(len(st["windows"]) == 1 and st["windows"][0][0] == et(2026, 2, 9, 8, 30), "window start should parse to ET")
# a window with end < start is dropped; a malformed pair is dropped; good ones survive
st = c.parse_state('{"win":[["2026-02-09T11:00:00","2026-02-09T08:30:00"],["x"],["2026-02-09T09:00:00","2026-02-09T10:00:00"]]}')
ok(len(st["windows"]) == 1, f"only the one valid ordered window should survive, got {st['windows']}")

# --- classify_tier --------------------------------------------------------------------------------------
w = [(et(2026, 2, 9, 8, 30), et(2026, 2, 9, 11, 0))]
ok(c.classify_tier(et(2026, 2, 9, 9, 0), w) == "IN_WINDOW", "inside the span -> IN_WINDOW")
ok(c.classify_tier(et(2026, 2, 9, 8, 0), w) == "IDLE", "before an upcoming span -> IDLE")
ok(c.classify_tier(et(2026, 2, 9, 12, 0), w) == "EMPTY", "after the only span -> EMPTY")
ok(c.classify_tier(et(2026, 2, 9, 9, 0), []) == "EMPTY", "no windows -> EMPTY")
# boundary: exactly at start and exactly at end are inclusive
ok(c.classify_tier(et(2026, 2, 9, 8, 30), w) == "IN_WINDOW", "start boundary inclusive")
ok(c.classify_tier(et(2026, 2, 9, 11, 0), w) == "IN_WINDOW", "end boundary inclusive")

# --- should_run: floors + fail-toward-freshness ---------------------------------------------------------
F = c.CALENDAR_TIER_FLOORS
run, _ = c.should_run(utc(2026, 2, 9, 12, 0), None, "EMPTY", F)
ok(run, "no last-run marker -> RUN (fail-toward-freshness)")
run, _ = c.should_run(utc(2026, 2, 9, 12, 0), utc(2026, 2, 9, 8, 0), "EMPTY", F)   # 240m >= 175
ok(run, "240m elapsed >= EMPTY floor 175 -> RUN")
run, _ = c.should_run(utc(2026, 2, 9, 12, 0), utc(2026, 2, 9, 11, 0), "EMPTY", F)  # 60m < 175
ok(not run, "60m elapsed < EMPTY floor 175 -> SKIP")
run, _ = c.should_run(utc(2026, 2, 9, 12, 0), utc(2026, 2, 9, 11, 0), "IN_WINDOW", F)  # floor 0
ok(run, "IN_WINDOW floor 0 -> always RUN")
run, _ = c.should_run(utc(2026, 2, 9, 12, 0), utc(2026, 2, 9, 11, 30), "IDLE", F)  # 30m < 55
ok(not run, "30m elapsed < IDLE floor 55 -> SKIP")
run, _ = c.should_run(utc(2026, 2, 9, 12, 0), utc(2026, 2, 9, 13, 0), "EMPTY", F)  # future marker
ok(run, "future last-run marker -> RUN (never trapped below floor)")

# --- build_windows --------------------------------------------------------------------------------------
now = et(2026, 2, 9, 7, 0)
rows = [
    ("2026-02-09", "09:00"),   # forward -> window [08:30, 11:00]
    ("2026-02-09", "10:00"),   # overlaps the above -> merges into one span
    ("2026-02-01", "09:00"),   # fully past -> dropped
    ("2026-02-20", "09:00"),   # beyond 36h horizon -> dropped
    ("bad", "nope"),           # unparseable -> counted, not crash
    ("2026-02-09", ""),        # unparseable time -> counted
]
wins, stats = c.build_windows(iter(rows), now)
ok(stats["parsed"] == 4, f"4 parseable rows expected, got {stats['parsed']}")
ok(stats["skipped"] == 2, f"2 unparseable rows expected, got {stats['skipped']}")
ok(len(wins) == 1, f"the two same-day meetings should MERGE to 1 span, got {len(wins)}: {wins}")
ok(wins[0] == ["2026-02-09T08:30:00", "2026-02-09T12:00:00"], f"merged span wrong: {wins[0]}")

# empty input is fine
wins, stats = c.build_windows([], now)
ok(wins == [] and stats["windows"] == 0, "no rows -> no windows")

# --- round trip: serialize -> parse ---------------------------------------------------------------------
raw = c.serialize_state(utc(2026, 2, 9, 14, 3, 11), [["2026-02-09T08:30:00", "2026-02-09T11:00:00"]])
back = c.parse_state(raw)
ok(back["lfr"] is not None and len(back["windows"]) == 1, "round-trip should survive parse")

# --- decide: calendar (own lfr) vs bill (own marker, shared windows) ------------------------------------
raw = c.serialize_state(utc(2026, 2, 9, 8, 55), [["2026-02-09T08:30:00", "2026-02-09T11:00:00"]])
# calendar tick at 09:00 ET / 14:00 UTC, lfr in cell = 08:55 UTC -> IN_WINDOW floor 0 -> RUN
run, tier, _ = c.decide(raw, utc(2026, 2, 9, 14, 0), et(2026, 2, 9, 9, 0), c.CALENDAR_TIER_FLOORS)
ok(run and tier == "IN_WINDOW", f"calendar in-window -> RUN/IN_WINDOW, got {run}/{tier}")
# bill worker: same windows, but its OWN last-run marker was 20m ago -> IN_WINDOW floor 55 -> SKIP
run, tier, _ = c.decide(raw, utc(2026, 2, 9, 14, 0), et(2026, 2, 9, 9, 0),
                        c.BILL_TIER_FLOORS, last_run_utc=utc(2026, 2, 9, 13, 40))
ok(not run and tier == "IN_WINDOW", f"bill in-window but 20m<55 floor -> SKIP, got {run}/{tier}")
# bill worker off-season (empty windows), last run 7h ago -> EMPTY floor 355 -> RUN
raw_empty = c.serialize_state(utc(2026, 7, 4, 12, 0), [])
run, tier, _ = c.decide(raw_empty, utc(2026, 7, 4, 19, 0), et(2026, 7, 4, 15, 0),
                        c.BILL_TIER_FLOORS, last_run_utc=utc(2026, 7, 4, 12, 0))
ok(run and tier == "EMPTY", f"bill empty 7h -> RUN/EMPTY, got {run}/{tier}")

print(f"ALL {_checks} cadence tests passed")
