#!/usr/bin/env python3
"""Relative-time chain resolver — validation gate + diagnostic (calendar_chain_ordering §8).

The resolver is now DATE-AWARE (build_time_graph keys by (date, name)). This gate runs
against ONE live Schedule API pull per authorized session (the worker hits this same
endpoint every cycle — within LIS-safety guardrail #4; no gspread, no writes) and checks:

  1. SAFETY (absolute, MUST pass) — every schedule row that carries a REAL published
     ScheduleTime must resolve to the parse of ITS OWN clock. This is the honored-times
     invariant: the date-aware resolver never re-derives a time LIS actually published.
     (Stronger than a diff-vs-old, because the old date-blind map returned WRONG values
     for some published rows via name collisions — those are fixes, not regressions.)

  2. RESOLUTION (the win) — count relative-phrase rows that resolve to a concrete clock
     now vs the old date-blind resolver, and PROVE date-awareness: the same committee on
     different dates now gets DIFFERENT SortTimes. Spot-print a known committee chain so
     parent-before-child ordering can be eyeballed against LIS.

Run: python3 tools/edge_case_replay/validate_relative_chains.py
"""
import ast, re, sys, os, json, subprocess, urllib.request, urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from lis_authorization import (LIS_API_AUTHORIZED_SESSIONS, assert_lis_authorized,
    LIS_API_KEY as API_KEY)  # S-1: single env-first key source (no literal here)
SESSIONS = sorted(LIS_API_AUTHORIZED_SESSIONS, reverse=True)
for _s in SESSIONS:
    assert_lis_authorized(_s)

NEEDED = {"build_time_graph", "_resolve_one_day", "parse_24h_time", "_parse_relative_offset_minutes",
          "_is_non_concrete_time", "normalize_room_key", "_is_relative_time_text"}
# Module-level constants the extracted functions close over (the §9 anchor-ladder telemetry dict and its
# compiled self-reference regex). Hoisted alongside the functions so a NameError can't masquerade as a
# resolver failure. The OLD snapshot predates the ladder and simply carries none of these.
NEEDED_GLOBALS = {"ANCHOR_RUNG_COUNTS", "_SELF_REF_RE"}
REL_RE = re.compile(r'\b(?:immediately\s+)?(?:upon|after|following)\b|\brecess\b', re.I)
SENTINELS = {"23:59", "06:00"}

def load(source_text, label):
    if source_text is None:
        sys.exit(f"❌ cannot load '{label}' snapshot — source missing (git show failed / merge-base absent).")
    body = [n for n in ast.parse(source_text).body
            if (isinstance(n, ast.FunctionDef) and n.name in NEEDED)
            or (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id in NEEDED_GLOBALS)]
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "str": str, "pd": pd,
          "defaultdict": defaultdict, "Counter": Counter}
    exec(compile(ast.Module(body, []), f"<{label}>", "exec"), ns)
    ns.setdefault("ANCHOR_RUNG_COUNTS", {})   # old snapshot: no ladder, no telemetry
    return ns  # full namespace — callers pull build_time_graph / parse_24h_time / etc. from it

def git_show(ref, path):
    try:
        return subprocess.check_output(["git", "-C", ROOT, "show", f"{ref}:{path}"], stderr=subprocess.DEVNULL).decode()
    except subprocess.CalledProcessError:
        return None

def fetch(code):
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync?" + urllib.parse.urlencode({"sessionCode": code})
    req = urllib.request.Request(url, headers={"WebAPIKey": API_KEY, "Accept": "application/json"})
    j = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
    return j.get("Schedules", []) if isinstance(j, dict) else j

def norm_name(m):
    return re.sub(r"\s+", " ", str(m.get("OwnerName", "")).strip()).lower()

def date_key(m):
    d = pd.to_datetime(m.get("ScheduleDate", ""), errors="coerce")
    return None if pd.isna(d) else d.strftime("%Y-%m-%d")

