import os
import sys
import json
import time
import requests
import gspread
import pandas as pd
import re
import io
import tempfile
import urllib.parse
from datetime import datetime, timedelta, timezone
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup
import pdfplumber

from investigation_config import INVESTIGATION_START as _WINDOW_START_STR
from investigation_config import INVESTIGATION_END as _WINDOW_END_STR

print("🚀 Waking up Enterprise Calendar Worker (Turing State Machine v6.0)...")

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# PR-C3: LegislationEvent / LegislationVersion endpoints reject the legacy
# WebAPIKey with HTTP 401 — they require the SPA's public key (sourced from
# https://lis.virginia.gov/handleTitle.js, which is loaded by every public
# page). Both keys are public; neither alone covers the full API surface.
# See docs/knowledge/lis_api_reference.md for the full key→endpoint mapping.
LIS_PUBLIC_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"
LEGISLATION_EVENT_HEADERS = {
    "WebAPIKey": LIS_PUBLIC_API_KEY,
    "Accept": "application/json",
}

# === INVESTIGATION WINDOW ===
# Single source of truth lives in investigation_config.py and is imported by
# both the worker and the X-Ray tool. The strings are parsed to datetime here
# for the worker's scrape-window filter. Do NOT define the window inline in
# this file — edit investigation_config.py to shift the zoom.
INVESTIGATION_START = datetime.strptime(_WINDOW_START_STR, "%Y-%m-%d")
INVESTIGATION_END = datetime.strptime(_WINDOW_END_STR, "%Y-%m-%d")

# === STATIC FALLBACK LEXICON (used only if Committee API is unavailable) ===
# Validated against session 261 Committee API response on 2026-04-03.
# Runtime: replaced by build_committee_maps() output from live API.
_STATIC_LOCAL_LEXICON = {
    "House Appropriations": ["appropriations"],
    "House Courts of Justice": ["courts of justice"],
    "House Rules": ["rules"],
    "House Finance": ["finance"],
    "House Counties, Cities and Towns": ["counties, cities and towns"],
    "House Privileges and Elections": ["privileges and elections"],
    "House Public Safety": ["public safety"],
    "House Communications, Technology and Innovation": ["communications", "technology", "innovation"],
    "House Education": ["education"],
    "House Agriculture, Chesapeake and Natural Resources": ["agriculture", "natural resources"],
    "House General Laws": ["general laws"],
    "House Transportation": ["transportation"],
    "House Labor and Commerce": ["labor and commerce", "labor"],
    "House Health and Human Services": ["health and human services", "health"],
    "Senate Finance and Appropriations": ["finance and appropriations", "finance"],
    "Senate Courts of Justice": ["courts of justice"],
    "Senate Rules": ["rules"],
    "Senate Rehabilitation and Social Services": ["rehabilitation and social services", "rehabilitation"],
    "Senate Local Government": ["local government"],
    "Senate Privileges and Elections": ["privileges and elections"],
    "Senate Education and Health": ["education and health", "education", "health"],
    "Senate Commerce and Labor": ["commerce and labor", "commerce"],
    "Senate General Laws and Technology": ["general laws and technology", "general laws"],
    "Senate Transportation": ["transportation"],
    "Senate Agriculture, Conservation and Natural Resources": ["agriculture", "conservation", "natural resources"]
}
LOCAL_LEXICON = dict(_STATIC_LOCAL_LEXICON)  # Will be replaced at runtime by build_committee_maps()

IGNORE_WORDS = {"committee", "on", "the", "of", "and", "for", "meeting", "joint", "to", "referred", "assigned", "re-referred", "substitute", "substitutes", "placed", "with", "amendment", "amendments", "a", "an", "by", "recommendation", "recommends", "recommend", "block", "vote", "voice"}

# === NOISE FILTER CONSTANTS (Positive Identification) ===
# Enterprise standard: actions are classified as KNOWN_NOISE, KNOWN_EVENT, or UNKNOWN.
# KNOWN_NOISE is silently filtered. KNOWN_EVENT passes through.
# UNKNOWN is flagged for human review (surfaced as ❓ tag, not suppressed).
#
# Assumption: these lists cover all Virginia action types for session 261.
# How it could break: new action types introduced in future sessions.
# Runtime check: UNKNOWN actions are tagged and counted; spike = new action type.
KNOWN_NOISE_PATTERNS = [
    "impact statement", "substitute printed", "laid on speaker's table",
    "laid on clerk's desk", "reprinted",
    "engrossed by senate - committee substitute",
    "engrossed by house - committee substitute",
    "printed as engrossed", "effective -",
    "fiscal impact statement", "acts of assembly chapter",
    # Administrative / scheduling entries (not real legislative actions)
    "governor's action deadline", "action deadline",
    "scheduled", "left in",
    "blank action", "fiscal impact review",
]
# NOTE: "enrolled", "signed by", "presented", "communicated" are real legislative
# milestones (not noise) but are ADMINISTRATIVE — they don't require people in a
# room at a specific time. They stay in KNOWN_EVENT (not silently filtered) but
# are NOT in ABSOLUTE_FLOOR_VERBS. See docs/failures/assumptions_audit.md #11, #24.
KNOWN_EVENT_PATTERNS = [
    "referred to", "assigned", "reported", "passed", "failed",
    "defeated", "tabled", "continued", "incorporate", "incorporated", "incorporates",
    "committee substitute", "floor substitute", "amended",
    "recommends", "recommend", "rereferred",
    "discharged", "stricken", "reconsidered", "conferee", "conference report",
    "approved by governor", "vetoed", "governor's",
    "placed on", "block vote", "voice vote", "roll call",
    "reading dispensed", "read first", "read second", "read third",
    "agreed to", "rejected",
    "enrolled", "signed by", "presented", "communicated",
    "received", "engrossed",
    "rules suspended", "offered",
    "requested conference committee", "acceded to request",
    # Floor actions: parliamentary maneuvering, conference resolution, readings
    "insisted", "taken up", "reconsideration of", "receded",
    "reading waived", "reading of substitute waived", "reading of amendment waived",
    "reading of amendments waived", "reading of amendment not waived",
    "elected by", "election by", "elected to by",
    "emergency clause", "requested second conference committee",
    "motion for", "vote:",
    "withdrawn", "concurred",
    # Administrative milestones (preserved for Ledger, not silently filtered)
    "moved from uncontested calendar", "no further action taken",
    "unanimous consent to introduce", "introduced at the request of",
    "budget amendments available", "recommitted",
    "removed from the table",
]

# === STATIC FALLBACK COMMITTEE CODE MAP ===
# Validated against session 261 Committee API + 3,868 HISTORY.CSV referrals.
# Runtime: replaced by build_committee_maps() output from live API.
# Drift detection: if live API returns different mappings, a COMMITTEE_DRIFT alert fires.
_STATIC_COMMITTEE_CODE_MAP = {
    "H01": "House Agriculture, Chesapeake and Natural Resources",
    "H02": "House Appropriations",
    "H07": "House Counties, Cities and Towns",
    "H08": "House Courts of Justice",
    "H09": "House Education",
    "H10": "House Finance",
    "H11": "House General Laws",
    "H14": "House Labor and Commerce",
    "H15": "House Public Safety",
    "H18": "House Privileges and Elections",
    "H19": "House Transportation",
    "H20": "House Rules",
    "H21": "House Communications, Technology and Innovation",
    "H24": "House Health and Human Services",
    "S01": "Senate Agriculture, Conservation and Natural Resources",
    "S02": "Senate Commerce and Labor",
    "S04": "Senate Education and Health",
    "S05": "Senate Finance and Appropriations",
    "S07": "Senate Local Government",
    "S08": "Senate Privileges and Elections",
    "S09": "Senate Rehabilitation and Social Services",
    "S10": "Senate Rules",
    "S11": "Senate Transportation",
    "S12": "Senate General Laws and Technology",
    "S13": "Senate Courts of Justice",
}
COMMITTEE_CODE_MAP = dict(_STATIC_COMMITTEE_CODE_MAP)  # Will be replaced at runtime

# === PARENT COMMITTEE MAP ===
# Maps CommitteeNumber -> parent CommitteeNumber (from API ParentCommitteeID).
# Used to validate subcommittee->parent fallback instead of name heuristics.
PARENT_COMMITTEE_MAP = {}  # Populated at runtime by build_committee_maps()

# === CHILDREN OF PARENT (reverse of PARENT_COMMITTEE_MAP) ===
# Maps parent CommitteeNumber -> list of child CommitteeNumbers.
# Pre-calculated to avoid O(n) scan of PARENT_COMMITTEE_MAP inside find_api_schedule_match().
CHILDREN_OF_PARENT = {}  # Populated at runtime by build_committee_maps()

# === NORMALIZED REVERSE LOOKUP (O(1) name->code) ===
# Pre-calculated after build_committee_maps() to avoid O(n) scans inside 60k-row loops.
NORM_TO_CODE = {}  # Populated at runtime by build_committee_maps()


def build_committee_maps(http_session, session_code, alert_fn=None):
    """Rebuild COMMITTEE_CODE_MAP, LOCAL_LEXICON, and PARENT_COMMITTEE_MAP from Committee API.

    Returns (code_map, lexicon, parent_map, success).
    On failure, returns static fallbacks with success=False.

    Assumption: Committee API returns all committees including subcommittees.
    How it could break: API schema changes, new fields, or endpoint moves.
    Runtime check: Drift detection compares live vs static and alerts on differences.
    """
    global COMMITTEE_CODE_MAP, LOCAL_LEXICON, PARENT_COMMITTEE_MAP, NORM_TO_CODE, CHILDREN_OF_PARENT

    url = f"https://lis.virginia.gov/Committee/api/getcommitteelistasync?sessionCode={session_code}"
    try:
        res = http_session.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"⚠️ Committee API returned status {res.status_code}. Using static fallback.")
            if alert_fn:
                alert_fn(f"⚠️ Committee API returned HTTP {res.status_code}. Using static COMMITTEE_CODE_MAP.", status="WARN")
            NORM_TO_CODE = {normalize_room_key(v): k for k, v in _STATIC_COMMITTEE_CODE_MAP.items()}
            return dict(_STATIC_COMMITTEE_CODE_MAP), dict(_STATIC_LOCAL_LEXICON), {}, False

        raw = res.json()
        committees = raw.get('Committees', []) if isinstance(raw, dict) else raw
        if not isinstance(committees, list) or len(committees) == 0:
            print("⚠️ Committee API returned empty list. Using static fallback.")
            if alert_fn:
                alert_fn("⚠️ Committee API returned 0 committees. Using static COMMITTEE_CODE_MAP.", status="WARN")
            NORM_TO_CODE = {normalize_room_key(v): k for k, v in _STATIC_COMMITTEE_CODE_MAP.items()}
            return dict(_STATIC_COMMITTEE_CODE_MAP), dict(_STATIC_LOCAL_LEXICON), {}, False

        # Build code map from API
        live_code_map = {}
        live_parent_map = {}  # CommitteeNumber -> parent CommitteeNumber
        committee_id_to_number = {}  # CommitteeID -> CommitteeNumber (for parent resolution)

        for c in committees:
            code = str(c.get('CommitteeNumber', '')).strip()
            name = str(c.get('Name', '')).strip()
            chamber = str(c.get('ChamberCode', '')).strip()
            comm_id = c.get('CommitteeID')
            parent_id = c.get('ParentCommitteeID')

            if not code or not name:
                continue

            # Build full name with chamber prefix
            chamber_prefix = "House " if chamber == "H" else "Senate " if chamber == "S" else ""
            full_name = f"{chamber_prefix}{name}"
            live_code_map[code] = full_name

            if comm_id is not None:
                committee_id_to_number[comm_id] = code

            if parent_id is not None:
                # Store parent_id temporarily; resolve to code after all committees loaded
                live_parent_map[code] = parent_id

        # Resolve parent IDs to committee numbers
        resolved_parent_map = {}
        for child_code, parent_id in live_parent_map.items():
            parent_code = committee_id_to_number.get(parent_id)
            if parent_code:
                resolved_parent_map[child_code] = parent_code

        # Build lexicon from API names
        live_lexicon = {}
        for code, full_name in live_code_map.items():
            # Skip subcommittees for lexicon (they're matched via parent fallback)
            if code in resolved_parent_map:
                continue
            # Extract the committee name part (after "House "/"Senate ")
            parts = full_name.split(" ", 1)
            if len(parts) < 2:
                continue
            name_part = parts[1].lower()
            # Generate aliases: full name, and each comma/and-separated segment
            aliases = [name_part]
            for segment in re.split(r',\s*|\s+and\s+', name_part):
                segment = segment.strip()
                if segment and len(segment) > 3:  # Skip tiny fragments like "and"
                    aliases.append(segment)
            live_lexicon[full_name] = aliases

        # === DRIFT DETECTION ===
        # Compare live vs static to catch unexpected changes
        drift_messages = []
        for code, static_name in _STATIC_COMMITTEE_CODE_MAP.items():
            if code not in live_code_map:
                drift_messages.append(f"Static code {code} ({static_name}) missing from live API")
            elif live_code_map[code] != static_name:
                drift_messages.append(f"Code {code} name changed: '{static_name}' -> '{live_code_map[code]}'")
        for code in live_code_map:
            if code not in _STATIC_COMMITTEE_CODE_MAP and code not in resolved_parent_map:
                drift_messages.append(f"New top-level committee from API: {code} = {live_code_map[code]}")

        if drift_messages:
            drift_summary = "; ".join(drift_messages[:5])  # Cap at 5 to avoid massive alerts
            print(f"🔄 COMMITTEE_DRIFT detected: {drift_summary}")
            if alert_fn:
                alert_fn(f"🔄 COMMITTEE_DRIFT: {drift_summary}", status="WARN")

        # Apply live maps
        COMMITTEE_CODE_MAP = live_code_map
        LOCAL_LEXICON = live_lexicon
        PARENT_COMMITTEE_MAP = resolved_parent_map
        NORM_TO_CODE = {normalize_room_key(v): k for k, v in live_code_map.items()}
        # Pre-calculate reverse parent->children map for O(1) lookups in find_api_schedule_match()
        CHILDREN_OF_PARENT = {}
        for child_code, parent_code in resolved_parent_map.items():
            CHILDREN_OF_PARENT.setdefault(parent_code, []).append(child_code)

        print(f"✅ Committee maps rebuilt from API: {len(live_code_map)} codes, {len(live_lexicon)} lexicon entries, {len(resolved_parent_map)} parent relationships.")
        return live_code_map, live_lexicon, resolved_parent_map, True

    except Exception as e:
        print(f"⚠️ Committee API call failed: {e}. Using static fallback.")
        if alert_fn:
            alert_fn(f"⚠️ Committee API failed: {e}. Using static COMMITTEE_CODE_MAP.", status="WARN")
        NORM_TO_CODE = {normalize_room_key(v): k for k, v in _STATIC_COMMITTEE_CODE_MAP.items()}
        return dict(_STATIC_COMMITTEE_CODE_MAP), dict(_STATIC_LOCAL_LEXICON), {}, False

def resolve_committee_from_refid(refid):
    """Extract committee name from History_refid using structural codes.

    Returns (committee_name, source) where source is:
      - "refid_direct" for committee code refids (H14, S04)
      - "refid_vote" for vote-style refids (H14V2610034 -> H14)
      - None if refid doesn't contain a usable committee code
    """
    if not refid:
        return None, None
    refid = refid.strip()

    # Direct committee code: H14, S04, etc.
    if re.match(r'^[HS]\d{1,2}$', refid):
        name = COMMITTEE_CODE_MAP.get(refid)
        if not name:
            # Try zero-padded: S2 -> S02
            padded = refid[0] + refid[1:].zfill(2)
            name = COMMITTEE_CODE_MAP.get(padded)
        if name:
            return name, "refid_direct"

    # Vote-style refid: H14V2610034 -> H14, S2V1869 -> S2
    # Subcommittee vote refid: H14003V2610048 -> H14 (3-digit sub suffix before V)
    # The parent committee code is always 1-2 digits after H/S.
    # Subcommittees add a strictly 3-digit suffix (001-007) before the V.
    # Non-greedy \d{1,2}? ensures 1-digit parent codes (S2) aren't consumed by the
    # subcommittee suffix (S2001V → S2 + 001, not S20 + 01).
    # Regex: H/S + 1-2 digit parent (non-greedy) + optional 3-digit sub + V + digits
    vote_match = re.match(r'^([HS])(\d{1,2}?)(?:\d{3})?V\d+', refid)
    if vote_match:
        code_raw = vote_match.group(1) + vote_match.group(2)
        name = COMMITTEE_CODE_MAP.get(code_raw)
        if not name:
            padded = vote_match.group(1) + vote_match.group(2).zfill(2)
            name = COMMITTEE_CODE_MAP.get(padded)
        if name:
            return name, "refid_vote"

    return None, None

# === ACTION SCOPE VECTORS ===
ABSOLUTE_FLOOR_VERBS = ["reading dispensed", "read first", "read second", "read third", "passed senate", "passed house", "agreed to", "rejected", "rules suspended", "conference report agreed"]
# Removed from ABSOLUTE_FLOOR: "signed by", "enrolled", "engrossed", "presented",
# "received", "communicated", "conferees:" — these are administrative/clerk actions
# per HISTORY.CSV data analysis. They do not require people in a room at a specific
# time. "read second" already catches "Read second time and engrossed".
# Added: "conference report agreed" — floor vote on conference committee compromise.
DYNAMIC_VERBS = ["passed by", "reconsidered", "failed", "defeated", "laid on the table", "tabled", "continued", "strike", "stricken", "incorporate", "recommend", "recommends"]

# Meeting-verb tokens used by the write-time chokepoint (_append_event, I4) to
# classify rows that REQUIRE a concrete time (people had to be in a room at
# HH:MM). Mirrors tools/crossover_audit/diff_sheet1.py MEETING_VERBS — keep
# the two lists in sync; a drift between them weakens the bug-detection
# signal from the audit tool. This list is intentionally high-recall: false
# positives only elevate the "meeting_unsourced" telemetry counter, they
# do not drop or reclassify rows.
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

