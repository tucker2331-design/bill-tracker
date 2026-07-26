"""bill_tracker.py — structural bill-record pipeline for the lobbyist product (B0/B1).

The forward-build backend for the new product (NOT the old text-driven `backend_worker`). It
REUSES calendar_worker's hardened machinery — the LIS-authorization gate, the counted/guarded
session (guardrail #4), the completeness/truncation-guarded blob fetch (guardrail #1), the
structural committee resolvers, and the Slack alerter — and emits one record per bill to a
`Bill_Tracker` tab that the React/Vite front end reads via gviz.

PR 1 = the SPINE: universe + title + raw LIS status + a derived outcome (raw status always kept) +
the action/date history + the FREE completeness check + the freshness/provenance fields.

PR 2 = STRUCTURAL POSITION, from refids (no text classification, no probabilistic guess): chamber +
crossed-over + last committee + referral count; latest vote WITH its location; upcoming meetings
(DOCKET). LIS's own `status` remains the authoritative "where it is".

PR 3 (this file) = BILLS.CSV ingest (ONE bulk blob — never per-bill, which over 3,645 bills would be
a ban risk): chief PATRON (name + id); a STRUCTURAL-first `outcome` from LIS's OWN fields (Vetoed /
Approved / Chapter_id / Carried_over / Failed / Passed — more reliable than the status keyword, and it
fixes "Continued"→carried_over and chaptered resolutions which the keyword missed); and a SELF-
CALIBRATING outcome check — the keyword fallback is validated each run against LIS's own structural
flags (the oracle), surfaced as a mismatch RATE. No hardcoded status vocabulary to maintain (Standard
#1/#8): LIS is internally inconsistent (its bill feed emits "Continued", absent from its OWN status
reference), so any name allow-list would false-flag forever — the structural reconciliation is the
sustainable check, zero extra LIS calls.
SUBJECT is DEFERRED: LIS publishes NO bulk subject blob (BILLS/HISTORY/DOCKET/VOTE are the only ones)
and the LegislationSubject endpoint is per-bill (a 3,645-call ban risk) — needs a confirmed bulk-safe
source before ingest (see docs/ideas/lis_data_inventory.md §6).

See docs/ideas/product_vision.md, docs/ideas/product_roadmap.md §B0, docs/ideas/lis_data_inventory.md.
"""
import os
import re
import json
import time
import random
import datetime

import gspread
import pytz
import pandas as pd
from google.oauth2.service_account import Credentials

import cadence   # LIS-safety guardrail #5 — the SHARED cadence decision (same signal the calendar worker maintains)

# Reuse the worker's proven, guarded primitives + structural resolvers — single source of truth.
from calendar_worker import (
    safe_fetch_csv,
    get_armored_session,
    get_active_session_info,
    build_committee_maps,           # populates the global COMMITTEE_CODE_MAP …
    resolve_committee_from_refid,   # … which this reads (refid -> committee name + direct/vote source)
    notify_slack,
    session_follow_gate,            # A-1: ban-safe auto-follow of the active session (shared with the worker)
    HEADERS,
    SPREADSHEET_ID,
)
from lis_authorization import normalize_session_code  # is_authorized_session now via session_follow_gate (A-1)

BILL_TRACKER_TAB = "Bill_Tracker"
BILL_LIST_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"
_TALLY_RE = re.compile(r'(\d+-Y\s+\d+-N(?:\s+\d+-A\w*)?)', re.IGNORECASE)


# W0d — alerts raised here previously went ONLY to stdout + Slack, so they could never reach the Health
# tab's alert panel (which reads the append-only Metrics_History tab). On 2026-07-25 that produced the
# worst possible pairing: a RED accuracy ring with the panel underneath it reporting "All clear". Buffered
# here, flushed once per cycle by `flush_alerts_to_metrics_history` — one batched append, and only when
# something actually fired.
_ALERT_BUFFER = []
METRICS_HISTORY_TAB = "Metrics_History"
METRICS_HISTORY_HEADER = ["RunTimestampUTC", "Status", "Origin", "Outcome"]
# Distinct origins from the calendar worker's system_alert/system_metrics: the two workers run on DIFFERENT
# cadences, so the Health tab must judge "is this alert still live?" against the cadence of the worker that
# RAISED it. Sharing one origin would have made every bill alert look instantly resolved.
BILL_ALERT_ORIGIN = "bill_system_alert"
BILL_METRICS_ORIGIN = "bill_system_metrics"


def _alert(severity, category, message):
    """Categorized, self-describing alert (Standard #4) → Slack if configured; always printed; and buffered
    for Metrics_History so it reaches the Health tab's alert panel (W0d)."""
    line = f"🚨 {severity} [BILL_TRACKER/{category}] {message}"
    print(line)
    # Same tagged shape the front end already parses: "[SEV:CATEGORY] message" (web/src/data/history.ts).
    _ALERT_BUFFER.append((str(severity).upper(), f"[{str(severity).upper()}:{str(category).upper()}] {message}"))
    try:
        notify_slack(line)
    except Exception as _slack_err:   # never swallow silently — the alert path itself must be visible
        print(f"⚠️ notify_slack failed for the above alert: {_slack_err}")


def flush_alerts_to_metrics_history(sheet, completeness=None):
    """Append this cycle's buffered alerts + ONE heartbeat row to Metrics_History.

    FAIL-OPEN (mirrors the calendar worker's contract): the alert ledger must never break the run that
    produced the data. The heartbeat is written even when nothing fired — it is how the Health tab knows
    THIS worker's latest cycle, so a bill alert is judged live/resolved against the bill worker's own clock
    rather than the calendar worker's (which ticks far more often)."""
    stamp = datetime.datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    beat = {}
    if completeness:
        # A few numbers worth trending; kept small (this row is appended every cycle, ~45d retention).
        for k in ("records_written", "universe_count", "outcome_unverified", "outcome_impeached",
                  "outcome_keyword_mismatches", "patron_present"):
            v = completeness.get(k)
            if isinstance(v, int):
                beat[k] = v
    rows = [[stamp, "OK", BILL_METRICS_ORIGIN, json.dumps(beat, ensure_ascii=False)]]
    rows += [[stamp, sev, BILL_ALERT_ORIGIN, msg] for sev, msg in _ALERT_BUFFER]
    try:
        try:
            ws = sheet.worksheet(METRICS_HISTORY_TAB)
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title=METRICS_HISTORY_TAB, rows=1000, cols=len(METRICS_HISTORY_HEADER))
            ws.update(values=[METRICS_HISTORY_HEADER], range_name="A1")
        ws.append_rows(rows, value_input_option="RAW")
        print(f"📈 Metrics_History: +{len(rows)} row(s) from the bill worker "
              f"({len(_ALERT_BUFFER)} alert(s) + 1 heartbeat).")
    except Exception as _mh_err:   # fail-open: never break the cycle over the alert ledger
        print(f"⚠️ [BILL_TRACKER] Metrics_History append failed (non-fatal): {_mh_err}")
    finally:
        _ALERT_BUFFER.clear()


# Outcome-provenance vocabulary (docs/architecture/source_precedence). CLOSED set: which rung produced the
# published outcome. `unresolved` is reserved for a future tie (two equally-authoritative sources disagreeing
# with no principle to discriminate) — measured at zero today across 37,832 calendar rows and 3,645 bills, and
# it exists so that case degrades into a visible honest state instead of an invented winner.
OUTCOME_ORIGINS = ("structural_flag", "keyword_fallback", "unresolved")