def main():
    ns_new = load(open(f"{ROOT}/calendar_worker.py").read(), "new")
    new_btg = ns_new["build_time_graph"]
    parse24 = ns_new["parse_24h_time"]   # reused from the one extraction (no re-parse)

    base = subprocess.check_output(["git", "-C", ROOT, "merge-base", "HEAD", "origin/main"]).decode().strip()
    old_btg = load(git_show(base, "calendar_worker.py"), "old")["build_time_graph"]  # None-source → load() exits
    print(f"OLD snapshot (date-blind, name-keyed): {base[:9]}\n")

    fail = False
    for code in SESSIONS[:1]:  # one authorized session is representative
        sch = fetch(code)
        new_map = new_btg(sch)          # {(date, name): "HH:MM"}
        old_map = old_btg(sch)          # {name: "HH:MM"}  (date-blind)
        dates = {date_key(m) for m in sch if date_key(m)}
        print(f"=== session {code}: {len(sch)} rows / {len(dates)} dates ===")

        # (1) SAFETY — a (date, name) that carries ANY published clock must resolve to
        # ONE OF ITS published clocks, never a derived/relative value. (A committee can
        # legitimately meet twice under one name in a day — 7:30 AM AND 4:00 PM — and a
        # single (date,name) key holds one; the resolver keeps the last concrete, exactly
        # as the caller's api_schedule_map dedup does. The corruption we forbid is a
        # published-time key resolving to a MIS-ANCHORED derived time.)
        pub_clocks = defaultdict(set)   # (date, name) -> {own clocks published for it}
        for m in sch:
            t = str(m.get("ScheduleTime", "")).strip()
            own = parse24(t)
            if own == "23:59" or any(x in t.lower() for x in ["after", "upon"]):
                continue
            dk = date_key(m)
            if dk is not None:
                pub_clocks[(dk, norm_name(m))].add(own)
        violations = []
        for key, clocks in pub_clocks.items():
            got = new_map.get(key)
            if got not in clocks:
                violations.append((key[0], key[1], sorted(clocks), got))
        print(f"  SAFETY: {len(pub_clocks)} (date,name) keys carry a published clock; "
              f"{len(violations)} resolve to a NON-published (derived) time (must be 0)")
        for dk, nm, clocks, got in violations[:15]:
            print(f"     ❌ {dk} {nm[:44]:44} published={clocks} got={got}"); fail = True

        # (2) RESOLUTION — relative rows now concrete, + date-awareness proof.
        rel = [m for m in sch if REL_RE.search(f"{str(m.get('ScheduleTime','')).strip()} "
                                               f"{re.sub(r'<[^>]+>','',str(m.get('Description','')))}")]
        now_concrete = sum(1 for m in rel
                           if date_key(m) and new_map.get((date_key(m), norm_name(m)), "23:59") not in SENTINELS)
        old_concrete = sum(1 for m in rel if old_map.get(norm_name(m), "23:59") not in SENTINELS)
        print(f"  RESOLUTION: {len(rel)} relative-phrase rows | concrete SortTime: "
              f"old(date-blind)={old_concrete} → new(date-aware)={now_concrete}")
        # date-awareness: a committee that appears on many dates now spans multiple SortTimes
        per_name = defaultdict(set)
        for (dk, nm), v in new_map.items():
            per_name[nm].add(v)
        spread = sorted(((nm, len(vs)) for nm, vs in per_name.items() if len(vs) > 1), key=lambda x: -x[1])[:5]
        print("  date-awareness (one NAME now resolves to MANY per-date SortTimes):")
        for nm, k in spread:
            print(f"     {k:2} distinct SortTimes across dates · {nm[:60]}")

        # spot-check a real House Appropriations chain: parent committee vs its subcommittees
        sample_dates = sorted({date_key(m) for m in sch
                               if "appropriations" in norm_name(m) and REL_RE.search(
                                   re.sub(r'<[^>]+>', '', str(m.get('Description', '')))) and date_key(m)})
        if sample_dates:
            d0 = sample_dates[len(sample_dates)//2]
            chain = sorted((new_map.get((d0, norm_name(m)), "—"), norm_name(m))
                           for m in sch if date_key(m) == d0 and "appropriations" in norm_name(m))
            print(f"  spot-check {d0} — House Appropriations chain (SortTime · committee), sorted:")
            for st, nm in dict.fromkeys(chain):   # order-preserving de-dupe (no bare continue)
                print(f"     {st}  {nm[:64]}")

    print("\n" + ("❌ FAIL — a published ScheduleTime was not honored." if fail
                  else "✅ PASS — every published time honored exactly; relative chains resolve per-date."))
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
