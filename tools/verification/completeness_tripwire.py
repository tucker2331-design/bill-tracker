#!/usr/bin/env python3
"""Completeness tripwire (Standard #2) — the verifiable NO-HIDDEN-MEETING guarantee.

The accuracy sentinel proves our *classification* is right; this proves our *coverage* is
complete: every committee meeting LIS itself puts on its calendar must appear in our Sheet1.
A meeting on the LIS Schedule that is ABSENT from our data is the catastrophic failure (a
hidden meeting — far worse than a misclassification), so it FAILS loudly.

INDEPENDENT SOURCE: the LIS Schedule API committee meetings (active session, in-window,
concrete time). JOIN KEY = committee CODE (H01-H24 / S01-S13), resolved on BOTH sides through
LIS's own committee list (getcommitteelistasync) — never raw name text, so phrasing variants
("House Committee on Courts of Justice" vs "House Courts of Justice") can't masquerade as a
gap. PoC measured 180/180 (100%) on 2026-06-09.

Exit codes:  0 = complete (every LIS meeting covered)
             1 = GAP — a LIS committee meeting is missing from Sheet1 (investigate)
             2 = EXTERNAL SOURCE CHANGE — the Schedule API returned too few meetings / failed;
                 a dead source can't certify completeness and must never read as PASS
                 (mirrors reconcile_votes.py). No secrets — Sheet1 via the public gviz CSV.

Usage: python3 tools/verification/completeness_tripwire.py [--session 20261]
"""
import sys, io, csv, re, json, time, os, argparse, urllib.request
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lis_authorization import (assert_lis_authorized,  # LIS API 2025/2026-only gate (ban-safe)
    LIS_API_KEY as API_KEY)  # S-1: single env-first key source (no literal here)

SHEET = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
MIN_EXPECTED_MEETINGS = 30   # a real session schedules hundreds of committee meetings; < this == source broke


def _get(url, headers=None, timeout=90, retries=3):
    for a in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout) as resp:
                return resp.read()
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(2 ** a)


def chamber_of(name):
    """Leading chamber letter from a committee/owner name ('House ...' -> H), else ''."""
    s = str(name or "").strip().lower()
    return "H" if s.startswith("house") else ("S" if s.startswith("senate") else "")


def committee_core(name):
    """Chamber/filler-stripped key (collapses 'House Committee on Courts of Justice' ==
    'Courts of Justice'). Chamber is carried SEPARATELY (chamber_of) so H02 != S02."""
    s = re.sub(r'\s+', ' ', str(name or '')).lower()
    s = s.split('-')[0]            # roll a subcommittee ("Parent-Subname") up to its parent code
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    for tok in ("house", "senate", "committee", "on", "for", "the", "of", "and", "subcommittee", "sub", "agenda"):
        s = re.sub(rf'\b{tok}\b', ' ', s)
    return ' '.join(s.split())