def normalize_room_key(text):
    if not text:
        return ""
    clean = str(text).lower()
    clean = re.sub(r'[^a-z0-9\s]', ' ', clean)
    for token in ["committee", "on", "for", "the", "of", "and", "subcommittee", "sub", "agenda"]:
        clean = clean.replace(token, " ")
    return " ".join(clean.split())
def derive_room_hints(outcome_text, acting_chamber_prefix):
    outcome = str(outcome_text)
    out_lower = outcome.lower()
    hints = []

    sub_match = re.search(r'sub:\s*([a-z0-9&,\-\s]+)', out_lower)
    if sub_match:
        sub_name = sub_match.group(1).strip()
        if sub_name:
            sub_title = re.sub(r'\s+', ' ', sub_name).title()
            hints.append(f"{acting_chamber_prefix}Appropriations - {sub_title} Subcommittee")
            hints.append(f"{acting_chamber_prefix}Appropriations {sub_title} Subcommittee")

    agenda_match = re.search(r'placed on\s+([a-z&,\-\s]+?)\s+agenda', out_lower)
    if agenda_match:
        agenda_name = re.sub(r'\s+', ' ', agenda_match.group(1)).strip().title()
        if agenda_name:
            hints.append(f"{acting_chamber_prefix}{agenda_name}")

    return hints

def find_api_schedule_match(api_schedule_map, date_str, event_location, outcome_text, acting_chamber_prefix):
    prefix = f"{date_str}_"
    dated_keys = [k for k in api_schedule_map.keys() if k.startswith(prefix)]
    if not dated_keys:
        return None

    def has_concrete_time(key):
        time_val = str(api_schedule_map.get(key, {}).get("Time", "")).strip().lower()
        return time_val not in ["", "time tba", "tba", "journal entry", "ledger"]

    target_norm = normalize_room_key(event_location)
    exact_matches = []
    for k in dated_keys:
        k_norm = normalize_room_key(k.split("_", 1)[1])
        if k_norm == target_norm:
            exact_matches.append(k)
    for k in exact_matches:
        if has_concrete_time(k):
            return k

    # --- Subcommittee -> parent committee fallback (both directions) ---
    # Direction 1 (child->parent): event is a subcommittee, look for parent schedule entry.
    # Direction 2 (parent->child): event is a parent committee, exact match has TBA time,
    #   look for subcommittee entries on the same date with concrete times.
    # Uses PARENT_COMMITTEE_MAP (from Committee API ParentCommitteeID) when available.
    # Falls back to normalized name prefix matching only if API parent data is unavailable.
    parent_matches = []
    child_matches = []

    # Direction 2: If exact match exists but has no concrete time, check children
    if exact_matches and not any(has_concrete_time(k) for k in exact_matches):
        # Strategy A: Structural lookup via CHILDREN_OF_PARENT (Committee API ParentCommitteeID)
        if CHILDREN_OF_PARENT:
            event_code = NORM_TO_CODE.get(target_norm)
            if event_code and event_code in CHILDREN_OF_PARENT:
                # O(1) lookup of child committees via pre-calculated reverse map
                child_codes = CHILDREN_OF_PARENT[event_code]
                # Pre-calculate normalized keys for dated entries (avoid redundant normalize_room_key calls)
                dated_norms = {k: normalize_room_key(k.split("_", 1)[1]) for k in dated_keys}
                for child_code in child_codes:
                    child_name = COMMITTEE_CODE_MAP.get(child_code, "")
                    if child_name:
                        child_norm = normalize_room_key(child_name)
                        for k in dated_keys:
                            if dated_norms[k] == child_norm and has_concrete_time(k):
                                child_matches.append(k)
        # Strategy B: Schedule-level hyphen-suffix matching.
        # Some committees (e.g., "House Courts of Justice") have Schedule API entries
        # for sub-panels ("House Courts of Justice-Civil", "-Criminal") that are NOT
        # separate committees in the Committee API. They use a hyphen or " - " suffix
        # after the parent name. These sub-panels often have concrete times when the
        # parent entry has TBA.
        # SAFETY: Only match entries whose raw name starts with the exact target name
        # followed by a hyphen or " - ", avoiding normalized prefix false positives.
        if not child_matches:
            # Iterate ALL exact matches — different raw names can normalize identically
            # (e.g., "House Courts of Justice" and "House Committee on Courts of Justice").
            # Each raw name variant may be the prefix used by sub-panel schedule entries.
            for em in exact_matches:
                raw_target = em.split("_", 1)[1]
                if not raw_target:
                    continue
                for k in dated_keys:
                    raw_k = k.split("_", 1)[1]
                    # Match "Parent-Suffix" or "Parent - Suffix" patterns only
                    if raw_k.startswith((raw_target + "-", raw_target + " -")) and has_concrete_time(k):
                        if k not in child_matches:
                            child_matches.append(k)
        # If we found children with concrete times, use the earliest by SortTime
        if child_matches:
            child_matches.sort(key=lambda k: api_schedule_map[k].get("SortTime", "23:59"))
            return child_matches[0]

    # Direction 1: event is a subcommittee, look for parent
    if not exact_matches:
        # Try structural parent lookup first (enterprise-grade: ParentCommitteeID)
        if PARENT_COMMITTEE_MAP:
            # O(1) reverse lookup via pre-calculated NORM_TO_CODE map
            event_code = NORM_TO_CODE.get(target_norm)
            if event_code and event_code in PARENT_COMMITTEE_MAP:
                parent_code = PARENT_COMMITTEE_MAP[event_code]
                parent_name = COMMITTEE_CODE_MAP.get(parent_code, "")
                if parent_name:
                    parent_norm = normalize_room_key(parent_name)
                    for k in dated_keys:
                        k_norm = normalize_room_key(k.split("_", 1)[1])
                        if k_norm == parent_norm:
                            parent_matches.append(k)
        # Fallback: name-prefix heuristic (only if no PARENT_COMMITTEE_MAP data)
        if not parent_matches and not PARENT_COMMITTEE_MAP:
            for k in dated_keys:
                k_norm = normalize_room_key(k.split("_", 1)[1])
                if k_norm and target_norm.startswith(k_norm) and target_norm != k_norm:
                    parent_matches.append(k)
        for k in parent_matches:
            if has_concrete_time(k):
                return k

    hints = derive_room_hints(outcome_text, acting_chamber_prefix)
    hint_matches = []
    for hint in hints:
        hint_norm = normalize_room_key(hint)
        for k in dated_keys:
            k_norm = normalize_room_key(k.split("_", 1)[1])
            if hint_norm and (hint_norm in k_norm or k_norm in hint_norm):
                hint_matches.append(k)
    for k in hint_matches:
        if has_concrete_time(k):
            return k

    if exact_matches:
        return exact_matches[0]
    if parent_matches:
        return parent_matches[0]
    if hint_matches:
        return hint_matches[0]

    for k in dated_keys:
        k_norm = normalize_room_key(k.split("_", 1)[1])
        if target_norm and (target_norm in k_norm or k_norm in target_norm):
            return k
    return None

def _normalize_session_code_5d(active_session):
    """PR-C3 helper: convert legacy 3-digit '261' to MVC-style '20261'.

    The Schedule / Committee / Session APIs accept either form, but the
    LegislationEvent / LegislationVersion / AdvancedLegislationSearch
    endpoints reject the 3-digit form with
    "Provided Session Code is invalid". Always convert before calling them.
    Empty / None / non-numeric inputs return "" so callers must guard.

    LIMITATION (Gemini PR-C3 review): the hardcoded "20" prefix assumes
    21st-century sessions. A legacy 3-digit "941" (1994 Regular) would
    incorrectly become "20941" — but the only path that reaches this
    helper with a 3-digit input is the OFFLINE-fallback inside
    `run_calendar_update()` (search for `ACTIVE_SESSION = "261"`) which
    fires only when `get_active_session_info()` fails. When the Session API
    succeeds, ACTIVE_SESSION already arrives in 5-digit form
    ("20261") from `Session/api/GetSessionListAsync` and this function
    is a no-op. If we ever need to look up historical (pre-2000)
    sessions, thread `session_year` from `session_data["start"].year`
    through this helper.
    """
    code = str(active_session or "").strip()
    if not code or not code.isdigit():
        return ""
    if len(code) == 5:
        return code
    if len(code) == 3:
        return f"20{code}"
    # Anything else is a format we haven't seen; surface as empty so caller
    # falls through to the existing journal_default path rather than emitting
    # a malformed API request.
    return ""


def _legislation_event_token_set(text):
    """Lowercased ≥3-letter alphabetic tokens for description matching.

    Stops emoji, punctuation, single-letter chamber prefixes ("H"/"S"),
    and small connectors ("by", "of", "to") from inflating the overlap
    score. Used by `_resolve_via_legislation_event_api` to match the
    Sheet1 outcome text against the right LegislationEvent when a bill
    has multiple events on the same date+chamber (Codex PR-C3 P1).
    """
    if not text:
        return set()
    return {w.lower() for w in re.findall(r'[A-Za-z]{3,}', text)}


def _resolve_via_legislation_event_api(
    http_session, bill_num, action_date_str, outcome_text,
    session_code_5d, acting_chamber_code,
    legislation_id_cache, legislation_event_cache, push_alert,
):
    """PR-C3: secondary time source via LIS LegislationEvent API.

    Triggered when `find_api_schedule_match()` returned no concrete time —
    the Class-1 bug pattern is meetings (e.g. House Privileges and Elections
    on 2026-02-12) where the Schedule API has zero entries for the parent
    committee but HISTORY shows the bill action. The LegislationEvent API
    publishes minute-precision `EventDate` for each action even when the
    Schedule API is silent. Verified against HB111/505/972/609 on Feb 12 →
    21:02:00 / 21:02:00 / 21:03:00 / 09:24:00 respectively.

    Two-step lookup: bill number → LegislationID (cached per cycle) →
    event history filtered to `action_date_str`.

    Returns (Time, SortTime, Status) tuple if recovery succeeds; None on
    miss, parse failure, network error, or API gap. Every failure path
    emits a categorized `push_alert` per CLAUDE.md Standard #4 — never
    raises into the caller.
    """
    if not session_code_5d:
        return None

    # Step 1: LegislationID lookup (cached for the cycle — IDs are stable
    # within a session).
    cache_key = (bill_num, session_code_5d)
    legislation_id = legislation_id_cache.get(cache_key)
    if legislation_id is None:
        try:
            r = http_session.get(
                "https://lis.virginia.gov/LegislationVersion/api/GetLegislationVersionbyBillNumberAsync",
                headers=LEGISLATION_EVENT_HEADERS,
                params={"billNumber": bill_num, "sessionCode": session_code_5d},
                timeout=10,
            )
        except Exception as e:
            push_alert(
                f"LegislationVersion lookup raised for {bill_num}: {type(e).__name__}: {e}",
                status="WARN", category="API_FAILURE", severity="WARN",
                dedup_key=f"legislation_version_exc::{bill_num}",
            )
            legislation_id_cache[cache_key] = ""  # negative-cache to avoid retry storms this cycle
            return None
        if r.status_code != 200:
            push_alert(
                f"LegislationVersion lookup failed for {bill_num}: HTTP {r.status_code}",
                status="WARN", category="API_FAILURE", severity="WARN",
                dedup_key=f"legislation_version_http::{bill_num}::{r.status_code}",
            )
            legislation_id_cache[cache_key] = ""
            return None
        try:
            raw_json = r.json()
        except Exception as e:
            push_alert(
                f"LegislationVersion JSON parse failed for {bill_num}: {e}",
                status="WARN", category="DATA_ANOMALY", severity="WARN",
                dedup_key=f"legislation_version_parse::{bill_num}",
            )
            legislation_id_cache[cache_key] = ""
            return None
        # Defensive: API contract says dict, but assert before .get() so a
        # contract change surfaces as a categorized alert, not an
        # AttributeError (Gemini PR-C3 review).
        if not isinstance(raw_json, dict):
            push_alert(
                f"LegislationVersion returned non-dict JSON for {bill_num}: "
                f"{type(raw_json).__name__}",
                status="WARN", category="DATA_ANOMALY", severity="WARN",
                dedup_key=f"legislation_version_shape::{bill_num}",
            )
            legislation_id_cache[cache_key] = ""
            return None
        versions = raw_json.get("LegislationsVersion") or []
        first = versions[0] if versions else None
        legislation_id = first.get("LegislationID") if isinstance(first, dict) else None
        legislation_id_cache[cache_key] = legislation_id or ""

    if not legislation_id:
        return None

    # Step 2: event history. PR-C3.1: cache the response per (bill,
    # session) — the endpoint returns the bill's whole history in one
    # shot, so subsequent journal_default rows for the same bill must
    # NOT re-fetch. `[]` means "fetched and negative" (either truly
    # empty or the fetch failed); either way, do not retry this cycle.
    cache_key = (bill_num, session_code_5d)
    if cache_key in legislation_event_cache:
        events = legislation_event_cache[cache_key]
    else:
        try:
            r = http_session.get(
                "https://lis.virginia.gov/LegislationEvent/api/GetPublicLegislationEventHistoryListAsync",
                headers=LEGISLATION_EVENT_HEADERS,
                params={"legislationID": legislation_id, "sessionCode": session_code_5d},
                timeout=10,
            )
        except Exception as e:
            push_alert(
                f"LegislationEvent fetch raised for {bill_num} (LID={legislation_id}): {type(e).__name__}: {e}",
                status="WARN", category="API_FAILURE", severity="WARN",
                dedup_key=f"legislation_event_exc::{bill_num}",
            )
            legislation_event_cache[cache_key] = []
            return None
        if r.status_code != 200:
            push_alert(
                f"LegislationEvent fetch failed for {bill_num} (LID={legislation_id}): HTTP {r.status_code}",
                status="WARN", category="API_FAILURE", severity="WARN",
                dedup_key=f"legislation_event_http::{bill_num}::{r.status_code}",
            )
            legislation_event_cache[cache_key] = []
            return None
        try:
            raw_json = r.json()
        except Exception as e:
            push_alert(
                f"LegislationEvent JSON parse failed for {bill_num}: {e}",
                status="WARN", category="DATA_ANOMALY", severity="WARN",
                dedup_key=f"legislation_event_parse::{bill_num}",
            )
            legislation_event_cache[cache_key] = []
            return None
        if not isinstance(raw_json, dict):
            push_alert(
                f"LegislationEvent returned non-dict JSON for {bill_num}: "
                f"{type(raw_json).__name__}",
                status="WARN", category="DATA_ANOMALY", severity="WARN",
                dedup_key=f"legislation_event_shape::{bill_num}",
            )
            legislation_event_cache[cache_key] = []
            return None
        events = raw_json.get("LegislationEvents") or []
        legislation_event_cache[cache_key] = events

    # Step 3: filter to events on the action date AND the acting chamber
    # (House actions should not borrow Senate-side timestamps).
    matching = []
    for e in events:
        edate_full = str(e.get("EventDate") or "")
        if edate_full[:10] != action_date_str:
            continue
        # Chamber filter: tolerate empty ChamberCode in the response (some
        # joint-action events lack it), but reject explicit cross-chamber.
        ev_chamber = str(e.get("ChamberCode") or "").strip().upper()
        if acting_chamber_code and ev_chamber and ev_chamber != acting_chamber_code:
            continue
        matching.append(e)
    if not matching:
        return None

    # Prefer events with a real wall-clock time (skip midnight-only
    # date-stamps, which encode date-only "filed" actions). Among real-time
    # events, MATCH the right action — Codex PR-C3 P1 flagged that a bill
    # may have multiple events in the same chamber on the same date (e.g.
    # HB1 on 2026-03-03 had a Senate "Constitutional reading dispensed"
    # at 13:44 and a "Passed by for the day" at 13:45). Picking the latest
    # would mis-time the earlier action. Score each candidate by token
    # overlap between the Sheet1 outcome text and the event Description;
    # tie-break by latest EventDate so the most recent rendering of the
    # same logical action wins. Score=0 (no token overlap) is treated as
    # NO confident match → return None and fall through to the existing
    # journal_default path; the alert there carries the diagnostic_hint
    # so the human can see what we did and didn't have.
    real_time_events = [
        e for e in matching
        if str(e.get("EventDate") or "")[11:] not in ("", "00:00:00")
    ]
    if not real_time_events:
        return None
    outcome_tokens = _legislation_event_token_set(outcome_text)
    if not outcome_tokens:
        # No outcome to match against — abstain rather than guess. The
        # existing journal_default path emits the categorized alert so
        # the row is still visible.
        return None
    scored = []
    for e in real_time_events:
        ev_tokens = _legislation_event_token_set(str(e.get("Description") or ""))
        score = len(outcome_tokens & ev_tokens)
        scored.append((score, e.get("EventDate") or "", e))
    # Sort: highest score first, latest EventDate as tie-break.
    scored.sort(key=lambda triple: (triple[0], triple[1]), reverse=True)
    best_score = scored[0][0]
    if best_score == 0:
        # No token overlap with any candidate — refuse to assign a time.
        # This is the safety net Codex P1 was concerned about.
        return None
    chosen = scored[0][2]

    edate_full = str(chosen.get("EventDate"))
    try:
        h = int(edate_full[11:13])
        m = int(edate_full[14:16])
    except (ValueError, IndexError) as e:
        push_alert(
            f"LegislationEvent EventDate parse failed for {bill_num}: "
            f"{edate_full!r} ({e})",
            status="WARN", category="DATA_ANOMALY", severity="WARN",
            dedup_key=f"legislation_event_time_parse::{bill_num}",
        )
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        push_alert(
            f"LegislationEvent EventDate out of range for {bill_num}: "
            f"{edate_full!r} (H={h}, M={m})",
            status="WARN", category="DATA_ANOMALY", severity="WARN",
            dedup_key=f"legislation_event_time_range::{bill_num}",
        )
        return None

    # 12-hour wall-clock string consistent with Schedule API ScheduleTime.
    if h == 0:
        time_12h = f"12:{m:02d} AM"
    elif h < 12:
        time_12h = f"{h}:{m:02d} AM"
    elif h == 12:
        time_12h = f"12:{m:02d} PM"
    else:
        time_12h = f"{h - 12}:{m:02d} PM"
    sort_time_24h = f"{h:02d}:{m:02d}"
    # LegislationEvent doesn't carry a cancellation flag on the public
    # history endpoint — leave Status empty so downstream Status logic
    # behaves identically to a clean api_schedule resolution.
    return (time_12h, sort_time_24h, "")


