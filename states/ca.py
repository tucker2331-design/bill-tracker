"""California — the per-state contract for the California Legislature (Legislative Counsel's pubinfo database).

Source and terms (scoped 2026-11-18, docs/knowledge/ca_pubinfo.md):
  * pubinfo is a relational export of the whole legislative record (bills, history, versions, authors, hearings,
    daily file, summary + per-member votes, legislators, location codes) at downloads.leginfo.legislature.ca.gov —
    a plain file index with no robots.txt. The Readme tells the public to load it into their own database.
  * Law: Government Code §10248 (free public access) and §10248.5 (the information is in the public domain; the
    State retains no copyright). The interactive site leginfo.legislature.ca.gov sits behind a bot challenge —
    it is NEVER fetched; CA is bulk files only (the PA rule).
  * Cadence: `pubinfo_<year>.zip` (full session, rebuilt Sunday) + `pubinfo_<Day>.zip` (that day's changed rows,
    Mon–Sat). The site is DAILY by construction; nothing here pretends to be faster.

Facts read off a REAL download (tools/historical_cache/ca/2025/), not carried over from Virginia or Pennsylvania:
  * TWO-YEAR session (`20252026`). Bills are AB/SB; resolutions ACR/SCR/AJR/SJR/HR/SR; constitutional amendments
    ACA/SCA. The first letter of the measure type names the house of origin (A = Assembly, S = Senate; HR = House
    Resolution of the Assembly).
  * A HOUSE-OF-ORIGIN deadline exists (a bill must pass its first house by a set date) — CA's crossover marker.
  * A passed bill becomes law by CHAPTERING (chapter number in BILL_TBL) or ends by VETO — both are fields.
"""
import re

from .base import Stage, StateConfig

CA = StateConfig(
    code="CA",
    name="California",
    source_name="California Legislature (Legislative Counsel pubinfo)",
    timezone="America/Los_Angeles",
    # measure-type first letter -> chamber. The contract's lower-chamber name is "House" (every consumer reads
    # House/Senate); California calls it the Assembly — a DISPLAY label (CHAMBER_DISPLAY below), never a code path.
    # "H" = the Assembly's House Resolutions (HR).
    chambers={"A": "House", "S": "Senate", "H": "House"},
    stages=(
        Stage("introduced", "Introduced"),
        Stage("committee1", "Committee"),
        Stage("floor1", "Floor"),
        Stage("crossover", "House of origin deadline", marker=True),
        Stage("committee2", "Committee"),
        Stage("floor2", "Floor"),
        Stage("concurrence", "Concurrence / enrollment"),
        Stage("governor", "Governor"),
        Stage("law", "Chaptered"),
        Stage("adopted", "Adopted"),
    ),
    session_years=2,
    bill_url_template="",            # leginfo bill pages are behind a bot challenge; never linked by a fetcher
    urls={
        "index": "https://downloads.leginfo.legislature.ca.gov/",
        "session_zip": "https://downloads.leginfo.legislature.ca.gov/pubinfo_{year}.zip",
        "day_zip": "https://downloads.leginfo.legislature.ca.gov/pubinfo_{day}.zip",
    },
    two_chamber_bill_re=re.compile(r"^(AB|SB|ACA|SCA|ACR|SCR|AJR|SJR)"),
    adapter="states.ca_adapter",
)

# How each contract chamber name is shown to a reader in California.
CHAMBER_DISPLAY = {"House": "Assembly", "Senate": "Senate"}
