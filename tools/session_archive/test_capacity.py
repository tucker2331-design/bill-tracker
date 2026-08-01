"""Capacity arithmetic, asserted against MEASURED numbers only.

Two independent measurements of Session_20261 exist and they disagree slightly:
  - docs/architecture/session_archive.md (PR #131, 2026-06-14): 37,542 rows
  - docs/state/va_todo_2026-07-30.md (measured 2026-07-30):      37,837 rows
The difference is immaterial to every decision here — both give 9 sessions per workbook — and the tests
below assert that explicitly rather than picking a favourite. If a future change makes the two disagree in
CONSEQUENCE, this test fails and someone has to go re-measure, which is the point.

Run: python3 tools/session_archive/test_capacity.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capacity import (GOOGLE_SHEETS_CELL_CAP, SAFETY_MARGIN_CELLS, cells, workbook_cells,
                      fits, should_roll, headroom_sessions, describe)

# --- MEASURED baselines (never invented) ------------------------------------------------------------
SHEET1_COLS = 29            # measured 2026-07-30
ROWS_DOC = 37_542           # session_archive.md, PR #131
ROWS_TODO = 37_837          # va_todo_2026-07-30.md

_p = _f = 0


def is_(name, got, want):
    global _p, _f
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name} -> {got}{'' if ok else f' (want {want})'}")
    _p, _f = (_p + 1, _f) if ok else (_p, _f + 1)


print("cell arithmetic")
is_("29 cols x 37,542 rows", cells(ROWS_DOC, SHEET1_COLS), 1_088_718)
is_("29 cols x 37,837 rows", cells(ROWS_TODO, SHEET1_COLS), 1_097_273)
is_("workbook total sums grids", workbook_cells([(10, 2), (5, 4)]), 40)
# A degenerate grid must be 0, never negative — a negative would make a full workbook look empty.
is_("negative rows floor at 0", cells(-5, 29), 0)
is_("zero cols", cells(1000, 0), 0)

print("\nthe headline claim: the vault says 9 sessions; WITH the safety margin it is 8")
# The vault's "9 sessions ≈ 4.5 years" is the RAW division and it is right about the raw division.
# The margin costs exactly one session: 8 x 1,097,273 + 250,000 = 9,028,184 fits, but a 9th would need
# 10,125,457 > 10,000,000. So the number the roller acts on is 8, and the doc must say so — a plan built
# on 9 would roll one session too late, which is the failure this whole module exists to prevent.
sess_doc, sess_todo = cells(ROWS_DOC, SHEET1_COLS), cells(ROWS_TODO, SHEET1_COLS)
is_("raw division is 9 (doc)", GOOGLE_SHEETS_CELL_CAP // sess_doc, 9)
is_("raw division is 9 (todo)", GOOGLE_SHEETS_CELL_CAP // sess_todo, 9)
is_("with margin: 8 (doc measurement)", headroom_sessions(0, sess_doc), 8)
is_("with margin: 8 (todo measurement)", headroom_sessions(0, sess_todo), 8)
# The two measurements must reach the SAME answer — that is what makes their disagreement immaterial.
is_("both measurements agree", headroom_sessions(0, sess_doc), headroom_sessions(0, sess_todo))

print("\nthe roll decision")
is_("empty workbook takes a session", should_roll(0, sess_todo), False)
is_("7 sessions in, 8th fits", should_roll(7 * sess_todo, sess_todo), False)
is_("8 sessions in, 9th does NOT fit", should_roll(8 * sess_todo, sess_todo), True)
# The exact boundary: used + incoming + margin == cap must FIT (<=), one cell more must not.
_used = GOOGLE_SHEETS_CELL_CAP - SAFETY_MARGIN_CELLS - 1000
is_("exact boundary fits", fits(_used, 1000), True)
is_("one cell past the boundary does not", fits(_used + 1, 1000), False)
is_("should_roll is the negation of fits", should_roll(_used + 1, 1000), not fits(_used + 1, 1000))

print("\nfail-closed properties")
# A session larger than the whole cap can never fit anywhere — it must report roll, not silently pass.
is_("oversized session always rolls", should_roll(0, GOOGLE_SHEETS_CELL_CAP * 2), True)
is_("oversized session reports 0 headroom", headroom_sessions(0, GOOGLE_SHEETS_CELL_CAP * 2), 0)
# An UNKNOWN incoming size (0) must not be read as "fits fine" — headroom is 0, the conservative answer.
is_("unknown incoming size => 0 headroom", headroom_sessions(0, 0), 0)
# A workbook already over cap must never report room.
is_("over-cap workbook has no room", headroom_sessions(GOOGLE_SHEETS_CELL_CAP + 1, sess_todo), 0)
is_("over-cap workbook rolls", should_roll(GOOGLE_SHEETS_CELL_CAP + 1, sess_todo), True)
# headroom==0 and should_roll must agree by construction, at every size — not two thresholds that drift.
_bad = [n for n in range(0, GOOGLE_SHEETS_CELL_CAP, 250_000)
        if (headroom_sessions(n, sess_todo) == 0) != should_roll(n, sess_todo)]
is_("headroom==0 <=> should_roll, across the range", _bad, [])

print("\nthe sentence (P25: one template, values substituted)")
d = describe(9 * sess_todo, sess_todo)
is_("names both quantities and the room left", ("9,875,457" in d and "1,097,273" in d and "room for 0" in d), True)

print(f"\n{_p} of {_p + _f} passed")
sys.exit(1 if _f else 0)
