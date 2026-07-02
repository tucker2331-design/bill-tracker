#!/usr/bin/env python3
"""Relative-time chain resolver — diagnostic + additive-only gate (calendar_chain_ordering §8).

TWO jobs, one live Schedule API pull per authorized session (the worker hits this
same endpoint every cycle — within LIS-safety guardrail #4; no gspread, no writes):

  1. DIAGNOSE the current state (always). Categorize the relative-phrase rows by how
     build_time_graph resolves them and PROVE the date-blindness finding: the resolver
     keys raw_times by OwnerName only, so a committee that meets on many dates collapses
     to ONE resolved SortTime (e.g. a single "house adjourned" clock stands in for all
     443 dates). This is the evidence behind the re-scope in calendar_chain_ordering §8.
  2. ADDITIVE-ONLY GATE (when the working tree changes build_time_graph). Diff the NEW
     resolved map against the merge-base OLD one and FAIL if any row carrying a REAL
     published ScheduleTime moves. Derived rows (empty ScheduleTime) are allowed to move
     — that's the point of the fix — but are listed for an eyeball spot-check vs LIS.

Run: python3 tools/edge_case_replay/validate_relative_chains.py
"""
import ast, re, sys, os, json, subprocess, urllib.request, urllib.parse
from collections import Counter
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
sys.path.insert(0, ROOT)
from lis_authorization import LIS_API_AUTHORIZED_SESSIONS, assert_lis_authorized
SESSIONS = sorted(LIS_API_AUTHORIZED_SESSIONS, reverse=True)
for _s in SESSIONS:
    assert_lis_authorized(_s)

NEEDED = {"build_time_graph", "parse_24h_time", "_parse_relative_offset_minutes",
          "_is_non_concrete_time", "normalize_room_key", "_is_relative_time_text"}
REL_RE = re.compile(r'\b(?:immediately\s+)?(?:upon|after|following)\b|\brecess\b', re.I)
SENTINELS = {"23:59", "06:00"}

def load_time_graph(source_text, label):
    body = [n for n in ast.parse(source_text).body if isinstance(n, ast.FunctionDef) and n.name in NEEDED]
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "str": str}
    exec(compile(ast.Module(body, []), f"<{label}>", "exec"), ns)
    return ns.get("build_time_graph"), {n.name for n in body}

def git_show(ref, path):
    try:
        return subprocess.check_output(["git", "-C", ROOT, "show", f"{ref}:{path}"],
                                       stderr=subprocess.DEVNULL).decode()
    except subprocess.CalledProcessError:
        return None

def fetch_schedules(code):
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync?" + urllib.parse.urlencode({"sessionCode": code})
    req = urllib.request.Request(url, headers={"WebAPIKey": API_KEY, "Accept": "application/json"})
    j = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
    return j.get("Schedules", []) if isinstance(j, dict) else j

def relative_rows(schedules):
    """(name_key, has_published_clock, date, owner, desc) for each relative-phrase row."""
    out = []
    for m in schedules:
        tval = str(m.get("ScheduleTime", "")).strip()
        desc = re.sub(r"<[^>]+>", "", str(m.get("Description", ""))).strip()
        if not REL_RE.search(f"{tval} {desc}"):
            continue
        out.append((str(m.get("OwnerName", "")).strip().lower(), bool(tval),
                    str(m.get("ScheduleDate", ""))[:10], str(m.get("OwnerName", "")).strip(), desc[:70]))
    return out

def main():
    new_btg, _ = load_time_graph(open(f"{ROOT}/calendar_worker.py").read(), "new")
    base = subprocess.check_output(["git", "-C", ROOT, "merge-base", "HEAD", "origin/main"]).decode().strip()
    old_btg, _ = load_time_graph(git_show(base, "calendar_worker.py"), "old")
    tree_changed = new_btg.__code__.co_code != old_btg.__code__.co_code

    fail = False
    for code in SESSIONS[:1]:  # one authorized session is representative; the map is date-blind anyway
        schedules = fetch_schedules(code)
        new_map = new_btg(schedules)
        rows = relative_rows(schedules)
        dates = {str(m.get("ScheduleDate", ""))[:10] for m in schedules}

        # (1) DIAGNOSTIC — current-state distribution + date-blindness proof.
        dist = Counter(new_map.get(r[0], "∅") for r in rows)
        published = sum(1 for r in rows if r[1])
        print(f"=== session {code}: {len(schedules)} rows across {len(dates)} dates | "
              f"{len(rows)} relative-phrase rows ({published} with a published clock, "
              f"{len(rows) - published} empty→derived) ===")
        print("  resolved SortTime distribution (build_time_graph, NAME-keyed → date-blind):")
        for v, c in dist.most_common(8):
            print(f"     {c:4} → {v}")
        multi = Counter(r[0] for r in rows)
        worst = [(n, c) for n, c in multi.most_common(4)]
        print("  date-blindness: one NAME → one SortTime, but the committee meets on many dates:")
        for n, c in worst:
            print(f"     {c:3} dated meetings collapse to 1 resolved value  ·  {n[:60]}")

        # (2) ADDITIVE-ONLY GATE — only when build_time_graph actually changed.
        if tree_changed:
            old_map = old_btg(schedules)
            published_names = {r[0] for r in rows if r[1]} | {
                str(m.get("OwnerName", "")).strip().lower() for m in schedules
                if str(m.get("ScheduleTime", "")).strip() and not REL_RE.search(str(m.get("Description", "")))}
            moved_published, moved_derived = [], []
            for k in set(old_map) | set(new_map):
                o, n = old_map.get(k, "∅"), new_map.get(k, "∅")
                if o == n:
                    continue
                (moved_published if k in published_names else moved_derived).append((k, o, n))
            print(f"\n  GATE: {len(moved_published)} PUBLISHED-clock rows moved (must be 0), "
                  f"{len(moved_derived)} derived rows moved (expected by the fix):")
            for k, o, n in moved_published:
                print(f"     ❌ PUBLISHED MOVED {o} → {n}   {k[:70]}"); fail = True
            for k, o, n in sorted(moved_derived)[:20]:
                print(f"     · derived {o} → {n}   {k[:70]}")
        else:
            print("\n  (build_time_graph unchanged vs merge-base — diagnostic only, gate skipped.)")

    if fail:
        print("\n❌ FAIL — a published ScheduleTime moved. Not additive-safe.")
        sys.exit(1)
    print("\n✅ OK.")

if __name__ == "__main__":
    main()
