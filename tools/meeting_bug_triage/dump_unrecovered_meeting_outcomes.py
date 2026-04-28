"""
Read-only triage: dump Sheet1 rows that are meeting actions hiding in
Ledger Updates with placeholder times.

Context
-------
The PR-C6 full-session stress test (Mastermind Ghost Worker 2 cycle on
2026-04-28, post PR-C6.2 trim) surfaced 997 meeting bugs in X-Ray
Section 9 vs 0 in the crossover-week sample. 994 of the 997 are in
Committee="Ledger Updates" — i.e. real meeting actions (votes, reports,
readings) that fell through the worker's classification path because:

  1. The HISTORY row's verb is not in `MEETING_VERB_TOKENS` (the
     worker's PR-C3.1 LegislationEvent gate at calendar_worker.py:362),
     so the LegislationEvent fallback never fired.
  2. The worker's silent default is `Origin = "journal_default"` →
     row written to Sheet1 with Committee="Ledger Updates" and a
     placeholder time. Per CLAUDE.md Standard #4 the row is visible
     (PR-A source-miss visibility), but the time is not recovered.

To fix: identify which meeting verbs the worker is missing and add
them to `MEETING_VERB_TOKENS`. This script produces the verb dump
that PR-C6.3 (the actual fix) will be scoped against.

Method
------
Replicates the X-Ray's `classify_action()` logic inline (so this tool
runs without importing pages/ray2.py, which has a Streamlit dependency).
The patterns below are duplicated from `pages/ray2.py:70-145, 255-261`
and `calendar_worker.py:362-391` as of 2026-04-28. Drift risk
acknowledged — see docs/ideas/future_improvements.md "Per-state
lexicon extraction" for the consolidation plan.

Output
------
Three sections:

  1. Top N unique outcomes (where N = OUTCOME_TOP_N) by row count,
     among Sheet1 rows where Committee="Ledger Updates", Time is a
     placeholder, and classify_action(Outcome)=="meeting". This is
     the raw bug distribution.

  2. Verb-coverage analysis. For each of those outcomes, extract the
     verb prefix (first VERB_PREFIX_LEN chars, lowercased, normalized)
     and check whether ANY substring in `MEETING_VERB_TOKENS` matches
     it. Outcomes where NO worker token matches are the actionable
     additions for PR-C6.3.

  3. Suggested additions to `MEETING_VERB_TOKENS`, deduplicated by
     verb prefix and ordered by aggregate row count. Copy-paste-ready.

Read-only by construction
-------------------------
Auth uses `https://www.googleapis.com/auth/spreadsheets.readonly` scope.
No `update`, `append_rows`, `resize`, `add_worksheet`, `del_worksheet`,
`batch_update`, or `clear` calls anywhere. Output is stdout only.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
TARGET_SHEET = "Sheet1"
TARGET_COMMITTEE = "Ledger Updates"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
OUTCOME_TOP_N = 50
VERB_PREFIX_LEN = 60

# Investigation window — single source of truth at the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from investigation_config import INVESTIGATION_START, INVESTIGATION_END  # noqa: E402

# === Pattern lists duplicated from pages/ray2.py (X-Ray classifier) ===
# Source: pages/ray2.py:37-42, 70-145, 255-261 (as of 2026-04-28).
# DRIFT RISK: when the X-Ray's lists are edited, this file must be
# updated in lockstep until the lexicons/va.py extraction lands. See
# docs/ideas/future_improvements.md "Per-state lexicon extraction".

PLACEHOLDER_TIMES = {
    "", "nan", "none", "time tba", "journal entry", "ledger",
    "⏱️ [no_schedule_match]", "⏱️ [no_convene_anchor]",
}

MEETING_ACTION_PATTERNS = [
    "reported", "recommends", "recommend", "committee substitute",
    "incorporate", "incorporated", "incorporates", "discharged", "stricken",
    "tabled", "continued",
    "passed", "failed", "defeated", "amended",
    "floor substitute", "rules suspended", "offered",
    "block vote", "voice vote", "roll call",
    "reading dispensed", "read first", "read second", "read third",
    "agreed to", "rejected", "reconsidered",
    "conference report agreed",
    "insisted", "taken up", "reconsideration of", "receded",
    "reading waived", "reading of substitute waived", "reading of amendment waived",
    "reading of amendments waived", "reading of amendment not waived",
    "elected by", "election by", "elected to by",
    "emergency clause", "requested second conference committee",
    "motion for", "vote:",
    "withdrawn", "concurred",
    "removed from the table",
]

ADMINISTRATIVE_PATTERNS = [
    "referred to", "assigned", "rereferred",
    "placed on",
    "impact statement", "fiscal impact", "substitute printed",
    "reprinted", "printed as engrossed",
    "enrolled", "signed by", "presented", "communicated",
    "received", "engrossed",
    "conferee", "conference report", "requested conference committee", "acceded to request",
    "approved by governor", "vetoed", "governor's recommendation",
    "governor's substitute", "governor:",
    "laid on speaker's table", "laid on clerk's desk",
    "effective -", "acts of assembly chapter",
    "governor's action deadline", "action deadline",
    "scheduled",
    "left in",
    "blank action",
    "moved from uncontested calendar",
    "no further action taken",
    "unanimous consent to introduce", "introduced at the request of",
    "budget amendments available",
    "recommitted",
    "fiscal impact review",
    "prefiled and ordered printed",
    "(view meeting)",
    "no agenda listed",
    "subcommittee info",
    "speaker's conference room",
    "[memory anchor: admin]",
]

ADMIN_OVERRIDE_PATTERNS = [
    "substitute printed",
    "committee substitute printed",
    "prefiled and ordered printed",
]

# === Pattern list duplicated from calendar_worker.py (worker gate) ===
# Source: calendar_worker.py:362-391 (as of 2026-04-28). The PR-C3.1
# LegislationEvent fallback gate is "origin == journal_default AND
# any token in this list is a substring of outcome.lower()". Outcomes
# in the bug list whose verb prefix doesn't match ANY of these tokens
# are exactly what PR-C6.3 needs to add.
MEETING_VERB_TOKENS = [
    "reported from",
    "recommends reporting",
    "recommends continuing",
    "recommends passing",
    "recommends laying",
    "recommends defeating",
    "recommends striking",
    "committee amendment offered",
    "committee substitute offered",
    "subcommittee substitute offered",
    "subcommittee amendment offered",
    "committee offered",
    "subcommittee offered",
    "continued to next session",
    "continued to 2027",
    "passed by for the day",
    "passed by indefinitely",
    "engrossed",
    "read first time",
    "read second time",
    "read third time",
    "constitutional reading dispensed",
    "taken up",
    "laid on the table",
    "stricken from docket",
    "block vote",
    "voice vote",
    "rules suspended",
]


def normalize_time(value: str) -> str:
    return str(value or "").strip().lower()


def classify_action(outcome_text: str) -> str:
    """Replicates pages/ray2.py:263 verbatim."""
    lower = str(outcome_text).lower().strip()
    if not lower or lower in ("none", "nan"):
        return "administrative"
    if any(p in lower for p in ADMIN_OVERRIDE_PATTERNS):
        return "administrative"
    is_meeting = any(p in lower for p in MEETING_ACTION_PATTERNS)
    is_admin = any(p in lower for p in ADMINISTRATIVE_PATTERNS)
    if is_meeting:
        return "meeting"
    if is_admin:
        return "administrative"
    return "unclassified"


def in_window(date_str: str) -> bool:
    s = str(date_str or "").strip()
    if not s:
        return False
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return False
    start = datetime.strptime(INVESTIGATION_START, "%Y-%m-%d").date()
    end = datetime.strptime(INVESTIGATION_END, "%Y-%m-%d").date()
    return start <= d <= end


def extract_verb_prefix(outcome: str) -> str:
    """Strip leading 'H ' / 'S ' chamber prefix; lowercase; truncate."""
    s = str(outcome).strip()
    if s[:2] in ("H ", "S "):
        s = s[2:].lstrip()
    return s.lower()[:VERB_PREFIX_LEN]


def main() -> int:
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        print("ERROR: GCP_CREDENTIALS env var not set.", file=sys.stderr)
        return 1

    gc = gspread.authorize(
        Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    )
    sheet = gc.open_by_key(SPREADSHEET_ID)
    ws = sheet.worksheet(TARGET_SHEET)

    print(f"Workbook:        {sheet.title}")
    print(f"Spreadsheet ID:  {SPREADSHEET_ID}")
    print(f"Target sheet:    {TARGET_SHEET}")
    print(f"Window:          {INVESTIGATION_START} → {INVESTIGATION_END}")
    print(f"Filter:          Committee=='{TARGET_COMMITTEE}' AND Time in PLACEHOLDER_TIMES")
    print()

    rows = ws.get_all_records()
    print(f"Loaded {len(rows):,} rows from {TARGET_SHEET}.")

    in_window_count = 0
    ledger_count = 0
    placeholder_count = 0
    bugs: list[dict] = []
    classification_counter: Counter[str] = Counter()
    for r in rows:
        if not in_window(r.get("Date", "")):
            continue
        in_window_count += 1
        if str(r.get("Committee", "")).strip() != TARGET_COMMITTEE:
            continue
        ledger_count += 1
        if normalize_time(r.get("Time", "")) not in PLACEHOLDER_TIMES:
            continue
        placeholder_count += 1
        outcome = str(r.get("Outcome", "") or "")
        cls = classify_action(outcome)
        classification_counter[cls] += 1
        if cls == "meeting":
            bugs.append(
                {
                    "date": str(r.get("Date", "")),
                    "bill": str(r.get("Bill", "")),
                    "outcome": outcome,
                }
            )

    print(f"In-window:                                  {in_window_count:,}")
    print(f"In-window AND committee=Ledger Updates:     {ledger_count:,}")
    print(f"  ... AND time is placeholder:              {placeholder_count:,}")
    print(f"  ... by classify_action() result:")
    for cls, n in classification_counter.most_common():
        print(f"      {cls:>15}  {n:,}")
    print()

    if not bugs:
        print(
            "No meeting-classified rows in Ledger Updates with placeholder "
            "times. Either the bug class has been resolved, or the X-Ray's "
            "classifier disagrees with this script's inline copy. Verify "
            "by re-running the X-Ray and comparing Section 9's "
            "'Meeting Actions Missing Times' count."
        )
        return 0

    # === Section 1: top outcomes by count ===
    outcome_counter: Counter[str] = Counter(b["outcome"] for b in bugs)
    print(f"=== Top {OUTCOME_TOP_N} unique outcomes (out of {len(outcome_counter):,} unique, {len(bugs):,} total bug rows) ===")
    print()
    print(f"  {'count':>5}  outcome")
    print(f"  {'─' * 5}  {'─' * 80}")
    for outcome, n in outcome_counter.most_common(OUTCOME_TOP_N):
        truncated = (outcome[:90] + "…") if len(outcome) > 90 else outcome
        print(f"  {n:>5}  {truncated}")
    print()

    # === Section 2: verb-coverage analysis ===
    print("=== Verb-coverage analysis (vs calendar_worker.py:362 MEETING_VERB_TOKENS) ===")
    print()
    covered_count = 0
    uncovered_count = 0
    uncovered_by_prefix: Counter[str] = Counter()
    for b in bugs:
        verb_prefix = extract_verb_prefix(b["outcome"])
        if any(token in verb_prefix for token in MEETING_VERB_TOKENS):
            covered_count += 1
        else:
            uncovered_count += 1
            uncovered_by_prefix[verb_prefix] += 1

    print(f"Bug rows where some MEETING_VERB_TOKENS substring matches: {covered_count:,}")
    print(f"Bug rows where NO MEETING_VERB_TOKENS matches (actionable): {uncovered_count:,}")
    print()

    if uncovered_count == 0:
        print(
            "All meeting-bug rows already match a MEETING_VERB_TOKENS entry. "
            "The 994 must be unrecovered for a different reason — most "
            "likely Schedule API coverage gap (House range ends 2026-04-23) "
            "or LegislationEvent abstain (zero-overlap, wrong-chamber). "
            "Check worker run log for LegEvent telemetry."
        )
        return 0

    # === Section 3: suggested additions, ranked by impact ===
    print("=== Suggested MEETING_VERB_TOKENS additions (ranked by impact) ===")
    print()
    print("Each line is a unique verb prefix from a bug row whose outcome")
    print("does not match any current MEETING_VERB_TOKENS entry. The")
    print("`bug_rows` column is the count of rows whose verb prefix")
    print("starts with this string. Pick the smallest substring that")
    print("uniquely identifies the meeting verb without matching any")
    print("admin pattern in ADMINISTRATIVE_PATTERNS.")
    print()
    print(f"  {'bug_rows':>9}  prefix")
    print(f"  {'─' * 9}  {'─' * 60}")
    for prefix, n in uncovered_by_prefix.most_common(OUTCOME_TOP_N):
        print(f"  {n:>9,}  {prefix!r}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
