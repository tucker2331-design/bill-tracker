#!/usr/bin/env python3
"""Accuracy Sentinel — the continuous, SESSION-AGNOSTIC guardian of calendar
accuracy (Standard #2 bank-grade + #8 zero-maintenance).

A one-time audit can't protect next session's NEW data. This runs the SAME
accuracy metric the X-Ray's Section 9 uses, against the LIVE sheet, on a schedule,
and FAILS LOUDLY on any regression -- so 2027's data can't silently lose the
accuracy 2026 reached. It reads the sheet directly (whatever session the worker
wrote), extracts the REAL ``classify_action``/``normalize_time`` from
pages/ray2.py (so it can never drift from production semantics), and checks four
invariants:

  1. SECTION 9   meeting-classified rows WITHOUT a time            == 0   (the goal)
  2. UNCLASSIFIED real legislative rows the classifier can't place == 0   (the goal's 2nd half)
  3. BALANCE     rows_in == rows_written + every counted drop            == exact  (row-conservation guard,
                 lesson #75: "Section 9 = 0 on a 277-row sheet" -- a collapsed sheet must FAIL, not pass.
                 REPLACED the old `>= MIN_ROWS` floor 2026-07-31: that threshold depended on how busy the
                 session was and was false-alarming on a COMPLETE 3,615-row special session. The identity
                 needs no constant and is strictly stronger -- a truncation leaving 6,000 rows passed the
                 floor and fails this.)
  4. DERIVED     flagged assumed-time rows <= DERIVED_MAX                 (over-derivation guard, G2)

System rows (SYSTEM_ALERT / SYSTEM_METRICS / Committee "System Status") are
EXCLUDED -- they are the worker's own diagnostics, not legislative actions.

Exit 0 = all invariants hold; non-zero = regression (the scheduled workflow then
fails and alerts). No secrets -- reads the live sheet via the public gviz CSV.
Usage: python3 tools/verification/accuracy_sentinel.py [--derived-max 25]
"""
import sys
import io
import os
import csv
import re
import ast
import argparse
import time
import json
import urllib.request

# Resolve ray2.py relative to THIS file, not the cwd, so the sentinel runs from
# any working directory (Gemini #106).
RAY = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pages", "ray2.py"))
SHEET = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
# Columns the accuracy metric depends on; a rename upstream must FAIL the sentinel,
# not let it silently pass (a missing column would read "" and classify benign).
REQUIRED_COLUMNS = ("Outcome", "Time", "LegEventRoute", "Origin", "Source", "RefidClass", "ScheduleClass")
# Floor on the POSITIVE health metric (structural-resolution rate = non-blank
# LegEventRoute / legislative rows). Baseline ~83.6% (2026). This is the answer to
# "homework grading" (Gemini review): a ceiling on BAD outcomes is gameable —
# if 2027 LIS breaks its schema, the worker gracefully routes everything to the
# fallback, meeting_unsourced/Section-9 stay 0, and a bad-outcome ceiling reports
# PASS. But the structural router goes BLANK en masse, so the resolution rate
# COLLAPSES — which IS the failure, un-gameable. Below this floor = CRITICAL.
MIN_STRUCTURAL_RESOLUTION = 0.70


