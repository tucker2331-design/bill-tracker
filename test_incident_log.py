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

# 9. THE UNDER-REPORT BUG (Gemini #225): a real incident whose trailing optional cols (Summary/DetectedBy)
#    were trimmed by Sheets — length 3, not 5 — MUST still be counted, or the counter reads "safe" while an
#    incident exists. Under the old `< len(HEADER)` guard this row was skipped; it must count now.
rows = [ROW("2026-07-01T00:00:00Z", "", "_genesis"),
        ["2026-07-15T00:00:00Z", "2026-07-15T02:00:00Z", "accuracy"]]  # len 3, trailing cols trimmed
ok(log.days_since(log.latest_incident_end(rows), NOW) == 5,
   f"trimmed-length real incident must be counted (was the under-report bug) -> {log.days_since(log.latest_incident_end(rows), NOW)}")

# 10. Space-separated timestamps parse (Gemini #225): a manual edit / other tool may not use the 'T'.
ok(log._parse_iso("2026-07-10 09:30:00") is not None, "space-separated ISO must parse")
ok(log._parse_iso("2026-07-10 09:30:00") == log._parse_iso("2026-07-10T09:30:00Z"), "space == T parse")
ok(log._parse_iso("garbage") is None, "unparseable → None, no raise")

# 11. Skipped-row VISIBILITY (CodeRabbit #226): an EMPTY row is silent padding; a non-empty but unusable
#     (< 3 cols) row is a DATA ANOMALY surfaced via the `malformed` collector, never silently dropped.
mal = []
rows = [ROW("2026-07-01T00:00:00Z", "", "_genesis"),
        ["", "", ""],                       # empty padding → silent, NOT collected
        ["partial-junk", "x"]]              # len 2, has data → malformed, collected
latest = log.latest_incident_end(rows, malformed=mal)
ok(mal == [["partial-junk", "x"]], f"non-empty unreadable row surfaced; empty row silent -> {mal}")
ok(log.days_since(latest, NOW) == 19, "genesis still counted alongside the malformed collection")


# ── W1: the counter means "days we could VERIFY clean" ─────────────────────────────────────────────────
# 12. FIRE DRILLS (owner: "don't build fake sandboxes to avoid resetting the timer"). A `_drill` row runs the
#     real write path against the real ledger, so it MUST NOT move the clock or the incident count — exactly
#     like `_genesis`. If this ever regressed, testing the alarm would burn the streak and nobody would test it.
rows = [ROW("2026-07-01T00:00:00Z", "", "_genesis"),
        ROW("2026-07-18T09:00:00Z", "2026-07-18T09:00:00Z", "_drill")]
ok(log.days_since(log.latest_incident_end(rows), NOW) == 19,
   "a fire drill does NOT reset the clock (genesis still the epoch)")
st = log.counter_state(rows, NOW)
ok(st["incidents_ever"] == 0, "a drill is not counted as an incident")
ok(st["last_drill_days"] == 2, f"the drill IS dated for the staleness signal -> {st['last_drill_days']}")
ok(log.counter_state([ROW("2026-07-01T00:00:00Z", "", "_genesis")], NOW)["last_drill_days"] is None,
   "no drill on record reads as None (an unproven write path), never as 0")

# 13. THE DENOMINATOR (Standard #7 applied to our own trust number): "N days clean" alone is meaningless, and
#     a young counter must not masquerade as a long record.
ok(log.monitoring_days([ROW("2026-07-01T00:00:00Z", "", "_genesis")], NOW) == 19,
   "monitoring_days measures from genesis")
ok(log.monitoring_days([ROW("2026-07-05T00:00:00Z", "", "accuracy")], NOW) is None,
   "no genesis => monitoring window is UNKNOWN, not a fabricated number")

# 14. OPEN-INCIDENT DEDUP (W1.2) — the flood fix. A 3-day outage fails ~100 cycles; without this the ledger
#     would show 100 incidents for ONE event and lie in the pessimistic direction.
outage = [ROW("2026-07-01T00:00:00Z", "", "_genesis"),
          ROW("2026-07-19T00:00:00Z", "", "accuracy", "sentinel FAIL", "accuracy_sentinel")]
ok(log.has_open(outage, "accuracy", "accuracy_sentinel"), "an unclosed incident reads as OPEN")
ok(not log.has_open(outage, "accuracy", "completeness_tripwire"),
   "dedup is per-DETECTOR: another guard may still open its own incident for the same class")
ok(not log.has_open(outage, "parity_gap", "accuracy_sentinel"),
   "dedup is per-CLASS: the same guard may open a different class")
closed = [ROW("2026-07-01T00:00:00Z", "", "_genesis"),
          ROW("2026-07-19T00:00:00Z", "2026-07-19T06:00:00Z", "accuracy", "recovered", "accuracy_sentinel")]
ok(not log.has_open(closed, "accuracy", "accuracy_sentinel"),
   "once EndUTC is filled the incident is no longer open (recovery detection is free)")

# 15. WHILE AN INCIDENT IS OPEN the clock reads from its START, so the counter cannot claim clean days during
#     an ongoing failure (fail-closed).
ok(log.days_since(log.latest_incident_end(outage), NOW) == 1,
   "an OPEN incident dates the clock from StartUTC, so the streak is broken now")
ok(log.counter_state(outage, NOW)["open_now"] == ["accuracy"], "the open class is reported for the red state")

# 16. The new classes exist and are CLOSED — `unverified` (an unknown is a violation) and `false_alarm` (a red
#     ring with no data failure under it is still a broken promise). A typo must not invent a class.
for cls in ("unverified", "false_alarm"):
    ok(cls in log.CLASSES, f"{cls} is a recognised class")
ok(log.record_incident("nope", "x", "y") is False, "an unknown class is refused, not coerced")
ok(log.NON_INCIDENT_CLASSES == frozenset({"_genesis", "_drill"}),
   "only genesis + drill are excluded from the clock — every real class counts")

print(f"ALL {_checks} incident-log tests passed")
