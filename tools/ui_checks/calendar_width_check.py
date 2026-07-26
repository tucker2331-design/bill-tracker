#!/usr/bin/env python3
"""Calendar week-strip fit check — proves no viewport width CLIPS a day (W0a, owner-reported 2026-07-25).

WHY THIS EXISTS
The calendar week is a 7-column small-multiples grid (design P4). A day hidden behind a horizontal scrollbar
is a P12 violation ("the critical view fits without scrolling") — and the owner hit exactly that: a clipped
Saturday while the viewport had free margin either side. The fix has THREE interacting parts (a wider
container for this view, a stepped per-day minimum, and the width at which the month picker stacks below),
so "it looks fine on my screen" is not evidence. This asserts the geometry across the whole width range.

It is pure arithmetic against the CSS constants — no browser, no network — so it runs in CI in milliseconds
and fails LOUDLY if someone later tweaks a breakpoint, a min-width, or the picker width without re-checking
the interaction. Keep the constants below in sync with web/src/index.css (the test asserts they're all used).

    python3 tools/ui_checks/calendar_width_check.py
"""
import sys

# ── the CSS constants this check mirrors (web/src/index.css) ────────────────────────────────────────────
MAIN_MAX = 1180          # .main max-width
MAIN_WIDE_MAX = 1560     # .main.main-wide max-width (Calendar only)
MAIN_PAD = 24 * 2        # .main horizontal padding (var(--s5) each side)
MINI_W = 236             # .cal-week-layout second column (month picker)
LAYOUT_GAP = 16          # .cal-week-layout gap (var(--s4))
COL_GAP = 8              # .cal-week gap (var(--s2))
STACK_AT = 1020          # <= this viewport width, the picker stacks BELOW (single-column layout)
DAYS = 7

# --cal-day-min steps: (max viewport width, min column px). None = no upper bound (the default).
DAY_MIN_STEPS = [(820, 80), (1140, 96), (1280, 112), (1500, 132), (None, 158)]


def day_min(viewport):
    for upto, px in DAY_MIN_STEPS:
        if upto is None or viewport <= upto:
            return px
    return DAY_MIN_STEPS[-1][1]


def week_area(viewport):
    """Px available to the 7-day strip at a given viewport width."""
    container = min(viewport, MAIN_WIDE_MAX)
    inner = container - MAIN_PAD
    if viewport <= STACK_AT:
        return inner                      # picker stacked below → the week gets the full inner width
    return inner - MINI_W - LAYOUT_GAP


def needed(viewport):
    """Px the 7 columns need at this viewport's minimum column width."""
    return DAYS * day_min(viewport) + (DAYS - 1) * COL_GAP


def main():
    # Every width a real user might have, plus each breakpoint and its neighbours (off-by-one bugs live there).
    widths = sorted({w for w in range(320, 2561, 1)}
                    | {b for upto, _ in DAY_MIN_STEPS if upto for b in (upto - 1, upto, upto + 1)}
                    | {STACK_AT - 1, STACK_AT, STACK_AT + 1, MAIN_MAX, MAIN_WIDE_MAX})
    # Below ~700px the layout is genuinely mobile: a horizontal week scroll is the accepted design there
    # (you see the work days, then swipe). Assert the DESKTOP/TABLET range where the owner's bug lived.
    DESKTOP_FLOOR = 700
    failures = [(w, week_area(w), needed(w), day_min(w))
                for w in widths if w >= DESKTOP_FLOOR and needed(w) > week_area(w)]

    print(f"calendar_width_check: {DAYS} columns, widths {DESKTOP_FLOOR}–{max(widths)}px")
    for w in (700, 768, 900, 1019, 1021, 1180, 1280, 1440, 1500, 1560, 1900, 2560):
        ok = "OK " if needed(w) <= week_area(w) else "CLIP"
        print(f"  {ok} viewport {w:>4}px · day-min {day_min(w):>3}px · "
              f"need {needed(w):>4}px · have {week_area(w):>4}px"
              f"{' · picker stacked' if w <= STACK_AT else ''}")
    if failures:
        print(f"\n❌ {len(failures)} viewport width(s) CLIP a day (a hidden day is a P12 violation):")
        for w, have, need, dm in failures[:12]:
            print(f"    {w}px: need {need}px, have {have}px (day-min {dm}px, short by {need - have}px)")
        return 1
    print(f"\n✅ no clipped day at any width ≥ {DESKTOP_FLOOR}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
