# === INVESTIGATION WINDOW — SINGLE SOURCE OF TRUTH ===
# This is the narrow date range we're currently driving to zero bugs.
# Both calendar_worker.py and the X-Ray tool (pages/ray2.py + calendar_xray.py)
# import from this module so the window can never drift out of sync.
#
# To shift the zoom: edit these two strings and redeploy.
# Do NOT replace with rolling ends like `now + timedelta(...)` — that produces
# a mechanically growing bug count and breaks the investigation strategy.
#
# Format: ISO date strings "YYYY-MM-DD", inclusive on both ends.
INVESTIGATION_START = "2026-02-09"
INVESTIGATION_END = "2026-02-13"