def _get(url, tries=4):
    """Fetch text with retries/backoff; always closes the response (no fd leak)."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def _notify_slack(text):
    """Best-effort Slack post when the sentinel FAILS. DORMANT until the
    SLACK_WEBHOOK_URL env var (a GitHub Actions secret) is set. stdlib-only
    (urllib + json) to keep the sentinel dependency- and secret-free by default.
    NEVER raises — a Slack outage must not change the sentinel's exit code (the
    real escalation is the non-zero exit → GitHub Actions failure email)."""
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url or not text:  # no webhook, or nothing to say -> don't post an empty msg
        return
    try:
        data = json.dumps({"text": str(text)[:3000]}).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8):  # close the response (no fd leak), matches _get
            pass
    except Exception as e:
        print(f"⚠️ Slack notify failed (non-fatal): {e}")


def _load_ray2_semantics():
    """classify_action is now IMPORTED from structural_router (PR-hardening1a — the single source
    of truth shared by the worker, X-Ray, and this sentinel; no more AST-extraction drift risk).
    normalize_time + PLACEHOLDER_TIMES are display helpers still defined in ray2.py, so they stay
    AST-extracted (so the sentinel never drifts from the X-Ray's time-presence semantics)."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from structural_router import classify_action  # canonical classifier
    with open(RAY, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    consts = {"PLACEHOLDER_TIMES", "NON_CONCRETE_LIS_TIMES"}  # PR-C8.2: verb-pattern lists deleted
    funcs = {"normalize_time"}  # PR-hardening1a: classify_action now imported, not extracted

    def _defines_const(node):
        targets = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AnnAssign) else [])
        return any(isinstance(t, ast.Name) and t.id in consts for t in targets)

    body = [n for n in tree.body
            if ((isinstance(n, (ast.Assign, ast.AnnAssign)) and _defines_const(n))
                or (isinstance(n, ast.FunctionDef) and n.name in funcs))]
    ns = {"re": re}
    exec(compile(ast.Module(body, []), "ray2-extract", "exec", dont_inherit=True), ns)
    return classify_action, ns["normalize_time"], ns["PLACEHOLDER_TIMES"]


def _is_system_row(source):
    # STRUCTURAL flag the worker writes on its own diagnostic rows (Source="SYSTEM",
    # Origin="system_alert"/"system_metrics") — NOT the "System Status" committee
    # TEXT (Standard #3: data-driven, not text-driven; Gemini review).
    return str(source).strip().upper() == "SYSTEM"


# ── days-clean ledger (W1.4) ────────────────────────────────────────────────────────────────────────────
# One of the three authorised WRITERS of the incident ledger. FAIL-OPEN by construction: this guard must fail
# on DATA, never on bookkeeping, so an unavailable ledger can never change its verdict.
_LEDGER_DETECTOR = "accuracy_sentinel"


def _ledger_api():
    """Import the ledger REGARDLESS of how this guard was invoked.

    The workflows run `python3 tools/<dir>/<guard>.py`, which puts that subdirectory on `sys.path` — NOT the
    repo root — so a bare `from tools.incident_log.log import …` raises ModuleNotFoundError. The fail-open
    handlers below would have swallowed it and the ledger would have been silently non-functional forever:
    every guard reporting success at recording nothing. Verified by probe, not assumed; regression-tested in
    test_incident_log_wiring.py.
    """
    import os
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.incident_log.log import close_incident, record_incident
    return record_incident, close_incident


def _ledger(cls, summary):
    """Open an incident. Deduped inside the ledger: a multi-cycle outage stays ONE incident (W1.2)."""
    try:
        record_incident, _ = _ledger_api()
        record_incident(cls, summary, _LEDGER_DETECTOR)
    except Exception as e:
        print(f"⚠️ [accuracy_sentinel] could not record the incident (non-fatal): {e}")