# Alarm floors for the UNVERIFIED-population delta guard (see `unverified_jump_is_alarming`).
_UNVERIFIED_ABS_JUMP = 25   # bills appearing in one cycle
_UNVERIFIED_MIN_BASE = 10   # below this, a "doubling" is noise, not signal


def unverified_jump_is_alarming(prior, current, prior_universe=None, current_universe=None):
    """Should a rise in the UNVERIFIED population raise an alarm? Pure + golden-tested.

    UNVERIFIED = bills where no structural flag exists, so we publish a text-derived outcome no oracle
    confirms. A DELTA guard, never an absolute floor: the population is legitimately large early in a
    session and ~0 off-season, so a fixed threshold either screams every January or never fires
    (pre-push #14 — prefer delta-vs-baseline for metrics whose floor depends on system behaviour).

    THE CALIBRATION THAT MATTERS (pre-push #14, caught while auditing this very change): a raw count delta
    would fire every session opening, when thousands of NEW bills are introduced before LIS has assigned
    any flags — expected behaviour, not an anomaly. So growth that the UNIVERSE explains is subtracted: we
    alarm on unverified rising FASTER than the bill universe. Session start (+3,000 bills, +3,000
    unverified) is silent; LIS dropping flags on bills it already flagged (+500 unverified, +0 universe)
    is loud — which is the failure we actually want to hear about.

    `prior is None` (first run / unreadable prior payload) → False: no baseline means no comparison, which
    is honest rather than a fabricated one. Universe figures are optional; when absent the guard falls back
    to the raw delta (still correct, just less specific).
    """
    if prior is None or current <= prior:
        return False
    unexplained = current - prior
    if prior_universe is not None and current_universe is not None:
        # Only the growth the universe does NOT explain counts. Clamped at 0 — a shrinking universe must
        # never manufacture a negative allowance and turn a benign cycle into an alarm.
        unexplained -= max(0, current_universe - prior_universe)
        if unexplained <= 0:
            return False
    # BOTH tests run on the UNEXPLAINED growth. Testing the second against the raw `current` was a bug the
    # goldens caught: at session start the raw count is huge for a legitimate reason, so a raw "has it
    # doubled?" fired even when the universe fully explained the rise.
    return unexplained >= _UNVERIFIED_ABS_JUMP or unexplained >= max(prior, _UNVERIFIED_MIN_BASE)


def _clean_bill(bill):
    """Match the worker's CleanBill convention so the universe and HISTORY join 1:1.
    NA/None-safe so a missing id reads as '' (and is skipped), never the literal 'NONE'/'<NA>'."""
    if bill is None or (not isinstance(bill, str) and pd.isna(bill)):
        return ""
    return str(bill).replace(" ", "").upper().strip()


def _parse_date(s):
    """Parse a DOCKET meeting date. Returns a `date`, or None on anything unparseable (never raises).

    Heuristic (Standard #1):
      - ASSUMES LIS publishes DOCKET dates in one of `%m/%d/%Y`, `%Y-%m-%d`, `%m/%d/%y`.
      - BREAKS if LIS introduces a new date format → that row returns None.
      - RUNTIME CHECK: every None is counted into `completeness.docket_unparseable_dates`
        (with its `docket_rows_total` denominator) so a format change surfaces as a rising
        rate instead of silently dropping upcoming meetings.
    """
    s = str(s).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue   # try the next format; exhausting all of them → None, counted by the caller
    return None


# Outcome is a CONVENIENCE label; the RAW LIS status is ALWAYS kept on the record. PR3 makes it
# STRUCTURAL-first: `_outcome_from_flags` reads LIS's OWN boolean flags from BILLS.CSV; the keyword
# path below is the FALLBACK for a bill absent from BILLS.CSV (consuming the controlled Status string,
# never free description text). "carried_over" is distinct from "dead": a continued bill returns next
# session — the PR1 keyword set wrongly folded "Continued" into in_progress/dead.
_OUTCOME_SIGNED = ("approved", "acts of assembly", "chapter")
_OUTCOME_VETOED = ("veto",)
_OUTCOME_CARRIED = ("carried over", "continued")   # carried over to the next session — NOT dead/failed
_OUTCOME_DEAD = ("passed by indefinitely", "stricken", "left in", "failed", "tabled",
                 "incorporated", "withdrawn", "no action")
_OUTCOME_AWAITING = ("enrolled", "pending governor", "awaiting governor", "communicated to governor",
                     "governor's action")   # NOTE: "passed" handled separately — a single-chamber
                                            # "Passed House"/"Passed Senate" is mid-process, not awaiting

# Per-chamber FLOOR outcome (for the Timeline's Floor stages). LIS records floor events in its OWN
# controlled action vocabulary, which NAMES the chamber — consuming those controlled phrases (never free
# prose), gated on the acting chamber:
#   passage — "(Read third time and) passed House/Senate", plus the voice-vote form "Agreed to by
#     House/Senate". A committee-substitute "agreed to" is NOT a floor passage — the `by (House|Senate)`
#     clause excludes it (it reads "committee substitute agreed to", no "by <chamber>").
#   defeat — "(Read third time and) defeated by House/Senate": the bill REACHED that floor and was voted
#     down (~29 instances in 2026 vs 834+ passages). NOT the procedural "substitute/amendments rejected
#     by X" votes — those reject the OTHER chamber's changes on bills that often still pass (e.g. HB55
#     was "Defeated by Senate," reconsidered, and SIGNED — which is also why passage WINS over defeat).
# Validated self-calibrating vs the structural outcome (Standard #1): 1157/1157 fully-passed BILLS show
# both chambers passed; 0 died/carried bills show both.
_PASS_HOUSE_RE = re.compile(r"\bpassed house\b|\bagreed to by house\b", re.I)
_PASS_SENATE_RE = re.compile(r"\bpassed senate\b|\bagreed to by senate\b", re.I)
_DEFEAT_HOUSE_RE = re.compile(r"\bdefeated by house\b", re.I)
_DEFEAT_SENATE_RE = re.compile(r"\bdefeated by senate\b", re.I)


def _outcome_from_flags(meta):
    """STRUCTURAL outcome (Standard #3) from BILLS.CSV's OWN fields; None if none is set (→ caller falls
    back to the keyword path). Precedence is most-terminal-first, validated against every status×flag
    combo in the live 2026 data: a vetoed bill also flags Passed (Vetoed wins); an Incorporated bill
    flags Failed; a Continued bill flags Carried_over (returns next session); and a `Chapter_id` (a
    chapter in the Acts of Assembly) means ENACTED whether or not `Approved` is set — that covers joint
    resolutions, which chapter WITHOUT a Governor's signature (so `Approved=N` yet they are signed/done;
    the keyword-vs-structural reconciliation surfaced these as the 8 HJ/SJ "Acts of Assembly Chapter"
    cases)."""
    if not meta:
        return None
    if meta.get("vetoed"):                            return "vetoed"
    if meta.get("approved") or meta.get("chaptered"): return "signed"   # gov-signed OR chaptered resolution
    if meta.get("carried_over"):                      return "carried_over"
    if meta.get("failed"):                            return "dead"     # covers Failed + Incorporated
    if meta.get("passed"):                            return "awaiting_governor"
    return None


