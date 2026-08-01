"""Archive capacity — the arithmetic that decides when to roll to a NEW archive workbook.

WHY THIS EXISTS
---------------
Google caps a spreadsheet at 10,000,000 cells. MEASURED 2026-07-30: Sheet1 is 29 columns and the archived
``Session_20261`` holds 37,837 rows = 1,097,273 cells. Raw division says 9 sessions per workbook
(10,000,000 / 1,097,273 = 9.1); the safety margin below costs exactly one, so the number this module acts
on is **8** — 8 x 1,097,273 + 250,000 = 9,028,184 fits, a 9th would need 10,125,457. Virginia runs roughly
two sessions a year, so one archive workbook lasts about **4 years**. The vault's "9 sessions ≈ 4.5 years"
is right about the raw division and would roll one session TOO LATE, which is the exact failure already
seen in production on 2026-04-28: ``APIError [400]: This action would increase the number of cells in the
workbook above the limit of 10000000 cells``, thrown at the final write after the whole pipeline had run.

(An independent measurement in session_archive.md records 37,542 rows for the same tab. Both round to the
same decisions — see test_capacity.py, which asserts that rather than choosing between them.)

Owner's question, verbatim: *"is there any way to automate the creation and switching to a new google sheet
to make the archiving last forever?"* **Yes** — an archive is not one workbook, it is a CHAIN. When the
current one cannot fit the next session, create the next workbook and record it in a registry. The chain has
no length limit, so the archive lasts as long as the project does with no diary entry and no human step
(Standard #8, zero routine maintenance).

THE PART THAT MAKES A CHAIN WORK IS THE REGISTRY, NOT THE CREATION
------------------------------------------------------------------
Creating a workbook is one API call. The thing that makes the chain USABLE is knowing where each session
went: without a registry, ``Session_20261`` is in workbook A and ``Session_20293`` is in workbook D, and
nothing can find either. So the registry is the load-bearing piece and it is written BEFORE the snapshot is
trusted, never after (confirm-before-advance).

WHY THE ROLL DECISION IS "WILL THE NEXT ONE FIT", NOT A PERCENTAGE
------------------------------------------------------------------
A "roll at 80% full" rule is another magic number, and it is wrong in both directions: 80% of 10M is
2.1 sessions of headroom (wasteful), while a session bigger than the remaining 20% still fails. The honest
question is the one the failure actually asks — *does the incoming session fit?* — which is arithmetic on
two measured quantities and needs no constant. The only judgement is SAFETY_MARGIN below, and it is a margin
against measurement error, not a guess about capacity.

This module is PURE (no gspread, no credentials) so the decision is unit-testable without touching Sheets.
"""
from __future__ import annotations

GOOGLE_SHEETS_CELL_CAP = 10_000_000

# A snapshot is a `copy_to` of the FULL live grid, so the incoming size is the SOURCE workbook's Sheet1
# grid, which we measure rather than assume. This margin covers the difference between the allocated grid
# and what a copy actually materialises, plus the registry tab's own handful of cells. It is deliberately
# generous: rolling one session early costs a spreadsheet (free), rolling one session late costs a failed
# archive at session rollover — the asymmetry is not close.
SAFETY_MARGIN_CELLS = 250_000


def cells(rows: int, cols: int) -> int:
    """Allocated cell count of one grid. Sheets bills the ALLOCATED grid, not the populated range."""
    return max(0, int(rows)) * max(0, int(cols))


def workbook_cells(grids) -> int:
    """Total allocated cells across a workbook. `grids` is an iterable of (rows, cols)."""
    return sum(cells(r, c) for r, c in grids)


def fits(used_cells: int, incoming_cells: int, cap: int = GOOGLE_SHEETS_CELL_CAP,
         margin: int = SAFETY_MARGIN_CELLS) -> bool:
    """Can `incoming_cells` be added to a workbook already holding `used_cells`?"""
    return used_cells + incoming_cells + margin <= cap


def should_roll(used_cells: int, incoming_cells: int, cap: int = GOOGLE_SHEETS_CELL_CAP,
                margin: int = SAFETY_MARGIN_CELLS) -> bool:
    """True when the incoming session must go to a NEW workbook."""
    return not fits(used_cells, incoming_cells, cap, margin)


def headroom_sessions(used_cells: int, session_cells: int,
                      cap: int = GOOGLE_SHEETS_CELL_CAP, margin: int = SAFETY_MARGIN_CELLS) -> int:
    """How many more sessions of the given size fit. Reported so the alert can say 'room for 2 more'
    rather than a bare percentage — a count is the actionable form (P26: natural frequencies).

    Returns 0 when the next one does not fit, so `headroom_sessions(...) == 0` and `should_roll(...)` agree
    by construction rather than by two thresholds that can drift apart.
    """
    if session_cells <= 0:
        return 0
    free = cap - used_cells - margin
    return max(0, free // session_cells)


def describe(used_cells: int, incoming_cells: int, cap: int = GOOGLE_SHEETS_CELL_CAP,
             margin: int = SAFETY_MARGIN_CELLS) -> str:
    """One invariant sentence with values substituted — never a lookup table of wordings (P25)."""
    room = headroom_sessions(used_cells, incoming_cells, cap, margin)
    return (f"archive holds {used_cells:,} of {cap:,} cells; incoming session needs {incoming_cells:,}; "
            f"room for {room} more session(s) of this size after it")
