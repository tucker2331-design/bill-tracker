#!/usr/bin/env python3
"""Incident log — the mechanism behind the "N days since a data incident" counter (build-wave TASK 2 P1).

The owner's trust goal expanded from "never wrong" to "never less than LIS" (docs/ideas/lobbyist_jtbd_ideation
§8b): a lobbyist must be able to see that the product has been faithful. The visible artifact is a
days-since-incident counter. THIS module is the mechanism; the exact incident DEFINITION and whether the
counter is shown PUBLICLY (vs Health-tab-only) are owner decisions — see docs/architecture/incident_counter.md.

Design:
  * append-only `Incident_Log` tab (VA·Live, gviz-readable) — one row per incident:
    StartUTC | EndUTC | Class | Summary | DetectedBy
  * a GENESIS row (Class="_genesis") is seeded on first use so "days since" has an honest epoch: the count is
    "days since the last incident, OR since monitoring began if none" — never a meaningless number.
  * `record_incident()` is FAIL-OPEN: it wraps all Sheets I/O so a logging failure can NEVER break the guard
    that called it (the accuracy sentinel etc. must fail on DATA problems, not on a ledger hiccup).

The pure date math (`days_since`, `latest_incident_end`) is separated out and unit-tested offline; the Sheets
I/O runs only in CI (needs GCP_CREDENTIALS).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

SPREADSHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"   # VA · Live (gviz-readable for the frontend)
INCIDENT_TAB = "Incident_Log"
HEADER = ["StartUTC", "EndUTC", "Class", "Summary", "DetectedBy"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
GENESIS_CLASS = "_genesis"

# Closed incident-class set (the WORDING of what counts is owner-gated, but the mechanism enforces a closed
# vocabulary so a typo can't invent a class). See the design doc for the owner's definition decision.
CLASSES = ("accuracy", "parity_gap", "degraded", GENESIS_CLASS)


# ── pure, unit-tested ───────────────────────────────────────────────────────────────────────────────────
def _parse_iso(s):
    try:
        # tolerate a space separator ("2026-07-01 00:00:00") as well as ISO "T" — a manual edit or another
        # tool may write either, and mis-parsing an incident's timestamp must not silently drop it (Gemini #225).
        return datetime.strptime(str(s).strip()[:19].replace(" ", "T"),
                                 "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def latest_incident_end(rows, *, include_genesis=True, malformed=None):
    """Given Incident_Log data rows (lists aligned to HEADER, header excluded), return the most recent
    EndUTC (falling back to StartUTC when an incident is still open/instantaneous). A `_genesis` row counts
    as the epoch when include_genesis=True. Returns a tz-aware datetime or None.

    Skipped-row visibility (Standard #9 / CodeRabbit #226): a truly-EMPTY row (Sheets appends blank padding
    at the grid's end) is legitimately skipped, silently. A row that HAS data but is unusable (< 3 cols, so
    Start/End/Class can't all be read) is a DATA ANOMALY — a malformed incident row that could hide a real
    incident and make the trust counter lie. Those are collected into the caller-supplied `malformed` list so
    the caller can raise a categorized alert; never dropped silently."""
    best = None
    for r in rows:
        if not any(str(c).strip() for c in r):
            continue                       # empty Sheets padding — not an incident, no alert warranted
        # only indices 0/1/2 are read here; requiring the full HEADER width (5) would SKIP a real incident
        # whose trailing optional cols (Summary/DetectedBy) were trimmed by Sheets — the under-report bug
        # (Gemini #225). >=3 matches days_since_last_incident.
        if len(r) < 3:
            if malformed is not None:
                malformed.append(r)        # has data but unreadable → surfaced, not silently swallowed
            continue
        cls = str(r[2]).strip()
        if cls == GENESIS_CLASS and not include_genesis:
            continue
        when = _parse_iso(r[1]) or _parse_iso(r[0])   # EndUTC, else StartUTC
        if when and (best is None or when > best):
            best = when
    return best


def days_since(latest, now):
    """Whole days between the latest incident/epoch and `now` (both tz-aware). None latest → None."""
    if latest is None:
        return None
    return max(0, (now - latest).days)


# ── Sheets I/O (CI only) ────────────────────────────────────────────────────────────────────────────────
def _open_tab():
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
        ws = sh.add_worksheet(title=INCIDENT_TAB, rows=200, cols=len(HEADER))
        ws.update("A1", [HEADER])
        # genesis epoch so the counter is meaningful from day one
        ws.append_row([datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "", GENESIS_CLASS,
                       "Incident monitoring began.", "incident_log.setup"], value_input_option="RAW")
        return ws


def record_incident(cls, summary, detected_by, *, start=None, end=None):
    """Append one incident. FAIL-OPEN: any error is swallowed with a print so the CALLER (a critical guard)
    is never broken by a logging problem. Returns True on a confirmed write, else False."""
    if cls not in CLASSES:
        print(f"⚠️ [incident_log] refusing unknown class {cls!r} (allowed: {CLASSES})")
        return False
    try:
        ws = _open_tab()
        if ws is None:
            print(f"[incident_log] no creds — would record: {cls} / {summary}")
            return False
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ws.append_row([start or now, end or "", cls, str(summary)[:500], str(detected_by)[:80]],
                      value_input_option="RAW")
        return True
    except Exception as e:   # fail-open: a guard must fail on DATA, never on the incident log
        print(f"⚠️ [incident_log] record failed (non-fatal): {e}")
        return False


def days_since_last_incident():
    """CLI/health helper: read the log and print 'N days since the last data incident' (genesis-aware)."""
    ws = _open_tab()
    if ws is None:
        print("[incident_log] no creds; run in CI.")
        return
    rows = ws.get_all_values() or []
    malformed = []
    latest = latest_incident_end(rows[1:], malformed=malformed)
    if malformed:
        # a non-empty unreadable row could be a real incident the counter is now ignoring — make it loud
        # (Standard #9: no silent skip on the trust path).
        print(f"⚠️ [DATA_ANOMALY] Incident_Log has {len(malformed)} unreadable non-empty row(s) — a real "
              f"incident could be hidden from the counter; fix the row(s): {malformed[:3]}")
    n = days_since(latest, datetime.now(timezone.utc))
    if n is None:
        print("Incident_Log is empty (no genesis) — seed it first.")
    else:
        real = [r for r in rows[1:] if len(r) >= 3 and str(r[2]).strip() not in (GENESIS_CLASS, "")]
        print(f"📅 {n} days since the last data incident "
              f"({len(real)} incident(s) ever recorded; genesis-aware).")


if __name__ == "__main__":
    days_since_last_incident()
