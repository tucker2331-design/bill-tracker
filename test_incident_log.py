"""Golden tests for the incident-log mechanism (tools/incident_log/log.py) — pure parts, network-free.

Run: python3 test_incident_log.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "incident_log"))
import log  # noqa: E402

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
ROW = lambda start, end, cls, summ="", by="": [start, end, cls, summ, by]  # noqa: E731

# 1. Genesis only, no real incident → days counts from the genesis epoch.
rows = [ROW("2026-07-01T00:00:00Z", "", "_genesis", "monitoring began")]
latest = log.latest_incident_end(rows)
ok(log.days_since(latest, NOW) == 19, f"genesis epoch → 19 days -> {log.days_since(latest, NOW)}")

# 2. A real incident AFTER genesis → counts from the incident's EndUTC, not genesis.
rows = [ROW("2026-07-01T00:00:00Z", "", "_genesis"),
        ROW("2026-07-10T08:00:00Z", "2026-07-10T09:30:00Z", "accuracy", "sentinel FAIL")]
latest = log.latest_incident_end(rows)
ok(log.days_since(latest, NOW) == 10, f"incident End 07-10 → 10 days -> {log.days_since(latest, NOW)}")

# 3. Open incident (no EndUTC) → falls back to StartUTC.
rows = [ROW("2026-07-18T06:00:00Z", "", "parity_gap", "LIS has a bill we don't")]
ok(log.days_since(log.latest_incident_end(rows), NOW) == 2, "open incident counts from StartUTC")

# 4. include_genesis=False ignores the epoch (used for 'incidents ever' vs 'days safe').
rows = [ROW("2026-07-01T00:00:00Z", "", "_genesis")]
ok(log.latest_incident_end(rows, include_genesis=False) is None, "genesis excluded when asked")

# 5. Malformed / short rows are skipped, never crash.
rows = [["bad"], ROW("2026-07-05T00:00:00Z", "", "accuracy"), [None, None, None, None, None]]
ok(log.days_since(log.latest_incident_end(rows), NOW) == 15, "malformed rows skipped; real one counts")

# 6. days_since floors at 0 (a clock skew can't produce a negative count) and None-latest → None.
ok(log.days_since(datetime(2026, 7, 25, tzinfo=timezone.utc), NOW) == 0, "future latest → 0, never negative")
ok(log.days_since(None, NOW) is None, "no latest → None")

# 7. record_incident refuses an unknown class (closed vocabulary) without touching Sheets.
ok(log.record_incident("not_a_class", "x", "test") is False, "unknown incident class refused")

# 8. record_incident is fail-open with no creds (prints, returns False, never raises).
os.environ.pop("GCP_CREDENTIALS", None)
ok(log.record_incident("accuracy", "test summary", "unit-test") is False, "no-creds record → False, no raise")

print(f"ALL {_checks} incident-log tests passed")
