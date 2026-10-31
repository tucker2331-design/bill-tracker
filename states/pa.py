"""Pennsylvania — the per-state contract for PA's General Assembly (LDPC bulk feeds), 2025-26 onward.

Every fact here was read off a REAL download on 2026-10-31 (tools/historical_cache/pa/2025_0/): the hourly
Bill History export and the House/Senate committee-schedule RSS. Nothing is carried over from Virginia:

  * TWO-YEAR session (`2025_0` = 2025-26 regular session). There is no crossover deadline, so there is no
    `crossover` stage; a bill reaching the second chamber is recorded as a fact, never as a deadline met or missed.
  * Bills do not "carry over" and are not declared dead inside an open session: a bill with no action is simply
    still pending until the session ends. The adapter never infers death from silence (no predictions).
  * A passed bill whose two chambers disagree goes back for CONCURRENCE before the Governor — its own stage.
  * Simple resolutions end at ADOPTION in one chamber (an outcome VA's contract does not have; added here).
  * Session codes are discovered at runtime from the data page's own list (states/pa_adapter.sessions_from_index),
    never hardcoded (Standard #5).
"""
import re

from .base import Stage, StateConfig

PA = StateConfig(
    code="PA",
    name="Pennsylvania",
    source_name="PA General Assembly (LDPC)",
    timezone="America/New_York",
    chambers={"H": "House", "S": "Senate"},
    stages=(
        Stage("introduced", "Introduced"),
        Stage("committee1", "Committee"),
        Stage("floor1", "Floor"),
        Stage("committee2", "Committee"),
        Stage("floor2", "Floor"),
        Stage("concurrence", "Concurrence / enrolment"),   # passed both floors; final vote on amendments or signing
        Stage("governor", "Governor"),
        Stage("law", "Law"),
        Stage("adopted", "Adopted"),   # a simple resolution's end, in one chamber
    ),
    session_years=2,
    # No per-bill page link is hardcoded: robots.txt protects /legislation/bills/* from crawling and we never fetch
    # one; the export carries its own structural URLs (bill-text PDF per printer's number, co-sponsorship memo).
    bill_url_template="",
    urls={
        "data_index": "https://www.palegis.us/data",
        "bill_history": "https://www.palegis.us/data/file?documentType=BillHistoryData&session={session}",
        "committee_schedule": "https://www.palegis.us/{chamber}/rss/committee/schedule",
    },
    two_chamber_bill_re=re.compile(r"^[HS]B"),
    adapter="states.pa_adapter",
)
