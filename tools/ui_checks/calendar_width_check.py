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

# ── the geometry, PARSED FROM THE REAL SOURCES (never hand-copied) ──────────────────────────────────────
# CodeRabbit #227 (Major) — and our own Standard #1: "never hardcode values derivable from an authoritative
# source at runtime." Hand-copied constants let a later CSS tweak leave this check green while the rendered
# calendar clips. Everything below is read out of web/src/index.css and Calendar.tsx, and a missing value is
# a hard FAILURE (never a silent default that would fake a pass).
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSS = os.path.join(ROOT, "web", "src", "index.css")
TSX = os.path.join(ROOT, "web", "src", "views", "Calendar.tsx")
DAYS = 7


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _need(match, what, path):
    if not match:
        raise SystemExit(f"❌ calendar_width_check: could not parse {what} from {os.path.relpath(path, ROOT)} "
                         f"— the layout moved; update this parser rather than the expectation.")
    return match


def _px(name, pattern, text, path, group=1):
    return int(_need(re.search(pattern, text), name, path).group(group))


def load_geometry():
    css, tsx = _read(CSS), _read(TSX)
    # spacing scale → the gap variables resolve through it
    scale = dict(re.findall(r"(--s\d):\s*(\d+)px", css))
    if not {"--s2", "--s4", "--s5"} <= set(scale):
        raise SystemExit("❌ calendar_width_check: spacing scale (--s2/--s4/--s5) not found in index.css")

    g = {
        "MAIN_MAX": _px("`.main` max-width", r"\.main\s*\{[^}]*?max-width:\s*(\d+)px", css, CSS),
        "MAIN_WIDE_MAX": _px("`.main.main-wide` max-width",
                             r"\.main\.main-wide\s*\{[^}]*?max-width:\s*(\d+)px", css, CSS),
        "MAIN_PAD": int(scale["--s5"]) * 2,
        "MINI_W": _px("`.cal-week-layout` picker column",
                      r"\.cal-week-layout\s*\{[^}]*?grid-template-columns:\s*1fr\s+(\d+)px", css, CSS),
        "LAYOUT_GAP": int(scale["--s4"]),
        "COL_GAP": int(scale["--s2"]),
        "STACK_AT": _px("the single-column stack breakpoint",
                        r"@media\s*\(max-width:\s*(\d+)px\)\s*\{\s*\.cal-week-layout", css, CSS),
    }
    # the inline fallback in Calendar.tsx IS the design minimum — parse it, don't assume it
    default_min = int(_need(re.search(r"minmax\(var\(--cal-day-min,\s*(\d+)px\)", tsx),
                            "the --cal-day-min fallback", TSX).group(1))
    steps = [(int(w), int(px)) for w, px in
             re.findall(r"@media\s*\(max-width:\s*(\d+)px\)\s*\{\s*\.cal-week\s*\{\s*--cal-day-min:\s*(\d+)px", css)]
    if not steps:
        raise SystemExit("❌ calendar_width_check: no --cal-day-min steps found in index.css")
    g["DAY_MIN_STEPS"] = sorted(steps) + [(None, default_min)]
    return g


G = load_geometry()
MAIN_MAX = G["MAIN_MAX"]
MAIN_WIDE_MAX = G["MAIN_WIDE_MAX"]
MAIN_PAD = G["MAIN_PAD"]
MINI_W = G["MINI_W"]
LAYOUT_GAP = G["LAYOUT_GAP"]
COL_GAP = G["COL_GAP"]
STACK_AT = G["STACK_AT"]
DAY_MIN_STEPS = G["DAY_MIN_STEPS"]


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
