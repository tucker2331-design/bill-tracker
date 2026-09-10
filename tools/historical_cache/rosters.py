#!/usr/bin/env python3
"""Committee rosters WITH the chair role, for the authorized sessions.

WHY
---
[[testing/venue_effect]] measures rooms as fixed objects: identical text dies four times more often in
some of them. The obvious causal handle underneath is the CHAIR — "this room is hostile" versus "this
person is" — and the calibration cache cannot answer it: `CommitteeMembers.csv` carries only
`CMB_COMNO` + `CMB_MBRNO`, no role. Roster ORDER does not encode it either (tested: the first-listed
member is on the winning side 90.1% against 88.0%, +2.1 points, noise).

The role IS published, structurally, on the API roster: `CommitteeRoleTitle` ∈ {Chair, Vice-Chair,
Member} ([[architecture/roster_and_votes_ingestion]], probe-verified 2026-07-17 on session 20261).

COST AND AUTHORIZATION
----------------------
One committee-list call plus one roster call per committee, per session: ~25 x 2 + 2 = ~52 requests, once,
cached. Every session code passes `assert_lis_authorized` — 2025/2026 only, which bounds any chair
finding to two sessions and means a chair-CHANGE claim needs the change to fall inside that window.
"""
from __future__ import annotations
import gzip, json, os, sys, time, urllib.error, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from lis_authorization import LIS_PUBLIC_API_KEY, assert_lis_authorized   # noqa: E402

BASE = "https://lis.virginia.gov"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va_rosters")
SESSIONS = ("20251", "20261")
DELAY = 1.2


def _get(url, body=None):
    h = {"WebAPIKey": LIS_PUBLIC_API_KEY, "Accept": "application/json",
         "Content-Type": "application/json; charset=utf-8"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h,
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.status, r.read()


def _list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                return v
    return []


def fetch():
    os.makedirs(CACHE, exist_ok=True)
    out = {}
    for code in SESSIONS:
        assert_lis_authorized(code)
        path = os.path.join(CACHE, f"{code}.json.gz")
        if os.path.exists(path):
            print(f"  cached {code}")
            continue
        st, raw = _get(f"{BASE}/Committee/api/GetCommitteeListAsync?sessionCode={code}")
        if st != 200:
            print(f"  FAIL committee list {code}: HTTP {st}")
            return 1
        coms = _list(json.loads(raw))
        print(f"  {code}: {len(coms)} committees")
        rows = []
        miss = 0
        for c in coms:
            cid = c.get("CommitteeID") or c.get("CommitteeId")
            if cid is None:
                miss += 1
                continue
            time.sleep(DELAY)
            try:
                st, raw = _get(f"{BASE}/MembersByCommittee/api/GetCommitteeMembersListAsync"
                               f"?committeeID={cid}&sessionCode={code}")
            except urllib.error.HTTPError as e:
                print(f"    FAIL committee {cid}: HTTP {e.code}")
                miss += 1
                continue
            if st != 200:
                miss += 1
                continue
            for m in _list(json.loads(raw)):
                rows.append({"session": code, "committee_id": cid,
                             "committee_no": c.get("CommitteeNumber"),
                             "committee_name": c.get("Name") or c.get("CommitteeName"),
                             "member_no": m.get("MemberNumber"),
                             "member_name": m.get("MemberDisplayName") or m.get("PatronDisplayName"),
                             "role": m.get("CommitteeRoleTitle"),
                             "role_id": m.get("CommitteeRoleID"),
                             "seq": m.get("VotingSequence")})
        # FAIL LOUD: a committee we could not read is a hole in the roster, not an empty committee.
        if miss:
            print(f"    WARN {miss} committees unreadable for {code} — recorded, not silently skipped")
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump({"rows": rows, "unreadable_committees": miss}, fh)
        print(f"    wrote {len(rows):,} roster rows")
        out[code] = len(rows)
    return 0


def load():
    d = {"rows": [], "unreadable": 0}
    for code in SESSIONS:
        p = os.path.join(CACHE, f"{code}.json.gz")
        if not os.path.exists(p):
            continue
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            j = json.load(fh)
        d["rows"].extend(j["rows"])
        d["unreadable"] += j.get("unreadable_committees", 0)
    return d


if __name__ == "__main__":
    sys.exit(fetch())