def _derive_outcome(raw_status):
    """KEYWORD-fallback outcome over the controlled Status string (used only when BILLS.CSV lacks the
    bill). The raw status is the authoritative field on the record; this is a convenience label."""
    s = str(raw_status).lower()
    if any(k in s for k in _OUTCOME_VETOED):
        return "vetoed"
    if any(k in s for k in _OUTCOME_SIGNED):
        return "signed"
    if any(k in s for k in _OUTCOME_CARRIED):   # before DEAD: "continued to" must not read as dead
        return "carried_over"
    if any(k in s for k in _OUTCOME_DEAD):      # before the "passed" check: "passed by indefinitely" is dead
        return "dead"
    if any(k in s for k in _OUTCOME_AWAITING):
        return "awaiting_governor"
    if "passed" in s:
        # A single-chamber pass ("Passed House"/"Passed Senate") is still mid-process; only a full pass
        # (bare "Passed" / "Passed Both") awaits the Governor (Qodo #162 — don't read one chamber as done).
        if ("house" in s or "senate" in s) and "both" not in s:
            return "in_progress"
        return "awaiting_governor"
    return "in_progress"


# NOTE (sustainability, Standard #1/#8): the bill-level `outcome` is derived STRUCTURALLY from
# BILLS.CSV's own fields (above), NOT from a hardcoded status-name vocabulary — so a new LIS status
# never needs a human to "extend a table". The keyword path is only a fallback for flagless bills, and
# it is itself runtime-VALIDATED by the structural-vs-keyword reconciliation in build_bill_records
# (LIS's own flags are the oracle). We deliberately do NOT diff against a status-name allow-list:
# LIS is internally inconsistent (its bill feed emits bare "Continued", which is absent from its OWN
# GetLegislationStatusListAsync reference), so any name allow-list — hardcoded or fetched — would
# false-flag forever. See docs/ideas/lis_data_inventory.md §6 / docs/log.md (2026-06-22).


def _build_bills_meta(blob_code):
    """BULK ingest of BILLS.CSV (one guarded blob — NEVER per-bill) → (meta, row_count, skipped_no_bill)
    where meta is {clean_bill: {patron_name, patron_id, vetoed, approved, chaptered, carried_over,
    failed, passed}}. `chaptered` is `Chapter_id` presence (a chapter in the Acts of Assembly = enacted,
    incl. resolutions that chapter without a Governor's signature). Enrichment only: on an empty/failed
    fetch or a missing bill column, returns ({}, 0, 0) and the caller fails soft (keyword-only outcome,
    empty patron) AND alerts on the total-failure case (bills_meta_rows == 0)."""
    df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/BILLS.CSV")
    if df.empty:
        return {}, 0, 0
    cols = {c.lower(): c for c in df.columns}
    bill_col = next((cols[c] for c in ("bill_id", "billnumber", "bill_number") if c in cols), None)
    if not bill_col:
        return {}, 0, 0

    def series(name):   # NA-safe column or all-empty placeholder (no iterrows, no `… or ''` on pd.NA).
        # Tolerate minor LIS header variants (Patron_name vs PatronName) by also trying the
        # underscore-stripped key (Gemini #162); cols keys are already lower-cased.
        c = cols.get(name) or cols.get(name.replace("_", ""))
        return df[c].fillna("").astype(str) if c else [""] * len(df)

    def is_y(v):
        return str(v).strip().upper() == "Y"

    meta, skipped_no_bill = {}, 0
    for b, pnm, pid, vet, app, chap, car, fail, pas in zip(
            df[bill_col].map(_clean_bill), series("patron_name"), series("patron_id"),
            series("vetoed"), series("approved"), series("chapter_id"),
            series("carried_over"), series("failed"), series("passed")):
        if not b:
            skipped_no_bill += 1   # malformed BILLS.CSV row, no bill id — counted (source-miss visibility)
            continue
        meta[b] = {
            "patron_name": pnm.strip(), "patron_id": pid.strip(),
            "vetoed": is_y(vet), "approved": is_y(app), "chaptered": bool(chap.strip()),
            "carried_over": is_y(car), "failed": is_y(fail), "passed": is_y(pas),
        }
    return meta, len(df), skipped_no_bill


def _derive_position(rows, bill):
    """STRUCTURAL position from refids only (rows oldest→newest). All CERTAIN facts — never a guess:
      - chamber: the chamber of the most recent committee action (origin until it crosses).
      - crossed_over: it had a committee action in the chamber OPPOSITE its origin (the crossover fact).
      - last_committee: the committee of its most recent committee-bearing refid.
      - referral_count: distinct sequential committees it was REFERRED to (refid_direct), i.e. how many
        committees it has moved through (the 1st/2nd/3rd-referral badge)."""
    origin = "House" if bill.startswith("H") else "Senate"
    last_committee, current_chamber, crossed = "", origin, False
    referred = []
    for r in rows:
        refid = str(r.get("refid", "")).strip()
        name, source = resolve_committee_from_refid(refid)
        if not name:
            continue   # non-committee action (floor/admin) — no position info; the row is still kept in `history`
        chamber = "House" if refid[:1].upper() == "H" else "Senate"
        current_chamber, last_committee = chamber, name
        if chamber != origin:
            crossed = True
        if source == "refid_direct" and (not referred or referred[-1] != name):
            referred.append(name)   # a new committee it was referred TO
    return {"current_chamber": current_chamber, "crossed_over": crossed,
            "last_committee": last_committee, "referral_count": len(referred)}


def _chief_patron_from_universe(item):
    """Chief patron (full name, member number) from the bill-universe payload's OWN `Patrons` list —
    LIS's authoritative structural field (Standard #3). Returns ("", "") on any absence/shape surprise
    so the caller falls back to BILLS.CSV. Full name "Jeion A. Ward" vs BILLS.CSV's surname "Ward".

    HEURISTIC (Standard #1):
      - ASSUMES `Patrons` is a LIST of DICT entries, the chief carrying PatronTypeID==1 (or Name=="Chief
        Patron"), with `MemberDisplayName` = full name and `MemberNumber` = the "H0173"/"S0012" id that
        MATCHES BILLS.CSV's Patron_id format (verified live 2026-07-04 — NOT the numeric MemberID 419,
        which would mismatch the fallback's format, so it is deliberately NOT used).
      - BREAKS if LIS returns Patrons as a non-list, non-dict elements, or renames the fields → this
        returns ("", "") and the row falls back to the BILLS.CSV surname (a display regression, never a
        crash — Standard #6 zero-trust: the whole cycle must not abort on one odd payload; Qodo #195).
      - RUNTIME CHECK: `completeness.patron_fullname_universe(+_rate)` tracks coverage every cycle; a drop
        from ~100% is the alarm that the shape drifted (Standard #7 — surfaced as a rate)."""
    pats = item.get("Patrons")
    if not isinstance(pats, list):
        return "", ""
    dicts = [p for p in pats if isinstance(p, dict)]
    if not dicts:
        return "", ""
    chief = next((p for p in dicts if p.get("PatronTypeID") == 1 or p.get("Name") == "Chief Patron"),
                 dicts[0])
    # MemberNumber only (the BILLS.CSV-consistent "H0173" format); if absent, leave the id empty rather
    # than substitute the format-incompatible numeric MemberID (Qodo #195).
    return str(chief.get("MemberDisplayName") or "").strip(), str(chief.get("MemberNumber") or "").strip()


