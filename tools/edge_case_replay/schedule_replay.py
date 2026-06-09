#!/usr/bin/env python3
"""Phase C — multi-session edge-case replay (proactive, not reactive).

The 2026 bugs (05:00 artifact, midnight-wrap, wrong-anchor, weak plurality) were
found because we happened to look at 2026 data. This replays the PURE
time/schedule/modal functions against MANY past sessions to surface format and
structure variations 2026 alone can't contain — the answer to "who's to say
that's all of them."

It extracts the real functions from calendar_worker.py via AST (no gspread) and,
for each session, pulls the public Schedule API and checks:
  1. TIME-FORMAT COVERAGE — every ScheduleTime either parses to a concrete clock
     OR matches a KNOWN relative grammar. Anything else is an UNRECOGNIZED format
     (a latent parser gap). 06:00 / 23:59 are parse_24h_time's failure sentinels.
  2. ADJOURNMENT MARKERS — collect "[chamber] adjourned" phrasings (the anchor
     the derivation depends on); flag novel phrasings.
  3. MODAL DERIVATION — run _build_standing_schedule_maps + simulate the
     derivation for every committee with a modal; flag out-of-hours results or
     anchors that slip the chamber allowlist (would mis-anchor).
Run: python3 tools/edge_case_replay/schedule_replay.py
"""
import ast, re, sys, json, urllib.request, urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # portable: repo root from this file
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
# === LIS API AUTHORIZATION RULE (single source of truth: lis_authorization.py) ===
# The toolset is authorized for 2025/2026 ONLY; pre-2025 must use legacylis CSV. An
# earlier run of this replay queried the new API for 2020-2024 sessions — outside
# that authorization. It is now restricted to the shared authorized set, enforced by
# the shared guard so it can't drift. For pre-2025 variety, repoint to legacylis CSV.
sys.path.insert(0, ROOT)
from lis_authorization import LIS_API_AUTHORIZED_SESSIONS, assert_lis_authorized
SESSIONS = sorted(LIS_API_AUTHORIZED_SESSIONS, reverse=True)  # only ever authorized sessions
for _s in SESSIONS:
    assert_lis_authorized(_s)  # belt-and-suspenders: hard-fail before any LIS call

def extract(path, names):
    src = open(f"{ROOT}/{path}").read()
    tree = ast.parse(src)
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {"re": re, "datetime": datetime, "timedelta": timedelta, "str": str,
          "_MEETING_HOUR_MIN": 7, "_MEETING_HOUR_MAX": 23}
    exec(compile(ast.Module(body, []), path, "exec"), ns)
    return ns

cw = extract("calendar_worker.py", {
    "_parse_relative_offset_minutes", "_plausible_meeting_time",
    "_build_standing_schedule_maps", "_derive_standing_committee_time",
    "normalize_room_key", "_is_non_concrete_time", "parse_24h_time"})
parse_24h = cw["parse_24h_time"]
build_maps = cw["_build_standing_schedule_maps"]
derive = cw["_derive_standing_committee_time"]

def fetch_schedule(code):
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync?" + urllib.parse.urlencode({"sessionCode": code})
    req = urllib.request.Request(url, headers={"WebAPIKey": API_KEY, "Accept": "application/json"})
    j = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
    return j.get("Schedules") or (j if isinstance(j, list) else [])

KNOWN_REL = ("after", "upon", "recess", "tbd", "tba", "cancel")
def is_concrete(t):
    try:
        datetime.strptime(t.strip().upper().replace(".", ""), "%I:%M %p"); return True
    except Exception:
        return False

print(f"{'SESSION':8s} {'#sched':>7s} {'#TIMEfmt':>8s} {'unparsed':>8s} {'#modal':>6s} {'derive-anomaly':>14s}")
print("-" * 64)
all_unparsed = Counter()
all_adj = Counter()
all_anomaly = []
for code in SESSIONS:
    try:
        sched = fetch_schedule(code)
    except Exception as e:
        print(f"{code:8s}  FETCH ERROR {type(e).__name__}"); continue
    times = Counter(); unparsed = Counter(); adjourned_phrasings = Counter()
    for m in sched:
        t = str(m.get("ScheduleTime") or "").strip()
        owner = str(m.get("OwnerName") or "").strip().lower()
        if "adjourn" in owner:
            adjourned_phrasings[owner[:40]] += 1
        if not t:
            continue
        times[t] += 1
        tl = t.lower()
        # recognized = concrete clock OR a known relative grammar token
        if not is_concrete(t) and not any(k in tl for k in KNOWN_REL):
            unparsed[t] += 1
    for k, v in unparsed.items():
        all_unparsed[k] += v
    for k, v in adjourned_phrasings.items():
        all_adj[k] += v
    # modal derivation across the session
    start = datetime(int(code[:4]), 1, 1); end = datetime(int(code[:4]), 12, 31)
    modal, adj = build_maps(sched, start, end)
    anomalies = 0
    for cm, (pat, n, ch) in modal.items():
        for d in list(adj.keys())[:60]:
            r = derive(cm, cm, "S" if ch == "Senate" else "H", d, modal, adj)
            if r:
                hh = int(r[1].split(":")[0])
                if hh < 7 or hh > 23:
                    anomalies += 1; all_anomaly.append((code, cm[:24], pat[:30], r[0])); break
    print(f"{code:8s} {len(sched):7d} {len(times):8d} {len(unparsed):8d} {len(modal):6d} {anomalies:14d}")

print("\n=== UNRECOGNIZED ScheduleTime formats across all sessions (potential parser gaps) ===")
if all_unparsed:
    for t, n in all_unparsed.most_common(30):
        print(f"  x{n:4d}  {t!r}")
else:
    print("  none — every ScheduleTime is a concrete clock or a known relative grammar")
print(f"\n=== distinct '[chamber] adjourned' marker phrasings (the derivation anchor) ===")
for p, n in all_adj.most_common(20):
    print(f"  x{n:4d}  {p!r}")
print(f"\n=== derivation anomalies (out-of-hours, should be 0 after #76/#100 hardening) ===")
for code, cm, pat, t in all_anomaly[:20]:
    print(f"  {code} {cm} {pat!r} -> {t}")
if not all_anomaly:
    print("  none")
