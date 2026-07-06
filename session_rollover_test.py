"""Unit tests for the A-2 session-rollover snapshot verification (confirm-before-advance).

Pure logic only — the grid-dimension check that decides whether an archived snapshot is trustworthy
BEFORE the worker advances the session marker (V1). If this is wrong, the worker could advance past a
partial/failed archive and lose a completed session's data — so it's worth measuring (Standard #7).

Also asserts the two DELIBERATELY-DUPLICATED copies (calendar_worker + tools/session_archive/archive.py,
which the docstrings promise to keep in sync) actually agree. Runnable with plain python3; matches
cadence_test.py / lis_authorization_test.py (standalone, local validation).
"""
import importlib.util
import os

import calendar_worker as cw

# load the standalone tool's module by path to compare its copy of the pure helper
_spec = importlib.util.spec_from_file_location(
    "session_archive_archive",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "session_archive", "archive.py"))
_arch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_arch)

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


# Both copies: identical dims pass; any shrink flags; ints are coerced (Sheets metadata can arrive as str).
for name, fn in [("worker", cw._snapshot_dim_mismatch), ("archive.py", _arch._snapshot_dim_mismatch)]:
    ok(fn(1000, 10, 1000, 10) == "", f"{name}: identical dims -> no mismatch")
    ok(fn(1000, 10, 999, 10) != "", f"{name}: fewer archived ROWS -> mismatch flagged (partial snapshot)")
    ok(fn(1000, 10, 1000, 9) != "", f"{name}: fewer archived COLS -> mismatch flagged")
    ok(fn(1000, 10, 1001, 10) != "", f"{name}: MORE archived rows -> still a mismatch (unexpected)")
    ok(fn("1000", "10", 1000, 10) == "", f"{name}: string dims coerced to int, equal -> no mismatch")
    ok("999" in fn(1000, 10, 999, 10), f"{name}: the description names the archived row count")

# The two copies must AGREE on every case (they're kept in sync on purpose).
for args in [(5, 5, 5, 5), (5, 5, 4, 5), (5, 5, 5, 4), (0, 0, 0, 0), (10, 26, 10, 27), (232000, 11, 231999, 11)]:
    ok((cw._snapshot_dim_mismatch(*args) == "") == (_arch._snapshot_dim_mismatch(*args) == ""),
       f"worker vs archive.py disagree on dims {args} — the two copies have drifted")

print(f"ALL {_checks} session-rollover tests passed")
