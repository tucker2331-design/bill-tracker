"""Golden tests for the Change Ledger differ (tools/change_ledger/differ.py).

Pure + network-free. Exhaustively covers the delta types the ledger promises, plus the structural-identity
subtleties (refid makes a tally correction an EDIT; no-refid makes it remove+add — honestly).

Run: python3 test_change_ledger_differ.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "change_ledger"))
import differ  # noqa: E402

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


def kinds(deltas):
    return [d["kind"] for d in deltas]


H = lambda bill, date, refid, action: {"bill": bill, "date": date, "refid": refid, "action": action}  # noqa: E731

# 1. Unchanged history → no deltas.
rows = [H("HB1", "2026-02-10", "r1", "Reported (12-Y 9-N)"), H("HB1", "2026-02-11", "r2", "Read second time")]
ok(differ.diff_history(rows, rows) == [], "identical history must yield no deltas")

# 2. New action → history_added, carrying the new text + refid.
d = differ.diff_history(rows, rows + [H("HB1", "2026-02-12", "r3", "Passed House (55-Y 44-N)")])
ok(kinds(d) == ["history_added"], f"new action → added -> {kinds(d)}")
ok(d[0]["new"] == "Passed House (55-Y 44-N)" and d[0]["refid"] == "r3", f"added payload wrong -> {d[0]}")

# 3. THE MARQUEE CASE — a vote-tally CORRECTION with the SAME refid → history_edited (old→new), not remove+add.
prev = [H("HB1", "2026-02-10", "r1", "Reported from Agriculture (12-Y 9-N)")]
curr = [H("HB1", "2026-02-10", "r1", "Reported from Agriculture (12-Y 10-N)")]
d = differ.diff_history(prev, curr)
ok(kinds(d) == ["history_edited"], f"same-refid tally change → EDITED (not remove+add) -> {kinds(d)}")
ok(d[0]["old"].endswith("(12-Y 9-N)") and d[0]["new"].endswith("(12-Y 10-N)"), f"edit payload -> {d[0]}")

# 4. Removed action → history_removed.
d = differ.diff_history(rows, [rows[0]])
ok(kinds(d) == ["history_removed"] and d[0]["old"] == "Read second time", f"removal -> {d}")

# 5. NO-REFID honesty: a text change with empty refid CANNOT be an edit → surfaces as removed + added, never
#    a guessed edit (structural honesty — no stable id).
prev = [H("HB2", "2026-02-10", "", "Referred to Finance")]
curr = [H("HB2", "2026-02-10", "", "Referred to Appropriations")]
d = differ.diff_history(prev, curr)
ok(set(kinds(d)) == {"history_added", "history_removed"}, f"no-refid change → add+remove, not edit -> {kinds(d)}")
ok(not any(x["kind"] == "history_edited" for x in d), "must NOT fabricate an edit without a stable refid")

# 6. Reorder-only (same rows, different source order) → no deltas (order must not matter).
ok(differ.diff_history(rows, list(reversed(rows))) == [], "row order must not produce deltas")

# 7. Determinism: the delta list is stable regardless of input ordering.
a = differ.diff_history(rows, rows + [H("HB1", "2026-02-12", "r3", "X"), H("HB1", "2026-02-09", "r0", "Y")])
b = differ.diff_history(rows, [H("HB1", "2026-02-09", "r0", "Y")] + rows + [H("HB1", "2026-02-12", "r3", "X")])
ok(a == b, "diff must be deterministic regardless of input order")

# ── schedule ──
M = lambda date, committee, time, status="": {"date": date, "committee": committee, "time": time, "status": status}  # noqa: E731

# 8. Meeting time moved (same date+committee identity) → schedule_time_moved (old→new).
d = differ.diff_schedule([M("2026-02-19", "House Commerce", "8:00 AM")],
                         [M("2026-02-19", "House Commerce", "7:30 AM")])
ok(kinds(d) == ["schedule_time_moved"] and d[0]["old"] == "8:00 AM" and d[0]["new"] == "7:30 AM", f"time move -> {d}")

# 9. Meeting cancelled → schedule_cancelled (once; a cancelled meeting is not also a time-move).
d = differ.diff_schedule([M("2026-02-19", "Senate Courts", "2:00 PM")],
                         [M("2026-02-19", "Senate Courts", "2:00 PM", "CANCELLED")])
ok(kinds(d) == ["schedule_cancelled"], f"cancellation -> {kinds(d)}")

# 10. A brand-new meeting is NOT a schedule-change (it's a docket/witness ADD) → diff_schedule stays silent.
d = differ.diff_schedule([], [M("2026-02-19", "House Rules", "9:00 AM")])
ok(d == [], "a new meeting is not a schedule CHANGE (handled elsewhere)")

# ── docket ──
# 11. Bills added/removed from a meeting agenda.
prev = {("2026-02-19", "House Commerce"): ["HB1", "HB2"]}
curr = {("2026-02-19", "House Commerce"): ["HB2", "HB3"]}
d = differ.diff_docket(prev, curr)
ok(set(kinds(d)) == {"docket_added", "docket_removed"}, f"docket membership -> {kinds(d)}")
added = [x["bill"] for x in d if x["kind"] == "docket_added"]
removed = [x["bill"] for x in d if x["kind"] == "docket_removed"]
ok(added == ["HB3"] and removed == ["HB1"], f"docket add/remove bills wrong -> +{added} -{removed}")

# 12. Unchanged docket → no deltas.
ok(differ.diff_docket(prev, prev) == [], "unchanged docket → no deltas")

# 13. Every emitted kind is in the closed KINDS set (no stray kinds leak).
alld = (differ.diff_history(rows, rows + [H("HB9", "2026-03-01", "r9", "Z")])
        + differ.diff_schedule([M("2026-02-19", "X", "8:00 AM")], [M("2026-02-19", "X", "9:00 AM")])
        + differ.diff_docket({("d", "c"): ["HB1"]}, {("d", "c"): []}))
for x in alld:
    ok(x["kind"] in differ.KINDS, f"stray kind escaped the closed set: {x['kind']}")

print(f"ALL {_checks} change-ledger differ tests passed")
