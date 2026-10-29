#!/usr/bin/env python3
"""Serve War Room member calls (Phase B2, 2026-10-29): FROZEN arm C on VENUE_FIX rows -> the private sheet.

What runs, and nothing else:
  * rows   = venue_fix's rebuild (ballot-count venue, case law #146 -- NEVER the text-derived venue);
  * model  = booster_2027.predict_boosted (arm C), the exact code pinned by frozen/prereg_2027_venuefix.json --
             the pinned hashes are re-checked before anything is served, and a mismatch serves NOTHING;
  * a CALL = |p - .5| >= .31 (the pre-registered edge); otherwise "cant_call". No AI checklist (Standard #3).
  * evidence per member = the counts the model was fed, as k-of-n (P26): this patron's bills, this room,
    similar bills, this subject -- all measured BEFORE the vote (first_vote replays in date order).

Off-season this is a REPLAY: train 2019-2025, predict every 2026 first vote, and the actual ballot rides along so
the page can show how the calls did. The tab (`War_Room_Calls`, one row per bill) is read by the app only through
the signed-in Worker (/api/sheet), never a public tab.

Run (CI only -- needs the Open States zips and GCP_CREDENTIALS):
  python3 tools/historical_cache/fetch.py fetch-openstates
  python3 tools/calibration/serve_calls.py            # writes the tab
  python3 tools/calibration/serve_calls.py --dry      # computes and prints, writes nothing
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import json
import os
import pickle
import sys

os.environ["VENUE_FIX"] = "1"                      # before content_votes is imported (venue_fix asserts it took)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import venue_fix as VF                             # noqa: E402  points first_vote's caches at the VENUE_FIX rows
import first_vote as FV                            # noqa: E402
import booster_2027 as BC                          # noqa: E402

SPEC = os.path.join(HERE, "frozen", "prereg_2027_venuefix.json")
CALL_EDGE = 0.31                                   # pre-registered: a call only when |p - .5| >= .31
TAB = "War_Room_Calls"
HEADER = ["Bill", "Session", "Room", "VoteDate", "Ballots", "YesNeeded", "CalledYes", "CalledNo", "CantCall",
          "ActualYes", "Members (JSON)"]
SUMMARY_CELL = "M1"                                # clear of the data columns (A..K)
SHEET = os.environ.get("SPREADSHEET_ID", "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM")   # VA · Live
EVIDENCE = (("mpat", "this patron's bills"), ("mroom", "this room"), ("sim", "similar bills"),
            ("msubj", "this subject"))


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def pinned_code_ok():
    """Every file the frozen spec pins must hash to its pin. Returns (ok, [mismatches])."""
    with open(SPEC) as fh:
        spec = json.load(fh)
    bad = [f for f, h in spec["code_sha256"].items() if _sha(os.path.join(HERE, f)) != h]
    return not bad, bad


def call_of(p):
    """'yes' / 'no' / 'cant_call' -- the one rule, pre-registered."""
    if abs(p - 0.5) < CALL_EDGE:
        return "cant_call"
    return "yes" if p >= 0.5 else "no"


def bill_rows(te, p):
    """Group first-vote ballots by bill -> sheet rows + run totals. Pure (unit-tested)."""
    by = collections.defaultdict(list)
    for r, pr in zip(te, p):
        by[r["bill"]].append((r, float(pr)))
    out, tot = [], collections.Counter()
    for (sess, bill), lst in sorted(by.items()):
        members = []
        for r, pr in sorted(lst, key=lambda t: t[0]["who"]):
            c = call_of(pr)
            members.append({"who": r["who"], "party": r["party"], "p": round(pr, 3), "call": c,
                            "actual": "yes" if r["y"] == 1 else "no",
                            "ev": {k: [int(r.get(f"k_{k}") or 0), int(r.get(f"n_{k}") or 0)] for k, _ in EVIDENCE}})
            tot["ballots"] += 1
            tot[c] += 1
            if c != "cant_call":
                tot["right" if (c == "yes") == (r["y"] == 1) else "wrong"] += 1
        n = len(members)
        out.append([bill.replace(" ", ""), sess, lst[0][0]["room"], lst[0][0].get("date", ""), n, n // 2 + 1,
                    sum(m["call"] == "yes" for m in members), sum(m["call"] == "no" for m in members),
                    sum(m["call"] == "cant_call" for m in members), sum(m["actual"] == "yes" for m in members),
                    json.dumps(members, ensure_ascii=False, separators=(",", ":"))])
    return out, tot


def write_tab(rows, summary):
    """Overwrite in place, blank the stale tail, THEN stamp the summary -- never clear first (the #240 lesson)."""
    import gspread
    from google.oauth2.service_account import Credentials
    gc = gspread.authorize(Credentials.from_service_account_info(
        json.loads(os.environ["GCP_CREDENTIALS"]), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
    sh = gc.open_by_key(SHEET)
    grid = [HEADER] + rows
    try:
        ws = sh.worksheet(TAB)
        if ws.row_count < len(grid) + 10 or ws.col_count < 13:
            ws.resize(rows=max(ws.row_count, len(grid) + 10), cols=max(ws.col_count, 13))
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=TAB, rows=len(grid) + 10, cols=13)
        print(f"🆕 [serve_calls] created the {TAB} tab")
    ws.update(values=grid, range_name="A1", value_input_option="RAW")
    if ws.row_count > len(grid):
        ws.batch_clear([f"A{len(grid) + 1}:K{ws.row_count}"])
    ws.update(values=[[json.dumps(summary, separators=(",", ":"))]], range_name=SUMMARY_CELL, value_input_option="RAW")


def main(argv):
    ok, bad = pinned_code_ok()
    if not ok:
        print(f"❌ [DATA_ANOMALY] [serve_calls] pinned code changed ({', '.join(bad)}); serving NOTHING. The frozen "
              f"model is the only one allowed on the page.")
        return 1
    if not os.path.exists(FV.ROWS):
        VF.rebuild()                               # slow: replays every vote (needs the Open States zips)
    with open(FV.ROWS, "rb") as fh:
        rows = [r for r in pickle.load(fh) if r["y"] >= 0]
    tr_years, te_year = VF.SPLITS["repeat"]        # train 2019-2025 (no 2023), replay 2026
    rc = FV.assemble()["rc"]
    vd = lambda r: rc[r["bill"]][0][0]             # noqa: E731  the bill's first roll-call date
    tr = [r for r in rows if r["yr"] in tr_years]
    te = [r for r in rows if r["yr"] == te_year]
    for r in te:
        r["date"] = vd(r)
    p = BC.predict_boosted(tr, te, vd)
    out, tot = bill_rows(te, p)
    called = tot["yes"] + tot["no"]
    with open(SPEC) as fh:
        expect = json.load(fh)["expected_from_2025_2026"]["repeat"]
    summary = {
        "model": "arm C (booster_2027.predict_boosted), frozen 2026-10-21", "rows": "VENUE_FIX (ballot-count venue)",
        "mode": "replay", "train_years": list(tr_years), "test_year": te_year, "call_edge": CALL_EDGE,
        "ballots": tot["ballots"], "called": called, "called_right": tot["right"], "cant_call": tot["cant_call"],
        "bills": len(out),
        "frozen_expected": {"ballots": expect["n"], "called": expect["calls"],
                            "called_right": expect["calls"] - expect["call_wrong"]},
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    match = (tot["ballots"], called, tot["right"]) == (expect["n"], expect["calls"], expect["calls"] - expect["call_wrong"])
    summary["matches_frozen"] = match
    print(json.dumps(summary, indent=1))
    if not match:
        print("⚠️ [DATA_ANOMALY] [serve_calls] the replay differs from the frozen expectation; served counts are the "
              "replay's own (computed from the served calls), and the difference is stamped in the summary.")
    if "--dry" in argv:
        return 0
    if not os.environ.get("GCP_CREDENTIALS"):
        print("❌ [serve_calls] GCP_CREDENTIALS unset -- cannot write the tab.")
        return 1
    write_tab(out, summary)
    print(f"✅ [serve_calls] {len(out)} bills, {tot['ballots']:,} ballots written to {TAB}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