def _derive_floor(rows):
    """STRUCTURAL per-chamber floor outcome for the Timeline's Floor stages. Reads LIS's OWN controlled
    action vocabulary (the regexes above), which names the chamber — consuming the source, not parsing free
    prose (Standard #3), the same basis as the outcome derivation. Returns {house, senate} each in
    {"passed", "defeated", ""}: "passed" = cleared that chamber's floor; "defeated" = REACHED that floor and
    was voted down (so the Timeline places its ✕ at Floor, not Committee); "" = no floor event. Passage WINS
    over defeat (a defeated bill can be reconsidered and then pass — HB55). The self-calibrating cross-check
    (a fully-passed BILL must show both passed; a died bill must not) lives in build_bill_records'
    reconciliation counters."""
    house = senate = ""
    for r in rows:
        act = str(r.get("action", ""))
        if house != "passed" and _PASS_HOUSE_RE.search(act):
            house = "passed"
        elif not house and _DEFEAT_HOUSE_RE.search(act):
            house = "defeated"
        if senate != "passed" and _PASS_SENATE_RE.search(act):
            senate = "passed"
        elif not senate and _DEFEAT_SENATE_RE.search(act):
            senate = "defeated"
    return {"house": house, "senate": senate}


def _latest_vote(rows):
    """Most recent recorded vote → {tally, location, date}. The location is STRUCTURAL (the committee
    from the vote refid, else Floor). The tally is a DISPLAY of LIS's OWN published tally string —
    showing it, never classifying on it.

    Granularity note (re: the calendar's meeting-time rule): this carries the vote's DATE, not a
    meeting TIME, on purpose. The card's "latest vote" summarises a PAST vote, for which date +
    location + tally is the complete, decision-relevant record. Meeting-TIME accuracy is the calendar
    subsystem's domain (X-Ray Section 9) — that separate, 100%-accurate engine owns the time lens; we
    do not duplicate its convene-time resolution here.

    Heuristic (Standard #1):
      - ASSUMES LIS writes tallies in its published `N-Y N-N [N-A...]` form (the `_TALLY_RE` shape).
      - BREAKS if LIS changes that surface form → a real vote could read as no-vote (empty tally).
      - RUNTIME CHECK: a structural cross-check (votes present in VOTE.CSV vs. tallies surfaced) is a
        future follow-up; until then the LIS bill-page link on the card is the authoritative backstop.
    """
    for r in reversed(rows):   # newest first
        m = _TALLY_RE.search(str(r.get("action", "")))
        if m:
            name, _src = resolve_committee_from_refid(str(r.get("refid", "")).strip())
            return {"tally": m.group(1).strip(), "location": name or "Floor", "date": r.get("date", "")}
    return {"tally": "", "location": "", "date": ""}