def _d10(s):
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(s)[:19] if 'T' in str(s) else str(s)[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="20261")
    args = ap.parse_args()
    session = assert_lis_authorized(args.session)   # ban-safe: never query an unauthorized session
    H = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    win_lo = f"{session[:4]}-01-01"                  # session-year floor; drops interim/old-year bleed

    # 1) committee name -> CODE map, from LIS's own committee list (the structural join key).
    try:
        cj = json.loads(_get(f"https://lis.virginia.gov/Committee/api/getcommitteelistasync?sessionCode={session}", H).decode())
        citems = next((v for v in cj.values() if isinstance(v, list)), cj) if isinstance(cj, dict) else cj
    except Exception as e:
        print(f"🚨 EXTERNAL SOURCE CHANGE — Committee API fetch/parse failed ({type(e).__name__}: {e}); "
              f"cannot build the code join. NOT reporting PASS.")
        return 2
    core2code = {}
    for c in citems or []:
        if not isinstance(c, dict):
            continue
        code = c.get("CommitteeNumber") or c.get("Number") or c.get("CommitteeCode")
        name = c.get("Name") or c.get("CommitteeName")
        if not (code and name):
            continue
        code = str(code).strip()
        # key by chamber + core. The committee list's Name is chamber-less ("Appropriations");
        # take the chamber from the code's first letter (H02 -> H).
        core2code[(code[:1] + committee_core(name))] = code
    if len(core2code) < 10:
        print(f"🚨 EXTERNAL SOURCE CHANGE — committee list resolved only {len(core2code)} codes (<10); "
              f"the Committee API likely changed shape. NOT reporting PASS.")
        return 2

    def to_code(name):   # "" if unresolved (counted, never silently joined)
        return core2code.get(chamber_of(name) + committee_core(name), "")

    # 2) INDEPENDENT meeting index: LIS Schedule committee meetings (in-window, concrete time).
    try:
        sj = json.loads(_get(f"https://lis.virginia.gov/Schedule/api/getschedulelistasync?sessionCode={session}", H).decode())
        sched = next((v for v in sj.values() if isinstance(v, list)), sj) if isinstance(sj, dict) else sj
    except Exception as e:
        print(f"🚨 EXTERNAL SOURCE CHANGE — Schedule API fetch/parse failed ({type(e).__name__}: {e}). "
              f"NOT reporting PASS.")
        return 2
    lis_meetings = set()          # (committee_code, date)
    unresolved_owner = set()
    for e in sched or []:
        if not isinstance(e, dict) or e.get("ScheduleType") != "Committee":
            continue
        d = _d10(e.get("ScheduleDate"))
        if not d or d < win_lo:                       # drop interim / prior-year bleed
            continue
        t = str(e.get("ScheduleTime") or "").strip()
        if not t or re.search(r'tba|tbd|call', t, re.I):   # only meetings LIS gave a concrete time
            continue
        owner = e.get("OwnerName")
        if not owner:
            continue          # schedule entry with no owner name — can't attribute, skip
        code = to_code(owner)
        if not code:
            unresolved_owner.add(committee_core(owner))
            continue
        lis_meetings.add((code, d))
    if len(lis_meetings) < MIN_EXPECTED_MEETINGS:
        print(f"🚨 EXTERNAL SOURCE CHANGE — only {len(lis_meetings)} timed committee meetings on the LIS "
              f"calendar (< {MIN_EXPECTED_MEETINGS}); the Schedule API likely changed/emptied. NOT reporting PASS.")
        return 2

    # 3) OUR coverage: every (committee_code, date) Sheet1 has a legislative row for.
    try:
        rows = list(csv.reader(io.StringIO(_get(f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet=Sheet1", timeout=120).decode())))
    except Exception as e:
        print(f"🚨 CANNOT VERIFY — Sheet1 fetch/parse failed ({type(e).__name__}: {e}); NOT reporting PASS.")
        return 2
    if len(rows) < 2:
        print("🚨 CANNOT VERIFY — Sheet1 returned <2 rows (empty/unreadable); NOT reporting PASS.")
        return 2
    ci = {c: i for i, c in enumerate(rows[0])}
    _need = [c for c in ("Source", "Committee", "Date") if c not in ci]
    if _need:
        # A renamed/removed column would read "" everywhere -> rows skipped -> a FALSE
        # completeness gap (false hidden-meeting alarm). Fail-clean instead (Gemini #114).
        print(f"🚨 CANNOT VERIFY — Sheet1 missing required column(s) {_need}; schema changed. NOT reporting PASS.")
        return 2
    g = lambda r, c: (r[ci[c]] if c in ci and ci[c] < len(r) else "")
    our = set()
    for r in rows[1:]:
        if g(r, "Source") == "SYSTEM":
            continue
        code = to_code(g(r, "Committee"))
        d = _d10(g(r, "Date"))
        if code and d:
            our.add((code, d))

    # 4) COMPLETENESS: every LIS meeting must be covered. Gaps = potential hidden meetings.
    gaps = sorted(m for m in lis_meetings if m not in our)
    covered = len(lis_meetings) - len(gaps)
    print(f"=== COMPLETENESS TRIPWIRE (session {session}) ===")
    print(f"  LIS calendar committee meetings (timed, in-window): {len(lis_meetings)}")
    print(f"  covered by Sheet1: {covered}/{len(lis_meetings)} ({100*covered/len(lis_meetings):.1f}%)")
    if unresolved_owner:
        print(f"  (note: {len(unresolved_owner)} schedule OwnerName(s) didn't resolve to a code, e.g. {sorted(unresolved_owner)[:3]})")
    if gaps:
        print(f"\n🚨 COMPLETENESS GAP — {len(gaps)} LIS committee meeting(s) absent from Sheet1 (possible hidden meeting):")
        for code, d in gaps[:25]:
            print(f"    {d}  committee {code}")
        return 1
    print("\n✅ COMPLETE — every committee meeting on the LIS calendar is covered by Sheet1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
