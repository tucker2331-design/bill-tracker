"""Golden tests for calendar_worker.compute_effective_scrape_end — the forward-calendar viewport
upper bound. Run: python3 test_compute_effective_scrape_end.py  (exit 0 = all pass).

Locks the three regimes, especially the 2026-06-29 OFF-SEASON interim-meeting fix: once the GA
adjourns, the worker must still surface LIS-published interim committee meetings within a bounded
horizon (the completeness tripwire caught a 2026-06-29 S10 meeting absent from Sheet1 because the old
code pinned the window at the session end off-season). See docs/state/health_gauge_calibration_plan.md.

NB: imports calendar_worker, which pulls pandas/gspread/google-auth — so this runs with the worker's
deps, NOT in the stdlib-only structural_tests.yml CI. The production proof is the completeness tripwire
going green after deploy.
"""
from datetime import datetime, timedelta

from calendar_worker import compute_effective_scrape_end, FORWARD_WINDOW, INTERIM_FORWARD_WINDOW

# (label, scrape_end, test_end_date, today, live_run) -> expected effective end
CASES = [
    # 1. LIVE in-session: extend to today + FORWARD_WINDOW (14d) when that's inside the session.
    ("in-session extends to today+14",
     datetime(2026, 1, 20), datetime(2026, 6, 1), datetime(2026, 2, 1), True,
     datetime(2026, 2, 1) + FORWARD_WINDOW),
    # 2. LIVE in-session near the end: the forward extension is CAPPED at test_end_date (no next-session leak).
    ("in-session capped at test_end_date",
     datetime(2026, 5, 15), datetime(2026, 5, 15), datetime(2026, 5, 10), True,
     datetime(2026, 5, 15)),
    # 3. LIVE OFF-SEASON (the fix): session adjourned (scrape_end in the past) -> extend to today+INTERIM (45d)
    #    so interim committee meetings surface. This is what restores the calendar + greens completeness.
    ("off-season extends to today+interim",
     datetime(2026, 5, 15), datetime(2026, 5, 15), datetime(2026, 6, 30), True,
     datetime(2026, 6, 30) + INTERIM_FORWARD_WINDOW),
    # 4. Off-season later in the year still tracks today+INTERIM (interim meetings surface ALL off-season).
    ("off-season tracks today+interim in fall",
     datetime(2026, 5, 15), datetime(2026, 5, 15), datetime(2026, 9, 1), True,
     datetime(2026, 9, 1) + INTERIM_FORWARD_WINDOW),
    # 5. PINNED REPLAY (live_run=False): never extend, whatever the dates — reproducibility.
    ("pinned replay unchanged",
     datetime(2025, 3, 1), datetime(2025, 3, 1), datetime(2026, 6, 30), False,
     datetime(2025, 3, 1)),
    # 6. Offline fallback (Session API down): test_end_date = scrape_end = now+14d (future) -> in-session branch.
    ("offline-fallback future window stays in-session",
     datetime(2026, 7, 14), datetime(2026, 7, 14), datetime(2026, 6, 30), True,
     datetime(2026, 7, 14)),
]


def main():
    failures = []
    for label, scrape_end, test_end, today, live, expected in CASES:
        got = compute_effective_scrape_end(scrape_end, test_end, today, live_run=live)
        ok = got == expected
        if not ok:
            failures.append((label, got, expected))
        print(f"  [{'ok' if ok else 'FAIL'}] {label}: {got.date()} (exp {expected.date()})")
    # Bound sanity: the off-season horizon must be small enough that today+INTERIM can never reach the next
    # regular session (~+8 months); a regression that made it huge would silently scrape the next session.
    if INTERIM_FORWARD_WINDOW > timedelta(days=120):
        failures.append(("INTERIM_FORWARD_WINDOW too large", INTERIM_FORWARD_WINDOW, "<=120d"))
    if failures:
        print(f"\n*** {len(failures)} FAILURE(S): {failures} ***")
        return 1
    print(f"\nAll {len(CASES)} compute_effective_scrape_end golden tests pass.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
