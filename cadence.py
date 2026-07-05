"""Activity-correlated cadence — LIS-safety guardrail #5 (docs/knowledge/lis_api_safety.md).

Both scheduled workers (calendar_worker.py, bill_tracker.py) fire on a FAST fixed cron and SELF-THROTTLE
here: they run a full cycle only when the legislature is actually active — a real, concrete-time meeting
on the Schedule API (STRUCTURAL, Standard #3, never a text/keyword guess) — and otherwise skip down to a
slow baseline. Load tracks the legislature, not a blind metronome (Standard #8). This replaces the fixed
3h / 6h crons: the cron only *offers* a tick; this module decides whether the tick does real work.

ONE structural signal drives BOTH workers so they never re-derive "is there activity" independently: the
calendar worker maintains the cadence-state cell **Sheet1!AC1** every successful cycle, and the bill worker
reads the same cell. Single source of truth.

AC1 payload (JSON, compact):
    {"lfr": "2026-02-09T14:03:11Z",                 # calendar worker's last full-run end (UTC)
     "win": [["2026-02-09T08:30:00","2026-02-09T11:00:00"], ...]}  # forward meeting windows, ET-local

Each window is [meeting_time - WINDOW_LEAD_MIN, meeting_time + WINDOW_TAIL_MIN] in ET wall-clock, merged so
overlapping same-day meetings collapse to a few spans (keeps the cell tiny).

SAFETY POSTURE — why guardrail #5 is safe to ship even with an edge-case bug in here. BOTH failure
directions are non-catastrophic, so every default fails toward the safe side:
  * Wrongly "always active"  -> workers run the FAST tier 24/7. Guardrails #1 (conditional fetch -> mostly
    304s), #2 (jitter) and #4 (hard request cap) already make 4x/hour sustainable — wasteful, not a ban
    risk (see lis_api_safety.md "Is 4x/hour sustainable?").
  * Wrongly "never active"   -> workers run at today's slow baseline. Identical to current behavior.
  * Any parse/read error     -> treated as EMPTY windows + unknown last-run -> RUN at baseline eligibility
    (fail-toward-freshness, never a silent skip).
The gate ALSO fails OPEN on any exception in the caller (a cadence bug can never *silence* a worker).

Pure decision functions (classify_tier / should_run / decide*) take already-parsed values and do no I/O,
so they are unit-tested directly in cadence_test.py (Standard #7 — measured, not vibed).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytz

# --- structural constants -------------------------------------------------------------------------------

CADENCE_STATE_CELL = "AC1"           # calendar worker's Sheet1: the shared cadence-state JSON (this module)
BILL_LAST_RUN_CELL = "U1"            # bill worker's Bill_Tracker tab: its OWN last-full-run marker (UTC iso)

# final_df Origins that carry a CONCRETE, real meeting time (not an administrative/placeholder row). Mirrors
# the _CONCRETE set in calendar_worker.run_calendar_update — keep in sync (both derive "a real meeting").
CONCRETE_ORIGINS = frozenset({"api_schedule", "convene_anchor", "legislation_event"})

ET = pytz.timezone("America/New_York")

# Window shape around a meeting's listed time. Votes/reports post DURING and shortly AFTER a meeting, so the
# window opens a little before (agendas/quorum) and stays open for a tail afterward.
WINDOW_LEAD_MIN = 30
WINDOW_TAIL_MIN = 120
FORWARD_HORIZON_HOURS = 36           # only cache windows this far ahead — comfortably covers the largest
                                     # gap between full runs (the EMPTY baseline is ~3h), so a window is
                                     # always cached before we enter it, with no LIS call needed to notice.
MAX_WINDOWS = 300                    # seatbelt on AC1 size (a Sheets cell caps at 50k chars; 300 spans is
                                     # ~15 KB and far more than a real 36h horizon ever produces post-merge).

# Per-tier minimum interval (MINUTES) between FULL runs. Tier is derived from the meeting windows below.
# Calibrated (pre-push audit #14) to PRESERVE today's baselines (calendar ~3h, bill ~6h) while adding faster
# tiers ONLY when the legislature is active:
#   IN_WINDOW  a meeting is happening right now      -> fastest (calendar every tick; bill hourly)
#   IDLE       meetings on the forward calendar,      -> medium  (~hourly)
#              but none active this instant
#   EMPTY      nothing on the forward calendar        -> slow baseline (calendar ~3h; bill ~6h)
CALENDAR_TIER_FLOORS = {"IN_WINDOW": 0,   "IDLE": 55,  "EMPTY": 175}
BILL_TIER_FLOORS     = {"IN_WINDOW": 55,  "IDLE": 55,  "EMPTY": 355}


# --- low-level parsing (total functions: never raise) ---------------------------------------------------

def _parse_utc(s):
    """ISO string -> tz-aware UTC datetime, or None. Accepts a trailing 'Z' or an explicit offset."""
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        t = s.strip()
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_et(s):
    """ET-local ISO string ('YYYY-MM-DDTHH:MM:SS', naive) -> tz-aware ET datetime, or None."""
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        dt = datetime.fromisoformat(s.strip())
        return ET.localize(dt) if dt.tzinfo is None else dt.astimezone(ET)
    except Exception:
        return None


def _et_iso(dt):
    """tz-aware ET datetime -> naive ET wall-clock ISO (no offset suffix; that's how windows are stored)."""
    return dt.astimezone(ET).strftime("%Y-%m-%dT%H:%M:%S")


def parse_marker(s):
    """Public: parse a stored UTC-ISO last-run marker (e.g. Bill_Tracker!U1) -> tz-aware UTC datetime|None."""
    return _parse_utc(s)


def parse_state(raw):
    """Parse the AC1 JSON into {"lfr": datetime|None (UTC), "windows": [(start_et, end_et)], "malformed": bool}.

    TOTAL: never raises. The `malformed` flag distinguishes a genuine LOAD/PARSE FAILURE (a non-empty cell we
    couldn't read) from a LEGITIMATE empty state ("no meetings"), so the two aren't collapsed into one
    sentinel — a persistently unreadable cell stays observable instead of masquerading as "quiet legislature"
    (pre-push audit #15, sentinel collision; Qodo #198). It never changes the RUN decision (both still
    fail-toward-freshness) — the caller just logs the malformed case. An EMPTY/absent cell (first deploy,
    cleared) is NOT malformed; unparseable JSON, a non-dict, a present-but-bad lfr, or any dropped window
    entry IS.
    """
    out = {"lfr": None, "windows": [], "malformed": False}
    if not raw:
        return out                       # empty cell (first deploy / cleared) — expected, not malformed
    try:
        obj = json.loads(raw)
    except Exception:
        out["malformed"] = True          # non-empty cell we couldn't parse at all — a real failure
        return out
    if not isinstance(obj, dict):
        out["malformed"] = True
        return out
    lfr_raw = obj.get("lfr")
    out["lfr"] = _parse_utc(lfr_raw)
    if lfr_raw and out["lfr"] is None:
        out["malformed"] = True          # lfr present but unparseable -> corruption
    win = obj.get("win")
    if win is None:
        pass                             # absent windows == legitimately "no meetings" (not malformed)
    elif isinstance(win, list):
        parsed = []
        for pair in win:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                s = _parse_et(pair[0])
                e = _parse_et(pair[1])
                if s is not None and e is not None and e >= s:
                    parsed.append((s, e))
                else:
                    out["malformed"] = True   # a window entry we had to drop -> corruption
            else:
                out["malformed"] = True
        out["windows"] = parsed
    else:
        out["malformed"] = True          # win present but not a list
    return out


# --- pure decision logic (no I/O — unit-tested in cadence_test.py) ---------------------------------------

def classify_tier(now_et, windows):
    """Which activity tier are we in? PURE.

    windows: iterable of (start_et, end_et) tz-aware ET pairs. now_et: tz-aware ET datetime.
      IN_WINDOW  now falls inside a window (a meeting is active) — regardless of tail.
      IDLE       no active window, but a window still lies ahead (a meeting is coming).
      EMPTY      no window ends at or after now (nothing on the forward calendar).
    """
    upcoming_or_active = [(s, e) for (s, e) in windows if e >= now_et]
    if any(s <= now_et <= e for (s, e) in upcoming_or_active):
        return "IN_WINDOW"
    return "IDLE" if upcoming_or_active else "EMPTY"


def should_run(now_utc, last_full_run_utc, tier, floors):
    """Given elapsed since the last full run and this tier's floor, RUN or SKIP this tick? PURE.

    Returns (run: bool, reason: str). Fail-toward-freshness on every ambiguous input:
      * last_full_run_utc is None (never ran / unreadable cell) -> RUN.
      * last_full_run_utc in the FUTURE (clock skew / bad marker) -> RUN (never let a bad marker trap us
        below the floor forever — same root class as audit #11 side-effect-gating / #15 sentinel).
    """
    floor = floors.get(tier, 0)
    if last_full_run_utc is None:
        return True, f"tier={tier} floor={floor}m: no last-run marker -> RUN (fail-toward-freshness)"
    elapsed_min = (now_utc - last_full_run_utc).total_seconds() / 60.0
    if elapsed_min < 0:
        return True, f"tier={tier}: last-run is {(-elapsed_min):.0f}m in the FUTURE -> RUN (ignore bad marker)"
    if elapsed_min >= floor:
        return True, f"tier={tier} floor={floor}m: {elapsed_min:.0f}m elapsed -> RUN"
    return False, f"tier={tier} floor={floor}m: {elapsed_min:.0f}m elapsed -> SKIP (throttled, quiet legislature)"


def decide(raw_state, now_utc, now_et, floors, last_run_utc=None):
    """High-level gate decision. Returns (run, tier, reason).

    Windows come from `raw_state` (the shared AC1 cell). The last-run marker is `raw_state`'s own `lfr` by
    default (the CALENDAR worker throttles against its own cadence), OR an explicitly-passed `last_run_utc`
    (the BILL worker throttles against ITS own marker but reads the SAME windows). PURE-ish: only the tiny
    string parse; no I/O.
    """
    st = parse_state(raw_state)
    tier = classify_tier(now_et, st["windows"])
    lfr = st["lfr"] if last_run_utc is None else last_run_utc
    run, why = should_run(now_utc, lfr, tier, floors)
    if st["malformed"]:
        # Make a parse failure OBSERVABLE in the caller's log (it never changes the decision — the calendar
        # worker rewrites AC1 every successful cycle, so a malformed cell self-heals on the next run).
        why = "[AC1 MALFORMED — self-heals next cycle] " + why
    return run, tier, why


# --- window construction (calendar worker writes AC1 from final_df) --------------------------------------

def _merge_windows(pairs):
    """Merge overlapping/adjacent (start_et, end_et) pairs into the fewest spans. Input/-output ET-aware."""
    spans = sorted(pairs, key=lambda p: p[0])
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            if e > merged[-1][1]:
                merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def build_windows(concrete_rows, now_et):
    """Build forward meeting windows from a cycle's concrete-time meeting rows.

    concrete_rows: iterable of (date_str 'YYYY-MM-DD', sorttime 'HH:MM') — the calendar worker's final_df
    rows whose Origin is in CONCRETE_ORIGINS and whose Time is not a placeholder. now_et: tz-aware ET.

    Returns (windows_iso, stats) where windows_iso is a list of [start_iso_et, end_iso_et] (ET-local, naive)
    within FORWARD_HORIZON_HOURS ahead, merged and capped at MAX_WINDOWS. EVERY skip is COUNTED into stats
    (never a silent `continue` — the caller logs the tally, satisfying source-miss visibility): `skipped`
    (unparseable date/time), `dropped_past` (window already elapsed), `dropped_horizon` (beyond the cache
    horizon — a later run recaptures it). A bad row is counted, never crashes cadence.
    """
    horizon_end = now_et + timedelta(hours=FORWARD_HORIZON_HOURS)
    lead = timedelta(minutes=WINDOW_LEAD_MIN)
    tail = timedelta(minutes=WINDOW_TAIL_MIN)
    pairs = []
    parsed = skipped = dropped_past = dropped_horizon = 0
    for date_str, sorttime in concrete_rows:
        dt = _parse_et(f"{str(date_str).strip()}T{str(sorttime).strip()}:00")
        if dt is None:
            skipped += 1                # unparseable date/time — counted, not silent
            continue
        parsed += 1
        start = dt - lead
        end = dt + tail
        if end < now_et:
            dropped_past += 1           # window already fully elapsed — irrelevant (counted)
            continue
        if start > horizon_end:
            dropped_horizon += 1        # beyond the 36 h horizon — a later full run recaptures it (counted)
            continue
        pairs.append((start, end))
    merged = _merge_windows(pairs)[:MAX_WINDOWS]
    windows_iso = [[_et_iso(s), _et_iso(e)] for (s, e) in merged]
    return windows_iso, {"parsed": parsed, "skipped": skipped, "dropped_past": dropped_past,
                         "dropped_horizon": dropped_horizon, "windows": len(windows_iso)}


def serialize_state(now_utc, windows_iso):
    """Build the compact AC1 JSON string from this cycle's end time (UTC) and its forward windows."""
    return json.dumps(
        {"lfr": now_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "win": windows_iso},
        ensure_ascii=False, separators=(",", ":"),
    )
