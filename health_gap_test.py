"""Unit tests for _quiet_window_overlap_minutes (the cycle-gap active-hours calibration, owner 2026-07-07).

The gap detector's WARN used to fire every morning on the benign overnight quiet-skip. The fix compares the
ACTIVE-hours gap (raw minus the overnight-quiet overlap) to the thresholds - so this helper's correctness is
what decides whether a real daytime outage still alerts while the nightly skip goes silent. Runnable with
plain python3 (matches cadence_test.py / session_rollover_test.py).
"""
import datetime

import pytz

import calendar_worker as cw

ET = pytz.timezone("America/New_York")
_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


def et2utc(y, mo, d, h, mi=0):
    return ET.localize(datetime.datetime(y, mo, d, h, mi)).astimezone(pytz.utc)


f = cw._quiet_window_overlap_minutes

# fully daytime (10:00-14:00 ET) → no quiet overlap
ok(f(et2utc(2026, 7, 15, 10), et2utc(2026, 7, 15, 14)) < 1, "daytime gap → ~0 quiet minutes")
# fully inside quiet (00:00-05:00 ET) → ~300 min
ok(abs(f(et2utc(2026, 7, 15, 0), et2utc(2026, 7, 15, 5)) - 300) <= 6, "00:00-05:00 → ~300 quiet min")
# spanning the quiet window (20:00 → next 06:00 ET, 10h) → quiet = 23:00-06:00 = ~420 min
ov = f(et2utc(2026, 7, 15, 20), et2utc(2026, 7, 16, 6))
ok(abs(ov - 420) <= 6, f"overnight span → ~420 quiet min, got {ov}")
# the benign overnight case: ACTIVE gap must fall UNDER the WARN floor (360) → no false WARN
raw = (et2utc(2026, 7, 16, 6) - et2utc(2026, 7, 15, 20)).total_seconds() / 60
ok(raw - ov < cw.GAP_WARN_MINUTES, f"benign overnight active gap {raw - ov:.0f} < WARN {cw.GAP_WARN_MINUTES} → silent")
# a real daytime outage (08:00-16:00 ET, 8h, no quiet) → full 480 active > WARN 360 → fires
day_active = (et2utc(2026, 7, 15, 16) - et2utc(2026, 7, 15, 8)).total_seconds() / 60 - \
    f(et2utc(2026, 7, 15, 8), et2utc(2026, 7, 15, 16))
ok(day_active >= cw.GAP_WARN_MINUTES, f"8h daytime outage active {day_active:.0f} ≥ WARN {cw.GAP_WARN_MINUTES} → fires")
# degenerate intervals
ok(f(et2utc(2026, 7, 15, 10), et2utc(2026, 7, 15, 10)) == 0.0, "empty interval → 0")
ok(f(et2utc(2026, 7, 15, 14), et2utc(2026, 7, 15, 10)) == 0.0, "reversed interval → 0")

print(f"ALL {_checks} health-gap tests passed")
