#!/usr/bin/env python3
"""Incident log — the mechanism behind the "N days clean" counter (build-wave TASK 2 P1 + W1).

The owner's trust goal expanded from "never wrong" to "never less than LIS" (docs/ideas/lobbyist_jtbd_ideation
§8b). Design decisions and the rejected alternatives live in docs/architecture/incident_counter.md; this module
is the mechanism.

WHAT THE COUNTER MEANS (owner, 2026-07-25): **"days we could VERIFY clean"**, not "days nothing broke".
  * `unverified` — a signal fired whose effect on published output could NOT be determined. An unknown is a
    violation: we never bank a day we couldn't check. (Fail-closed — Standard #2's circuit-breaker posture,
    plus "allowed not to know, never pretend".)
  * `false_alarm` — the trust surface went red with no verified data failure underneath. The alarm system is
    part of the product: a client cannot tell "the data is wrong" from "the alarm is wrong", so either way the
    product broke its promise that morning. (This class exists because of the 2026-07-25 red Accuracy ring.)
  * ABSENCE IS NOT AN INCIDENT. If no source published a value and we published nothing, that's a disclosed
    gap, not a failure — the precedent is §9 itself, which counts *meeting* actions without times as bugs while
    administrative actions legitimately have none. `unverified` means **we published something no oracle
    confirms**. Measured 2026-07-25: 16.31% of calendar rows sit on a terminal rung while §9 = 0.

DESIGN
  * append-only `Incident_Log` tab (VA·Live, gviz-readable): StartUTC | EndUTC | Class | Summary | DetectedBy
  * a GENESIS row seeds an honest epoch, so the count is "days since the last incident, OR since monitoring
    began" — never a meaningless number. Every un-seeded day is provable trust thrown away, so seed early.
  * OPEN-INCIDENT semantics (W1.2): a guard failing 100 consecutive cycles must produce ONE incident, not 100.
    `record_incident` refuses to append while an incident of the same (Class, DetectedBy) is open;
    `close_incident` fills its EndUTC when the guard next passes. Recovery detection comes free.
  * FIRE DRILLS, not sandboxes (owner: "don't build fake sandboxes to avoid resetting the timer — use the real
    data"): the `_drill` class runs the ENTIRE production write path against the REAL ledger and is excluded
    from the clock exactly as `_genesis` is. Stronger than a scratch workbook (it proves the real workbook,
    permissions and quota, not a copy) and it leaves an honest record that the alarm is tested.
  * FAIL-OPEN everywhere: a logging failure must never break the guard that called it.

The pure date/state math is separated out and unit-tested offline; the Sheets I/O runs only in CI.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone


def _raw_value_input_option():
    """gspread 6 types `value_input_option` as a ValueInputOption enum; earlier versions took the plain
    string "RAW". Resolve whichever this environment provides so the call is correct under both and a
    version bump cannot silently change how values are parsed on write."""
    try:
        from gspread.utils import ValueInputOption
        return ValueInputOption.raw
    except (ImportError, AttributeError):
        return "RAW"


_RAW = _raw_value_input_option()

# An env override exists ONLY so a human can point a manual run at a scratch workbook. The automated
# verification path deliberately does NOT use it — see the fire-drill note above.
SPREADSHEET_ID = os.environ.get("INCIDENT_LOG_SPREADSHEET_ID",
                                "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM")   # VA · Live
INCIDENT_TAB = "Incident_Log"
HEADER = ["StartUTC", "EndUTC", "Class", "Summary", "DetectedBy"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

GENESIS_CLASS = "_genesis"
DRILL_CLASS = "_drill"
# Rows that are NOT incidents: they must never move the clock or the "incidents ever" count.
NON_INCIDENT_CLASSES = frozenset({GENESIS_CLASS, DRILL_CLASS})

# Closed incident-class set (the WORDING of what counts is owner-settled; the mechanism enforces a closed
# vocabulary so a typo can't invent a class). Order is documentation: real failures, then the meta-classes.
CLASSES = (
    "accuracy",      # wrong data was visible on the product, OR a human had to correct product data
    "parity_gap",    # content on LIS not visible here for > 1 worker cycle
    "degraded",      # a user-visible degraded state (stale banner / missing panel) lasting > 60 min
    "unverified",    # a signal fired whose effect on published output could not be determined
    "false_alarm",   # the trust surface went red with no verified data failure underneath
    GENESIS_CLASS,
    DRILL_CLASS,
)


# ── pure, unit-tested ───────────────────────────────────────────────────────────────────────────────────
def _parse_iso(s):
    try:
        # tolerate a space separator ("2026-07-01 00:00:00") as well as ISO "T" — a manual edit or another
        # tool may write either, and mis-parsing an incident's timestamp must not silently drop it (Gemini #225).
        return datetime.strptime(str(s).strip()[:19].replace(" ", "T"),
                                 "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _cell(r, i):
    return str(r[i]).strip() if len(r) > i and r[i] is not None else ""


def is_incident_row(r):
    """True when this row represents a REAL incident (not genesis, not a drill, not padding/garbage)."""
    return len(r) >= 3 and _cell(r, 2) and _cell(r, 2) not in NON_INCIDENT_CLASSES


def open_incidents(rows):
    """Incidents with no EndUTC — i.e. still ongoing. Returns [(class, detected_by, start, row_index)].

    This is what makes one outage ONE row: a guard consults it before appending (W1.2).
    """
    out = []
    for i, r in enumerate(rows):
        if not is_incident_row(r):
            continue
        if _cell(r, 1):                      # EndUTC present → already closed
            continue
        out.append((_cell(r, 2), _cell(r, 4), _cell(r, 0), i))
    return out


def has_open(rows, cls, detected_by):
    """Is an incident of this (class, detector) already open? The dedup key — a guard owns its own incident."""
    return any(c == cls and d == detected_by for c, d, _s, _i in open_incidents(rows))


def latest_incident_end(rows, *, include_genesis=True, malformed=None):
    """Most recent incident boundary — EndUTC, falling back to StartUTC while an incident is still OPEN (so the
    counter correctly reads ~0 *during* an incident). `_genesis` counts as the epoch; `_drill` never does.

    Skipped-row visibility (Standard #9 / CodeRabbit #226): a truly-EMPTY row (Sheets appends blank padding) is
    legitimately skipped, silently. A row that HAS data but is unusable (< 3 cols, so Start/End/Class can't all
    be read) is a DATA ANOMALY that could HIDE a real incident and make the trust counter lie — those are
    collected into the caller-supplied `malformed` list for a categorized alert, never dropped silently.
    """
    best = None
    for r in rows:
        if not any(str(c).strip() for c in r):
            continue                       # empty Sheets padding — not an incident, no alert warranted
        # only indices 0/1/2 are read here; requiring the full HEADER width (5) would SKIP a real incident
        # whose trailing optional cols were trimmed by Sheets — the under-report bug (Gemini #225).
        if len(r) < 3:
            if malformed is not None:
                malformed.append(r)        # has data but unreadable → surfaced, not silently swallowed
            continue
        cls = _cell(r, 2)
        if cls == DRILL_CLASS:
            continue                       # a fire drill tests the alarm; it is never a break in the streak
        if cls == GENESIS_CLASS and not include_genesis:
            continue
        when = _parse_iso(_cell(r, 1)) or _parse_iso(_cell(r, 0))   # EndUTC, else StartUTC (still open)
        if when and (best is None or when > best):
            best = when
    return best


def days_since(latest, now):
    """Whole days between the latest incident/epoch and `now` (both tz-aware). None latest → None."""
    if latest is None:
        return None
    return max(0, (now - latest).days)


def monitoring_days(rows, now):
    """Days since GENESIS — the counter's DENOMINATOR. Standard #7 applied to our own trust number: "47 days
    clean" is meaningless alone, and a young counter must not masquerade as a long record."""
    for r in rows:
        if len(r) >= 3 and _cell(r, 2) == GENESIS_CLASS:
            g = _parse_iso(_cell(r, 0))
            if g:
                return max(0, (now - g).days)
    return None


def last_drill(rows, now):
    """Days since the last fire drill, or None. A STALE drill date is itself a signal — it means we've stopped
    proving the write path works, so the next real incident might fail to record."""
    best = None
    for r in rows:
        if len(r) >= 3 and _cell(r, 2) == DRILL_CLASS:
            d = _parse_iso(_cell(r, 0))
            if d and (best is None or d > best):
                best = d
    return None if best is None else max(0, (now - best).days)


def counter_state(rows, now):
    """Everything the Health line needs, computed once: the honest verdict WITH its denominator."""
    malformed: list = []
    latest = latest_incident_end(rows, malformed=malformed)
    return {
        "days_clean": days_since(latest, now),
        "monitoring_days": monitoring_days(rows, now),
        "incidents_ever": len([r for r in rows if is_incident_row(r)]),
        "open_now": [c for c, _d, _s, _i in open_incidents(rows)],
        "last_drill_days": last_drill(rows, now),
        "malformed_rows": len(malformed),
    }


# ── Sheets I/O (CI only) ────────────────────────────────────────────────────────────────────────────────
def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _open_tab(create=True):
    creds = os.environ.get("GCP_CREDENTIALS")
    if not creds:
        return None
    import gspread
    from google.oauth2.service_account import Credentials
    gc = gspread.authorize(Credentials.from_service_account_info(json.loads(creds), scopes=SCOPES))
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        return sh.worksheet(INCIDENT_TAB)
    except gspread.exceptions.WorksheetNotFound:   # gspread.__init__ binds .exceptions; no extra import (Gemini #226)
        # ONLY create on a genuine not-found — catching broad Exception would treat a rate-limit/network/
        # credential error as "absent" and then add_worksheet fails confusingly (Gemini #225).
        if not create:
            return None
        ws = sh.add_worksheet(title=INCIDENT_TAB, rows=200, cols=len(HEADER))
        # gspread 6 signature is update(values, range_name) — the OPPOSITE of the pre-6 order. Calling it
        # positionally as ("A1", [HEADER]) passes the range as the values and vice versa, so the genesis row
        # would have failed the first time the ledger was ever created. Caught by mypy, not by any reviewer
        # (docs/workflow/reviewer_strategy.md — the deterministic-checker argument, demonstrated).
        # Keyword args make the call correct under either version.
        ws.update(values=[HEADER], range_name="A1")
        # Genesis epoch, so the counter is meaningful from day one.
        ws.append_row([_now(), "", GENESIS_CLASS, "Incident monitoring began.", "incident_log.setup"],
                      value_input_option=_RAW)
        return ws


def _data_rows(ws):
    return (ws.get_all_values() or [])[1:]


def record_incident(cls, summary, detected_by, *, start=None, end=None):
    """Open an incident, unless this (class, detector) already has one open.

    FAIL-OPEN: any error is swallowed with a print so the CALLER (a critical guard) is never broken by a
    logging problem. Returns True on a confirmed write, False otherwise — including a deliberate no-op when an
    incident is already open (the caller doesn't need to know the difference and shouldn't branch on it).
    """
    if cls not in CLASSES:
        print(f"⚠️ [incident_log] refusing unknown class {cls!r} (allowed: {CLASSES})")
        return False
    try:
        ws = _open_tab()
        if ws is None:
            print(f"[incident_log] no creds — would record: {cls} / {summary}")
            return False
        detected_by = str(detected_by)[:80]
        # W1.2 — one event, one row. A 3-day outage fails ~100 cycles; without this the counter would report
        # 100 incidents for a single event and lie in the pessimistic direction.
        if cls not in NON_INCIDENT_CLASSES and has_open(_data_rows(ws), cls, detected_by):
            print(f"ℹ️  [incident_log] {cls} from {detected_by} is already open — not duplicating.")
            return False
        ws.append_row([start or _now(), end or "", cls, str(summary)[:500], detected_by],
                      value_input_option="RAW")
        return True
    except Exception as e:   # fail-open: a guard must fail on DATA, never on the incident log
        print(f"⚠️ [incident_log] record failed (non-fatal): {e}")
        return False


def close_incident(cls, detected_by, *, end=None):
    """Close this guard's own open incident (fills EndUTC). Called when the guard next PASSES — which is why
    recovery detection needs no extra machinery: whoever detects the failure declares its end.

    Append-only in spirit is preserved: rows are never deleted, a blank cell is filled. FAIL-OPEN.
    """
    try:
        ws = _open_tab(create=False)
        if ws is None:
            return False
        detected_by = str(detected_by)[:80]
        for c, d, _s, i in open_incidents(_data_rows(ws)):
            if c == cls and d == detected_by:
                ws.update_cell(i + 2, 2, end or _now())   # +2: 1-based rows, and row 1 is the header
                print(f"✅ [incident_log] closed {cls} from {detected_by} (recovered).")
                return True
        return False
    except Exception as e:
        print(f"⚠️ [incident_log] close failed (non-fatal): {e}")
        return False


def run_drill(note="scheduled fire drill"):
    """Exercise the ENTIRE production write path against the REAL ledger, then read it back to prove it landed.
    Excluded from the clock like `_genesis`, so the alarm is testable without faking a fire.

    Returns True only when the row was written AND read back — "it didn't raise" is not proof (verify-the-row).
    """
    stamp = _now()
    if not record_incident(DRILL_CLASS, f"{note} @ {stamp}", "incident_log.drill", start=stamp, end=stamp):
        print("❌ [incident_log] DRILL FAILED to write — the real write path is broken RIGHT NOW.")
        return False
    ws = _open_tab(create=False)
    if ws is None:
        return False
    landed = any(_cell(r, 0) == stamp and _cell(r, 2) == DRILL_CLASS for r in _data_rows(ws))
    print("✅ [incident_log] drill row verified in the real ledger." if landed
          else "❌ [incident_log] drill row did NOT read back — the write path is silently failing.")
    return landed


def status(now=None):
    """Print the counter the way the Health tab shows it: the verdict WITH its denominator."""
    ws = _open_tab(create=False)
    if ws is None:
        print("[incident_log] no creds (or tab absent); run in CI.")
        return None
    st = counter_state(_data_rows(ws), now or datetime.now(timezone.utc))
    if st["malformed_rows"]:
        # A non-empty unreadable row could be a real incident the counter is now ignoring — make it loud
        # (Standard #9: no silent skip on the trust path).
        print(f"⚠️ [DATA_ANOMALY] Incident_Log has {st['malformed_rows']} unreadable non-empty row(s) — a real "
              f"incident could be hidden from the counter; fix the row(s).")
    if st["days_clean"] is None:
        print("Incident_Log is empty (no genesis) — seed it first.")
        return st
    md = st["monitoring_days"]
    line = f"📅 {st['days_clean']} days clean"
    line += f" · monitoring for {md} days" if md is not None else " · monitoring window unknown"
    line += f" · {st['incidents_ever']} incident(s) ever"
    if st["open_now"]:
        line += f" · ⚠️ OPEN NOW: {', '.join(st['open_now'])}"
    line += (f" · last drill {st['last_drill_days']}d ago" if st["last_drill_days"] is not None
             else " · ⚠️ no drill on record (the write path is unproven)")
    print(line)
    return st


def _cli(argv):
    """`record <class> <summary> [detected_by]` · `close <class> [detected_by]` · `drill` · `status`.

    `record` exists so the owner's "before intervention" definition is loggable BY HAND: if a human had to
    correct product data, the data did not hold clean on its own and the intervention IS the incident.
    """
    cmd = argv[0] if argv else "status"
    if cmd == "status":
        return 0 if status() is not None else 1
    if cmd == "drill":
        return 0 if run_drill() else 1
    if cmd == "record":
        if len(argv) < 3:
            print("usage: record <class> <summary> [detected_by]")
            return 2
        return 0 if record_incident(argv[1], argv[2], argv[3] if len(argv) > 3 else "manual") else 1
    if cmd == "close":
        if len(argv) < 2:
            print("usage: close <class> [detected_by]")
            return 2
        return 0 if close_incident(argv[1], argv[2] if len(argv) > 2 else "manual") else 1
    print(f"unknown command {cmd!r}; expected record | close | drill | status")
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
