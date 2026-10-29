#!/usr/bin/env python3
"""Trust-surface guard — the watcher of the watchers (2026-10-26, owner: "clear to add all").

WHY THIS EXISTS. On 2026-10-26 the Health tab showed the days-clean counter as unknown and five checks as
"unconfirmed", and neither had been visible as a problem for months:
  * the incident-ledger workflow had FAILED on every run since it was created (Aug, Sep, Oct) — but the Health
    tab only listed four guards, so a guard that never once succeeded was invisible (assumptions_audit #141);
  * the bill backend had stopped delivering its check results to the live sheet on 2026-07-30 (PR #238) — the
    page said "unconfirmed" five times for one cause, and the LEDGER recorded nothing, because only three guards
    could write to it. The page and the ledger disagreed (docs/architecture/incident_counter.md: "one truth
    pipeline: checks -> verdicts -> (display AND ledger)").

WHAT IT DOES. One pass, two outputs that come from the SAME verdicts:
  1. For EVERY scheduled workflow in .github/workflows (found structurally from each file's own `schedule:`
     cron, so a new scheduled job is covered without editing this file — Standard #8): latest run, last
     success, failures in a row, and whether it is OVERDUE against the gap its own cron implies. A job that has
     NEVER succeeded is a failure, not "scheduled".
  2. The bill backend's check results (the completeness payload) are present in the live Bill_Tracker header.
  -> writes the verdicts to the `Guard_Status` tab (a snapshot, rewritten each run; the Health tab reads it)
  -> opens an `unverified` incident in the days-clean ledger for each non-OK check (detected_by
     `trust_surface:<check>`), and closes it when the check is OK again (the ledger dedupes open incidents).

FAIL-OPEN on bookkeeping, FAIL-LOUD on its own blindness: if it cannot reach GitHub or the sheet it says so
(state `unknown`, which also opens `unverified` — "we never bank a day we couldn't check").
Run: python3 tools/verification/trust_surface_guard.py          (CI: GH_TOKEN + GCP_CREDENTIALS)
     python3 tools/verification/trust_surface_guard.py --dry    (print verdicts, write nothing)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.environ.get("GITHUB_REPOSITORY", "tucker2331-design/bill-tracker")
SHEET = os.environ.get("INCIDENT_LOG_SPREADSHEET_ID", "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM")
STATUS_TAB = "Guard_Status"
STATUS_HEADER = ["CheckedUTC", "Check", "Label", "State", "SinceUTC", "LastSuccessUTC", "FailuresInARow",
                 "ExpectedEvery", "Detail", "URL"]
DETECTOR = "trust_surface"
STATES_OK = {"ok", "disabled", "running"}   # disabled = switched off on purpose; running = first run in progress
# Liveness and recovery are judged on SCHEDULED runs only: a manual dispatch can be a diagnostic that skips the
# production write (ny_bill_tracker.yml's check-config / dry-run), and its success must not close a production
# failure (Codex #247). The exception is a workflow whose EVERY dispatch runs the same production path as its
# schedule -- listed here explicitly, with the reason, so it is a decision on record and never a default.
DISPATCH_IS_PRODUCTION = {
    "incident_ledger.yml",   # both modes (drill, status) read/write the REAL ledger with the same code as the cron
}
NOT_EVIDENCE = ("skipped", "cancelled")

# What each job PROVES, in plain words for the client-facing tab. OPTIONAL: a job missing here is still
# checked and shown under its workflow name — this dict only improves wording, it never gates coverage.
PROVES = {
    "accuracy_sentinel.yml": "every meeting action on the calendar has a time; no unclassified rows",
    "bill_tracker.yml": "the bill list is refreshed from LIS",
    "calendar_worker.yml": "the calendar is refreshed from LIS",
    "compact_archive.yml": "old session data is compacted so the sheet stays within limits",
    "completeness_tripwire.yml": "no hidden meeting: everything on LIS's own calendar appears here",
    "endpoint_parity_audit.yml": "the LIS sources we read still return what we expect",
    "incident_ledger.yml": "the days-clean record can still be written (monthly fire drill)",
    "legevent_reconcile.yml": "our committee votes match the official minutes",
    "metrics_history_retention.yml": "the trend history stays within its size limit",
    "ny_bill_tracker.yml": "the New York bill list is refreshed",
    "stm_order_invariance.yml": "results do not depend on the order data arrives in",
    "sustainability_audit.yml": "capacity, schema drift, retention and duplicate checks",
    "witness_retention.yml": "the change record stays within its size limit",
}


def _now():
    return datetime.now(timezone.utc)


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else ""


def _parse_ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ── 1. scheduled workflows, found from their own files ──────────────────────────────────────────────────────
def cron_period(expr):
    """Nominal period of a 5-field cron, from its structure. Returns (timedelta, label) or (None, why)."""
    if not isinstance(expr, str):                   # YAML can hand back an int/bool for a malformed cron (Gemini #247)
        return None, f"unreadable cron {expr!r}"
    f = expr.split()
    if len(f) != 5:
        return None, f"unreadable cron {expr!r}"
    minute, hour, dom, _mon, dow = f
    if dom != "*":
        return timedelta(days=31), "monthly"
    if dow != "*":
        return timedelta(days=7), "weekly"
    m = re.fullmatch(r"\*/(\d+)", hour)
    if m:
        return timedelta(hours=int(m.group(1))), f"every {m.group(1)} h"
    if hour != "*":
        return timedelta(days=1), "daily"
    m = re.fullmatch(r"\*/(\d+)", minute)
    if m:
        return timedelta(minutes=int(m.group(1))), f"every {m.group(1)} min"
    return timedelta(hours=1), "hourly"


def scheduled_workflows(wf_dir=None):
    """[(file, name, cron)] for every workflow whose `on:` has an active `schedule:` (comments ignored).
    A file that does not parse is returned with cron=None: GitHub cannot run it either, so it is reported."""
    import yaml
    wf_dir = wf_dir or os.path.join(ROOT, ".github", "workflows")
    out = []
    for fn in sorted(os.listdir(wf_dir)):
        if not fn.endswith((".yml", ".yaml")):
            continue                                   # not a workflow file (README etc.) -- nothing to check
        try:
            with open(os.path.join(wf_dir, fn)) as fh:
                doc = yaml.safe_load(fh) or {}
        except (yaml.YAMLError, OSError) as e:
            out.append((fn, fn, None, f"workflow file does not parse or read ({type(e).__name__}); GitHub cannot run it"))
            continue                                   # reported as an `unknown` row, never dropped
        if not isinstance(doc, dict):                  # a list/string at top level is not a workflow (Gemini #247)
            out.append((fn, fn, None, f"workflow file is a {type(doc).__name__}, not a mapping; GitHub cannot run it"))
            continue                                   # reported as an `unknown` row, never dropped
        on = doc.get("on", doc.get(True))           # PyYAML reads the bare key `on` as boolean True
        sched = on.get("schedule") if isinstance(on, dict) else None
        crons = [s.get("cron") for s in (sched or []) if isinstance(s, dict) and s.get("cron")]
        if crons:
            out.append((fn, str(doc.get("name") or fn), crons[0], ""))
    return out


def _gh(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}",
                                 headers={"Accept": "application/vnd.github+json"})
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GitHub API {path}: {last}")


def production_runs(runs, fn):
    """The runs that are evidence about the PRODUCTION path: scheduled runs, plus every dispatch of a workflow in
    DISPATCH_IS_PRODUCTION. Pure; unit-tested."""
    return [r for r in runs if r.get("event") == "schedule" or fn in DISPATCH_IS_PRODUCTION]


def judge_runs(runs, period, now):
    """Pure verdict over newest-first completed/in-progress runs. Returns dict (no I/O; unit-tested)."""
    done = [r for r in runs if r.get("status") == "completed"]
    last_success = next((_parse_ts(r.get("created_at")) for r in done if r.get("conclusion") == "success"), None)
    fails = 0
    for r in done:
        if r.get("conclusion") == "success":
            break
        if r.get("conclusion") in NOT_EVIDENCE:
            continue                                   # not evidence either way
        fails += 1
    # Liveness comes from SUBSTANTIVE runs only: a cancelled/skipped run proves nothing ran, so it must not refresh
    # the overdue clock (Codex #247 -- a daily job cancelled every day would otherwise read ok forever).
    real = [r for r in done if r.get("conclusion") not in NOT_EVIDENCE]
    latest = _parse_ts(real[0].get("created_at")) if real else None
    first_fail = None
    if fails:
        streak = [r for r in done if r.get("conclusion") not in ("success", "skipped", "cancelled")][:fails]
        first_fail = _parse_ts(streak[-1].get("created_at")) if streak else None
    # Calibrated against the job's OWN rhythm, not just its cron (pre-push #14). GitHub throttles schedules:
    # measured 2026-10-27, the `*/15` workers actually fire every ~3-4 h, so a cron-only grace of 2 h would
    # raise a false alarm every night -- and a false alarm IS an incident on our own ledger. Use the larger of
    # twice the cron period, twice the median observed gap, and 1.5x the largest gap in the recent window.
    times = [t for t in (_parse_ts(r.get("created_at")) for r in runs) if t]
    gaps = sorted((a - b) for a, b in zip(times, times[1:]) if a > b)
    observed = [gaps[len(gaps) // 2] * 2, gaps[-1] * 1.5] if gaps else []
    grace = max([period * 2, timedelta(hours=2)] + observed)
    if not done and any(r.get("status") in ("in_progress", "queued") for r in runs):
        # First run ever, happening now (the guard's own first cycle sees exactly this). Not a failure -- opening an
        # incident here would put a false alarm on the ledger on day one. GitHub's job timeout ends a stuck run,
        # after which a real verdict follows.
        state, since, detail = "running", None, "first run in progress"
    elif not done:
        state, since, detail = "never_run", None, "no completed run on record"
    elif last_success is None:
        state, since = "never_succeeded", _parse_ts(done[-1].get("created_at"))
        detail = f"none of its last {len(done)} runs succeeded"
    elif fails:
        state, since, detail = "failing", first_fail, f"{fails} failed run(s) in a row"
    elif latest and now - latest > grace:
        state, since, detail = "overdue", latest + grace, f"no run since {_iso(latest)}"
    else:
        state, since, detail = "ok", None, ""
    return {"state": state, "since": since, "last_success": last_success, "fails": fails, "detail": detail,
            "url": (done[0].get("html_url") if done else "") or ""}


def _workflow_states():
    """{file: state} from GitHub (active / disabled_manually / disabled_inactivity ...). {} if unreachable."""
    try:
        wfs = _gh("/actions/workflows?per_page=100").get("workflows", [])
    except RuntimeError as e:
        print(f"⚠️ [trust_surface] could not read workflow states ({e}); treating every scheduled job as active")
        return {}
    return {os.path.basename(w.get("path", "")): w.get("state", "") for w in wfs}


def check_workflows(now):
    rows = []
    states = _workflow_states()
    for fn, name, cron, why in scheduled_workflows():
        st = states.get(fn, "active")
        if st and st != "active":
            # Switched off deliberately (e.g. the paused legacy worker): shown, never an incident. NOTE GitHub's
            # own `disabled_inactivity` (60 days without a push) also lands here -- shown, so it cannot hide.
            rows.append({"check": f"workflow:{fn}", "label": re.sub(r'^[^A-Za-z0-9]+', '', name).strip() or fn,
                         "state": "disabled", "since": None, "last_success": None, "fails": 0, "every": "off",
                         "detail": f"switched off on GitHub ({st})", "url": ""})
            continue
        if cron is None:
            rows.append({"check": f"workflow:{fn}", "label": fn, "state": "unknown", "since": None,
                         "last_success": None, "fails": 0, "every": "?", "detail": why, "url": ""})
            continue
        period, every = cron_period(cron)
        label = f"{re.sub(r'^[^A-Za-z0-9]+', '', name).strip()} — {PROVES.get(fn, name)}"
        if period is None:
            rows.append({"check": f"workflow:{fn}", "label": label, "state": "unknown", "since": None,
                         "last_success": None, "fails": 0, "every": every, "detail": every, "url": ""})
            continue
        try:
            runs = _gh(f"/actions/workflows/{fn}/runs?per_page=30").get("workflow_runs", [])
            v = judge_runs(production_runs(runs, fn), period, now)
        except RuntimeError as e:
            v = {"state": "unknown", "since": None, "last_success": None, "fails": 0,
                 "detail": f"could not read run history: {e}"[:300], "url": ""}
        rows.append({"check": f"workflow:{fn}", "label": label, "every": every, **v})
    return rows


# ── 2. the bill backend's check results reached the live sheet ─────────────────────────────────────────────
def _json_obj(c):
    """The cell as a JSON object, or None when it is brace-shaped but not JSON (the caller keeps looking)."""
    try:
        v = json.loads(c)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def payload_in_header(cells):
    """True when one header cell is JSON carrying `universe_count` — found by CONTENT, like the front end."""
    for c in cells:
        c = (c or "").strip()
        if c.startswith("{") and '"universe_count"' in c:
            obj = _json_obj(c)
            if obj is not None and isinstance(obj.get("universe_count"), int):
                return True
    return False


def _sheet_token():
    """A read-only bearer token from GCP_CREDENTIALS, or None without credentials. The app went private (#242): once
    the sheet is Restricted, an anonymous gviz read gets Google's sign-in page, and this check would raise a false
    `unknown` every run. Same credentials the ledger write already uses."""
    raw = os.environ.get("GCP_CREDENTIALS")
    if not raw:
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    creds.refresh(Request())
    return creds.token


def check_bill_payload(now):
    import csv
    import io
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet=Bill_Tracker"
           f"&range=A1:AF1&headers=0")
    base = {"check": "bill_backend_checks", "label": "Bill backend check results reach the live sheet",
            "every": "each bill cycle", "last_success": None, "fails": 0, "url": ""}
    req = urllib.request.Request(url)
    try:
        tok = _sheet_token()
    except Exception as e:   # bad JSON, missing google-auth, refresh refused (revoked key): categorized, read anyway
        print(f"⚠️ [API_FAILURE] [trust_surface] service-account token unavailable ({type(e).__name__}: {e}); "
              f"reading the sheet without one")
        tok = None
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode("utf-8", "replace")
        header = next(csv.reader(io.StringIO(txt)), [])
    except (urllib.error.URLError, TimeoutError) as e:
        return {**base, "state": "unknown", "since": None, "detail": f"could not read the sheet: {e}"[:300]}
    if not header or (header[0] or "").strip() != "Bill":
        return {**base, "state": "unknown", "since": None,
                "detail": "the response was not the Bill_Tracker tab (gviz serves the first sheet for a missing tab)"}
    if payload_in_header(header):
        return {**base, "state": "ok", "since": None, "detail": ""}
    return {**base, "state": "failing", "since": None,
            "detail": "the bill backend's completeness payload is missing from the Bill_Tracker header; "
                      "the Health tab cannot confirm outcomes, completeness or patron coverage"}


# ── outputs: Guard_Status snapshot + ledger, from the same verdicts ────────────────────────────────────────
def _carry_since(rows, prior):
    """A failure's start must not reset each run. Keep the earliest known SinceUTC for a still-failing check."""
    for r in rows:
        p = prior.get(r["check"])
        if r["state"] in STATES_OK:
            r["since"] = None
        elif p and p.get("State") not in STATES_OK and p.get("SinceUTC"):
            ps = _parse_ts(p["SinceUTC"])
            if ps and (r["since"] is None or ps < r["since"]):
                r["since"] = ps
    return rows


def write_status(rows, now):
    import gspread
    from google.oauth2.service_account import Credentials
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(os.environ["GCP_CREDENTIALS"]), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sh = gc.open_by_key(SHEET)
    try:
        ws = sh.worksheet(STATUS_TAB)
        prior = {r.get("Check"): r for r in ws.get_all_records()}
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=STATUS_TAB, rows=100, cols=len(STATUS_HEADER))
        prior = {}
        print(f"🆕 [trust_surface] created the {STATUS_TAB} tab")
    rows = _carry_since(rows, prior)
    values = [STATUS_HEADER] + [[_iso(now), r["check"], r["label"], r["state"], _iso(r["since"]),
                                 _iso(r["last_success"]), r["fails"], r["every"], r["detail"], r["url"]]
                                for r in rows]
    ws.clear()
    ws.update(values=values, range_name="A1", value_input_option="RAW")
    return rows


