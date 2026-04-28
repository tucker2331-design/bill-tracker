# === INVESTIGATION WINDOW — SINGLE SOURCE OF TRUTH ===
# This is the date range we're currently driving to zero bugs.
# Both calendar_worker.py and the X-Ray tool (pages/ray2.py + calendar_xray.py)
# import from this module so the window can never drift out of sync.
#
# To shift the zoom: edit these two strings and redeploy.
# Do NOT replace with rolling ends like `now + timedelta(...)` — that produces
# a mechanically growing bug count and breaks the investigation strategy
# (see docs/failures/assumptions_audit.md #38).
#
# Format: ISO date strings "YYYY-MM-DD", inclusive on both ends.
#
# History:
#   2026-02-09 → 2026-02-13: crossover-week test value, used while driving
#     bug count to 0 (see docs/testing/crossover_week_baseline.md). Closed
#     2026-04-27 with both halves of CLAUDE.md "done" criterion HIT.
#   2026-04-28 (PR-C6 / Move 3a): widened to full 2026 session
#     (Jan 14 → May 1) for the architecture stress test. Per
#     docs/failures/assumptions_audit.md #5.
INVESTIGATION_START = "2026-01-14"
INVESTIGATION_END = "2026-05-01"
