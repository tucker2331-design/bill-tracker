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
from datetime import datetime, timedelta
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from google.oauth2.service_account import Credentials
from bs4 import BeautifulSoup
import pdfplumber

print("🚀 Waking up Enterprise Calendar Worker (Turing State Machine v6.0)...")

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

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
    vote_match = re.match(r'^([HS])(\d{1,2})V\d+', refid)
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
ABSOLUTE_FLOOR_VERBS = ["reading dispensed", "read first", "read second", "read third", "engrossed", "passed senate", "passed house", "agreed to", "rejected", "rules suspended", "conference report agreed"]
# Removed from ABSOLUTE_FLOOR: "signed by", "enrolled", "presented", "received",
# "communicated", "conferees:" — these are administrative/clerk actions per HISTORY.CSV
# data analysis. They do not require people in a room at a specific time.
# Added: "conference report agreed" — floor vote on conference committee compromise.
DYNAMIC_VERBS = ["passed by", "reconsidered", "failed", "defeated", "laid on the table", "tabled", "continued", "strike", "stricken", "incorporate", "recommend", "recommends"]

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
                        except: pass
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
    except: pass
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
    except: pass
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

def run_calendar_update():
    http_session = get_armored_session()
    
    session_data, api_is_online = get_active_session_info(http_session)
    
    tz = pytz.timezone('America/New_York')
    now = datetime.now(tz).replace(tzinfo=None)
    alert_rows = []

    def push_system_alert(message, status="ALERT"):
        alert_rows.append({
            "Date": now.strftime("%Y-%m-%d"),
            "Time": now.strftime("%I:%M %p"),
            "SortTime": now.strftime("%H:%M"),
            "Status": status,
            "Committee": "System Status",
            "Bill": "SYSTEM_ALERT",
            "Outcome": message,
            "AgendaOrder": -99,
            "Source": "SYSTEM",
        })

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

    # === DYNAMIC COMMITTEE MAPS (Enterprise: rebuilt from API each run) ===
    build_committee_maps(http_session, ACTIVE_SESSION, alert_fn=push_system_alert)

    scrape_start = datetime(2026, 2, 9)
    scrape_end = now + timedelta(days=7)

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

    print("🗄️ Pulling historical schedule from API_Cache...")
    api_schedule_map = {}
    convene_times = {}
    cache_sheet = None
    cache_records = []  # Must be initialized before try block to avoid NameError on failure
    try:
        cache_sheet = sheet.worksheet("API_Cache")
        cache_records = cache_sheet.get_all_records()
        for r in cache_records:
            d = str(r.get("Date", ""))
            c = str(r.get("Committee", ""))
            k = f"{d}_{c}"
            api_schedule_map[k] = {"Time": str(r.get("Time", "")), "SortTime": str(r.get("SortTime", "")), "Status": str(r.get("Status", ""))}
            
            c_lower = c.lower()
            _is_house_convene = any(h in c_lower for h in ["house convenes", "house chamber", "house session", "house floor", "house of delegates"])
            _is_senate_convene = any(s in c_lower for s in ["senate convenes", "senate chamber", "senate session", "senate floor", "senate of virginia"])
            if _is_house_convene or _is_senate_convene:
                chamber = "House" if _is_house_convene else "Senate"
                if d not in convene_times: convene_times[d] = {}
                if chamber not in convene_times[d]:  # Don't overwrite with stale cache if live data exists
                    convene_times[d][chamber] = {"Time": str(r.get("Time", "")), "SortTime": str(r.get("SortTime", "")), "Name": c}
    except Exception as e:
        print(f"⚠️ Cache tab empty or unreadable. ({e})")

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
                    owner_lower = raw_owner_name.lower()
                    is_cancelled = meeting.get('IsCancelled', False)
                    status = "CANCELLED" if is_cancelled else ""
                    
                    raw_time = str(meeting.get('ScheduleTime', '')).strip()
                    raw_desc = str(meeting.get('Description', ''))
                    clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
                    
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

                    normalized_name = raw_owner_name
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
                    api_schedule_map[map_key] = {"Time": time_val, "SortTime": sort_time_24h, "Status": status}
                    
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
                        new_cache_entries.append([date_str, normalized_name.strip(), time_val, sort_time_24h, status])
                    
                    if any(k in owner_lower for k in ["caucus", "session", "floor", "convenes", "adjourned"]):
                        master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip() if normalized_name else "Chamber Event", "Bill": clean_desc, "Outcome": "", "AgendaOrder": -1, "Source": "API"})
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
                            master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip(), "Bill": bill, "Outcome": "Scheduled", "AgendaOrder": 1, "Source": "DOCKET"})
                            if date_str not in docket_memory: docket_memory[date_str] = {}
                            if bill not in docket_memory[date_str]: docket_memory[date_str][bill] = []
                            if normalized_name.strip() not in docket_memory[date_str][bill]: docket_memory[date_str][bill].append(normalized_name.strip())
                        has_docket = True

                    if dlq_flag:
                        master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip(), "Bill": dlq_flag, "Outcome": "", "AgendaOrder": 0, "Source": "API_Skeleton"})
                        has_docket = True

                    if not has_docket:
                        if sort_time_24h == "06:00" and "after" in time_val.lower(): clean_desc = f"⚠️ Time Unverified (Check Parent) - {clean_desc}"
                        master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": normalized_name.strip(), "Bill": clean_desc if clean_desc else "No agenda listed.", "Outcome": "", "AgendaOrder": -1, "Source": "API_Skeleton"})

                # If LIS provides multiple schedule rows for the same date+committee,
                # promote any concrete time to sibling API/API_Skeleton rows that are
                # still placeholder time values.
                def _is_non_concrete_time(value):
                    t = str(value or "").strip().lower()
                    return t in {"", "time tba", "tba", "journal entry", "ledger", "none", "nan"}

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
        
        df_past['OriginalOrder'] = range(len(df_past))
        df_past = df_past.sort_values(by=['ParsedDate', 'OriginalOrder'])
        
        # Enterprise State Memory
        bill_locations = {}
        last_seen_date = {}
        _floor_hit = 0      # Floor actions that got convene times
        _floor_miss = 0     # Floor actions that missed convene times
        _floor_miss_dates = set()  # Which dates are missing

        for _, row in df_past.iterrows():
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
                    if is_dynamic_verb and "Floor" not in event_location:
                        outcome_text = f"⚙️ [Memory Anchor] " + outcome_text
                    
                    # Advance state if it was a nameless report (rare but possible)
                    if any(x in outcome_lower for x in ["reported", "discharged"]) and not any(x in outcome_lower for x in ["fail"]):
                        bill_locations[bill_num] = acting_chamber_prefix + "Floor"

            # === NOISE FILTER (Positive Identification — see module-level constants) ===
            is_known_noise = any(n in outcome_lower for n in KNOWN_NOISE_PATTERNS)
            is_known_event = any(e in outcome_lower for e in KNOWN_EVENT_PATTERNS)

            if is_known_noise and not is_known_event:
                continue  # Confirmed noise, safe to filter
            if not is_known_noise and not is_known_event:
                # UNKNOWN action type — flag but don't suppress
                outcome_text = f"❓ [UNKNOWN_ACTION] " + outcome_text
            
            # --- UI RENDERING & FUZZY MATCH ---
            event_location = event_location.strip()
            time_val = "Journal Entry"
            sort_time_24h = "23:59"
            status = ""
            
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
                else:
                    _floor_miss += 1
                    _floor_miss_dates.add(f"{date_str}_{acting_chamber_prefix.strip()}")
                
            master_events.append({"Date": date_str, "Time": time_val, "SortTime": sort_time_24h, "Status": status, "Committee": event_location, "Bill": bill_num, "Outcome": outcome_text, "AgendaOrder": 999, "Source": "CSV"})

    # === CONVENE TIME GAP REPORT ===
    print(f"📊 Convene times populated for {len(convene_times)} dates total")
    # Check for TBA convene times (populated but useless)
    _tba_convene = [(d, ch) for d in convene_times for ch in convene_times[d] if convene_times[d][ch].get("Time", "") in ("Time TBA", "TBA", "")]
    if _tba_convene:
        print(f"⚠️ {len(_tba_convene)} convene time entries have TBA/empty times (populated but not concrete):")
        for d, ch in sorted(_tba_convene)[:10]:
            print(f"     {d}_{ch}: Time='{convene_times[d][ch].get('Time', '')}'")
    if _floor_miss > 0:
        print(f"🚨 CONVENE GAP: {_floor_miss} floor actions missed convene times (vs {_floor_hit} hits)")
        print(f"   Missing date/chamber combos ({len(_floor_miss_dates)}):")
        for combo in sorted(_floor_miss_dates)[:20]:
            print(f"     {combo}")
        if len(_floor_miss_dates) > 20:
            print(f"     ... and {len(_floor_miss_dates) - 20} more")
    else:
        print(f"✅ All {_floor_hit} floor actions matched convene times.")

    print("🧹 Filtering Noise & Slicing Viewport...")
    filtered_events = []
    ephemeral_pattern = re.compile(r'\b(for the day|temporarily|temporarilly|to tomorrow|until tomorrow|till tomorrow|for the week|temporay)\b', re.IGNORECASE)
    
    for ev in master_events:
        if bool(ephemeral_pattern.search(ev["Outcome"])) and ev["Time"] == "Journal Entry":
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
                if not was_scheduled: continue 
        filtered_events.append(ev)

    if alert_rows:
        filtered_events.extend(alert_rows)

    final_df = pd.DataFrame(filtered_events)
    if not final_df.empty:
        # === OPTION A: Collapse Journal Entry phantoms into single Ledger Updates block ===
        # Must run BEFORE dedup so that journal entries from different phantom committees
        # that share the same bill+date get properly deduplicated under one card.
        journal_mask = final_df['Time'] == 'Journal Entry'
        if journal_mask.any():
            final_df.loc[journal_mask, 'Committee'] = '📋 Ledger Updates'
            print(f"📋 Collapsed {journal_mask.sum()} journal entries into Ledger Updates blocks.")

        final_df = final_df[~((final_df['Bill'] == "No agenda listed.") & final_df.duplicated(subset=['Date', 'Committee', 'Time'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='last')
        final_df = final_df.fillna("")

        scrape_start_str = scrape_start.strftime('%Y-%m-%d')
        scrape_end_str = scrape_end.strftime('%Y-%m-%d')
        final_df = final_df[(final_df['Date'] >= scrape_start_str) & (final_df['Date'] <= scrape_end_str)]

        if not final_df.empty:
            # Write cache FIRST so any failure alert can be included in Sheet1 output
            if new_cache_entries and cache_sheet:
                print(f"🗄️ Writing {len(new_cache_entries)} new historic records to API_Cache...")
                try:
                    existing_keys = {f"{r.get('Date', '')}_{r.get('Committee', '')}".strip().lower() for r in cache_records} if cache_sheet else set()
                    unique_new_entries = [e for e in new_cache_entries if f"{e[0]}_{e[1]}".strip().lower() not in existing_keys]
                    if unique_new_entries:
                        cache_sheet.append_rows(unique_new_entries)
                        print(f"✅ Wrote {len(unique_new_entries)} new records to API_Cache.")
                except Exception as e:
                    print(f"🚨 CRITICAL: Failed to update API_Cache: {e}")
                    # Inject alert directly into final_df so it's visible on Sheet1
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
                    }])
                    final_df = pd.concat([final_df, cache_alert], ignore_index=True)

            sheet_data = [final_df.columns.values.tolist()] + final_df.values.tolist()
            print("💾 Writing to Enterprise Database...")
            worksheet.clear()
            worksheet.update(values=sheet_data, range_name="A1")

            print("✅ SUCCESS: Regression Test Build is complete.")
        else:
            print("⚠️ Viewport slice resulted in an empty dataframe.")
            worksheet.clear()
            worksheet.update(values=[["Date", "Time", "SortTime", "Status", "Committee", "Bill", "Outcome", "AgendaOrder", "Source"]], range_name="A1")
    else:
        print("⚠️ No data generated for the window.")

if __name__ == "__main__": 
    run_calendar_update()
