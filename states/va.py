"""Virginia — every VA assumption the bill pipeline used to hard-code, in one place.

Values are copied VERBATIM from bill_tracker.py as of 2026-10-31 (pre-split); `test_state_va_goldens.py` proves
the pipeline's output for a real 2026 sample is byte-identical before and after the move.
"""
import re

from .base import Stage, StateConfig

_BLOB = "https://lis.blob.core.windows.net/lisfiles/{session}/{file}"

VA = StateConfig(
    code="VA",
    name="Virginia",
    source_name="LIS",
    timezone="America/New_York",
    chambers={"H": "House", "S": "Senate"},
    # The crossover-lane pipeline (web/src/data/derive.ts Stage): origin committee + floor, the crossover
    # deadline, then the second chamber, then the Governor. VA sessions are annual (session_years=1).
    stages=(
        Stage("prefiled", "Prefiled"),
        Stage("committee1", "Committee"),
        Stage("floor1", "Floor"),
        Stage("crossover", "Crossover", marker=True),
        Stage("committee2", "Committee"),
        Stage("floor2", "Floor"),
        Stage("governor", "Governor"),
    ),
    session_years=1,
    bill_url_template="https://lis.virginia.gov/bill-details/{session}/{bill}",
    urls={
        "bill_list": "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync",
        "session_list": "https://lis.virginia.gov/Session/api/GetSessionListAsync",
        "legislation_search": "https://lis.virginia.gov/AdvancedLegislationSearch/api/GetLegislationListAsync",
        "blob": _BLOB,
    },
    outcome_vocab={
        "signed": ("approved", "acts of assembly", "chapter"),
        "vetoed": ("veto",),
        "carried_over": ("carried over", "continued"),
        "dead": ("passed by indefinitely", "stricken", "left in", "failed", "tabled",
                 "incorporated", "withdrawn", "no action"),
        "awaiting_governor": ("enrolled", "pending governor", "awaiting governor", "communicated to governor",
                              "governor's action"),
    },
    floor_patterns={
        "House": {"passed": re.compile(r"\bpassed house\b|\bagreed to by house\b", re.I),
                  "defeated": re.compile(r"\bdefeated by house\b", re.I)},
        "Senate": {"passed": re.compile(r"\bpassed senate\b|\bagreed to by senate\b", re.I),
                   "defeated": re.compile(r"\bdefeated by senate\b", re.I)},
    },
    two_chamber_bill_re=re.compile(r"^[HS]B"),
    # LIS's SUMMARY_TYPE vocabulary (Summaries.csv, measured on 20261 — see bill_tracker.SUMMARY_STAGE_RANK).
    summary_stage_rank={
        "SUMMARY AS INTRODUCED": 0,
        "SUMMARY AS PASSED HOUSE": 1,
        "SUMMARY AS PASSED SENATE": 1,
        "SUMMARY AS PASSED": 2,
        "SUMMARY AS ENACTED WITH GOVERNOR'S RECOMMENDATION": 3,
    },
    adapter="states.va_lis",
)


def blob_url(session: str, file: str) -> str:
    return VA.urls["blob"].format(session=session, file=file)
