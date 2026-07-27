#!/usr/bin/env python3
"""Goldens for committee-roster ingest. Offline: fake HTTP, no network, no credentials."""
import sys

sys.path.insert(0, "tools/roster")
import roster as R  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        print(f"      got: {got!r}  want: {want!r}")
        FAILURES.append(label)


class Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p


MEMBERS = {"ShallowMembers": [
    {"MemberNumber": "H0285", "MemberID": 170, "ListDisplayName": "Hayes, C.E.",
     "PartyCode": "D", "ChamberCode": "H", "MemberStatus": "Active"},
    {"MemberNumber": "H0301", "MemberID": 171, "ListDisplayName": "Newman, S.",
     "PartyCode": "R", "ChamberCode": "H", "MemberStatus": "Active"},
    {"MemberNumber": "H0999", "MemberID": 999, "ListDisplayName": "Nomatter, X.",
     "PartyCode": "", "ChamberCode": "H", "MemberStatus": "Active"},
]}
COMMITTEES = {"Committees": [
    {"CommitteeID": 21, "CommitteeNumber": "H21", "Name": "Communications", "ChamberCode": "H"},
]}
ROSTER = {"MemberList": [
    {"MemberNumber": "H0285", "MemberID": 170, "MemberDisplayName": "Hayes",
     "CommitteeRoleTitle": "Chair", "CommitteeRoleID": 3, "VotingSequence": 1},
    {"MemberNumber": "H0301", "MemberID": 171, "MemberDisplayName": "Newman",
     "CommitteeRoleTitle": "Member", "CommitteeRoleID": 1, "VotingSequence": 2},
    {"MemberNumber": "H0999", "MemberID": 999, "MemberDisplayName": "Nomatter",
     "CommitteeRoleTitle": "Member", "CommitteeRoleID": 1, "VotingSequence": 3},
]}
# The REAL shape, verified live 2026-07-27: the detail payload is WRAPPED under "Members", not flat.
# A flat fake here is what let the wrapper bug ship — the golden passed while live data returned nothing.
DETAIL = {"Members": [{"MemberID": 170, "DistrictName": "91st", "PartyCode": "D"}], "Success": True}


class FakeHTTP:
    def __init__(self, roster=ROSTER, status=200, detail=DETAIL):
        self.calls, self._roster, self._status, self._detail = [], roster, status, detail

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if "GetMemberListAsync" in url:
            return Resp(MEMBERS, self._status)
        if "GetMemberByIdAsync" in url:
            return Resp(self._detail, self._status)
        if "getcommitteelistasync" in url:
            return Resp(COMMITTEES, self._status)
        return Resp(self._roster, self._status)


print("— authorization is asserted BEFORE any request —")
# Catch the SPECIFIC exception, not any. A bare `except Exception` here would pass even if construction
# failed for an unrelated reason (a typo, a missing import) — it would assert "something went wrong"
# rather than "the authorization gate refused it". Our own Semgrep house rule flagged the broad form on
# this very file, and narrowing it made the test stricter rather than merely quieter.
try:
    R.RosterFetcher("20241", FakeHTTP())
    blocked = False
except PermissionError:
    blocked = True
check("a pre-2025 session is refused at construction, by the AUTHORIZATION gate specifically", blocked, True)
check("an authorized session constructs", bool(R.RosterFetcher("20261", FakeHTTP())), True)

print("\n— the whole chamber in ONE call —")
http = FakeHTTP()
f = R.RosterFetcher("20261", http)
mem = f.members()
check("members keyed by MemberNumber (the id VOTE.CSV also uses)", sorted(mem), ["H0285", "H0301", "H0999"])
check("party captured", mem["H0285"]["party"], "D")
check("one request for the whole chamber", len(http.calls), 1)
check("every request carries the session code",
      all(c[1].get("sessionCode") == "20261" for c in http.calls), True)

print("\n— THE CHAIR (the field the whip board hangs on) —")
f2 = R.RosterFetcher("20261", FakeHTTP())
assigns = f2.roster_for(21)
ch = R.chair_of(assigns)
check("the chair is identified structurally", ch["member_number"], "H0285")
check("...by role, not by seniority guessing", ch["role"], "Chair")
check("a committee with NO chair returns None, not a guess",
      R.chair_of([{"role": "Member", "member_number": "H1"}]), None)

print("\n— an unseen role SURFACES, never flattens —")
odd = {"MemberList": [{"MemberNumber": "H1", "CommitteeRoleTitle": "Co-Chair", "CommitteeRoleID": 9}]}
f3 = R.RosterFetcher("20261", FakeHTTP(roster=odd))
f3.roster_for(21)
check("an unknown role is counted", f3.stats["unknown_roles"], 1)
check("...and named, so it can be added deliberately", sorted(f3.unknown_roles), ["Co-Chair"])

print("\n— party arithmetic —")
split = R.party_split(assigns, mem)
check("R and D counted", (split.get("D"), split.get("R")), (1, 1))
check("a member with NO party is counted separately, never folded into a side",
      split.get("unknown"), 1)

print("\n— honest failure modes —")
f4 = R.RosterFetcher("20261", FakeHTTP(status=500))
check("an upstream error yields no members", f4.members(), {})
check("...and no roster", f4.roster_for(21), [])
check("the miss is COUNTED, not silent", f4.stats["committee_miss"] >= 1, True)

f5 = R.RosterFetcher("20261", FakeHTTP(detail={"Members": [{"MemberID": 170}]}))  # wrapped, no district
m5 = f5.members()
f5.enrich_districts(m5, only={"H0285"})
check("a missing district is counted as a miss, not left looking populated",
      f5.stats["member_detail_miss"], 1)
check("...and the field stays empty rather than guessed", m5["H0285"]["district"], "")

print("\n— district enrichment is SCOPED to who we show —")
http6 = FakeHTTP()
f6 = R.RosterFetcher("20261", http6)
m6 = f6.members()
f6.enrich_districts(m6, only={"H0285"})
detail_calls = [c for c in http6.calls if "GetMemberByIdAsync" in c[0]]
check("only the requested member is enriched (not the whole chamber)", len(detail_calls), 1)
check("the district lands", m6["H0285"]["district"], "91st")

print("\n— the runaway guard —")
saved = R.REQUEST_CAP
R.REQUEST_CAP = 1
try:
    f7 = R.RosterFetcher("20261", FakeHTTP())
    f7.members()
    try:
        f7.committees()
        raised = False
    except R.RosterRequestCapExceeded:
        raised = True
    check("exceeding the per-run cap RAISES", raised, True)
    check("it is a BaseException (a broad except cannot swallow a runaway)",
          issubclass(R.RosterRequestCapExceeded, BaseException)
          and not issubclass(R.RosterRequestCapExceeded, Exception), True)
finally:
    R.REQUEST_CAP = saved

print("\n— a full snapshot —")
f8 = R.RosterFetcher("20261", FakeHTTP())
snap = R.snapshot(f8)
check("session travels with the snapshot", snap["session_code"], "20261")
check("committees captured", len(snap["committees"]), 1)
check("rosters captured", len(snap["rosters"][21]), 3)
check("stats are reported honestly", snap["stats"]["assignments"], 3)
check("request count is visible", snap["requests_made"] > 0, True)

print()
if FAILURES:
    print(f"❌ {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("✅ all roster-ingest goldens pass")