def build_bill_records(http_session, session_code):
    """Build one structural record per bill. Returns (records, completeness)."""
    blob_code = normalize_session_code(session_code)   # 5-digit (reuse, don't re-implement)

    # 1) Authoritative bill UNIVERSE (titles + status + the completeness source).
    resp = http_session.get(BILL_LIST_URL, headers=HEADERS,
                            params={"sessionCode": blob_code}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict):   # explicit, not precedence-dependent (Qodo #159)
        raise RuntimeError("bill universe response was not a JSON object — refusing to overwrite "
                           "(fail-safe: keep last-known-good).")
    universe = payload.get("Legislations") or []
    if not universe:
        raise RuntimeError("bill universe came back empty — refusing to overwrite with nothing "
                           "(fail-safe: keep last-known-good).")

    # 2) HISTORY (guarded) → per-bill rows WITH the refid (needed for the structural position).
    hist_df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
    if hist_df.empty:
        raise RuntimeError("HISTORY.CSV came back empty — refusing to overwrite with empty histories "
                           "(fail-safe: keep last-known-good).")
    cols = {c.lower(): c for c in hist_df.columns}
    bill_col = next((cols[c] for c in ("billnumber", "bill_number", "bill_id") if c in cols), None)
    desc_col = next((cols[c] for c in ("description", "history_description", "action") if c in cols), None)
    date_col = next((cols[c] for c in ("historydate", "history_date", "date") if c in cols), None)
    refid_col = next((cols[c] for c in ("history_refid", "refid") if c in cols), None)
    if not (bill_col and desc_col):
        raise RuntimeError(f"HISTORY.CSV missing the bill/description columns (cols={list(hist_df.columns)}) "
                           "— refusing to overwrite with empty histories (fail-safe).")
    hist_by_bill = {}
    bills = hist_df[bill_col].map(_clean_bill)
    descs = hist_df[desc_col].fillna("").astype(str)
    dates = hist_df[date_col].fillna("").astype(str) if date_col else [""] * len(hist_df)
    refids = hist_df[refid_col].fillna("").astype(str) if refid_col else [""] * len(hist_df)
    for b, act, dt, rf in zip(bills, descs, dates, refids):
        act = act.strip()
        if b and act:
            # Normalize the refid at this ingestion boundary — resolve_committee_from_refid matches
            # case-sensitive `^[HS]…` regexes, so a lowercase/mixed-case refid from LIS would silently
            # fail to resolve (Gemini #161). Upper-case once here so every downstream read is clean.
            hist_by_bill.setdefault(b, []).append(
                {"action": act, "date": dt.strip(), "refid": rf.strip().upper()})

    # 3) Committee maps (populates the global COMMITTEE_CODE_MAP for resolve_committee_from_refid).
    #    Enrichment only: build_committee_maps already has its OWN static fallback, so this broad
    #    catch is a deliberate belt-and-suspenders guard for a truly unexpected failure — it must
    #    never sink the spine. Kept broad ON PURPOSE (any failure here is acceptable to absorb), but
    #    the alert carries the exception TYPE so an unexpected mode is still diagnosable, not hidden.
    try:
        build_committee_maps(http_session, blob_code)
    except Exception as _cm_err:
        _alert("WARN", "API_FAILURE",
               f"committee map build failed ({type(_cm_err).__name__}: {_cm_err}); using static fallback.")

    # 4) DOCKET (guarded) → upcoming committee meetings per bill. Empty off-season is correct, not an error.
    docket_by_bill = {}
    doc_df = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/DOCKET.CSV")
    if not doc_df.empty:
        dcols = {c.lower(): c for c in doc_df.columns}
        dbill = next((dcols[c] for c in ("billnumber", "bill_number", "bill_id", "bill") if c in dcols), None)
        ddate = next((dcols[c] for c in ("meetingdate", "meeting_date", "docketdate", "date", "doc_date") if c in dcols), None)
        dcomm = next((dcols[c] for c in ("committeename", "committee_name", "committee", "ownername", "description") if c in dcols), None)
        if dbill and ddate:
            dbills = doc_df[dbill].map(_clean_bill)
            ddates = doc_df[ddate].fillna("").astype(str)
            dcomms = doc_df[dcomm].fillna("").astype(str) if dcomm else [""] * len(doc_df)
            for b, dt, cm in zip(dbills, ddates, dcomms):
                if b:
                    docket_by_bill.setdefault(b, []).append({"date": str(dt).strip(), "committee": str(cm).strip()})
    # 5) BILLS.CSV (one guarded BULK blob) → chief patron + structural outcome flags for every bill.
    bills_meta, bills_meta_rows, bills_skipped_no_bill = _build_bills_meta(blob_code)

    # Virginia-local (ET) date — NOT the runner's UTC date. An evening run on a UTC CI box would
    # otherwise treat tomorrow as "today" and drop a meeting still scheduled for today in ET
    # (Gemini/Qodo #161). Matches the repo's America/New_York convention (calendar_worker).
    today = datetime.datetime.now(pytz.timezone("America/New_York")).date()

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records, universe_bills, skipped_universe = [], set(), 0
    docket_unparseable, docket_rows_total = 0, 0   # the metric + its denominator (Standard #7)
    outcome_structural, outcome_keyword, patron_present = 0, 0, 0   # trust counters (coverage of the bulk join)
    patron_fullname_universe = 0   # bills whose chief-patron FULL name came from the universe (vs BILLS.CSV surname)
    outcome_mismatches = []   # LIS-internal: its status STRING disagrees with its own FLAGS (we publish the flag)
    unverified_bills = []     # no structural flag exists → we published a text-derived value NO oracle confirms
    # Floor-passage self-calibration (Standard #1): among fully-passed BILLS (HB/SB — resolutions are
    # single-chamber and excluded), how many DON'T show both floor passages? Should be ~0; a rising rate
    # means LIS drifted its "passed House/Senate" action vocabulary. floor_both_expected is the denominator.
    floor_house_bills = floor_senate_bills = floor_both_expected = floor_both_missing = 0
    for item in universe:
        bill = _clean_bill(item.get("LegislationNumber", ""))
        if not bill:
            skipped_universe += 1   # surfaced in completeness (source-miss visibility), never silent
            continue
        universe_bills.add(bill)
        rows = hist_by_bill.get(bill, [])
        position = _derive_position(rows, bill)
        upcoming = []
        for d in docket_by_bill.get(bill, []):
            docket_rows_total += 1         # the denominator for the unparseable-rate metric
            meeting_day = _parse_date(d["date"])
            if meeting_day is None:
                docket_unparseable += 1    # counted (over docket_rows_total), not silently dropped
                continue                   # malformed date → skip this meeting; surfaced as a rate
            if meeting_day >= today:       # future meetings only (empty off-season, correctly)
                upcoming.append(d)

        raw_status = str(item.get("LegislationStatus", "") or "").strip()
        meta = bills_meta.get(bill)
        structural_outcome = _outcome_from_flags(meta)   # STRUCTURAL-first (Standard #3)
        keyword_outcome = _derive_outcome(raw_status)    # always computed — also the reconciliation probe
        # PROVENANCE (W0c, docs/architecture/source_precedence): record WHICH RUNG produced the published
        # outcome, the same way the calendar stamps `Origin` on every row. Without this the adjudication
        # verdict — "the sources disagreed AND we published the oracle's value" — was computed here and then
        # THROWN AWAY, leaving only a bare mismatch rate downstream. That discarded verdict is the root cause
        # of the 2026-07-25 false red: the rate tripped a threshold even though every published value was the
        # authoritative one. With the origin on the row, `published_output_impeached` is derivable downstream
        # for free, and the genuinely-unverified rows stop being invisible.
        if structural_outcome:
            outcome, outcome_structural = structural_outcome, outcome_structural + 1
            outcome_origin = "structural_flag"   # published LIS's OWN flag = the oracle ⇒ NOT impeached
            # Self-calibrating runtime check (Standard #1): LIS's OWN flags are the oracle. A keyword
            # outcome that disagrees means the status STRING and the FLAGS disagree — an observation about
            # LIS's internal consistency, NOT about our accuracy (we published the flag). See the completeness
            # payload comment: this is deliberately no longer an accuracy alarm.
            if keyword_outcome != structural_outcome:
                outcome_mismatches.append(bill)
        else:
            # No oracle exists for this bill: we publish a value derived from LIS's status TEXT that nothing
            # structural confirms. This is the genuinely UNVERIFIED population (fail-closed doctrine — the
            # one the surface must disclose), and it is what the alarm now watches.
            outcome, outcome_keyword = keyword_outcome, outcome_keyword + 1   # flagless (early-stage) bill
            outcome_origin = "keyword_fallback"
            unverified_bills.append(bill)
        # Chief patron: PREFER the bill-universe payload's OWN Patrons list — LIS's authoritative field,
        # carrying the FULL name ("Jeion A. Ward") + member number, vs BILLS.CSV's surname-only ("Ward").
        # Same call we already make (zero extra LIS traffic). BILLS.CSV is the fallback if LIS ever drops
        # Patrons from the list endpoint. NB: this bulk endpoint carries ONLY the chief patron
        # (PatronTypeID==1) — verified all 3,645 lists are size 1 — so co-patrons remain a separate,
        # bounded per-member backfill, not sourceable here (2026-07-04).
        u_name, u_id = _chief_patron_from_universe(item)
        patron = u_name or (meta["patron_name"] if meta else "")
        patron_id = u_id or (meta["patron_id"] if meta else "")
        if patron:
            patron_present += 1
        if u_name:
            patron_fullname_universe += 1   # coverage of the richer source; a drop = LIS changed the list shape
        floor = _derive_floor(rows)
        floor_house_bills += floor["house"] == "passed"
        floor_senate_bills += floor["senate"] == "passed"
        # Self-calibrating reconciliation: a fully-passed BILL (HB/SB, not a single-chamber resolution)
        # must have cleared BOTH floors. Count the exceptions as a rate (Standard #1/#7).
        if outcome in ("awaiting_governor", "signed", "vetoed") and re.match(r"^[HS]B", bill):
            floor_both_expected += 1
            if not (floor["house"] == "passed" and floor["senate"] == "passed"):
                floor_both_missing += 1
        records.append({
            "bill": bill,
            "title": str(item.get("Description", "") or "").strip(),
            "status_lis": raw_status,                                # authoritative, always shown
            "outcome": outcome,                                      # structural-first, keyword fallback
            "outcome_origin": outcome_origin,                        # WHICH rung produced it (provenance)
            "patron": patron,                                        # chief patron FULL name (universe payload; BILLS.CSV surname fallback)
            "patron_id": patron_id,
            "chamber": position["current_chamber"],
            "crossed_over": position["crossed_over"],
            "floor_house": floor["house"],                           # ""|"passed"|"defeated" (Timeline Floor stage)
            "floor_senate": floor["senate"],                         # ""|"passed"|"defeated" (Timeline Floor stage)
            "last_committee": position["last_committee"],
            "referral_count": position["referral_count"],
            "latest_vote": _latest_vote(rows),                       # {tally, location, date}
            "upcoming": upcoming,                                    # [{date, committee}] (empty off-season)
            "last_action_date": rows[-1]["date"] if rows else "",
            "history": [{"action": r["action"], "date": r["date"]} for r in rows],  # UI doesn't need refids
            "data_as_of_utc": now_utc,                               # trust: freshness
            "source": "LIS",                                         # trust: provenance
        })

    # 5) COMPLETENESS (the top trust signal, free).
    history_bills = set(hist_by_bill)
    completeness = {
        "universe_count": len(universe_bills),
        "records_written": len(records),
        "history_bills": len(history_bills),
        "prefiled_no_history": len(universe_bills - history_bills),
        "in_history_not_in_universe": sorted(history_bills - universe_bills),  # should be empty
        "skipped_malformed_universe": skipped_universe,
        # Unparseable DOCKET dates as a RATE with its explicit denominator (Standard #7), not a bare
        # count — so a format change reads as a rising fraction regardless of docket size.
        "docket_unparseable_dates": docket_unparseable,
        "docket_rows_total": docket_rows_total,
        "docket_unparseable_rate": round(docket_unparseable / docket_rows_total, 4) if docket_rows_total else 0.0,
        # BILLS.CSV bulk-join coverage (trust: did the patron/outcome enrichment actually reach the bills?)
        "bills_meta_rows": bills_meta_rows,
        "bills_skipped_no_bill": bills_skipped_no_bill,   # malformed BILLS.CSV rows (no bill id), counted
        "outcome_structural": outcome_structural,
        "outcome_keyword_fallback": outcome_keyword,
        "patron_present": patron_present,
        "patron_missing": len(records) - patron_present,
        # Coverage of the RICHER chief-patron source (universe full name vs BILLS.CSV surname). Steady ≈
        # records_written; a drop means LIS stopped carrying Patrons on the list endpoint and we fell back
        # to surnames (a display regression, not a data loss — surfaced, per Standard #7).
        "patron_fullname_universe": patron_fullname_universe,
        "patron_fullname_universe_rate": round(patron_fullname_universe / len(records), 4) if records else 0.0,
        # ── LIS-INTERNAL consistency observation (NOT an accuracy metric — re-aimed 2026-07-25) ──────────
        # Among bills LIS gives structural flags for, how often does LIS's own status STRING disagree with
        # LIS's own FLAGS? We publish the flag (the oracle), so a disagreement here does NOT impeach our
        # output — it reports that LIS's two surfaces disagree with each other. On 2026-07-25 this read
        # 12.2% (443/3,633: LIS batch-marked interim carryover in the flags and left the strings alone) and
        # tripped a RED accuracy ring while every published value was correct. It is deliberately no longer
        # an alarm; `outcome_impeached` below is the accuracy-bearing number.
        "outcome_keyword_mismatches": len(outcome_mismatches),
        "outcome_keyword_mismatch_rate": round(len(outcome_mismatches) / outcome_structural, 4) if outcome_structural else 0.0,
        "outcome_mismatch_sample": sorted(outcome_mismatches)[:10],
        # ── The ACCURACY-bearing numbers (what the trust surface must key on) ────────────────────────────
        # impeached = we published a value the authoritative source contradicts. Structurally 0 here: every
        # flagged bill publishes the flag itself, so our value cannot disagree with the oracle. Emitted
        # explicitly (rather than left implicit) so the surface reads a VERDICT, not a raw disagreement rate.
        "outcome_impeached": 0,
        # UNVERIFIED = we published a text-derived outcome that NO oracle confirms (flagless bills). This is
        # the population fail-closed doctrine says to disclose — and the one nothing alarmed on before.
        "outcome_unverified": outcome_keyword,
        "outcome_unverified_rate": round(outcome_keyword / len(records), 4) if records else 0.0,
        "outcome_unverified_sample": sorted(unverified_bills)[:10],
        # Floor-passage coverage + self-calibrating reconciliation (Timeline Floor stages). The mismatch
        # rate is the share of fully-passed BILLS not showing both floor passages — a drift signal on LIS's
        # "passed House/Senate" vocabulary; steady ≈ 0 on 2026 data.
        "floor_passage_house_bills": floor_house_bills,
        "floor_passage_senate_bills": floor_senate_bills,
        "floor_passage_both_expected": floor_both_expected,
        "floor_passage_both_missing": floor_both_missing,
        "floor_passage_reconcile_rate": round(floor_both_missing / floor_both_expected, 4) if floor_both_expected else 0.0,
        "checked_at_utc": now_utc,
    }
    # Self-calibrating check must ALERT, not just sit in the JSON (Standard #4; CodeRabbit #191). Steady
    # state is 0 (validated 1157/1157); >1% of fully-passed bills missing a floor passage means LIS drifted
    # its "passed House/Senate" action vocabulary and the Timeline's Floor stages are silently under-counting.
    if floor_both_expected and (floor_both_missing / floor_both_expected) > 0.01:
        _alert("WARN", "DATA_ANOMALY",
               f"floor-passage reconcile drift: {floor_both_missing}/{floor_both_expected} fully-passed "
               f"bills lack both floor passages ({100 * floor_both_missing / floor_both_expected:.1f}%; "
               f"steady ≈ 0). LIS's floor-passage vocabulary may have changed — check _PASS_HOUSE_RE / "
               f"_PASS_SENATE_RE against current HISTORY actions.")
    return records, completeness