def _ledger_close(cls):
    """Close this guard's own open incident — the recovery signal."""
    try:
        _, close_incident = _ledger_api()
        close_incident(cls, _LEDGER_DETECTOR)
    except Exception as e:
        print(f"⚠️ [accuracy_sentinel] could not close the incident (non-fatal): {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--derived-max", type=int, default=25, help="over-derivation guard (G2)")
    ap.add_argument("--section9-max", type=int, default=0)
    ap.add_argument("--unclassified-max", type=int, default=0)
    ap.add_argument("--unconfirmed-max", type=int, default=150,
                    help="ABSOLUTE backstop for the surfaced fail-safe lane. PR-hardening1b: the "
                         "sensitive, self-calibrating spike detection is now the WORKER's Y3 "
                         "rolling-baseline alert (delta vs the prior cycle — the sentinel is "
                         "stateless and cannot do rolling); this absolute gate remains as the "
                         "catastrophic backstop, mirroring the breaker's abs floor alongside its delta.")
    ap.add_argument("--min-resolution", type=float, default=MIN_STRUCTURAL_RESOLUTION,
                    help="floor on the ORIGINAL router (LegEventRoute) reach (anti-homework-grading)")
    ap.add_argument("--min-coverage", type=float, default=0.97,
                    help="floor on TOTAL structural coverage (1 - unconfirmed/rows); baseline ~99.8%% (PR-C8)")
    ap.add_argument("--staleness-max-business-days", type=int, default=2,
                    help="during an ACTIVE session, fail if the newest action Date is older than this many "
                         "business days (data-FLOW guard, Gemini SRE C)")
    args = ap.parse_args()

    classify_action, normalize_time, placeholder = _load_ray2_semantics()
    try:
        raw = _get(f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet=Sheet1")
    except Exception as e:
        print(f"🚨 SENTINEL FAIL — could not fetch the live sheet after retries: {e}")
        return 1
    rows = list(csv.reader(io.StringIO(raw)))
    # An empty/unreadable sheet is itself a failure to catch, not a crash.
    if len(rows) < 2:
        print(f"🚨 SENTINEL FAIL — sheet returned {len(rows)} rows (empty/unreadable). Cannot verify.")
        return 1
    ci = {c: i for i, c in enumerate(rows[0])}
    # Schema-drift guard: a renamed/removed column would read "" everywhere and
    # let the metric silently pass (Section 9 falsely 0). Require the columns the
    # accuracy metric depends on (Gemini #106).
    _missing = [c for c in REQUIRED_COLUMNS if c not in ci]
    if _missing:
        print(f"🚨 SENTINEL FAIL — sheet is missing required column(s) {_missing}; "
              f"schema may have changed. Cannot trust the accuracy metric.")
        return 1

    def cell(r, c):
        i = ci.get(c, -1)
        return r[i] if 0 <= i < len(r) else ""

    total = meeting = mwt = unclass = unconfirmed = derived = system = routed = executive = 0
    # Rows the router COULD resolve: history-derived (Source=CSV). Schedule/docket rows describe meetings
    # that have not happened, so a blank route on them is correct, not a miss.
    routable = 0
    # Meetings that have not happened yet and legitimately carry no time. Tracked apart from `mwt` so the
    # gate judges only actions that HAVE happened, while the count stays visible rather than vanishing.
    mwt_future = 0
    # The worker's SYSTEM_METRICS payload, if present. `None` means "we could not read the worker's own
    # accounting" — which the BALANCE gate treats as a FAILURE, not as an all-clear (fail closed: the
    # absence of evidence that rows survived is not evidence that they did).
    metrics = None
    s9_rows, uc_rows, unconf_rows = [], [], []
    s9_future_rows = []
    _TODAY = time.strftime("%Y-%m-%d", time.gmtime())   # UTC, matching the sheet's date strings
    latest_date = ""  # newest action Date seen (ISO sorts lexically) — for the staleness gate
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        if _is_system_row(cell(r, "Source")):
            system += 1
            # The worker's own per-cycle counters ride in the SYSTEM_METRICS row's Outcome as JSON.
            # They carry the row-conservation terms the BALANCE invariant below needs.
            if str(cell(r, "Origin")).strip() == "system_metrics":
                try:
                    metrics = json.loads(cell(r, "Outcome"))
                except (ValueError, TypeError):
                    metrics = None   # malformed → BALANCE reports "unavailable" and fails, never passes
            continue
        total += 1
        _d = cell(r, "Date").strip()
        if len(_d) == 10 and _d[4] == "-" and _d > latest_date:  # YYYY-MM-DD, lexical max
            latest_date = _d
        # ROUTER RESOLUTION NEEDS THE RIGHT DENOMINATOR (2026-07-30, and Standard #7 verbatim: "your metric
        # must have a denominator"). It was routed/ALL rows, which includes SCHEDULE and DOCKET entries --
        # meetings that have not happened, so there is no event to route and there never will be until they
        # do. Measured on the live sheet: Source=CSV routes 862/863 = 99.9%, while api_schedule (2,661 rows)
        # and DOCKET (1,061) route 0/… by nature. Dividing by everything gave 23.9%.
        #
        # That is worse than a false alarm, it is a BLIND one: sitting permanently under the 70% gate, the
        # number could not move if the router genuinely collapsed. On the honest denominator a total failure
        # reads 99.9% -> 0%. Narrowing the denominator makes this guard MORE sensitive, not softer -- which
        # is the only reason it is allowed to change at all (the doctrine forbids softening an alarm).
        _routable = str(cell(r, "Source")).strip().upper() == "CSV"
        if _routable:
            routable += 1
            if str(cell(r, "LegEventRoute")).strip():
                routed += 1  # structurally resolved by the router (non-blank route)
        cls = classify_action(cell(r, "Outcome"), cell(r, "LegEventRoute"), cell(r, "RefidClass"), cell(r, "ScheduleClass"))
        has_time = normalize_time(cell(r, "Time")) not in placeholder
        if cell(r, "Origin") == "derived_standing":
            derived += 1
        if cls == "meeting":
            meeting += 1
            if not has_time:
                # FUTURE MEETINGS ARE NOT SECTION-9 BUGS (2026-07-30). The rule in CLAUDE.md is precise about
                # this and the check was not: "every action that HAPPENED in a meeting must show the time of
                # that meeting". A meeting scheduled for November, read in July, has no time because LIS has
                # not set one -- that is the truth, not a missing value we failed to capture.
                #
                # Conflating the two made the sentinel FAIL on 6 rows that were all correct ("Annual Meeting
                # of Senate Finance and Appropriations Committee", 2026-11-19/20, status Scheduled), which
                # opens an incident and resets the days-clean clock for a non-defect. A trust counter that
                # resets on correct data is worse than no counter.
                #
                # Counted separately, never dropped (Standard #4): a future meeting that STAYS time-less
                # after its date passes becomes a real Section-9 row on the next run, automatically.
                if _d and len(_d) == 10 and _d > _TODAY:
                    mwt_future += 1
                    if len(s9_future_rows) < 15:
                        s9_future_rows.append((cell(r, "Bill"), _d, cell(r, "Committee"), cell(r, "Outcome")[:50]))
                else:
                    mwt += 1
                    if len(s9_rows) < 15:
                        s9_rows.append((cell(r, "Bill"), cell(r, "Date"), cell(r, "Committee"), cell(r, "Outcome")[:50]))
        elif cls == "unclassified":
            unclass += 1
            if len(uc_rows) < 15:
                uc_rows.append((cell(r, "Bill"), cell(r, "Date"), cell(r, "Outcome")[:60]))
        elif cls == "unconfirmed":
            unconfirmed += 1
            if len(unconf_rows) < 15:
                unconf_rows.append((cell(r, "Bill"), cell(r, "Date"), cell(r, "Outcome")[:60]))
        elif cls == "executive":   # PR-C8.4b: action-required governor action, on the calendar, time-less by design
            executive += 1

    print(f"=== ACCURACY SENTINEL (live sheet, {total} legislative rows; {system} system rows excluded) ===")
    print(f"  meeting={meeting}  unclassified={unclass}  unconfirmed={unconfirmed}  executive={executive}  derived_standing={derived}")
    failed = []

    def gate(name, val, mx, examples):
        ok = val <= mx
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val} (max {mx})")
        if not ok:
            failed.append(name)
            for ex in (examples or []):
                print(f"        - {ex}")

    gate("SECTION 9 (meeting without time)", mwt, args.section9_max, s9_rows)
    if mwt_future:
        # Reported, never gated. These become real Section-9 rows automatically once their date passes.
        print(f"  [note] {mwt_future} FUTURE meeting(s) without a time — not yet due, excluded from the gate:")
        for ex in s9_future_rows[:5]:
            print(f"        - {ex}")
    gate("UNCLASSIFIED legislative rows", unclass, args.unclassified_max, uc_rows)
    gate("UNCONFIRMED (surfaced fail-safe lane)", unconfirmed, args.unconfirmed_max, unconf_rows)
    # ── BALANCE: the conservation identity that REPLACED the magic floor (2026-07-31) ──────────────
    # The old gate asked "are there >= 5,000 rows?" — a question whose answer depends on how busy the
    # session is, not on whether anything was lost. It was FALSE-ALARMING on this very sheet: 3,615 rows
    # is the complete 2026 special session (300 bills), and the guard called it a partial sheet.
    # Owner, verbatim: "you are just guessing based on one or two sessions worth of data and even if we
    # could use historical it's not enough because the past doesn't repeat itself."
    #
    # The ABC "Balance" question instead: can every row be ACCOUNTED for?
    #     rows_in == rows_written + placeholder_dups + key_dups + out_of_window
    # The worker computes this per cycle and publishes the residual. It is provably right on day 1 and
    # day 90, at ANY size, with NO constant to calibrate — and it is strictly STRONGER than the floor:
    # a truncation that still left 6,000 rows passed `>= 5000` and fails this.
    if metrics is None:
        print("  [FAIL] BALANCE (row conservation): SYSTEM_METRICS row absent or unparseable — "
              "the worker's own accounting could not be read")
        failed.append("BALANCE (worker accounting unreadable)")
    elif "balance_residual" not in metrics and "worker_version" not in metrics:
        # MIGRATION WINDOW, and it is identifiable rather than assumed: a worker that publishes the
        # counters also stamps `worker_version`. Neither key present => this sheet was written before the
        # change shipped, so there is nothing to reconcile yet. Reported, never silent — but not a gate
        # failure, because a guaranteed-red gate for a whole cron cycle is a gate people learn to ignore.
        print("  [note] BALANCE (row conservation): sheet predates the conservation counters — "
              "the next worker cycle publishes them; gate arms itself then")
    elif "balance_residual" not in metrics:
        # A CURRENT worker ran (it stamped its version) and still published no residual. That is a real
        # fault, not a migration artifact — an absent counter is not a zero one (audit #53).
        print(f"  [FAIL] BALANCE (row conservation): worker {metrics.get('worker_version')} published no "
              "`balance_residual` — the conservation counters did not run")
        failed.append("BALANCE (current worker published no counters)")
    else:
        residual = metrics.get("balance_residual", 0)
        rows_in = metrics.get("rows_final", 0) + residual + sum(
            metrics.get(k, 0) for k in ("dropped_placeholder_dup", "dropped_key_dup", "dropped_out_of_window"))
        bal_ok = residual == 0
        print(f"  [{'PASS' if bal_ok else 'FAIL'}] BALANCE (row conservation): {rows_in} in → "
              f"{metrics.get('rows_final', 0)} written + "
              f"{metrics.get('dropped_placeholder_dup', 0)} placeholder-dup + "
              f"{metrics.get('dropped_key_dup', 0)} key-dup + "
              f"{metrics.get('dropped_out_of_window', 0)} out-of-window; "
              f"unaccounted = {residual} (must be 0) — replaces the old --min-rows floor")
        if not bal_ok:
            failed.append("BALANCE (rows vanished between the pipeline and the sheet)")
    # EMPTY-SHEET guard retained, but as an identity rather than a guess: a sheet with zero legislative
    # rows is broken at any session size. This is the one thing the balance cannot catch — a pipeline that
    # correctly accounts for having produced nothing still balances.
    if total == 0:
        print("  [FAIL] NON-EMPTY: 0 legislative rows on the sheet")
        failed.append("NON-EMPTY (sheet carries no legislative rows)")
    gate("DERIVED volume (over-derivation guard)", derived, args.derived_max, None)
    # TWO complementary positive-health metrics (anti-homework-grading, Gemini #78):
    #  (a) ROUTER RESOLUTION = LegEventRoute / rows — how far the ORIGINAL structural router
    #      (route_event) reaches on its own. Baseline ~83.6%; a collapse = an LIS schema break.
    #  (b) STRUCTURAL COVERAGE = 1 - unconfirmed/rows — how much of the calendar is classified by
    #      ANY structural signal (route + RefidClass + ScheduleClass + skeleton) after PR-C8. This
    #      is the honest "we replaced the 16% text with structure" number (~99.8%); only the
    #      'unconfirmed' fail-safe lane is uncovered. (PR-C8.3: the headline the owner expected —
    #      the old "83.8%" was only metric (a) and undersold the structural work.)
    resolution = (routed / routable) if routable else 0.0
    res_ok = resolution >= args.min_resolution
    print(f"  [{'PASS' if res_ok else 'FAIL'}] ROUTER RESOLUTION (LegEventRoute): {resolution:.1%} (min {args.min_resolution:.0%}) "
          f"— un-gameable mass-degradation guard")
    if not res_ok:
        failed.append(f"ROUTER RESOLUTION collapsed to {resolution:.1%} (CRITICAL: possible LIS schema break — the router is falling through en masse)")
    coverage = ((total - unconfirmed) / total) if total else 0.0
    cov_ok = coverage >= args.min_coverage
    print(f"  [{'PASS' if cov_ok else 'FAIL'}] STRUCTURAL COVERAGE (any signal): {coverage:.2%} (min {args.min_coverage:.0%}) "
          f"— the 16% is now structural, not text; only the surfaced 'unconfirmed' lane is uncovered")
    if not cov_ok:
        failed.append(f"STRUCTURAL COVERAGE dropped to {coverage:.2%} (too many rows fell to the unconfirmed lane — new LIS structure?)")

    # STALENESS GATE (Gemini SRE C): the checks above verify data SHAPE, not data FLOW.
    # If LIS stops publishing (or the API returns empty) the worker preserves last-known-
    # good and every shape-check still passes — a silently frozen pipeline. So: ONLY while
    # the GA is actually in session (worker writes Sheet1!S1=ACTIVE via the API's IsActive),
    # fail if the newest action Date is more than N BUSINESS days old (weekend-aware, so a
    # Fri→Mon gap is not a false alarm). Off-session, S1=ADJOURNED and this stays silent.
    try:
        # &headers=0 so gviz returns the raw single cell rather than inferring it as a header (Gemini #138).
        _s1 = _get(f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet=Sheet1&range=S1&headers=0")
        session_flag = next((c.strip().strip('"') for c in _s1.replace("\n", ",").split(",") if c.strip().strip('"')), "")
    except Exception as _sf_err:
        session_flag = ""
        print(f"  [SKIP] STALENESS: could not read the S1 session flag ({_sf_err}); gate inactive this run.")
    if session_flag.upper() == "ACTIVE":
        import datetime as _dt
        try:
            _latest = _dt.date.fromisoformat(latest_date) if latest_date else None
        except ValueError:
            _latest = None
        if _latest is None:
            print(f"  [FAIL] STALENESS: session is ACTIVE but no parseable action Date (latest={latest_date!r}).")
            failed.append("STALENESS (active session, no parseable dated rows)")
        else:
            # "today" in EASTERN time — the sheet's Dates are ET. _dt.date.today() on the
            # GitHub runner is UTC, which in the ET evening is the NEXT day -> a false +1 in
            # the age (Gemini #138). zoneinfo is stdlib; fall back to a fixed EST offset if
            # the tz database isn't present.
            try:
                from zoneinfo import ZoneInfo
                _today = _dt.datetime.now(ZoneInfo("America/New_York")).date()
            except Exception:
                _today = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=-5))).date()
            biz_age = sum(1 for n in range(1, (_today - _latest).days + 1)
                          if (_latest + _dt.timedelta(days=n)).weekday() < 5)  # weekdays only
            stale_ok = biz_age <= args.staleness_max_business_days
            print(f"  [{'PASS' if stale_ok else 'FAIL'}] STALENESS (active session): newest action {latest_date} "
                  f"is {biz_age} business day(s) old (max {args.staleness_max_business_days}) — data-FLOW guard")
            if not stale_ok:
                failed.append(f"STALENESS: newest action {latest_date} is {biz_age} business days old during an "
                              f"ACTIVE session — LIS ingestion may be broken / the API returning empty")
    else:
        print(f"  [PASS] STALENESS: session flag is {session_flag or 'unset'} (not ACTIVE) — freshness gate "
              f"correctly silent off-session")

    if failed:
        _msg = f"\n🚨 SENTINEL FAIL — {len(failed)} invariant(s) breached: {', '.join(failed)}"
        print(_msg)
        # Mirror to Slack (dormant until SLACK_WEBHOOK_URL is set). The non-zero
        # exit below already escalates to a GitHub Actions failure email; this adds
        # a faster, specific channel naming the breached invariant(s).
        _notify_slack(f"🚨 *Accuracy Sentinel FAILED* (calendar) — {len(failed)} invariant(s): {', '.join(failed)}")
        _ledger("accuracy", f"{len(failed)} accuracy invariant(s) breached: {', '.join(failed)}")
        return 1
    print("\n✅ SENTINEL PASS — all accuracy invariants hold.")
    # Whoever detects a failure declares its end: on a PASS we close our own open incident, which is all the
    # recovery detection the ledger needs (docs/architecture/incident_counter.md §3).
    _ledger_close("accuracy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