def ledger(rows):
    sys.path.insert(0, ROOT)
    try:
        from tools.incident_log.log import close_incident, record_incident
    except ImportError as e:   # fail-open on bookkeeping, but loudly: Guard_Status is already written (Gemini #247)
        print(f"❌ [API_FAILURE] [trust_surface] cannot import the incident log ({e}); the ledger was NOT updated "
              f"for {len(rows)} check(s).")
        return
    for r in rows:
        det = f"{DETECTOR}:{r['check']}"
        try:
            if r["state"] in STATES_OK:
                close_incident("unverified", det)
            else:
                # The ledger records WHEN WE DETECTED it (start = now): incidents before genesis are not
                # backfilled (incident_counter.md, pre-genesis rule). The true start stays in Guard_Status.
                since = f" (since {_iso(r['since'])})" if r["since"] else ""
                record_incident("unverified", f"{r['label']}: {r['state']}{since} — {r['detail']}", det)
        except Exception as e:            # fail-open: bookkeeping must never stop the status write
            print(f"⚠️ [trust_surface] ledger write failed for {det} (non-fatal): {e}")


def main(argv):
    now = _now()
    rows = check_workflows(now) + [check_bill_payload(now)]
    bad = [r for r in rows if r["state"] not in STATES_OK]
    for r in rows:
        print(f"  [{r['state']:>15}] {r['check']:40s} {r['detail']}")
    print(f"\n{len(rows)} checks, {len(bad)} not OK.")
    if "--dry" in argv:
        return 0
    if not os.environ.get("GCP_CREDENTIALS"):
        print("❌ [trust_surface] GCP_CREDENTIALS unset — cannot write Guard_Status or the ledger.")
        return 1
    rows = write_status(rows, now)
    ledger(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