def write_bill_tracker(records, completeness):
    """Write records + a completeness summary to the Bill_Tracker tab (create if missing).
    Resizes the grid first — gspread.update does NOT auto-expand and errors past the grid.

    RETURNS `(prior_unverified, sheet)`:
      * `prior_unverified`, `prior_universe` — last cycle's counts (read from T1 *before* the overwrite), or
        None when there is no usable prior payload. The caller uses it as the baseline for the
        unverified-population delta guard — a fixed threshold can't work there (the population is
        legitimately large in-session, ~0 off-season). None means "no baseline", and the caller then
        declines to alarm rather than inventing a comparison.
      * `sheet` — the already-authorized workbook handle, so the end-of-cycle Metrics_History flush (W0d)
        reuses this connection instead of re-authenticating."""
    creds_json = os.environ.get("GCP_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GCP_CREDENTIALS not set")
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sheet = gc.open_by_key(SPREADSHEET_ID)

    # House Floor / Senate Floor are APPENDED (cols Q,R) so the existing A..P column indices the front
    # end reads stay stable; the completeness summary moves right (T1) to stay clear of the widened data.
    # Values: "passed" (cleared that floor) | "defeated" (reached that floor, voted down) | "" (no floor event).
    header = ["Bill", "Title", "Status (LIS)", "Outcome", "Patron", "Patron ID", "Chamber",
              "Crossed Over", "Last Committee", "Referrals", "Last Action", "Latest Vote (JSON)",
              "Upcoming (JSON)", "History (JSON)", "Data As Of (UTC)", "Source",
              "House Floor", "Senate Floor", "Outcome Origin"]
    rows = [header] + [[
        r["bill"], r["title"], r["status_lis"], r["outcome"], r["patron"], r["patron_id"], r["chamber"],
        "yes" if r["crossed_over"] else "no", r["last_committee"], r["referral_count"], r["last_action_date"],
        json.dumps(r["latest_vote"], ensure_ascii=False), json.dumps(r["upcoming"], ensure_ascii=False),
        json.dumps(r["history"], ensure_ascii=False), r["data_as_of_utc"], r["source"],
        r["floor_house"], r["floor_senate"], r["outcome_origin"],
    ] for r in records]
    # 19 data cols (A..S — "Outcome Origin" took the former empty spacer at S, so every A..R index the
    # front end reads is unchanged); the completeness summary still lives at T1 (col 20); the cadence
    # last-run marker (U1, col 21, guardrail #5 — this worker's OWN throttle clock) sits clear of the data.
    completeness_cell, need_rows, need_cols = "T1", len(rows) + 50, 21

    try:
        ws = sheet.worksheet(BILL_TRACKER_TAB)
        if ws.row_count < need_rows or ws.col_count < need_cols:   # grow to fit (update won't auto-expand)
            ws.resize(rows=max(ws.row_count, need_rows), cols=max(ws.col_count, need_cols))
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=BILL_TRACKER_TAB, rows=need_rows, cols=need_cols)

    # Read the PRIOR completeness payload before clearing — this is the only moment last cycle's numbers
    # are still on the sheet. Wrapped: a missing/garbled prior payload must never block today's write.
    prior_unverified = None
    prior_universe = None
    try:
        _raw_prior = ws.acell(completeness_cell).value
        if _raw_prior:
            _prior = json.loads(_raw_prior)
            _pv = _prior.get("outcome_unverified")
            if isinstance(_pv, int):
                prior_unverified = _pv
            _pu = _prior.get("universe_count")
            if isinstance(_pu, int):
                prior_universe = _pu
    except (gspread.exceptions.APIError, ValueError, TypeError, AttributeError) as _prior_err:
        # Categorized + visible (Standard #4) — never a bare except, never silent. No baseline this cycle.
        print(f"ℹ️  [BILL_TRACKER] no usable prior completeness payload ({type(_prior_err).__name__}: "
              f"{_prior_err}) — the unverified-delta guard has no baseline this cycle and will not alarm.")

    # Write-time invariant on the new provenance column, mirroring the calendar worker's I2 and the lesson
    # of audit #176 (a producer emitted an Origin the validator didn't know, and a false alarm fired
    # forever). Here the failure would be quieter and worse: an unregistered origin means the trust surface
    # cannot tell whether those rows are oracle-confirmed. Counted + alerted, never silently written.
    _bad_origins = {}
    for _r in records:
        _o = _r.get("outcome_origin")
        if _o not in OUTCOME_ORIGINS:
            _bad_origins[_o] = _bad_origins.get(_o, 0) + 1
    if _bad_origins:
        _alert("CRITICAL", "DATA_ANOMALY",
               f"unregistered outcome_origin value(s) {_bad_origins} across {sum(_bad_origins.values())} "
               f"of {len(records)} bills — the trust surface cannot classify those rows as verified or not. "
               f"Register the value in OUTCOME_ORIGINS or fix the producer.")

    ws.clear()
    # One batched write: rows + the completeness summary (front-end trust header) + the guardrail-#5 last-run
    # marker (U1). U1 is written ONLY on a successful cycle (we only reach here on success), so a failed run
    # leaves the prior U1 → the next scheduled tick sees a stale marker and is eligible to run (fail-toward-
    # freshness). Same write-on-success discipline as the calendar worker's AA1/AC1.
    ws.batch_update([
        {"range": "A1", "values": rows},
        {"range": completeness_cell, "values": [[json.dumps(completeness, ensure_ascii=False)]]},
        {"range": cadence.BILL_LAST_RUN_CELL,
         "values": [[datetime.datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")]]},
    ])
    return prior_unverified, prior_universe, sheet


def run_bill_tracker():
    try:
        http_session = get_armored_session()   # counted/guarded (guardrail #4)

        # Session derived at runtime from the Session API (Standard #5 — never hardcoded).
        info, ok, _auth_failed = get_active_session_info(http_session)
        if not ok or not info or not info.get("code"):
            _alert("CRITICAL", "API_FAILURE",
                   "could not derive the active session; skipped (kept last-known-good).")
            return
        session_code = str(info["code"])

        # LIS-authorization gate (ban-safe): never pull data for an unauthorized session. A-1: auto-follow
        # the active session LIS declares (probe-verified in session_follow_gate) instead of a hard annual
        # halt; historical sessions stay frozen; halts only if LIS actually refuses the key. Shares the S2
        # probe cache with the calendar worker (the probe fires once across both).
        proceed, halt_reason = session_follow_gate(session_code, http_session)
        if not proceed:
            _alert("CRITICAL", "API_FAILURE", f"LIS authorization halt — session {session_code}: {halt_reason}")
            return

        records, completeness = build_bill_records(http_session, session_code)
        prior_unverified, prior_universe, _sheet = write_bill_tracker(records, completeness)
        crossed = sum(1 for r in records if r["crossed_over"])
        print(f"✅ Bill_Tracker written: {len(records)} bills "
              f"({completeness['prefiled_no_history']} prefiled-no-history, {crossed} crossed over, "
              f"{completeness['patron_present']} with patron). "
              f"Completeness: {completeness['records_written']}/{completeness['universe_count']} of the "
              f"universe; {len(completeness['in_history_not_in_universe'])} in-history-not-in-universe; "
              f"{completeness['skipped_malformed_universe']} skipped. "
              f"Outcome: {completeness['outcome_structural']} structural / "
              f"{completeness['outcome_keyword_fallback']} keyword-fallback; "
              f"keyword-vs-structural mismatch {completeness['outcome_keyword_mismatch_rate']:.2%}.")
        if completeness["in_history_not_in_universe"]:
            _alert("WARN", "DATA_ANOMALY",
                   f"{len(completeness['in_history_not_in_universe'])} bills in HISTORY but absent from "
                   f"the universe: {completeness['in_history_not_in_universe'][:10]}")
        # ── RE-AIMED 2026-07-25 (docs/architecture/source_precedence, incident_counter §3c) ──────────────
        # The keyword-vs-structural mismatch RATE is no longer an alarm. It measures LIS's INTERNAL
        # consistency (its status STRING vs its own FLAGS), not our accuracy: on a mismatch we publish the
        # FLAG — the oracle — so our output is not impeached. Alarming on it produced a RED accuracy ring on
        # 2026-07-25 (12.2%, 443/3,633) when LIS batch-marked interim carryover in the flags without touching
        # the strings, while every value we published was correct. It stays VISIBLE as an upstream-drift
        # observation (printed + in the payload); it no longer claims our data is wrong.
        if completeness["outcome_keyword_mismatch_rate"] > 0.01:
            print(f"ℹ️  [BILL_TRACKER/upstream-observation] LIS status-string vs LIS-flag disagreement "
                  f"{completeness['outcome_keyword_mismatch_rate']:.2%} "
                  f"({completeness['outcome_keyword_mismatches']} of {completeness['outcome_structural']}, "
                  f"e.g. {completeness['outcome_mismatch_sample']}). We publish the FLAG, so no published "
                  f"value is impeached — this reports LIS disagreeing with itself, not a defect in our data.")
        # What DOES deserve an alarm: the genuinely UNVERIFIED population — bills with no structural flag,
        # where we publish a text-derived outcome NO oracle confirms (fail-closed doctrine). The rule itself
        # lives in `unverified_jump_is_alarming` (pure + golden-tested); `prior_unverified` is last cycle's
        # value, read from the sheet before the overwrite.
        if unverified_jump_is_alarming(prior_unverified, completeness["outcome_unverified"],
                                       prior_universe, completeness.get("universe_count")):
            _alert("WARN", "DATA_ANOMALY",
                   f"UNVERIFIED outcomes jumped {prior_unverified} → {completeness['outcome_unverified']} "
                   f"of {completeness['records_written']} bills "
                   f"(e.g. {completeness['outcome_unverified_sample']}) — these publish a text-derived "
                   f"outcome no structural flag confirms. A jump means LIS stopped emitting flags for a "
                   f"population it used to flag; check BILLS.CSV coverage.")
        # BILLS.CSV TOTAL failure (fetch empty or bill column undetected) — distinct from partial
        # under-coverage: every bill lost its patron + structural outcome this cycle (CodeRabbit #162).
        if completeness["bills_meta_rows"] == 0 and completeness["records_written"] > 0:
            _alert("WARN", "API_FAILURE",
                   "BILLS.CSV fetched/parsed to 0 rows — patron + structural outcome UNAVAILABLE this "
                   "cycle; fell back to keyword-only outcome + empty patron (spine still written).")
        # Partial under-coverage (BILLS.CSV present but didn't cover the universe): a different signal.
        elif completeness["patron_missing"] > 0.05 * max(1, completeness["records_written"]):
            _alert("WARN", "DATA_ANOMALY",
                   f"patron missing for {completeness['patron_missing']}/{completeness['records_written']} "
                   f"bills — BILLS.CSV partially under-covered the universe (schema/join issue).")
        # Flush the cycle's alerts + heartbeat LAST, once every check above has had its say (W0d). Placed
        # here rather than inside write_bill_tracker because the alert checks run AFTER the write.
        flush_alerts_to_metrics_history(_sheet, completeness)
    except Exception as e:
        _alert("CRITICAL", "API_FAILURE", f"bill_tracker cycle failed: {type(e).__name__}: {e}")
        # A cycle that DIED is exactly when the Health tab most needs to say so. Pre-push audit #11: the
        # recovery-carrying side effect must not sit behind a gate that can stay permanently true — an early
        # failure (before the sheet is opened) would otherwise be permanently unable to report itself, which
        # is the silent-death case. So if no connection exists yet, open one; the whole path is wrapped, and
        # `raise` still fires, so a failure to report can never mask the original failure.
        _s = locals().get("_sheet")
        try:
            if _s is None:
                _creds = os.environ.get("GCP_CREDENTIALS")
                if _creds:
                    _gc = gspread.authorize(Credentials.from_service_account_info(
                        json.loads(_creds), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
                    _s = _gc.open_by_key(SPREADSHEET_ID)
            if _s is not None:
                flush_alerts_to_metrics_history(_s)
        except Exception as _flush_err:
            print(f"⚠️ [BILL_TRACKER] could not report the cycle failure to Metrics_History: {_flush_err}")
        raise


def _cadence_should_run():
    """Guardrail #5 for the bill worker: consult the SHARED meeting-window signal (Sheet1!AC1, maintained by
    the calendar worker) plus this worker's OWN last-run marker (Bill_Tracker!U1) to decide fast vs slow.

    Returns True to PROCEED, False to SKIP. Reads Sheets only — ZERO LIS on a skip. FAILS OPEN (returns True)
    on ANY error, and on a missing/unreadable AC1 (empty state → EMPTY tier) or missing U1 (→ no marker →
    run): a cadence read problem must never silence the worker (Standard #4, fail-toward-freshness). Pure
    decision logic lives in cadence.py (unit-tested); this is just the I/O wrapper.
    """
    try:
        creds_json = os.environ.get("GCP_CREDENTIALS")
        if not creds_json:
            return True   # no creds here == a local/dev invocation; let the normal path handle auth
        gc = gspread.authorize(Credentials.from_service_account_info(
            json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
        sheet = gc.open_by_key(SPREADSHEET_ID)
        raw_state = sheet.worksheet("Sheet1").acell(cadence.CADENCE_STATE_CELL).value
        last_raw = None
        try:
            last_raw = sheet.worksheet(BILL_TRACKER_TAB).acell(cadence.BILL_LAST_RUN_CELL).value
        except gspread.exceptions.WorksheetNotFound:
            last_raw = None   # tab not created yet (first deploy) → no marker → run (expected, benign)
        except Exception as _u1_err:
            # A REAL Sheets/API error reading U1 (not just first-deploy): don't swallow it silently (Qodo
            # #198). Surface it, then still default to "no marker → run" (fail-toward-freshness).
            print(f"⚠️ Cadence: couldn't read {BILL_TRACKER_TAB}!{cadence.BILL_LAST_RUN_CELL} "
                  f"({type(_u1_err).__name__}: {_u1_err}) — treating as no marker (will run).")
            last_raw = None
        run, tier, why = cadence.decide(
            raw_state, datetime.datetime.now(pytz.utc),
            datetime.datetime.now(pytz.timezone("America/New_York")),
            cadence.BILL_TIER_FLOORS, last_run_utc=cadence.parse_marker(last_raw))
        print(f"⏱️ Cadence gate (guardrail #5): {why}")
        return run
    except Exception as e:
        # Fail OPEN (run), but ROUTE the error through the categorized alerter — not just print (Qodo #198):
        # a recurring gate failure is an operational signal, not a transient to swallow.
        _alert("WARN", "API_FAILURE", f"cadence gate error ({type(e).__name__}: {e}) — running this cycle "
               f"(fail-open). Investigate if it persists.")
        return True


def _scheduled_gate():
    """Ban-safety for SCHEDULED runs only (mirrors calendar_worker.py __main__; keep in sync). Returns
    True if the cycle should PROCEED, False to SKIP — the caller, not this helper, exits (Gemini #163:
    no sys.exit inside a helper → unit-testable). Manual dispatch always proceeds (returns True
    immediately). Two ban-safety behaviours for scheduled runs:
      - QUIET HOURS: skip 11pm–6am ET — no GA business overnight and the bill data is static then, so a
        scheduled hit is pure, pointless LIS exposure → return False.
      - JITTER (guardrail #2): a fixed cron fires at the same wall-clock instant every cycle (a needless
        metronome signature); delay a small random amount to decorrelate from the tick → return True.

    Heuristic config (Standard #1):
      - ASSUMES `JITTER_MAX_SECONDS` is a non-negative int (default 180); `GITHUB_EVENT_NAME` is set by
        the Actions runner ('schedule' vs 'workflow_dispatch').
      - BREAKS if `JITTER_MAX_SECONDS` is malformed → caught, defaulted to 180, AND surfaced as a WARN
        (never a silent fallback). A missing `GITHUB_EVENT_NAME` (e.g. a local run) reads as non-schedule
        → proceeds immediately, the safe default.
      - RUNTIME CHECK: the malformed-config WARN above; quiet-hours/jitter decisions are printed every
        scheduled run so the log is self-describing. See docs/knowledge/lis_api_safety.md.
    """
    if os.environ.get("GITHUB_EVENT_NAME", "") != "schedule":
        return True
    quiet_start_et, quiet_end_et = 23, 6
    et_hour = datetime.datetime.now(pytz.timezone("America/New_York")).hour
    in_quiet = ((et_hour >= quiet_start_et or et_hour < quiet_end_et)   # midnight-spanning window
                if quiet_start_et > quiet_end_et else (quiet_start_et <= et_hour < quiet_end_et))
    if in_quiet:
        print(f"😴 Quiet hours ({quiet_start_et}:00–{quiet_end_et}:00 ET): ET hour={et_hour}; "
              f"scheduled run skipped (no GA business overnight; manual dispatch bypasses).")
        return False
    # LIS-safety guardrail #5: activity-correlated cadence (mirrors calendar_worker __main__; keep in sync).
    # The bill worker fires on a fast (hourly) cron and self-throttles here — hourly when the legislature is
    # active (a meeting on the SHARED calendar signal, Sheet1!AC1), ~6h when the forward calendar is empty.
    # ZERO LIS on a skip. Checked AFTER quiet hours (cheapest first) and BEFORE jitter (never sleep to skip).
    if not _cadence_should_run():
        return False
    raw_jitter = os.environ.get("JITTER_MAX_SECONDS", "180")
    try:
        jitter_max = max(0, int(raw_jitter))
    except (ValueError, TypeError):
        jitter_max = 180   # a malformed env var must never crash the run — but it must NOT be silent
        _alert("WARN", "UNKNOWN", f"JITTER_MAX_SECONDS malformed ({raw_jitter!r}); using default 180s.")
    if jitter_max:
        jitter = random.randint(0, jitter_max)
        print(f"🎲 Jitter (guardrail #2): sleeping {jitter}s (of max {jitter_max}s) before the "
              f"scheduled cycle — decorrelate from the cron tick.")
        time.sleep(jitter)
    return True


if __name__ == "__main__":
    if _scheduled_gate():       # quiet-hours + jitter for scheduled runs (always True for manual dispatch)
        run_bill_tracker()      # else: scheduled run skipped (quiet hours) — clean exit 0