def get_armored_session():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
    retries = Retry(total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_active_session_info(http_session):
    print("📡 Pinging Master API for Session Intelligence...")
    try:
        res = http_session.get("https://lis.virginia.gov/Session/api/GetSessionListAsync", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            raw_json = res.json()
            sessions = raw_json.get('Sessions', []) if isinstance(raw_json, dict) else raw_json
            if not isinstance(sessions, list) or len(sessions) == 0: return None, False

            tz = pytz.timezone('America/New_York')
            now = datetime.now(tz).replace(tzinfo=None)

            def extract_dates(session_obj):
                events = session_obj.get('SessionEvents', [])
                valid_dates = []
                for e in events:
                    d = e.get('ActualDate') or e.get('ProjectedDate')
                    if d:
                        try: valid_dates.append(pd.to_datetime(d).replace(tzinfo=None))
                        except (ValueError, TypeError):
                            print(f"⚠️ Session date parsing failed for: {d}")
                if valid_dates: return min(valid_dates), max(valid_dates)
                return now, now 

            for s in sessions:
                if s.get('IsActive') or s.get('IsDefault'):
                    start, end = extract_dates(s)
                    return {"code": str(s.get('SessionCode')), "start": start, "end": end + timedelta(days=14)}, True

            current_year = now.year
            for s in sessions:
                if str(s.get('SessionYear')) == str(current_year):
                    start, end = extract_dates(s)
                    return {"code": str(s.get('SessionCode')), "start": start, "end": end + timedelta(days=14)}, True
    except Exception as e:
        print(f"⚠️ Session API parsing failed: {e}")
    return None, False

def safe_fetch_csv(url):
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            if b'BillNumber' not in res.content and b'HistoryDate' not in res.content and b'Committee' not in res.content:
                return pd.DataFrame()
            raw_text = res.content.decode('iso-8859-1')
            df = pd.read_csv(io.StringIO(raw_text))
            return df.rename(columns=lambda x: x.strip())
    except Exception as e:
        print(f"⚠️ CSV fetch failed for {url}: {e}")
    return pd.DataFrame()

def generate_date_variants(dt):
    m = str(dt.month); d = str(dt.day); y = str(dt.year)
    m_pad = f"{dt.month:02d}"; d_pad = f"{dt.day:02d}"; y_short = y[-2:]
    month_full = dt.strftime('%B'); month_short = dt.strftime('%b')
    return [
        f"{m_pad}/{d_pad}/{y}", f"{m}/{d}/{y}", f"{m_pad}/{d_pad}/{y_short}", f"{m}/{d}/{y_short}",
        f"{month_full} {d}", f"{month_short} {d}", f"{month_full} {d_pad}", f"{month_short} {d_pad}"
    ]

def parse_24h_time(raw_time, parent_time_24h=None):
    time_val = raw_time.strip().replace('.', '').upper()
    if any(m in time_val.lower() for m in ["after", "upon"]):
        if parent_time_24h and parent_time_24h != "06:00":
            try:
                pt = datetime.strptime(parent_time_24h, '%H:%M')
                return (pt + timedelta(minutes=1)).strftime('%H:%M')
            except: return "06:00" 
        return "06:00" 
    try: return datetime.strptime(time_val, '%I:%M %p').strftime('%H:%M')
    except: return "23:59"

def build_time_graph(schedules):
    raw_times = {}
    for m in schedules:
        name = str(m.get('OwnerName', '')).strip().lower()
        t_val = str(m.get('ScheduleTime', '')).strip()
        desc = re.sub(r'<[^>]+>', '', str(m.get('Description', ''))).strip()
        stitched = f"{t_val} {desc}".lower()
        raw_times[name] = t_val if not any(x in stitched for x in ["upon adjournment", "minutes after", "hour after", "recess"]) else stitched

    for k, v in list(raw_times.items()):
        if "house convenes" in k or "house chamber" in k: raw_times["house"] = v; raw_times["the house"] = v
        if "senate convenes" in k or "senate chamber" in k: raw_times["senate"] = v; raw_times["the senate"] = v

    resolved_times = {}
    def resolve_node(name_key, visited=None):
        if visited is None: visited = set()
        if name_key in resolved_times: return resolved_times[name_key]
        if name_key in visited: return "06:00" 
        
        visited.add(name_key)
        raw_str = raw_times.get(name_key, "")
        if not raw_str: return "23:59"

        dynamic_markers = ["upon adjournment", "minutes after", "hour after", "recess"]
        if any(m in raw_str.lower() for m in dynamic_markers):
            found_parent = next((p for p in raw_times if len(p) > 5 and p in raw_str.lower()), None)
            if not found_parent:
                rl = raw_str.lower()
                if "senate adjourns" in rl or "adjournment of the senate" in rl: found_parent = "senate convenes"
                elif "house adjourns" in rl or "adjournment of the house" in rl: found_parent = "house convenes"
                elif "recess" in rl and "house" in rl: found_parent = next((k for k, v in raw_times.items() if "recess" in v.lower() and "house" in k.lower()), None)
                elif "recess" in rl and "senate" in rl: found_parent = next((k for k, v in raw_times.items() if "recess" in v.lower() and "senate" in k.lower()), None)

            if found_parent:
                res = parse_24h_time(raw_str, resolve_node(found_parent, visited))
                resolved_times[name_key] = res
                return res
            return "06:00"

        res = parse_24h_time(raw_str)
        resolved_times[name_key] = res
        return res

    for name in raw_times: resolve_node(name)
    return resolved_times

def extract_rogue_agenda(url, session, target_date_dt=None, depth=0):
    if depth > 1: return [], False 
    found_bills = set()
    regex_pattern = r'\b([HS][BJR]\s*\d+)'
    if url.startswith('/'): url = f"https://lis.virginia.gov{url}"
        
    try:
        time.sleep(0.25)
        res = session.get(url, timeout=15)
        if res.status_code != 200: return [], False
        
        if '.pdf' in url.lower() or b'%PDF' in res.content[:5]:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                    temp_pdf.write(res.content)
                    temp_pdf_path = temp_pdf.name
                with pdfplumber.open(temp_pdf_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text: found_bills.update([m.upper() for m in re.findall(regex_pattern, text.replace(" ", ""))])
                os.remove(temp_pdf_path)
            except Exception as e:
                print(f"⚠️ Agenda PDF parse failed for {url}: {e}")
                return [], True
        else:
            soup = BeautifulSoup(res.text, 'html.parser')
            target_href = None
            if target_date_dt:
                date_matrix = generate_date_variants(target_date_dt)
                for row in soup.find_all(['tr', 'li', 'div', 'p']): 
                    if any(variant in row.get_text() for variant in date_matrix):
                        link = row.find('a', string=re.compile(r'Agenda|Docket', re.I)) or row.find('a', href=re.compile(r'\.pdf$', re.I))
                        if link: target_href = link.get('href'); break
            if not target_href:
                agenda_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.I)) or soup.find_all('a', string=re.compile(r'Agenda|Docket', re.I))
                if agenda_links: target_href = agenda_links[0].get('href')
                    
            if target_href: return extract_rogue_agenda(urllib.parse.urljoin(url, target_href), session, target_date_dt, depth + 1)
            
            for script in soup.find_all('script'):
                if script.string and any(x in script.string for x in ['HB', 'SB', 'HJ', 'SJ']):
                    found_bills.update([m.upper() for m in re.findall(regex_pattern, script.string.replace(" ", ""))])
            
            found_bills.update([m.upper() for m in re.findall(regex_pattern, soup.get_text(separator=' ').replace(" ", ""))])
    except Exception as e:
        print(f"⚠️ Agenda extraction failed for {url}: {e}")
    return sorted(list(found_bills)), False


def _is_non_concrete_time(value):
    """Check if a time value is a non-concrete placeholder (TBA, empty, etc.)."""
    t = str(value or "").strip().lower()
    return t in {"", "time tba", "tba", "journal entry", "ledger", "none", "nan"}


# PR-C2 Part B (Gemini round 2, concern #1):
# The Schedule API documents only OwnerName / ScheduleDate / ScheduleTime /
# Description / IsCancelled (see docs/knowledge/lis_api_reference.md). The
# room/location field is NOT documented. Empirically, LIS has used the keys
# "Location", "Room", and "RoomDescription" across different payload shapes.
# We try them in that order and return the first non-empty value, reporting
# which key fired so we can track whichever one LIS is currently using.
# Returning "" (not None) keeps the value JSON-serializable and lexically
# comparable against cache entries that default to empty string.
_LOCATION_KEY_ORDER = ("Location", "Room", "RoomDescription")


def _extract_meeting_location(meeting):
    """Return (location_str, key_fired) for a Schedule API meeting dict.

    Tries the documented-alias fallback chain and returns the first non-empty
    value, stripped. Returns ("", None) when none of the keys resolve.
    """
    if not isinstance(meeting, dict):
        return "", None
    for key in _LOCATION_KEY_ORDER:
        raw = meeting.get(key)
        if raw is None:
            continue
        val = str(raw).strip()
        if val:
            return val, key
    return "", None


def run_calendar_update():
    http_session = get_armored_session()
    
    session_data, api_is_online = get_active_session_info(http_session)
    
    tz = pytz.timezone('America/New_York')
    now = datetime.now(tz).replace(tzinfo=None)
    alert_rows = []
    _alert_dedup_keys = set()

    # Source-miss visibility counters (see docs/workflow/source_miss_visibility.md).
    #
    # DENOMINATOR BUCKETS (mutually exclusive — sum to total_processed):
    #   sourced_api, sourced_convene, unsourced_journal, floor_anchor_miss, dropped_noise.
    #   Every HISTORY.CSV row enumerated lands in exactly one of these.
    #
    # ORTHOGONAL TAG COUNTERS (overlap with the denominator buckets — do NOT add
    # to the sum):
    #   unsourced_anchor — rows whose committee came from Memory Anchor fallback.
    #     Their time may still have been resolved via API or convene anchor, so
    #     these overlap with sourced_api / sourced_convene / unsourced_journal.
    #   dropped_ephemeral — rows removed by the post-loop ephemeral filter.
    #     These are a subset of (unsourced_journal ∪ floor_anchor_miss).
    #
    # X-Ray Section 0 renders the denominator buckets as the primary metric
    # and the tag counters below as side-metrics. See
    # docs/failures/gemini_review_patterns.md #31 / #32.
    source_miss_counts = {
        # Denominator buckets
        "total_processed": 0,       # actions visited in the main loop
        "sourced_api": 0,           # concrete API-schedule match (and no floor-anchor override)
        "sourced_convene": 0,       # floor action resolved via convene anchor
        "sourced_legislation_event": 0,  # PR-C3: time recovered via LegislationEvent API fallback
        "unsourced_journal": 0,     # no schedule, no anchor, no LegislationEvent recovery, non-floor -> NO_SCHEDULE_MATCH
        "floor_anchor_miss": 0,     # Floor action with no convene anchor hit -> NO_CONVENE_ANCHOR
        "dropped_noise": 0,         # positive-noise filter drops (continue at noise filter)
        # Orthogonal tag counters (overlap with the above)
        "unsourced_anchor": 0,      # Memory Anchor committee fallback applied
        "dropped_ephemeral": 0,     # Post-loop ephemeral filter drops (subset of unsourced_*)
        # PR-C1: write-time chokepoint telemetry (see _append_event below)
        "invariant_violations": 0,  # Rows that failed I1/I2/I3 at append time
        "meeting_unsourced": 0,     # Meeting-verb outcome with Origin in {journal_default, floor_miss}
        # PR-C1 review-fix (Gemini): orthogonal-tag counter that is the true
        # denominator for the circuit breaker's violation-rate threshold. It
        # counts ONLY rows that actually reached _append_event (so ~system
        # rows + bill rows), which is the universe where invariants COULD
        # have been violated. Using the pipeline-level total_processed here
        # would be wrong because total_processed also counts rows that died
        # before append (noise drops, etc.), inflating the denominator and
        # making the rate threshold less sensitive. Kept orthogonal so
        # existing denominator-bucket math (sourced_api + sourced_convene +
        # ... = total_processed) stays intact.
        "rows_appended": 0,
        # PR-C2 Part B (Gemini review): witness observability.
        #   witness_location_backfills — count of CHANGED deltas suppressed
        #     because the ONLY field that changed was Location going empty
        #     → populated. These are the expected one-time migration burst
        #     after Location was introduced as a tracked field; surface the
        #     count so the burst is visible but quiet.
        #   witness_rows — size-of-tab read (first-column length, incl.
        #     header) captured after the append so the canary threshold
        #     and the L3b prune lag are observable.
        "witness_location_backfills": 0,
        "witness_rows": -1,
        # PR-C3 telemetry: orthogonal counters for the LegislationEvent
        # fallback. `legislation_event_attempted` increments every time we
        # call the fallback (i.e. find_api_schedule_match returned no
        # concrete time AND the row isn't a Floor action). `..._recovered`
        # is the subset that actually returned a usable time. The delta
        # (attempted - recovered) is the row count we still cannot source
        # from any API (true Class-1 unrecoverable). Independent of the
        # `sourced_legislation_event` denominator bucket so the bucket
        # math (sum = total_processed) stays clean.
        "legislation_event_attempted": 0,
        "legislation_event_recovered": 0,
    }

    def push_system_alert(message, status="ALERT", category=None, severity=None, dedup_key=None):
        """Append a row to alert_rows for Bug_Logs/Sheet1 surfacing.

        category: one of TIMING_LAG, PARENT_CHILD, COMMITTEE_DRIFT, API_FAILURE,
                  DATA_ANOMALY, UNKNOWN (CLAUDE.md Standard #4).
        severity: INFO, WARN, CRITICAL.
        dedup_key: optional stable key; duplicate keys are dropped so a repeated
                   miss doesn't flood alert_rows. Use None to allow every call.
        """
        if dedup_key is not None:
            if dedup_key in _alert_dedup_keys:
                return
            _alert_dedup_keys.add(dedup_key)
        tagged = message
        if category or severity:
            sev = (severity or "WARN").upper()
            cat = (category or "UNKNOWN").upper()
            tagged = f"[{sev}:{cat}] {message}"
        alert_rows.append({
            "Date": now.strftime("%Y-%m-%d"),
            "Time": now.strftime("%I:%M %p"),
            "SortTime": now.strftime("%H:%M"),
            "Status": status,
            "Committee": "System Status",
            "Bill": "SYSTEM_ALERT",
            "Outcome": tagged,
            "AgendaOrder": -99,
            "Source": "SYSTEM",
            "Origin": "system_alert",
            "DiagnosticHint": "",
        })

    # PR-C1: single chokepoint for every master_events.append in this run.
    # All 5 append sites route through here so write-time invariants fire in
    # ONE place, and the mass-violation circuit breaker downstream has a
    # concrete counter to watch. Closes over master_events, source_miss_counts,
    # push_system_alert from the enclosing scope — no args needed at call
    # sites, so the diff at each call site is just a function-name swap.
    #
    # Invariants (violations tag + alert, do NOT drop the row — visibility
    # beats silence; the circuit breaker watches the rate):
    #   I1 schema        — all 11 required columns present
    #   I2 origin_enum   — Origin in VALID_ORIGINS
    #   I3 time/origin   — concrete-source Origins cannot carry a [NO_*] Time
    #   I4 meeting_verb  — telemetry only: outcome carries a meeting verb
    #                      AND Origin is unsourced → increment
    #                      meeting_unsourced (what the breaker watches).
    _VALID_ORIGINS = {
        "api_schedule", "convene_anchor", "journal_default",
        "floor_miss", "system_alert", "system_metrics",
        # PR-C3: secondary time source via LegislationEvent API. Used when
        # the Schedule API has no concrete-time entry for the parent
        # committee (Class-1 bug class). Treated as a CONCRETE source for
        # I3 below.
        "legislation_event",
    }
    _REQUIRED_KEYS = {
        "Date", "Time", "SortTime", "Status", "Committee", "Bill",
        "Outcome", "AgendaOrder", "Source", "Origin", "DiagnosticHint",
    }
    _UNSOURCED_ORIGINS_FOR_METRICS = {"journal_default", "floor_miss"}

    def _append_event(event):
        """PR-C1 write-time chokepoint. See comment block above for invariants."""
        bill_id = event.get("Bill", "?")
        date_id = event.get("Date", "?")

        # I1: schema completeness. Fill missing keys with "" so downstream
        # pandas/serialization stays happy, but count + alert so the gap is
        # never silent.
        missing = _REQUIRED_KEYS - set(event.keys())
        if missing:
            for k in missing:
                event[k] = ""
            source_miss_counts["invariant_violations"] += 1
            push_system_alert(
                f"I1 schema violation on append: missing {sorted(missing)}; "
                f"bill={bill_id} date={date_id}",
                status="CRITICAL",
                category="DATA_ANOMALY",
                severity="CRITICAL",
                dedup_key=f"I1::{bill_id}::{date_id}",
            )

        # I2: Origin must be in the declared enum. An unrecognized value
        # means a code path set Origin to something the pipeline doesn't
        # know how to handle downstream (Ledger collapse, viewport exempt,
        # X-Ray Section 0). Tag + alert; do not rewrite.
        origin = event.get("Origin", "")
        if origin not in _VALID_ORIGINS:
            source_miss_counts["invariant_violations"] += 1
            push_system_alert(
                f"I2 origin enum violation: Origin='{origin}' not in "
                f"{sorted(_VALID_ORIGINS)}; bill={bill_id} date={date_id}",
                status="CRITICAL",
                category="DATA_ANOMALY",
                severity="CRITICAL",
                dedup_key=f"I2::{origin}::{bill_id}",
            )

        # I3: time/origin parity. If we claimed a concrete source
        # (api_schedule / convene_anchor) the Time cannot be a [NO_*] tag —
        # that combination means the matcher's return value got lost
        # somewhere on the way to the append. Catch it at write time.
        time_val = str(event.get("Time", ""))
        if origin in {"api_schedule", "convene_anchor", "legislation_event"} and time_val.startswith("\u23f1\ufe0f [NO_"):
            source_miss_counts["invariant_violations"] += 1
            push_system_alert(
                f"I3 time/origin parity violation: Origin='{origin}' but "
                f"Time='{time_val}'; bill={bill_id} date={date_id}",
                status="CRITICAL",
                category="DATA_ANOMALY",
                severity="CRITICAL",
                dedup_key=f"I3::{origin}::{bill_id}::{date_id}",
            )

        # I4: meeting-verb telemetry. Pure counter — what the circuit
        # breaker watches for regression. A row with a meeting-verb outcome
        # AND an unsourced Origin is exactly the Section 9 bug shape.
        if origin in _UNSOURCED_ORIGINS_FOR_METRICS:
            outcome_lower = str(event.get("Outcome", "")).lower()
            if any(v in outcome_lower for v in MEETING_VERB_TOKENS):
                source_miss_counts["meeting_unsourced"] += 1

        # Breaker denominator (PR-C1 review-fix, Gemini). Count AFTER the
        # invariant checks so rows_appended tracks the chokepoint's actual
        # throughput, including rows that tripped an invariant (they still
        # append — visibility beats silence). rate = violations / appended
        # is then the true "what fraction of chokepoint rows failed", not
        # "what fraction of pipeline entries failed".
        source_miss_counts["rows_appended"] += 1
        master_events.append(event)

    if not session_data:
        print("🚨 CRITICAL: Failed to retrieve active session. Proceeding in OFFLINE mode.")
        push_system_alert("🚨 LIS Session API unavailable. Running in OFFLINE mode; schedule times may be stale from API_Cache.", status="OFFLINE")
        ACTIVE_SESSION = "261"
        test_start_date = datetime(2026, 1, 14)
        test_end_date = datetime(2026, 5, 1)
    else:
        ACTIVE_SESSION = session_data["code"]
        test_start_date = session_data["start"]
        test_end_date = session_data["end"]

    # PR-C3 per-cycle state for LegislationEvent fallback. The 5-digit
    # session code is required by the new MVC endpoints (LegislationEvent
    # rejects the legacy 3-digit form). The cache is per-cycle because
    # LegislationID values are stable within a session and we don't want
    # to re-pay the bill-number → ID hop for every action of the same
    # bill. Keys are (bill_num, session_code_5d); a cached "" means
    # "looked up and not found" (negative cache to suppress retry storms
    # this cycle).
    _session_code_5d = _normalize_session_code_5d(ACTIVE_SESSION)
    _legislation_id_cache = {}
    # PR-C3.1: per-cycle response cache for the LegislationEvent fetch.
    # The endpoint returns the bill's FULL event history in one shot, so a
    # single fetch covers every action_date for that bill. Without this
    # cache, every journal_default row in HISTORY.CSV (thousands across the
    # full session window) re-fetched the same payload — that combined
    # with the urllib3 Retry(total=4, backoff_factor=2) on 429s caused the
    # Apr 25 worker hang. Negative cache (`[]`) suppresses re-attempt on
    # a same-cycle failure; categorized alert already fired on the miss.
    _legislation_event_cache = {}

    # === DYNAMIC COMMITTEE MAPS (Enterprise: rebuilt from API each run) ===
    build_committee_maps(http_session, ACTIVE_SESSION, alert_fn=push_system_alert)

    # Investigation window comes from module-level constants (see top of file).
    # Previously: scrape_start=Feb 9 + scrape_end=now+7d (rolling). That made
    # the bug count grow mechanically every day and hid whether fixes worked.
    scrape_start = INVESTIGATION_START
    scrape_end = INVESTIGATION_END

    print("🔐 Authenticating with Google Cloud...")
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json: sys.exit(1)
        
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sheet.worksheet("Sheet1")
    
    try:
        if api_is_online: worksheet.update_acell("Z1", "ONLINE")
        else: worksheet.update_acell("Z1", "OFFLINE")
    except Exception as e:
        print(f"⚠️ Failed to write API status flag to Sheet1!Z1: {e}")

    # PR-C1: read the last-successful-cycle timestamp from Sheet1!Y1.
    # PR-C2 Part A consumes this as the "since" cursor for gap detection.
    # PR-C2 Part C consumes `_gap_window_start_utc` (derived below) to bound
    # HISTORY-vs-witness reconciliation. Written to Y1 at the end of a
    # successful Sheet1 write. Read is INFO-only on failure because a
    # missing state cell on first run is expected; a permission / API
    # error is logged so it can be triaged.
    last_successful_cycle_end_utc = None
    try:
        _raw_y1 = worksheet.acell("Y1").value
        last_successful_cycle_end_utc = (_raw_y1 or "").strip() or None
        if last_successful_cycle_end_utc:
            print(f"🕒 Last successful cycle ended: {last_successful_cycle_end_utc} (state cell Y1)")
        else:
            print("🕒 State cell Y1 is empty — this is normal on first run after PR-C1 deploys.")
    except Exception as _state_read_err:
        push_system_alert(
            f"Could not read state cell Sheet1!Y1 (last_successful_cycle_end_utc): {_state_read_err}",
            status="INFO",
            category="API_FAILURE",
            severity="INFO",
            dedup_key="state_cell_y1_read_fail",
        )

    # Review-fix (Codex P2): carry-forward read for Sheet1!W1. If the
    # previous cycle tripped the mass-violation circuit breaker, it left a
    # JSON trip record in W1 (because its in-memory alert_rows died with
    # the process). Surface it here as a first-class SYSTEM_ALERT row on
    # THIS cycle so any monitor watching Bug_Logs / SYSTEM_ALERT rows sees
    # the trip — just delayed by one cycle. W1 is then cleared on THIS
    # cycle's successful overwrite so we don't double-report. Read is
    # INFO-only on failure; a missing cell is the common case (W1 empty
    # means previous cycle was healthy).
    #
    # PR-C2 Part A: _breaker_carryforward_detected flag is consumed by the
    # gap-classification block below to label `gap_cause = breaker_carryforward`
    # when the gap was caused by a trip (vs. a genuine outage).
    _breaker_carryforward_detected = False
    _breaker_carryforward_trip_utc = None
    try:
        _raw_w1 = worksheet.acell("W1").value
        _raw_w1 = (_raw_w1 or "").strip()
        if _raw_w1:
            try:
                _prev = json.loads(_raw_w1)
                _breaker_carryforward_detected = True
                _breaker_carryforward_trip_utc = _prev.get('trip_utc')
                push_system_alert(
                    f"Previous cycle tripped circuit breaker at {_prev.get('trip_utc', '?')} — "
                    f"invariant_violations={_prev.get('invariant_violations', '?')} "
                    f"meeting_unsourced={_prev.get('meeting_unsourced', '?')} "
                    f"rows_appended={_prev.get('rows_appended', '?')} "
                    f"violation_rate={_prev.get('violation_rate', '?')}. "
                    f"Sheet1 overwrite was skipped; data you saw in the previous window was "
                    f"last-known-good from an earlier cycle.",
                    status="CRITICAL",
                    category="DATA_ANOMALY",
                    severity="CRITICAL",
                    dedup_key=f"breaker_carryforward::{_prev.get('trip_utc', 'unknown')}",
                )
            except (ValueError, json.JSONDecodeError) as _w1_parse_err:
                # W1 had non-JSON content — surface anyway so the operator can
                # eyeball it rather than silently lose the signal.
                push_system_alert(
                    f"Sheet1!W1 contained non-JSON content (possible manual edit or "
                    f"partial write): {_raw_w1[:200]}",
                    status="WARN",
                    category="DATA_ANOMALY",
                    severity="WARN",
                    dedup_key="w1_parse_fail",
                )
    except Exception as _w1_read_err:
        push_system_alert(
            f"Could not read state cell Sheet1!W1 (breaker carry-forward): {_w1_read_err}",
            status="INFO",
            category="API_FAILURE",
            severity="INFO",
            dedup_key="state_cell_w1_read_fail",
        )

    # ================================================================
    # PR-C2 Part A: Y1 gap detection + classification
    # ================================================================
    # PR-C1 wrote Y1 (last_successful_cycle_end_utc) but didn't consume it.
    # This block closes that loop: compute how far behind we are vs. the
    # last known-good cycle, classify the cause, and emit WARN/CRITICAL
    # alerts. The classification is fed to SYSTEM_METRICS (source_miss_counts)
    # for X-Ray Section 0 cycle-health telemetry, and `_gap_window_start_utc`
    # is used by Part C to bound the HISTORY-vs-witness reconciliation.
    #
    # ALL gap math uses REAL UTC (datetime.now(timezone.utc)). The naive-ET
    # `now` variable 150 lines up would introduce a 4-5 hour DST-dependent
    # offset and cause false alarms twice a year (see PR-C1 Codex P1 fix).
    #
    # gap_cause values (string; one-of):
    #   first_run            Y1 empty — fresh deploy or cleared by operator
    #   future_cursor        Y1 > now — clock skew or manual edit, WARN
    #   stale_cursor         Y1 older than GAP_STALE_DAYS — CRITICAL
    #   malformed_cursor     Y1 parse failed — WARN, recovery disabled this cycle
    #   breaker_carryforward W1 populated — previous cycle was suppressed by
    #                         the mass-violation circuit breaker (PR-C1)
    #   outage               valid cursor, gap past WARN threshold, no breaker
    #   normal               valid cursor, gap within WARN threshold
    #
    # NOTE (future consideration): the CRITICAL alert on stale_cursor (>7 days
    # for Part C reconciliation, >30 days for stale detection) is currently
    # routed through the existing push_system_alert → Bug_Logs path. Owner may
    # later route these through a separate dashboard / push channel. See
    # docs/ideas/future_improvements.md (PR-C2 7-day alert routing).
    GAP_WARN_MINUTES = 20                  # >1 missed 15-min cycle + slop
    GAP_CRITICAL_MINUTES = 60              # >4 missed cycles
    GAP_STALE_DAYS = 30                    # cursor too old to trust for recovery
    GAP_RECONCILIATION_MAX_DAYS = 7        # hard cap for Part C re-poll window

    _cycle_start_utc = datetime.now(timezone.utc)
    gap_minutes = None              # None when unknown (first_run / malformed)
    gap_cause = None
    _gap_window_start_utc = None    # Set ONLY when cursor is usable for Part C

    if not last_successful_cycle_end_utc:
        gap_cause = "first_run"
        print("🕒 Gap detection: first_run (Y1 empty — fresh deploy or cleared).")
    else:
        _y1_parsed = None
        try:
            _y1_parsed = datetime.strptime(
                last_successful_cycle_end_utc, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as _y1_parse_err:
            gap_cause = "malformed_cursor"
            push_system_alert(
                f"Sheet1!Y1 has malformed timestamp {last_successful_cycle_end_utc!r} "
                f"({_y1_parse_err}). Treating as empty; PR-C2 gap-recovery disabled this "
                f"cycle. Next successful Sheet1 overwrite will re-anchor the cursor.",
                status="WARN",
                category="DATA_ANOMALY",
                severity="WARN",
                dedup_key=f"y1_malformed::{last_successful_cycle_end_utc}",
            )

        if _y1_parsed is not None:
            _delta_seconds = (_cycle_start_utc - _y1_parsed).total_seconds()
            if _delta_seconds < 0:
                gap_cause = "future_cursor"
                gap_minutes = round(_delta_seconds / 60.0, 2)
                push_system_alert(
                    f"Sheet1!Y1 timestamp {last_successful_cycle_end_utc} is in the future "
                    f"relative to cycle start {_cycle_start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')} "
                    f"(delta={gap_minutes} min). Possible clock skew or manual edit. "
                    f"Gap-recovery disabled this cycle.",
                    status="WARN",
                    category="DATA_ANOMALY",
                    severity="WARN",
                    dedup_key=f"y1_future::{last_successful_cycle_end_utc}",
                )
            elif _delta_seconds > GAP_STALE_DAYS * 86400:
                gap_cause = "stale_cursor"
                gap_minutes = round(_delta_seconds / 60.0, 2)
                push_system_alert(
                    f"Sheet1!Y1 cursor is {gap_minutes:.0f} min old "
                    f"(>{GAP_STALE_DAYS} days). Worker has been offline for an extended "
                    f"period; reconciliation window exceeds safe bounds. Manual review "
                    f"required before trusting recovery output.",
                    status="CRITICAL",
                    category="DATA_ANOMALY",
                    severity="CRITICAL",
                    dedup_key=f"y1_stale::{_cycle_start_utc.strftime('%Y-%m-%d')}",
                )
            else:
                gap_minutes = round(_delta_seconds / 60.0, 2)
                _gap_window_start_utc = _y1_parsed  # usable anchor for Part C
                if _breaker_carryforward_detected:
                    gap_cause = "breaker_carryforward"
                    # Carry-forward alert already fired in the W1 block above;
                    # do not double-alert here. Part C still evaluates this
                    # cycle for reconciliation because the gap is real.
                    print(
                        f"🕒 Gap detection: breaker_carryforward — gap={gap_minutes:.1f} min "
                        f"(trip_utc={_breaker_carryforward_trip_utc})"
                    )
                elif _delta_seconds >= GAP_CRITICAL_MINUTES * 60:
                    gap_cause = "outage"
                    push_system_alert(
                        f"Cycle gap is {gap_minutes:.1f} min (>{GAP_CRITICAL_MINUTES}) — "
                        f"4+ missed 15-min cycles since last successful overwrite at "
                        f"{last_successful_cycle_end_utc}. PR-C2 Part C will attempt "
                        f"reconciliation if gap ≤ {GAP_RECONCILIATION_MAX_DAYS} days.",
                        status="CRITICAL",
                        category="API_FAILURE",
                        severity="CRITICAL",
                        dedup_key=f"gap_critical::{_cycle_start_utc.strftime('%Y-%m-%d %H')}",
                    )
                elif _delta_seconds >= GAP_WARN_MINUTES * 60:
                    gap_cause = "outage"
                    push_system_alert(
                        f"Cycle gap is {gap_minutes:.1f} min (>{GAP_WARN_MINUTES}) — "
                        f"at least one missed 15-min cycle since {last_successful_cycle_end_utc}.",
                        status="WARN",
                        category="API_FAILURE",
                        severity="WARN",
                        dedup_key=f"gap_warn::{_cycle_start_utc.strftime('%Y-%m-%d %H')}",
                    )
                else:
                    gap_cause = "normal"
                print(
                    f"🕒 Gap detection: cause={gap_cause}, gap_minutes={gap_minutes}, "
                    f"cursor={last_successful_cycle_end_utc}"
                )

    # Feed into SYSTEM_METRICS so X-Ray Section 0 (future renderer) can
    # visualize per-cycle health. gap_minutes uses -1 as the "not applicable"
    # sentinel (JSON-safe, distinguishable from any real gap value which is
    # always >= 0 or None-sentinel at first_run).
    source_miss_counts["gap_minutes"] = gap_minutes if gap_minutes is not None else -1
    source_miss_counts["gap_cause"] = gap_cause or "unknown"

    print("🗄️ Pulling historical schedule from API_Cache...")
    api_schedule_map = {}
    convene_times = {}
    cache_sheet = None
    cache_records = []  # Must be initialized before try block to avoid NameError on failure
    try:
        cache_sheet = sheet.worksheet("API_Cache")
        cache_records = cache_sheet.get_all_records()

        # PR-C2 Part B: one-time header migration so the Location column
        # written by new_cache_entries is actually readable by future
        # get_all_records() calls. Without this, column F receives data
        # but row 1 has only 5 labels, so every subsequent cycle reads
        # Location as "" and the migration burst guard has to fire forever.
        # Writing "Location" into F1 is idempotent and cheap.
        try:
            _cache_header = cache_sheet.row_values(1)
            if "Location" not in _cache_header:
                cache_sheet.update(values=[["Location"]], range_name="F1")
                print("🗄️ API_Cache: migrated header to include Location (PR-C2).")
        except Exception as _mig_err:
            # Do not block the cycle on header migration — the witness
            # migration burst guard will keep deltas quiet if this fails;
            # surface once so the stuck state is visible.
            push_system_alert(
                f"API_Cache header migration skipped: {_mig_err}. "
                f"Location delta detection will be suppressed by the "
                f"migration burst guard until header is repaired manually.",
                status="INFO", category="API_FAILURE", severity="INFO",
                dedup_key="cache_header_migration_fail",
            )

        for r in cache_records:
            d = str(r.get("Date", ""))
            c = str(r.get("Committee", ""))
            k = f"{d}_{c}"
            api_schedule_map[k] = {
                "Time": str(r.get("Time", "")),
                "SortTime": str(r.get("SortTime", "")),
                "Status": str(r.get("Status", "")),
                # PR-C2 Part B: Location is a new column in API_Cache. Pre-migration
                # rows won't have it (get_all_records returns "" for missing keys),
                # which is exactly what the migration burst guard below expects.
                "Location": str(r.get("Location", "")),
            }
            
            c_lower = re.sub(r'\s+', ' ', c).lower()
            _is_house_convene = any(h in c_lower for h in ["house convenes", "house chamber", "house session", "house floor", "house of delegates"])
            _is_senate_convene = any(s in c_lower for s in ["senate convenes", "senate chamber", "senate session", "senate floor", "senate of virginia"])
            if _is_house_convene or _is_senate_convene:
                chamber = "House" if _is_house_convene else "Senate"
                if d not in convene_times: convene_times[d] = {}
                if chamber not in convene_times[d]:  # Don't overwrite with stale cache if live data exists
                    convene_times[d][chamber] = {"Time": str(r.get("Time", "")), "SortTime": str(r.get("SortTime", "")), "Name": c}
    except Exception as e:
        # Do NOT swallow silently: downstream historic-time resolution depends on
        # API_Cache. If it fails, downstream misses must be attributable to this.
        print(f"⚠️ Cache tab empty or unreadable. ({e})")
        push_system_alert(
            f"API_Cache read failed: {e}. Historic schedule times will be missing this run.",
            status="WARN",
            category="API_FAILURE",
            severity="WARN",
            dedup_key="cache_read_failure",
        )

    blob_code = f"20{ACTIVE_SESSION}" if len(ACTIVE_SESSION) == 3 else ACTIVE_SESSION
    master_events = []
    docket_memory = {} 

    print("📡 Downloading Official DOCKET.CSV...")
    df_docket = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/DOCKET.CSV")
    if not df_docket.empty:
        df_docket.columns = df_docket.columns.str.strip().str.lower().str.replace(' ', '_')
        bill_col = next((c for c in df_docket.columns if 'bill' in c), None)
        date_col = next((c for c in df_docket.columns if 'date' in c), None)
        comm_col = next((c for c in df_docket.columns if 'comm' in c or 'des' in c), None)
        
        if bill_col and date_col and comm_col:
            for _, row in df_docket.iterrows():
                b_num = str(row[bill_col]).replace(" ", "").upper()
                m_date = pd.to_datetime(row[date_col], errors='coerce')
                c_name = str(row[comm_col]).strip()
                if pd.notna(m_date) and b_num and c_name and c_name.lower() != 'nan':
                    date_str = m_date.strftime('%Y-%m-%d')
                    if date_str not in docket_memory: docket_memory[date_str] = {}
                    if b_num not in docket_memory[date_str]: docket_memory[date_str][b_num] = []
                    docket_memory[date_str][b_num].append(c_name)

    new_cache_entries = []

    # ================================================================
    # PR-C2 Part B: Schedule_Witness change-feed — constants & snapshot
    # ================================================================
    # These constants are hoisted ABOVE the live loop so the delta
    # computation inside the loop can reference WITNESS_DELTA_FIELDS (the
    # strict whitelist). Moving them below would reintroduce a NameError
    # the moment any delta is computed.
    #
    # WITNESS_DELTA_FIELDS (Gemini review, concerns #1 + round-2 #1):
    # **STRICT WHITELIST** — any field added here becomes a delta trigger
    # and WILL appear in witness rows. NEVER add volatile LIS metadata
    # (last_modified, cache ETags, opaque IDs, computed sort helpers) or
    # the change-feed will explode into junk. The bar is: "does a change
    # to this field represent a real-world schedule delta a legislative
    # tracker cares about?" Time / SortTime / Status / Location = yes.
    # Everything else = no.
    WITNESS_TAB_NAME = "Schedule_Witness"
    WITNESS_RETENTION_DAYS = 90
    WITNESS_CANARY_ROW_THRESHOLD = 500_000
    WITNESS_DELTA_FIELDS = ("Time", "SortTime", "Status", "Location")
    WITNESS_HEADER = [
        "seen_at_utc", "run_id", "event_type", "meeting_date", "committee",
        "time", "sort_time", "status", "location",
        "prev_time", "prev_sort_time", "prev_status", "prev_location",
    ]

    # Capture the state of api_schedule_map BEFORE the live loop runs.
    # This is the "what we knew last cycle" reference for delta computation
    # below. Deep-copy the inner dicts so the post-pass best_times promotion
    # (which mutates entries in-place) can't corrupt our snapshot.
    #
    # Deltas are computed at the END of the live loop (pre-best_times, so the
    # witness captures raw LIS signal rather than our post-processing) into
    # `_witness_deltas`, then written to the Schedule_Witness tab after the
    # live try/except block so the write path is independent of live-API
    # exceptions. Write is also NOT gated by the circuit breaker — the
    # witness log exists precisely to survive cycle failures.
    _pre_live_schedule_snapshot = {k: dict(v) for k, v in api_schedule_map.items()}
    _witness_deltas = []  # list of dicts; written after live try/except
    _witness_run_id = os.environ.get("GITHUB_RUN_ID", "local")
    _witness_seen_at_utc = _cycle_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    if api_is_online:
        print("📡 Downloading Live API Schedule & Agendas...")
        try:
            sched_res = http_session.get("https://lis.virginia.gov/Schedule/api/getschedulelistasync", headers=HEADERS, params={"sessionCode": ACTIVE_SESSION}, timeout=10)
            if sched_res.status_code == 200:
                schedules = sched_res.json().get('Schedules', []) if isinstance(sched_res.json(), dict) else sched_res.json()
                resolved_parent_map = build_time_graph(schedules)
                
                for meeting in schedules:
                    meeting_date = pd.to_datetime(meeting.get('ScheduleDate', '1970-01-01'), errors='coerce')
                    if not (test_start_date <= meeting_date <= test_end_date): continue
                    date_str = meeting_date.strftime('%Y-%m-%d')
                    raw_owner_name = str(meeting.get('OwnerName', '')).strip()
                    # Normalize whitespace: "House  Convenes" -> "house convenes"
                    owner_lower = re.sub(r'\s+', ' ', raw_owner_name).lower()
                    is_cancelled = meeting.get('IsCancelled', False)
                    status = "CANCELLED" if is_cancelled else ""
                    
                    raw_time = str(meeting.get('ScheduleTime', '')).strip()
                    raw_desc = str(meeting.get('Description', ''))
                    clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()

                    # PR-C2 Part B (Gemini round 2, concern #1): room moves are
                    # frequent during GA session; witness MUST capture them. Field
                    # name is undocumented — try the alias chain. The first-fire
                    # key is recorded only on the first hit per cycle so we can
                    # tell whether LIS has migrated schemas without spamming logs.
                    location_val, _loc_key_fired = _extract_meeting_location(meeting)
                    
                    agenda_url = None
                    link_match = re.search(r'href=[\'"]?([^\'" >]+)', raw_desc)
                    if link_match and any(x in raw_desc.lower() for x in ["agenda", "docket", "info"]):
                        agenda_url = link_match.group(1)
                    
                    sort_time_24h = resolved_parent_map.get(owner_lower, "23:59")
                    time_val = raw_time
                    dynamic_markers = ["upon adjournment", "minutes after", "hour after", "recess"]
                    stitched_text = f"{raw_time} {clean_desc}"
                    if any(m in stitched_text.lower() for m in dynamic_markers):
                        for part in stitched_text.split(';'):
                            if any(m in part.lower() for m in dynamic_markers):
                                time_val = part.strip(); break
                                
                    if not time_val: time_val = "Time TBA"
                    
                    if "joint" in owner_lower or ("house" in owner_lower and "senate" in owner_lower): chamber_prefix = "Joint "
                    elif "house" in owner_lower: chamber_prefix = "House "
                    elif "senate" in owner_lower: chamber_prefix = "Senate "
                    else: chamber_prefix = ""

                    normalized_name = re.sub(r'\s+', ' ', raw_owner_name).strip()
                    sub_regex = re.compile(r'\bsubcommittee\b|\bsub-committee\b|\bsub\.\b|\bsub #\b')
                    is_explicit_sub = bool(sub_regex.search(owner_lower))

                    if not is_explicit_sub:
                        for api_name, aliases in LOCAL_LEXICON.items():
                            if api_name.startswith(chamber_prefix) and any(alias in owner_lower for alias in aliases):
                                original_words = set(re.findall(r'\b\w+\b', owner_lower))
                                lexicon_words = set(re.findall(r'\b\w+\b', api_name.lower()))
                                leftovers = original_words - lexicon_words - IGNORE_WORDS
                                if not leftovers: normalized_name = api_name; break

                    map_key = f"{date_str}_{normalized_name.strip()}"
                    # Don't overwrite a concrete time with a non-concrete one.
                    # Multiple Schedule API entries per date+committee exist; keep the best time.
                    existing_entry = api_schedule_map.get(map_key)
                    if existing_entry and not _is_non_concrete_time(existing_entry.get("Time", "")) and _is_non_concrete_time(time_val):
                        pass  # Keep existing concrete time, skip this TBA/empty overwrite
                    else:
                        api_schedule_map[map_key] = {
                            "Time": time_val,
                            "SortTime": sort_time_24h,
                            "Status": status,
                            "Location": location_val,
                        }
                    
                    # Capture convene times from any floor-session-like Schedule API entry.
                    # Primary: "House Convenes", "House Chamber" (canonical LIS names)
                    # Expanded: "House Session", "House Floor Period", "House of Delegates"
                    # Only set if not already set for this date (first match wins = most specific)
                    _is_house_floor = any(h in owner_lower for h in [
                        "house convenes", "house chamber", "house session",
                        "house floor", "house of delegates",
                    ])
                    _is_senate_floor = any(s in owner_lower for s in [
                        "senate convenes", "senate chamber", "senate session",
                        "senate floor", "senate of virginia",
                    ])
                    if _is_house_floor:
                        if date_str not in convene_times: convene_times[date_str] = {}
                        # Live API ALWAYS overwrites cache — cache is fallback, not primary
                        convene_times[date_str]["House"] = {"Time": time_val, "SortTime": sort_time_24h, "Name": normalized_name.strip()}
                    elif _is_senate_floor:
                        if date_str not in convene_times: convene_times[date_str] = {}
                        convene_times[date_str]["Senate"] = {"Time": time_val, "SortTime": sort_time_24h, "Name": normalized_name.strip()}
                    
                    if meeting_date <= now:
                        # PR-C2 Part B: Location is column 6. Pre-migration cache
                        # rows lack this column; compaction block below pads on
                        # first read so get_all_records returns "" rather than
                        # KeyError.
                        new_cache_entries.append([date_str, normalized_name.strip(), time_val, sort_time_24h, status, location_val])
                    
                    if any(k in owner_lower for k in ["caucus", "session", "floor", "convenes", "adjourned"]):
                        _append_event({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip() if normalized_name else "Chamber Event", "Bill": clean_desc, "Outcome": "", "AgendaOrder": -1, "Source": "API", "Origin": "api_schedule", "DiagnosticHint": ""})
                        continue
                    
                    has_docket = False
                    combined_bills = set()
                    dlq_flag = ""
                    
                    if agenda_url and not is_cancelled and (scrape_start <= meeting_date <= scrape_end):
                        extracted_bills, is_corrupt = extract_rogue_agenda(agenda_url, http_session, meeting_date)
                        combined_bills.update(extracted_bills)
                        if is_corrupt: dlq_flag = "⚠️ [Agenda unreadable - Manual check required]"
                    
                    if date_str in docket_memory:
                        for b_num, comm_list in docket_memory[date_str].items():
                            if any(normalized_name.lower().strip() == c.lower().strip() for c in comm_list):
                                combined_bills.add(b_num)
                                
                    if combined_bills:
                        for bill in sorted(list(combined_bills)):
                            _append_event({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip(), "Bill": bill, "Outcome": "Scheduled", "AgendaOrder": 1, "Source": "DOCKET", "Origin": "api_schedule", "DiagnosticHint": ""})
                            if date_str not in docket_memory: docket_memory[date_str] = {}
                            if bill not in docket_memory[date_str]: docket_memory[date_str][bill] = []
                            if normalized_name.strip() not in docket_memory[date_str][bill]: docket_memory[date_str][bill].append(normalized_name.strip())
                        has_docket = True

                    if dlq_flag:
                        _append_event({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip(), "Bill": dlq_flag, "Outcome": "", "AgendaOrder": 0, "Source": "API_Skeleton", "Origin": "api_schedule", "DiagnosticHint": ""})
                        has_docket = True

                    if not has_docket:
                        if sort_time_24h == "06:00" and "after" in time_val.lower(): clean_desc = f"⚠️ Time Unverified (Check Parent) - {clean_desc}"
                        _append_event({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip(), "Bill": clean_desc if clean_desc else "No agenda listed.", "Outcome": "", "AgendaOrder": -1, "Source": "API_Skeleton", "Origin": "api_schedule", "DiagnosticHint": ""})

                # ============================================================
                # PR-C2 Part B: compute ADDED / CHANGED deltas (raw LIS signal)
                # ============================================================
                # Diff the post-live api_schedule_map against the pre-live
                # snapshot captured before this loop. Deltas are computed
                # BEFORE the best_times post-pass so the witness log faithfully
                # records what LIS told us, not our downstream adjustments.
                # REMOVED is intentionally NOT emitted — a key missing from a
                # given poll cannot be reliably distinguished from "LIS did
                # not return it this cycle due to filtering / cross-session
                # cache staleness". Data-loss detection for those cases is
                # handled by Part C (HISTORY-vs-witness reconciliation).
                try:
                    for _wkey, _wval in api_schedule_map.items():
                        _prev = _pre_live_schedule_snapshot.get(_wkey)
                        # Iterate the whitelist (Gemini concern #1): if we ever add
                        # a new tracked field, we only have to touch
                        # WITNESS_DELTA_FIELDS + WITNESS_HEADER and the comparison
                        # stays honest. Never iterate _wval.items() — that would
                        # make any future metadata key (last_modified, ETag, etc.)
                        # implicitly a delta trigger.
                        _cur_by_field = {f: str(_wval.get(f, "")) for f in WITNESS_DELTA_FIELDS}
                        if "_" in _wkey:
                            _mdate, _mcomm = _wkey.split("_", 1)
                        else:
                            _mdate, _mcomm = "", _wkey
                        if _prev is None:
                            # New key — not seen in cache snapshot; treat as ADDED.
                            # First-run note: on first cycle after a fresh deploy,
                            # EVERY live meeting is ADDED because the cache is
                            # empty. That's expected and self-normalizes after
                            # one cycle.
                            _witness_deltas.append({
                                "seen_at_utc": _witness_seen_at_utc,
                                "run_id": _witness_run_id,
                                "event_type": "ADDED",
                                "meeting_date": _mdate,
                                "committee": _mcomm,
                                "time": _cur_by_field["Time"],
                                "sort_time": _cur_by_field["SortTime"],
                                "status": _cur_by_field["Status"],
                                "location": _cur_by_field["Location"],
                                "prev_time": "",
                                "prev_sort_time": "",
                                "prev_status": "",
                                "prev_location": "",
                            })
                        else:
                            _prev_by_field = {f: str(_prev.get(f, "")) for f in WITNESS_DELTA_FIELDS}
                            _changed_fields = {
                                f for f in WITNESS_DELTA_FIELDS
                                if _cur_by_field[f] != _prev_by_field[f]
                            }
                            if not _changed_fields:
                                continue
                            # Migration burst guard (Gemini concern #1): API_Cache
                            # did not previously store Location, so on the first
                            # cycle(s) after this deploy EVERY cached entry has
                            # Location="" while the live entry has a real value.
                            # Without this guard, every pre-existing meeting would
                            # emit a bogus CHANGED delta. Real Location changes —
                            # prev non-empty and current non-empty but different —
                            # still pass through untouched. Count backfills so the
                            # one-time burst is visible without being noise.
                            if (
                                _changed_fields == {"Location"}
                                and _prev_by_field["Location"] == ""
                                and _cur_by_field["Location"] != ""
                            ):
                                source_miss_counts["witness_location_backfills"] += 1
                                continue
                            _witness_deltas.append({
                                "seen_at_utc": _witness_seen_at_utc,
                                "run_id": _witness_run_id,
                                "event_type": "CHANGED",
                                "meeting_date": _mdate,
                                "committee": _mcomm,
                                "time": _cur_by_field["Time"],
                                "sort_time": _cur_by_field["SortTime"],
                                "status": _cur_by_field["Status"],
                                "location": _cur_by_field["Location"],
                                "prev_time": _prev_by_field["Time"],
                                "prev_sort_time": _prev_by_field["SortTime"],
                                "prev_status": _prev_by_field["Status"],
                                "prev_location": _prev_by_field["Location"],
                            })
                    print(
                        f"📝 Schedule_Witness: {len(_witness_deltas)} deltas detected "
                        f"(ADDED+CHANGED); "
                        f"suppressed_location_backfills={source_miss_counts['witness_location_backfills']}."
                    )
                except Exception as _delta_err:
                    # Delta computation must never block the live merge. If it
                    # fails we still want the cache + master_events writes to
                    # proceed; the next cycle will recompute.
                    push_system_alert(
                        f"Schedule_Witness delta computation failed: {_delta_err}. "
                        f"Witness log skipped this cycle.",
                        status="WARN", category="DATA_ANOMALY", severity="WARN",
                        dedup_key="witness_delta_fail",
                    )
                    _witness_deltas = []

                # If LIS provides multiple schedule rows for the same date+committee,
                # promote any concrete time to sibling API/API_Skeleton rows that are
                # still placeholder time values.
                best_times = {}
                for ev in master_events:
                    if not str(ev.get("Source", "")).startswith("API"):
                        continue
                    date_key = str(ev.get("Date", "")).strip()
                    committee_key = str(ev.get("Committee", "")).strip()
                    if not date_key or not committee_key:
                        continue
                    t_val = str(ev.get("Time", "")).strip()
                    if _is_non_concrete_time(t_val):
                        continue
                    best_times[f"{date_key}_{committee_key}"] = {
                        "Time": t_val,
                        "SortTime": str(ev.get("SortTime", "23:59")).strip()
                    }

                if best_times:
                    for ev in master_events:
                        if not str(ev.get("Source", "")).startswith("API"):
                            continue
                        map_key = f"{str(ev.get('Date', '')).strip()}_{str(ev.get('Committee', '')).strip()}"
                        if map_key in best_times and _is_non_concrete_time(ev.get("Time", "")):
                            ev["Time"] = best_times[map_key]["Time"]
                            ev["SortTime"] = best_times[map_key]["SortTime"]

                    for map_key, sched in api_schedule_map.items():
                        if map_key in best_times and _is_non_concrete_time(sched.get("Time", "")):
                            sched["Time"] = best_times[map_key]["Time"]
                            sched["SortTime"] = best_times[map_key]["SortTime"]

        except Exception as e:
            print(f"🚨 API Schedule failed: {e}")
            push_system_alert(f"🚨 LIS Schedule API failed during run: {e}. Times may be stale or unavailable.", status="OFFLINE")

    # ================================================================
    # PR-C2 Part B: write Schedule_Witness change-feed (append-only)
    # ================================================================
    # Append-only log of ADDED/CHANGED LIS Schedule API events, one row per
    # delta. NOT gated by the circuit breaker: witness is an independent tab
    # whose entire purpose is to survive cycle failures so Part C can run
    # HISTORY-vs-witness reconciliation even when Sheet1 was held back.
    #
    # Schema (13 cols): see WITNESS_HEADER (hoisted above the live loop).
    # ISO timestamps (YYYY-MM-DDTHH:MM:SSZ) sort lexically, so retention
    # deletes by contiguous prefix — done by L3b nightly audit, not here
    # (Gemini round-1 concern #2: in-cycle append + delete_rows race).
    #
    # Volume math: steady-state ~0-100 deltas/cycle × 96 cycles/day × 90-day
    # retention × 13 cols << Sheets' 10M-cell limit (change-feed semantics,
    # not snapshot). The size canary below surfaces runaway growth.
    def _ensure_witness_tab():
        """Return the Schedule_Witness worksheet, auto-creating it with
        header on first call. Returns None on permanent failure so callers
        can skip gracefully."""
        try:
            return sheet.worksheet(WITNESS_TAB_NAME)
        except gspread.exceptions.WorksheetNotFound:
            try:
                new_ws = sheet.add_worksheet(
                    title=WITNESS_TAB_NAME,
                    rows=1000,
                    cols=len(WITNESS_HEADER),
                )
                new_ws.update(values=[WITNESS_HEADER], range_name="A1")
                print(f"📝 Created {WITNESS_TAB_NAME} tab with header.")
                return new_ws
            except Exception as _create_err:
                push_system_alert(
                    f"Could not create {WITNESS_TAB_NAME} tab: {_create_err}. "
                    f"PR-C2 witness log disabled until tab exists.",
                    status="WARN", category="API_FAILURE", severity="WARN",
                    dedup_key="witness_create_fail",
                )
                return None
        except Exception as _lookup_err:
            push_system_alert(
                f"Could not open {WITNESS_TAB_NAME} tab: {_lookup_err}. "
                f"PR-C2 witness log skipped this cycle.",
                status="WARN", category="API_FAILURE", severity="WARN",
                dedup_key="witness_open_fail",
            )
            return None

    witness_tab = None
    if _witness_deltas:
        witness_tab = _ensure_witness_tab()
        if witness_tab is not None:
            try:
                rows_to_append = [
                    [d[col] for col in WITNESS_HEADER]
                    for d in _witness_deltas
                ]
                witness_tab.append_rows(rows_to_append, value_input_option="RAW")
                print(
                    f"📝 {WITNESS_TAB_NAME}: appended {len(rows_to_append)} deltas "
                    f"(run_id={_witness_run_id})."
                )
            except Exception as _append_err:
                push_system_alert(
                    f"{WITNESS_TAB_NAME} append failed: {_append_err}. "
                    f"{len(_witness_deltas)} deltas lost this cycle; next cycle "
                    f"will re-observe any still-current state.",
                    status="WARN", category="API_FAILURE", severity="WARN",
                    dedup_key="witness_append_fail",
                )

    # Size canary (Gemini concern #2): in-cycle prune was removed because
    # append_rows + col_values(1) + delete_rows on the same tab in the same
    # 15-min cycle is a documented eventual-consistency race in the Sheets
    # API — it can silently delete rows we just wrote, or skew the prune
    # boundary. Retention is now owned by the L3b Nightly Audit (TODO, see
    # docs/ideas/future_improvements.md) which runs outside the 15-min path
    # and has exclusive use of the tab.
    #
    # What stays in-cycle: a cheap first-column read so we can (a) WARN if
    # the tab exceeds the safety threshold — which indicates L3b hasn't run
    # — and (b) expose the row count in source_miss_counts so X-Ray can
    # plot witness growth. Read-only; no writes from here.
    if witness_tab is None:
        # Open read-only for the canary even if we had no deltas this cycle.
        witness_tab = _ensure_witness_tab()
    if witness_tab is not None:
        try:
            _witness_rows_total = len(witness_tab.col_values(1))
            source_miss_counts["witness_rows"] = _witness_rows_total
            if _witness_rows_total > WITNESS_CANARY_ROW_THRESHOLD:
                push_system_alert(
                    f"{WITNESS_TAB_NAME} row count is {_witness_rows_total:,} "
                    f"(> {WITNESS_CANARY_ROW_THRESHOLD:,}). L3b nightly audit "
                    f"retention prune has not been running; witness tab is "
                    f"approaching Sheets' 10M-cell limit. Manual compact or "
                    f"L3b audit required.",
                    status="WARN", category="DATA_ANOMALY", severity="WARN",
                    dedup_key="witness_canary_over_threshold",
                )
        except Exception as _canary_err:
            # Canary failure must not block the cycle. Surface it once so we
            # know the read path is broken — next cycle will retry.
            push_system_alert(
                f"{WITNESS_TAB_NAME} size canary read failed: {_canary_err}. "
                f"Retention monitoring disabled this cycle.",
                status="INFO", category="API_FAILURE", severity="INFO",
                dedup_key="witness_canary_read_fail",
            )

    # === SESSION MARKER FALLBACK FOR MISSING CONVENE TIMES ===
    # Some dates have session activity (adjourned, recessed) but no "Convenes" entry.
    # Use the earliest session marker as a fallback convene time.
    # This is an approximation, flagged via "~" prefix in the Time field.
    _session_markers = {}  # date -> chamber -> earliest (time, sort_time, name)
    for ev in master_events:
        if not str(ev.get("Source", "")).startswith("API"):
            continue
        committee = str(ev.get("Committee", ""))
        c_lower = committee.lower()
        if not any(k in c_lower for k in ["adjourned", "recessed", "reconvene"]):
            continue
        t = ev.get("Time", "")
        if not t or t.lower() in ("", "time tba", "tba"):
            continue
        date = ev.get("Date", "")
        chamber = "House" if "house" in c_lower else "Senate" if "senate" in c_lower else None
        if not chamber or not date:
            continue
        sort_t = ev.get("SortTime", "23:59")
        if date not in _session_markers:
            _session_markers[date] = {}
        if chamber not in _session_markers[date] or sort_t < _session_markers[date][chamber][1]:
            _session_markers[date][chamber] = (t, sort_t, committee)

    _fallback_count = 0
    for date, chambers in _session_markers.items():
        for chamber, (t, sort_t, name) in chambers.items():
            existing_time = convene_times.get(date, {}).get(chamber, {}).get("Time", "")
            if date not in convene_times or chamber not in convene_times.get(date, {}) or _is_non_concrete_time(existing_time):
                if date not in convene_times:
                    convene_times[date] = {}
                convene_times[date][chamber] = {
                    "Time": f"~{t}",
                    "SortTime": sort_t,
                    "Name": f"{chamber} Convenes",
                }
                _fallback_count += 1
    if _fallback_count:
        print(f"⚠️ {_fallback_count} convene times derived from session markers (adjourned/recessed fallback)")

    # === CONVENE TIME COVERAGE DIAGNOSTIC ===
    # Log which dates have convene times and which don't.
    # Floor actions on dates without convene times become Journal Entry -> Ledger.
    convene_dates_house = sorted([d for d in convene_times if "House" in convene_times[d]])
    convene_dates_senate = sorted([d for d in convene_times if "Senate" in convene_times[d]])
    print(f"📊 Convene time coverage: House={len(convene_dates_house)} dates, Senate={len(convene_dates_senate)} dates")
    if convene_dates_house:
        print(f"   House range: {convene_dates_house[0]} to {convene_dates_house[-1]}")
    if convene_dates_senate:
        print(f"   Senate range: {convene_dates_senate[0]} to {convene_dates_senate[-1]}")

    print("📡 Processing HISTORY.CSV via Sequential Turing Machine...")
    df_past = safe_fetch_csv(f"https://blob.lis.virginia.gov/lisfiles/{blob_code}/HISTORY.CSV")
    if df_past.empty: df_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
        
    if not df_past.empty:
        bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
        desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
        refid_col = next((c for c in df_past.columns if 'refid' in c.lower() or 'ref_id' in c.lower() or 'ref' in c.lower()), None)
        if refid_col:
            print(f"🔑 Found refid column: '{refid_col}' — enabling structural committee resolution.")
        else:
            print("⚠️ No refid column found in HISTORY.CSV — falling back to text-only committee matching.")
        df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
        df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
        df_past = df_past[(df_past['ParsedDate'] >= test_start_date) & (df_past['ParsedDate'] <= test_end_date)]

        # ============================================================
        # PR-C2 Part C: HISTORY-vs-witness reconciliation (gap recovery)
        # ============================================================
        # Runs ONLY when Part A detected a gap that crossed the CRITICAL
        # threshold (>= GAP_CRITICAL_MINUTES) AND the gap is bounded (<=
        # GAP_RECONCILIATION_MAX_DAYS). Over the 7-day cap the check is
        # skipped with a CRITICAL alert — the window is too wide for the
        # blind-window-loss signal to be actionable (user requested manual
        # review above that threshold).
        #
        # "Active re-poll" is already happening: the current cycle's live
        # Schedule API pass (Part B) captured whatever LIS has NOW. Part C
        # is the downstream check — for each meeting-verb HISTORY row whose
        # ParsedDate falls inside the gap window, see if Schedule_Witness has
        # ANY evidence that ANY committee was scheduled on that same date.
        # A date with meeting-verb HISTORY actions but zero witness evidence
        # = confirmed blind-window loss (we were offline while LIS surfaced
        # and then retracted the schedule, and the meeting happened anyway).
        #
        # NOTE (future consideration): the CRITICAL notification here is
        # routed through push_system_alert → SYSTEM_ALERT row. Owner may
        # later want this on a dedicated dashboard / push channel. See
        # docs/ideas/future_improvements.md (PR-C2 7-day alert routing).
        _reconciliation_should_run = (
            gap_cause in {"outage", "breaker_carryforward"}
            and gap_minutes is not None
            and gap_minutes >= GAP_CRITICAL_MINUTES
            and _gap_window_start_utc is not None
        )
        if _reconciliation_should_run:
            _gap_days = gap_minutes / (60.0 * 24.0)
            if _gap_days > GAP_RECONCILIATION_MAX_DAYS:
                push_system_alert(
                    f"Gap-recovery reconciliation SKIPPED: gap of {_gap_days:.2f} days exceeds "
                    f"{GAP_RECONCILIATION_MAX_DAYS}-day cap (gap_cause={gap_cause}). "
                    f"HISTORY.CSV will still be processed, but blind-window losses during "
                    f"the gap cannot be confirmed programmatically. Manual review required.",
                    status="CRITICAL", category="DATA_ANOMALY", severity="CRITICAL",
                    dedup_key=f"gap_reconciliation_oversized::{_cycle_start_utc.strftime('%Y-%m-%d')}",
                )
            else:
                try:
                    _et = pytz.timezone("America/New_York")
                    _gap_start_et_date = _gap_window_start_utc.astimezone(_et).date()
                    _cycle_end_et_date = _cycle_start_utc.astimezone(_et).date()
                    gap_date_strs = set()
                    _d = _gap_start_et_date
                    while _d <= _cycle_end_et_date:
                        gap_date_strs.add(_d.strftime("%Y-%m-%d"))
                        _d += timedelta(days=1)

                    # Build witness date index from THIS cycle's deltas +
                    # any prior witness rows. Prior rows matter for gaps
                    # that start long before the current cycle — we may
                    # have witnessed a committee well ahead of its meeting
                    # date. Read failure falls back to deltas-only; alert
                    # fires but reconciliation proceeds with a weaker index
                    # (better a partial check than no check).
                    witness_dates = {
                        delta.get("meeting_date", "") for delta in _witness_deltas
                    }
                    if witness_tab is not None:
                        try:
                            # Gemini round-3 HIGH: do NOT use get_all_values()
                            # — Schedule_Witness is a change-feed that can
                            # approach Sheets' 10M-cell ceiling; pulling the
                            # entire tab into memory every cycle is a
                            # scale cliff. Only meeting_date is needed to
                            # build the witness-date set. WITNESS_HEADER is
                            # the canonical schema we write at tab creation,
                            # so the column index is stable; col_values is
                            # 1-indexed.
                            _date_col_idx = WITNESS_HEADER.index("meeting_date") + 1
                            _dates_from_tab = witness_tab.col_values(_date_col_idx)
                            if len(_dates_from_tab) > 1:
                                # _dates_from_tab[0] is the header cell; skip it.
                                witness_dates.update(_dates_from_tab[1:])
                        except Exception as _wread_err:
                            push_system_alert(
                                f"Part C reconciliation: couldn't read {WITNESS_TAB_NAME} "
                                f"for prior-cycle witness index ({_wread_err}). Falling "
                                f"back to this-cycle deltas only.",
                                status="WARN", category="API_FAILURE", severity="WARN",
                                dedup_key="reconciliation_witness_read_fail",
                            )

                    if desc_col in df_past.columns:
                        _desc_lower = df_past[desc_col].astype(str).str.lower()
                        _meeting_verb_mask = _desc_lower.apply(
                            lambda _d: any(v in _d for v in MEETING_VERB_TOKENS)
                        )
                        _date_strs_series = df_past['ParsedDate'].dt.strftime('%Y-%m-%d')
                        _date_mask = _date_strs_series.isin(gap_date_strs)
                        _candidates = df_past[_meeting_verb_mask & _date_mask]

                        _reconciled_dates = 0
                        _blind_window_dates = 0
                        for _gdate, _group in _candidates.groupby(
                            _candidates['ParsedDate'].dt.strftime('%Y-%m-%d')
                        ):
                            _reconciled_dates += 1
                            if _gdate not in witness_dates:
                                _blind_window_dates += 1
                                _bills = (
                                    _group[bill_col].astype(str)
                                    .str.replace(' ', '').str.upper().unique().tolist()
                                )
                                _bills_sample = ', '.join(_bills[:5])
                                if len(_bills) > 5:
                                    _bills_sample += f"...+{len(_bills) - 5}"
                                push_system_alert(
                                    f"CONFIRMED BLIND-WINDOW LOSS on {_gdate}: HISTORY shows "
                                    f"{len(_group)} meeting-verb actions (bills: {_bills_sample}) "
                                    f"but {WITNESS_TAB_NAME} has zero evidence of ANY committee "
                                    f"being scheduled that date. Gap window: "
                                    f"{_gap_start_et_date}→{_cycle_end_et_date} "
                                    f"(cause={gap_cause}, gap_minutes={gap_minutes:.1f}).",
                                    status="WARN", category="DATA_ANOMALY", severity="WARN",
                                    dedup_key=f"blind_window_loss::{_gdate}::{gap_cause}",
                                )
                        print(
                            f"🔍 Part C reconciliation: checked {len(_candidates)} "
                            f"meeting-verb HISTORY rows across {_reconciled_dates} of "
                            f"{len(gap_date_strs)} gap-window dates; "
                            f"{_blind_window_dates} confirmed blind-window dates."
                        )
                        source_miss_counts["reconciliation_blind_dates"] = _blind_window_dates
                        source_miss_counts["reconciliation_checked_dates"] = _reconciled_dates
                    else:
                        push_system_alert(
                            f"Part C reconciliation: HISTORY.CSV missing description column "
                            f"{desc_col!r}. Skipping blind-window check.",
                            status="WARN", category="DATA_ANOMALY", severity="WARN",
                            dedup_key="reconciliation_no_desc_col",
                        )
                except Exception as _recon_err:
                    push_system_alert(
                        f"Part C reconciliation failed: {_recon_err}. "
                        f"Gap-recovery blind-window check skipped this cycle.",
                        status="WARN", category="DATA_ANOMALY", severity="WARN",
                        dedup_key="reconciliation_fail",
                    )

        df_past['OriginalOrder'] = range(len(df_past))
        df_past = df_past.sort_values(by=['ParsedDate', 'OriginalOrder'])
        
        # Enterprise State Memory
        bill_locations = {}
        last_seen_date = {}
        _floor_hit = 0      # Floor actions that got convene times
        _floor_miss = 0     # Floor actions that missed convene times
        _floor_miss_dates = set()  # Which dates are missing

        # PR-B: Date-indexed view of api_schedule_map so NO_SCHEDULE_MATCH rows
        # can carry a diagnostic_hint listing the committees LIS *did* schedule
        # that day. Pure measurement — no classification impact. See
        # docs/workflow/source_miss_visibility.md and
        # docs/failures/gemini_review_patterns.md #37.
        api_schedule_by_date = {}
        for _api_key, _api_val in api_schedule_map.items():
            if "_" not in _api_key:
                continue
            _d, _c = _api_key.split("_", 1)
            api_schedule_by_date.setdefault(_d, []).append(
                (_c, str(_api_val.get("Time", "")))
            )

        def _build_diagnostic_hint(date_str, event_location, acting_chamber_prefix):
            """Return a compact string describing why the row couldn't be sourced.

            Lists up to 3 same-chamber committees LIS scheduled that date so
            a human triaging can see if the miss is a naming mismatch (API had
            a meeting but under a different label) vs a genuine absence (no
            scheduled committee that day could plausibly host this action).
            """
            candidates = api_schedule_by_date.get(date_str, [])
            chamber = (acting_chamber_prefix or "").strip().lower()
            if chamber:
                # Prefer same-chamber candidates when possible.
                same = [c for c in candidates if c[0].strip().lower().startswith(chamber)]
                if same:
                    candidates = same
            # Deduplicate on committee name, keep first occurrence order.
            seen = set()
            trimmed = []
            for name, t in candidates:
                if name in seen:
                    continue
                seen.add(name)
                trimmed.append(f"{name}@{t}")
                if len(trimmed) >= 3:
                    break
            api_str = "; ".join(trimmed) if trimmed else "<none>"
            return f"loc='{event_location}'; api_{date_str}=[{api_str}]"

        for _, row in df_past.iterrows():
            source_miss_counts["total_processed"] += 1
            # Tracks whether committee was resolved via Memory Anchor fallback
            # (rather than refid or lexicon). Drives the orthogonal
            # unsourced_anchor tag counter (which overlaps denominator buckets
            # intentionally — see docs/failures/gemini_review_patterns.md #31).
            anchor_applied = False
            # PR-B: populated for NO_SCHEDULE_MATCH / NO_CONVENE_ANCHOR rows
            # so X-Ray §9 can show *why* the miss happened without hand-
            # chasing through worker logs. Empty string for sourced rows.
            diagnostic_hint = ""
            bill_num = row['CleanBill']
            outcome_text = str(row[desc_col]).strip()
            outcome_lower = outcome_text.lower()
            date_str = row['ParsedDate'].strftime('%Y-%m-%d')
            
            if outcome_text.startswith('H '): acting_chamber_prefix = "House "
            elif outcome_text.startswith('S '): acting_chamber_prefix = "Senate "
            else: acting_chamber_prefix = "House " if bill_num.startswith('H') else "Senate "
            
            if bill_num not in bill_locations: bill_locations[bill_num] = acting_chamber_prefix + "Floor"
            
            # --- MORNING RECONCILIATION ---
            if bill_num not in last_seen_date or last_seen_date[bill_num] != date_str:
                last_seen_date[bill_num] = date_str
                if date_str in docket_memory and bill_num in docket_memory[date_str]:
                    scheduled_rooms = docket_memory[date_str][bill_num]
                    for room in scheduled_rooms:
                        if acting_chamber_prefix.lower() in room.lower() or "joint" in room.lower():
                            bill_locations[bill_num] = room # Proactive Docket Heal
                            break
            
            # --- ACTION SCOPE: ABSOLUTES ---
            is_exec = any(ev in outcome_lower for ev in ["approved by governor", "vetoed by governor", "governor's substitute", "governor's recommendation", "governor:"]) and not (outcome_text.startswith('H ') or outcome_text.startswith('S '))
            is_absolute_floor = any(f in outcome_lower for f in ABSOLUTE_FLOOR_VERBS)
            # "conferee" alone (appointing names) = administrative, no time needed.
            # "conference report agreed" = floor vote, caught by is_absolute_floor above.
            is_conf = ("conferee" in outcome_lower or "conference report" in outcome_lower) and not is_absolute_floor

            if is_exec:
                event_location = "Executive Action"
                bill_locations[bill_num] = "Executive Action"
            elif is_absolute_floor:
                event_location = acting_chamber_prefix + "Floor"
                bill_locations[bill_num] = event_location # Force heal memory
            elif is_conf:
                event_location = "Conference Committee"
                bill_locations[bill_num] = "Conference Committee"
            else:
                # --- ACTION SCOPE: DYNAMIC & EXPLICIT ROOM MATCH ---
                committee_search_prefix = "Joint " if "joint" in outcome_lower or ("house" in outcome_lower and "senate" in outcome_lower) else acting_chamber_prefix

                # PHASE 1: Structural resolution via History_refid (primary key lookup)
                refid_committee = None
                if refid_col:
                    raw_refid = str(row.get(refid_col, '')).strip()
                    refid_committee, refid_source = resolve_committee_from_refid(raw_refid)

                # PHASE 2: Text-based resolution via LOCAL_LEXICON (fallback)
                lexicon_committee = None
                for api_name, aliases in LOCAL_LEXICON.items():
                    if api_name.startswith(committee_search_prefix) and any(alias and alias in outcome_lower for alias in aliases):
                        lexicon_committee = api_name; break

                # Determine action type
                is_referral = any(x in outcome_lower for x in ["referred", "assigned"]) and not any(x in outcome_lower for x in ["fail", "defeat", "strike"])
                is_report = any(x in outcome_lower for x in ["reported", "discharged"]) and not any(x in outcome_lower for x in ["fail", "defeat"])
                is_rerefer = is_report and ("rereferred" in outcome_lower or ("referred" in outcome_lower and "reported" in outcome_lower))
                destination_committee = None  # Used for rerefer: where the bill goes next

                # PHASE 3: Select the correct committee for each role
                # For "reported from X and rereferred to Y":
                #   - refid encodes X (the committee that voted/met)
                #   - lexicon may match X or Y depending on alias iteration order
                #   - We need: event_location = X (for time lookup), destination = Y (for state update)
                if is_report and refid_committee:
                    # Refid is authoritative for the ACTING committee (where the vote happened)
                    acting_committee = refid_committee
                    # If also a rerefer, try to find the destination from text
                    destination_committee = None
                    if is_rerefer:
                        # Find destination after the LAST "referred to" in the full text.
                        # Previous logic split on "referred" which removed the word itself,
                        # making the regex unable to match. Fix: use rfind on the full string.
                        _ref_idx = outcome_text.lower().rfind('referred to')
                        _dest_search = outcome_text[_ref_idx:] if _ref_idx >= 0 else ''
                        dest_match = re.search(r'referred to\s+(?:Committee (?:on|for)\s+)?([A-Z][A-Za-z,\s&\-]+?)(?:\s*\(|\s*[;.]|\s*$)', _dest_search, re.IGNORECASE)
                        if dest_match:
                            dest_name_raw = dest_match.group(1).strip().rstrip(',').strip()
                            # Look up destination in LOCAL_LEXICON
                            for api_name, aliases in LOCAL_LEXICON.items():
                                if api_name.startswith(committee_search_prefix) and any(alias and alias in dest_name_raw.lower() for alias in aliases):
                                    destination_committee = api_name; break
                    matched_committee = acting_committee
                elif is_referral and not is_report:
                    # Pure referral: refid = destination committee code, lexicon also finds destination
                    matched_committee = refid_committee if refid_committee else lexicon_committee
                else:
                    # All other actions: prefer refid, fall back to lexicon
                    matched_committee = refid_committee if refid_committee else lexicon_committee

                if matched_committee:
                    # === DOUBLE-ENTRY MISMATCH DETECTION (Categorized) ===
                    # Instead of suppressing mismatches, categorize them by root cause.
                    # Categories: PARENT_CHILD (INFO), TIMING_LAG (INFO), COMMITTEE_DRIFT (WARN)
                    memory_room = bill_locations[bill_num]
                    if "Floor" not in memory_room and matched_committee != memory_room and not is_referral:
                        mem_norm = normalize_room_key(memory_room)
                        match_norm = normalize_room_key(matched_committee)

                        # Category 1: PARENT_CHILD — subcommittee action within parent committee
                        # Validated via PARENT_COMMITTEE_MAP when available, name prefix fallback otherwise
                        is_parent_child = False
                        if PARENT_COMMITTEE_MAP:
                            # O(1) reverse lookup via pre-calculated NORM_TO_CODE map
                            mem_code = NORM_TO_CODE.get(mem_norm)
                            match_code = NORM_TO_CODE.get(match_norm)
                            if mem_code and match_code:
                                is_parent_child = (PARENT_COMMITTEE_MAP.get(mem_code) == match_code or
                                                   PARENT_COMMITTEE_MAP.get(match_code) == mem_code)
                        if not is_parent_child:
                            # Fallback: name prefix (still valid for unregistered subcommittees)
                            is_parent_child = mem_norm.startswith(match_norm) or match_norm.startswith(mem_norm)

                        # Category 2: TIMING_LAG — agenda placement before referral records
                        is_timing_lag = "placed on" in outcome_lower and "agenda" in outcome_lower

                        # Route by category
                        if is_parent_child:
                            outcome_text = f"ℹ️ [PARENT_CHILD: Memory={memory_room}] " + outcome_text
                        elif is_timing_lag:
                            outcome_text = f"ℹ️ [TIMING_LAG: Memory={memory_room}] " + outcome_text
                        else:
                            outcome_text = f"⚠️ [COMMITTEE_DRIFT: Origin State was {memory_room}] " + outcome_text

                    if is_referral and "from" not in outcome_lower:
                        # Floor to Committee Referral
                        event_location = bill_locations[bill_num]
                        bill_locations[bill_num] = matched_committee # Update target
                    elif is_report:
                        event_location = matched_committee # Distributed Checkpoint Heal (now refid-verified)
                        if is_rerefer and destination_committee:
                            bill_locations[bill_num] = destination_committee # Bill goes to new committee
                        else:
                            bill_locations[bill_num] = acting_chamber_prefix + "Floor"
                    else:
                        event_location = matched_committee
                        bill_locations[bill_num] = matched_committee
                else:
                    # Dynamic Nameless (Memory Anchor)
                    event_location = bill_locations[bill_num]
                    is_dynamic_verb = any(v in outcome_lower for v in DYNAMIC_VERBS)
                    # Previously only dynamic verbs were tagged, leaving admin Memory-Anchor
                    # rows indistinguishable from cleanly-resolved rows downstream
                    # (silent source-miss — see docs/state/open_anti_patterns.md item #3).
                    # Tag both paths with distinct markers so X-Ray can tell them apart.
                    anchor_applied = "Floor" not in event_location
                    if anchor_applied:
                        anchor_tag = "⚙️ [Memory Anchor]" if is_dynamic_verb else "📝 [Memory Anchor: admin]"
                        outcome_text = f"{anchor_tag} " + outcome_text
                    # unsourced_anchor is incremented after time-resolution
                    # (orthogonal tag counter). See
                    # docs/failures/gemini_review_patterns.md #31.

                    # Advance state if it was a nameless report (rare but possible)
                    if any(x in outcome_lower for x in ["reported", "discharged"]) and not any(x in outcome_lower for x in ["fail"]):
                        bill_locations[bill_num] = acting_chamber_prefix + "Floor"

            # === NOISE FILTER (Positive Identification — see module-level constants) ===
            is_known_noise = any(n in outcome_lower for n in KNOWN_NOISE_PATTERNS)
            is_known_event = any(e in outcome_lower for e in KNOWN_EVENT_PATTERNS)

            if is_known_noise and not is_known_event:
                source_miss_counts["dropped_noise"] += 1
                continue  # Confirmed noise, safe to filter
            if not is_known_noise and not is_known_event:
                # UNKNOWN action type — flag but don't suppress
                outcome_text = f"❓ [UNKNOWN_ACTION] " + outcome_text

            # --- UI RENDERING & FUZZY MATCH ---
            event_location = event_location.strip()
            time_val = "Journal Entry"
            sort_time_24h = "23:59"
            status = ""
            # Origin tracks how time_val was resolved. Required by
            # docs/workflow/source_miss_visibility.md so downstream (X-Ray
            # Section 0) can filter silent defaults from concrete sources.
            origin = "journal_default"

            matched_api_key = find_api_schedule_match(
                api_schedule_map=api_schedule_map,
                date_str=date_str,
                event_location=event_location,
                outcome_text=outcome_text,
                acting_chamber_prefix=acting_chamber_prefix,
            )

            if matched_api_key:
                time_val = api_schedule_map[matched_api_key]["Time"]
                sort_time_24h = api_schedule_map[matched_api_key]["SortTime"]
                status = api_schedule_map[matched_api_key]["Status"]
                origin = "api_schedule"
                source_miss_counts["sourced_api"] += 1
                # Adopt parent committee's canonical name when a subcommittee
                # matched via parent fallback (e.g. "Courts of Justice-Civil" -> "Courts of Justice")
                matched_name = matched_api_key.split("_", 1)[1]
                if normalize_room_key(matched_name) != normalize_room_key(event_location):
                    event_location = matched_name

            if "Floor" in event_location:
                anchor = convene_times.get(date_str, {}).get(acting_chamber_prefix.strip())
                if anchor:
                    time_val, sort_time_24h, event_location = anchor["Time"], anchor["SortTime"], anchor["Name"]
                    _floor_hit += 1
                    # Origin/metric parity: if the row was already counted as
                    # api_schedule, move it to sourced_convene so the row's
                    # Origin field and the SYSTEM_METRICS counters agree.
                    # See docs/failures/gemini_review_patterns.md #32.
                    if origin == "api_schedule":
                        source_miss_counts["sourced_api"] -= 1
                    source_miss_counts["sourced_convene"] += 1
                    origin = "convene_anchor"
                else:
                    _floor_miss += 1
                    _floor_miss_dates.add(f"{date_str}_{acting_chamber_prefix.strip()}")
                    if origin == "journal_default":
                        # Concrete source miss: floor action with no convene anchor.
                        # Tag the row so it cannot masquerade as a clean row downstream.
                        time_val = "⏱️ [NO_CONVENE_ANCHOR]"
                        origin = "floor_miss"
                        source_miss_counts["floor_anchor_miss"] += 1
                        diagnostic_hint = _build_diagnostic_hint(
                            date_str, event_location, acting_chamber_prefix
                        )

            # PR-C3: LegislationEvent API as secondary time source. Fires
            # ONLY when (a) the Schedule API didn't yield a concrete time,
            # (b) the row is not a Floor action (Floor goes through
            # convene_anchor / floor_miss), AND (c) the outcome carries a
            # MEETING_VERB_TOKENS verb (PR-C3.1 gate tightening). The
            # un-tightened gate fired for every journal_default row in the
            # full session window — thousands of administrative actions
            # ("Prefiled", "Referred to Committee", "Printed") with zero
            # chance of recovering a meeting time, all hammering the LIS
            # WAF and stacking urllib3 retry/backoff. Restricting to
            # meeting-verb rows collapses the candidate set to the actual
            # Class-1 pattern. This targets HB111/505/972 vs P&E and
            # HB609 vs Finance on Feb 12 2026 — all recovered with
            # minute-precision EventDate. The helper guarantees no
            # exceptions escape and emits categorized alerts for every
            # failure path.
            if origin == "journal_default" and any(v in outcome_lower for v in MEETING_VERB_TOKENS):
                source_miss_counts["legislation_event_attempted"] += 1
                _le_result = _resolve_via_legislation_event_api(
                    http_session=http_session,
                    bill_num=bill_num,
                    action_date_str=date_str,
                    outcome_text=outcome_text,
                    session_code_5d=_session_code_5d,
                    acting_chamber_code=acting_chamber_prefix.strip()[:1].upper(),
                    legislation_id_cache=_legislation_id_cache,
                    legislation_event_cache=_legislation_event_cache,
                    push_alert=push_system_alert,
                )
                if _le_result is not None:
                    time_val, sort_time_24h, status = _le_result
                    origin = "legislation_event"
                    source_miss_counts["sourced_legislation_event"] += 1
                    source_miss_counts["legislation_event_recovered"] += 1

            if origin == "journal_default":
                # No API match, no convene anchor, AND LegislationEvent
                # had nothing — the historic silent "Journal Entry" default
                # that PR#22's post-mortem flagged. Replace with a visible
                # marker and count it. One alert per date+committee+bill
                # is enough; bulk rows would flood.
                time_val = "⏱️ [NO_SCHEDULE_MATCH]"
                source_miss_counts["unsourced_journal"] += 1
                diagnostic_hint = _build_diagnostic_hint(
                    date_str, event_location, acting_chamber_prefix
                )
                push_system_alert(
                    f"No schedule match for {bill_num} at '{event_location}' on {date_str} — row deferred to Ledger.",
                    status="WARN",
                    category="TIMING_LAG",
                    severity="WARN",
                    dedup_key=f"no_match::{date_str}::{event_location}::{bill_num}",
                )

            # Orthogonal tag counter: fires on every row where the Memory
            # Anchor committee fallback was applied, regardless of how the
            # time ultimately resolved. Intentionally overlaps with the
            # denominator buckets — see docs/failures/gemini_review_patterns.md #31.
            if anchor_applied:
                source_miss_counts["unsourced_anchor"] += 1

            _append_event({
                "Date": date_str,
                "Time": time_val,
                "SortTime": sort_time_24h,
                "Status": status,
                "Committee": event_location,
                "Bill": bill_num,
                "Outcome": outcome_text,
                "AgendaOrder": 999,
                "Source": "CSV",
                "Origin": origin,
                "DiagnosticHint": diagnostic_hint,
            })

    # === CONVENE TIME GAP REPORT ===
    scrape_start_str = scrape_start.strftime('%Y-%m-%d')
    print(f"📊 Convene times populated for {len(convene_times)} dates total")
    _scrape_convene = {d for d in convene_times if d >= scrape_start_str}
    print(f"   In scrape window (>= {scrape_start_str}): {len(_scrape_convene)} dates")
    # Check for TBA convene times (populated but useless)
    _tba_convene = [(d, ch) for d in convene_times for ch in convene_times[d] if convene_times[d][ch].get("Time", "") in ("Time TBA", "TBA", "")]
    if _tba_convene:
        print(f"⚠️ {len(_tba_convene)} convene time entries have TBA/empty times (populated but not concrete):")
        for d, ch in sorted(_tba_convene)[:10]:
            print(f"     {d}_{ch}: Time='{convene_times[d][ch].get('Time', '')}'")
    if _floor_miss > 0:
        # Separate pre-scrape misses (expected) from in-window misses (real bugs)
        _in_window_misses = {c for c in _floor_miss_dates if c.split("_")[0] >= scrape_start_str}
        _pre_window_misses = _floor_miss_dates - _in_window_misses
        print(f"🚨 CONVENE GAP: {_floor_miss} floor actions missed convene times (vs {_floor_hit} hits)")
        print(f"   Missing date/chamber combos: {len(_floor_miss_dates)} total")
        print(f"   Pre-scrape (expected, state-building only): {len(_pre_window_misses)}")
        print(f"   In scrape window (REAL BUGS): {len(_in_window_misses)}")
        if _in_window_misses:
            for combo in sorted(_in_window_misses)[:20]:
                print(f"     🔴 {combo}")
        if _pre_window_misses:
            for combo in sorted(_pre_window_misses)[:5]:
                print(f"     ⚪ {combo} (pre-scrape)")
            if len(_pre_window_misses) > 5:
                print(f"     ... and {len(_pre_window_misses) - 5} more pre-scrape combos")
    else:
        print(f"✅ All {_floor_hit} floor actions matched convene times.")

    print("🧹 Filtering Noise & Slicing Viewport...")
    filtered_events = []
    ephemeral_pattern = re.compile(r'\b(for the day|temporarily|temporarilly|to tomorrow|until tomorrow|till tomorrow|for the week|temporay)\b', re.IGNORECASE)
    # Origins that originally manifested as "Journal Entry" time (pre-PR-A).
    # The ephemeral filter used to key off Time == "Journal Entry"; now that
    # Time carries a visible tag instead, gate off Origin.
    UNSOURCED_ORIGINS = {"journal_default", "floor_miss"}

    for ev in master_events:
        if bool(ephemeral_pattern.search(ev["Outcome"])) and ev.get("Origin") in UNSOURCED_ORIGINS:
            if any(x in ev["Committee"] for x in ["Floor", "Convenes", "Chamber", "Executive", "Conference"]):
                pass
            else:
                was_scheduled = False
                d_str = ev["Date"]
                b_num = ev["Bill"]
                c_name = ev["Committee"]
                if d_str in docket_memory and b_num in docket_memory[d_str]:
                    for d_comm in docket_memory[d_str][b_num]:
                        if d_comm.lower() in c_name.lower() or c_name.lower() in d_comm.lower():
                            was_scheduled = True; break
                if not was_scheduled:
                    # Source-miss visibility: was silent `continue` pre-PR-A.
                    # Count the drop and push one alert per date+committee+bill
                    # so X-Ray Section 0 can surface it.
                    source_miss_counts["dropped_ephemeral"] += 1
                    push_system_alert(
                        f"Ephemeral-filter dropped {b_num} at '{c_name}' on {d_str} ({ev.get('Outcome', '')[:80]}).",
                        status="INFO",
                        category="DATA_ANOMALY",
                        severity="INFO",
                        dedup_key=f"ephemeral::{d_str}::{c_name}::{b_num}",
                    )
                    continue
        filtered_events.append(ev)

    # === SOURCE-MISS METRICS (Section 0 denominator) ===
    # Surface the counters that PR-A's post-mortem identified as missing.
    # Encoded as a JSON-in-outcome alert row with Bill="SYSTEM_METRICS" so
    # X-Ray Section 0 can parse it. One-liner summary also goes to stdout
    # so it lands in worker logs.
    try:
        metrics_summary = (
            f"Source-miss metrics: processed={source_miss_counts['total_processed']} "
            f"sourced_api={source_miss_counts['sourced_api']} "
            f"sourced_convene={source_miss_counts['sourced_convene']} "
            f"unsourced_journal={source_miss_counts['unsourced_journal']} "
            f"unsourced_anchor={source_miss_counts['unsourced_anchor']} "
            f"dropped_ephemeral={source_miss_counts['dropped_ephemeral']} "
            f"dropped_noise={source_miss_counts['dropped_noise']} "
            f"floor_anchor_miss={source_miss_counts['floor_anchor_miss']} "
            f"gap_cause={source_miss_counts.get('gap_cause', 'unknown')} "
            f"gap_minutes={source_miss_counts.get('gap_minutes', -1)} "
            f"witness_rows={source_miss_counts.get('witness_rows', -1)} "
            f"witness_location_backfills={source_miss_counts.get('witness_location_backfills', 0)}"
        )
        print(f"📊 {metrics_summary}")
        alert_rows.append({
            "Date": now.strftime("%Y-%m-%d"),
            "Time": now.strftime("%I:%M %p"),
            "SortTime": now.strftime("%H:%M"),
            "Status": "METRICS",
            "Committee": "System Status",
            "Bill": "SYSTEM_METRICS",
            "Outcome": json.dumps(source_miss_counts, separators=(',', ':')),
            "AgendaOrder": -100,
            "Source": "SYSTEM",
            "Origin": "system_metrics",
            "DiagnosticHint": "",
        })
    except Exception as _metrics_err:
        print(f"⚠️ Failed to emit source-miss metrics row: {_metrics_err}")

    if alert_rows:
        filtered_events.extend(alert_rows)

    final_df = pd.DataFrame(filtered_events)
    if not final_df.empty:
        # === OPTION A: Collapse unsourced rows into single Ledger Updates block ===
        # Must run BEFORE dedup so that journal entries from different phantom committees
        # that share the same bill+date get properly deduplicated under one card.
        #
        # Pre-PR-A this keyed off Time == "Journal Entry", which silently erased
        # provenance. The Origin column now carries the true source so downstream
        # (X-Ray Section 0) can still distinguish these rows even after the
        # committee-label rename (see docs/workflow/source_miss_visibility.md).
        if 'Origin' not in final_df.columns:
            final_df['Origin'] = ''
        journal_mask = final_df['Origin'].isin(['journal_default', 'floor_miss'])
        if journal_mask.any():
            final_df.loc[journal_mask, 'Committee'] = '📋 Ledger Updates'
            print(f"📋 Collapsed {int(journal_mask.sum())} unsourced rows into Ledger Updates blocks.")

        final_df = final_df[~((final_df['Bill'] == "No agenda listed.") & final_df.duplicated(subset=['Date', 'Committee', 'Time'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='last')
        final_df = final_df.fillna("")

        scrape_start_str = scrape_start.strftime('%Y-%m-%d')
        scrape_end_str = scrape_end.strftime('%Y-%m-%d')
        # System rows (SYSTEM_ALERT, SYSTEM_METRICS) are stamped with `now`
        # which typically falls outside the investigation window. Exempt them
        # from the viewport slice so X-Ray Section 0 / Bug_Logs can see them.
        # Without this exemption, PR-A's denominator row is silently dropped
        # before Sheet1 is written. See docs/failures/gemini_review_patterns.md #36.
        system_origins = {'system_alert', 'system_metrics'}
        in_window = (final_df['Date'] >= scrape_start_str) & (final_df['Date'] <= scrape_end_str)
        is_system = final_df['Origin'].isin(system_origins)
        final_df = final_df[in_window | is_system]

        if not final_df.empty:
            # Write cache FIRST so any failure alert can be included in Sheet1 output
            if new_cache_entries and cache_sheet:
                print(f"🗄️ Writing {len(new_cache_entries)} new historic records to API_Cache...")
                try:
                    existing_keys = {f"{r.get('Date', '')}_{r.get('Committee', '')}".strip().lower() for r in cache_records} if cache_sheet else set()
                    unique_new_entries = [e for e in new_cache_entries if f"{e[0]}_{e[1]}".strip().lower() not in existing_keys]
                    if unique_new_entries:
                        try:
                            cache_sheet.append_rows(unique_new_entries)
                            print(f"✅ Wrote {len(unique_new_entries)} new records to API_Cache.")
                        except Exception as append_err:
                            if "10000000" in str(append_err) or "limit" in str(append_err).lower():
                                # Cache hit cell limit — compact by deduplicating and replacing
                                print(f"⚠️ API_Cache hit cell limit. Compacting...")
                                merged = {}
                                for r in cache_records:
                                    k = f"{r.get('Date', '')}_{r.get('Committee', '')}".strip().lower()
                                    # PR-C2 Part B: pad pre-migration rows (no Location
                                    # column) with "" so the compaction schema stays
                                    # rectangular and get_all_records() keeps working.
                                    merged[k] = [str(r.get("Date", "")), str(r.get("Committee", "")),
                                                 str(r.get("Time", "")), str(r.get("SortTime", "")),
                                                 str(r.get("Status", "")), str(r.get("Location", ""))]
                                for e in new_cache_entries:
                                    k = f"{e[0]}_{e[1]}".strip().lower()
                                    merged[k] = e  # new data overwrites stale
                                header = [["Date", "Committee", "Time", "SortTime", "Status", "Location"]]
                                rows = list(merged.values())
                                # Write in chunks to stay under Sheets API payload limits
                                CHUNK_SIZE = 10000
                                cache_sheet.clear()
                                try:
                                    cache_sheet.update(values=header, range_name="A1")
                                    for i in range(0, len(rows), CHUNK_SIZE):
                                        chunk = rows[i:i + CHUNK_SIZE]
                                        start_row = i + 2  # row 1 is header
                                        cache_sheet.update(values=chunk, range_name=f"A{start_row}")
                                    print(f"✅ Compacted API_Cache: {len(merged)} unique entries (was {len(cache_records)} rows).")
                                except Exception as compact_err:
                                    # Compaction write failed after clear — attempt to restore original data
                                    print(f"🚨 Compaction write failed: {compact_err}. Attempting rollback...")
                                    try:
                                        restore_rows = header
                                        for r in cache_records:
                                            # Pad pre-migration rows with "" so rollback
                                            # stays rectangular against the new 6-col header.
                                            restore_rows.append([str(r.get("Date", "")), str(r.get("Committee", "")),
                                                                 str(r.get("Time", "")), str(r.get("SortTime", "")),
                                                                 str(r.get("Status", "")), str(r.get("Location", ""))])
                                        for i in range(0, len(restore_rows), CHUNK_SIZE):
                                            chunk = restore_rows[i:i + CHUNK_SIZE]
                                            cache_sheet.update(values=chunk, range_name=f"A{i + 1}")
                                        print(f"✅ Rollback succeeded: restored {len(cache_records)} original rows.")
                                    except Exception as rollback_err:
                                        print(f"🚨 CRITICAL: Rollback also failed: {rollback_err}. Cache data lost.")
                                    raise compact_err
                            else:
                                raise append_err
                except Exception as e:
                    print(f"🚨 CRITICAL: Failed to update API_Cache: {e}")
                    cache_alert = pd.DataFrame([{
                        "Date": now.strftime("%Y-%m-%d"),
                        "Time": now.strftime("%I:%M %p"),
                        "SortTime": now.strftime("%H:%M"),
                        "Status": "CRITICAL",
                        "Committee": "System Status",
                        "Bill": "SYSTEM_ALERT",
                        "Outcome": f"🚨 API_Cache write failure: {e}. {len(new_cache_entries)} records lost. Historical data may be incomplete on next offline run.",
                        "AgendaOrder": -99,
                        "Source": "SYSTEM",
                        "Origin": "system_alert",
                        "DiagnosticHint": "",
                    }])
                    final_df = pd.concat([final_df, cache_alert], ignore_index=True)
                    final_df = final_df.fillna("")

            sheet_data = [final_df.columns.values.tolist()] + final_df.values.tolist()

            # PR-C1: MASS-VIOLATION CIRCUIT BREAKER — last safety net before
            # Sheet1 is overwritten. If this cycle's write-time invariants
            # failed at a high rate, OR the meeting-verb-unsourced count
            # spiked well past today's known-bug baseline (9 for crossover
            # week), refuse the clear+update. The previous cycle's data
            # stays as last-known-good; a compact summary goes to Sheet1!X1
            # so lobbyists / X-Ray can see that a cycle was held back and
            # why. Thresholds are intentionally generous — the breaker is a
            # safety net for REGRESSIONS, not a gate on normal operation.
            CIRCUIT_MAX_VIOLATION_RATE = 0.10         # >10% of rows failing invariants
            CIRCUIT_MAX_ABS_VIOLATIONS = 50           # or >=50 absolute
            CIRCUIT_MAX_MEETING_UNSOURCED = 50        # or >=50 meeting-verb misses (baseline ~9)
            # Review-fix (Gemini): denominator is rows_appended, not
            # total_processed — rows_appended counts ONLY rows that reached
            # the chokepoint (the universe where invariants COULD fire),
            # so the rate is a true fraction-of-opportunity, not diluted
            # by pre-append drops.
            _rows_appended = max(1, source_miss_counts["rows_appended"])
            _total_processed = source_miss_counts["total_processed"]
            _violations = source_miss_counts["invariant_violations"]
            _meeting_unsourced = source_miss_counts["meeting_unsourced"]
            _violation_rate = _violations / _rows_appended
            _breaker_tripped = (
                _violation_rate > CIRCUIT_MAX_VIOLATION_RATE
                or _violations >= CIRCUIT_MAX_ABS_VIOLATIONS
                or _meeting_unsourced >= CIRCUIT_MAX_MEETING_UNSOURCED
            )

            # Review-fix (Codex P1): cycle-end timestamp for Sheet1!Y1 MUST
            # be real UTC. The `now` variable 30 lines up is
            # datetime.now(America/New_York).replace(tzinfo=None) — naive
            # ET mislabeled as UTC by its "Z" suffix. Compute a real UTC
            # timestamp here and use it for every "end of cycle UTC" write
            # below. Kept separate so all other uses of `now` (alert row
            # Date/Time stamped in ET, which is what lobbyists expect) are
            # unchanged.
            _cycle_end_utc = datetime.now(timezone.utc)
            _cycle_end_utc_iso = _cycle_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            if _breaker_tripped:
                _breaker_msg = (
                    f"🚨 CIRCUIT BREAKER TRIPPED at {_cycle_end_utc_iso} — "
                    f"invariant_violations={_violations} "
                    f"meeting_unsourced={_meeting_unsourced} "
                    f"rows_appended={_rows_appended} "
                    f"total_processed={_total_processed} "
                    f"violation_rate={_violation_rate:.2%}. "
                    f"Refusing Sheet1 overwrite to preserve last-known-good. "
                    f"Thresholds: rate>{CIRCUIT_MAX_VIOLATION_RATE:.0%} or "
                    f"violations>={CIRCUIT_MAX_ABS_VIOLATIONS} or "
                    f"meeting_unsourced>={CIRCUIT_MAX_MEETING_UNSOURCED}."
                )
                print(_breaker_msg)
                # Non-destructive visibility #1: compact banner to Sheet1!X1.
                # Does not clear the data. Normal cycles overwrite X1 with ""
                # below so a stale banner never lingers across healthy cycles.
                try:
                    worksheet.update_acell("X1", _breaker_msg[:4500])
                except Exception as _x1_err:
                    print(f"⚠️ Failed to write circuit-breaker banner to Sheet1!X1: {_x1_err}")

                # Review-fix (Codex P2): durable machine-readable trip record
                # to Sheet1!W1. `push_system_alert` only appends to the
                # in-memory `alert_rows` list, which is thrown away on this
                # path because we intentionally skip worksheet.update(). So
                # the critical trip was previously only visible in the X1
                # banner + GitHub Actions stdout — invisible to any monitor
                # that watches SYSTEM_ALERT rows. W1 now carries a JSON
                # payload that the NEXT cycle reads + surfaces as a proper
                # SYSTEM_ALERT carry-forward alert (see _breaker_carryforward
                # block at the top of run_calendar_update). W1 is cleared on
                # successful overwrite so stale records don't double-report.
                try:
                    _breaker_record = {
                        "trip_utc": _cycle_end_utc_iso,
                        "invariant_violations": _violations,
                        "meeting_unsourced": _meeting_unsourced,
                        "rows_appended": _rows_appended,
                        "total_processed": _total_processed,
                        "violation_rate": round(_violation_rate, 4),
                        "thresholds": {
                            "rate": CIRCUIT_MAX_VIOLATION_RATE,
                            "violations_abs": CIRCUIT_MAX_ABS_VIOLATIONS,
                            "meeting_unsourced_abs": CIRCUIT_MAX_MEETING_UNSOURCED,
                        },
                    }
                    worksheet.update_acell("W1", json.dumps(_breaker_record)[:49000])
                except Exception as _w1_err:
                    print(f"⚠️ Failed to write circuit-breaker record to Sheet1!W1: {_w1_err}")

                push_system_alert(
                    _breaker_msg,
                    status="CRITICAL",
                    category="DATA_ANOMALY",
                    severity="CRITICAL",
                    dedup_key=f"circuit_breaker::{_cycle_end_utc.strftime('%Y-%m-%d')}",
                )
                print("🛑 Sheet1 overwrite skipped. State cell Y1 NOT advanced so next cycle's gap-backfill (PR-C2) covers this missed window.")
            else:
                print("💾 Writing to Enterprise Database...")
                worksheet.clear()
                worksheet.update(values=sheet_data, range_name="A1")

                # Non-destructive: clear any stale breaker banner from a prior
                # tripped cycle so X1 reflects CURRENT state. Cheap cell write.
                try:
                    worksheet.update_acell("X1", "")
                except Exception as _x1_clear_err:
                    print(f"⚠️ Failed to clear Sheet1!X1 breaker banner: {_x1_clear_err}")

                # Review-fix (Codex P2): also clear W1 (the durable trip
                # record) on successful write. If we didn't, a healthy
                # cycle would leave the prior trip record sitting in W1,
                # and the NEXT cycle's carry-forward read would surface
                # the same trip a second time.
                try:
                    worksheet.update_acell("W1", "")
                except Exception as _w1_clear_err:
                    print(f"⚠️ Failed to clear Sheet1!W1 breaker record: {_w1_clear_err}")

                # PR-C1: advance the last-successful-cycle cursor. Written
                # ONLY on a successful Sheet1 write so that a failed/halted
                # cycle leaves Y1 pointing at the last good cycle — PR-C2's
                # gap-backfill logic can then use this as its "since" cursor.
                # Review-fix (Codex P1): use real UTC, not ET-masquerading-
                # as-UTC. _cycle_end_utc_iso is computed above from
                # datetime.now(timezone.utc).
                try:
                    worksheet.update_acell("Y1", _cycle_end_utc_iso)
                except Exception as _state_write_err:
                    push_system_alert(
                        f"Could not write state cell Sheet1!Y1 after successful cycle: {_state_write_err}",
                        status="WARN",
                        category="API_FAILURE",
                        severity="WARN",
                        dedup_key="state_cell_y1_write_fail",
                    )

                print("✅ SUCCESS: Regression Test Build is complete.")
        else:
            print("⚠️ Viewport slice resulted in an empty dataframe.")
            worksheet.clear()
            worksheet.update(values=[["Date", "Time", "SortTime", "Status", "Committee", "Bill", "Outcome", "AgendaOrder", "Source", "Origin"]], range_name="A1")
    else:
        print("⚠️ No data generated for the window.")

if __name__ == "__main__": 
    run_calendar_update()
