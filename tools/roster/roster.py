#!/usr/bin/env python3
"""Committee roster + member ingest — the data under the War Room's whip board.

WHY THIS EXISTS: the War Room mockup's entire "FROM LIS · verified" column group (who sits on the committee,
who CHAIRS it, each member's party and district) sits on data we ingest nowhere. This was the hard blocker
under the whole feature. Every field below was probe-confirmed against the live API on 2026-07-17 and is
STRUCTURAL — a code or id, never parsed prose (Standard #3).

AUTHORIZATION: gated through `lis_authorization` like every other LIS caller. 2025/2026 sessions only.

SAFETY (knowledge/lis_api_safety.md): rosters are near-static WITHIN a session — chairs and membership change
rarely — so this is a per-session backfill with a slow re-check, never a per-cycle poll. One call fetches the
whole chamber's member map; committees are then one call each. A hard per-run cap guards a runaway.

WHAT IT DELIBERATELY DOES NOT DO: votes. Those are already in `VOTE.CSV`, a blob the calendar worker fetches
every cycle — 318,282 member-vote pairs measured 2026-07-27 — so pulling them per-member would be ~147
redundant API calls for bytes we already have (architecture/roster_and_votes_ingestion.md §W5).
"""
from __future__ import annotations

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MEMBER_LIST_URL = "https://lis.virginia.gov/Member/api/GetMemberListAsync"
MEMBER_BY_ID_URL = "https://lis.virginia.gov/Member/api/GetMemberByIdAsync"
COMMITTEE_LIST_URL = "https://lis.virginia.gov/Committee/api/getcommitteelistasync"
COMMITTEE_MEMBERS_URL = "https://lis.virginia.gov/MembersByCommittee/api/GetCommitteeMembersListAsync"

REQUEST_CAP = int(os.environ.get("ROSTER_REQUEST_CAP", "400"))

# The role vocabulary LIS actually emits, measured on H21 (Chair 1 · Vice-Chair 1 · Member 29). Treated as a
# CLOSED set: an unseen role is surfaced, never silently mapped to "Member", because a new leadership role we
# quietly flatten would make the whip board wrong about who controls the docket.
KNOWN_ROLES = frozenset({"Chair", "Vice-Chair", "Member"})


class RosterRequestCapExceeded(BaseException):
    """BaseException so a broad `except Exception` cannot swallow a runaway (as with the other caps here)."""


def _first_list(payload, *keys):
    """LIS wraps its lists under varying keys. Try the known ones, then any single list of dicts. Returns []
    on an unexpected shape rather than guessing — the caller counts that as a source miss."""
    if not isinstance(payload, dict):
        return []
    for k in keys:
        v = payload.get(k)
        if isinstance(v, list):
            return v
    for v in payload.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    return []


class RosterFetcher:
    """HTTP is injected so every path is testable offline."""

    def __init__(self, session_code, http_get, headers=None):
        from lis_authorization import assert_lis_authorized
        assert_lis_authorized(str(session_code))      # asserted BEFORE any request can be issued
        self.session_code = str(session_code)
        self._get = http_get
        self._headers = headers or {}
        self.requests_made = 0
        self.stats = {"members": 0, "committees": 0, "assignments": 0,
                      "unknown_roles": 0, "member_detail_miss": 0, "committee_miss": 0}
        self.unknown_roles: set = set()

    def _request(self, url, params):
        if self.requests_made >= REQUEST_CAP:
            raise RosterRequestCapExceeded(
                f"roster ingest hit its per-run cap ({REQUEST_CAP}); aborting rather than hammering LIS.")
        self.requests_made += 1
        return self._get(url, params=params, headers=self._headers, timeout=20)

    def members(self):
        """The WHOLE chamber in one call — `ShallowMembers` carries party/chamber/status, so a per-member
        detail call is only needed for district. Keyed by MemberNumber (H0285), the id VOTE.CSV also uses,
        so the join to votes needs no mapping table."""
        r = self._request(MEMBER_LIST_URL, {"sessionCode": self.session_code})
        if getattr(r, "status_code", 0) != 200:
            return {}
        out = {}
        for m in _first_list(r.json(), "ShallowMembers", "MemberList", "Members"):
            num = str(m.get("MemberNumber") or "").strip()
            if not num:
                continue
            out[num] = {
                "member_number": num,
                "member_id": m.get("MemberID"),
                "name": (m.get("ListDisplayName") or m.get("MemberDisplayName") or "").strip(),
                "patron_name": (m.get("PatronDisplayName") or "").strip(),
                "party": (m.get("PartyCode") or "").strip(),      # the party-math column
                "chamber": (m.get("ChamberCode") or "").strip(),
                "status": (m.get("MemberStatus") or "").strip(),
                "district": "",                                    # filled by enrich_districts()
            }
        self.stats["members"] = len(out)
        return out

    def enrich_districts(self, members, only=None):
        """District needs the per-member detail call. `only` restricts it to the members we actually show
        (committee members), so a full-chamber district pull is opt-in rather than automatic."""
        targets = [m for k, m in members.items() if only is None or k in only]
        for m in targets:
            if m.get("member_id") is None:
                self.stats["member_detail_miss"] += 1
                continue
            r = self._request(MEMBER_BY_ID_URL, {"memberId": m["member_id"], "sessionCode": self.session_code})
            if getattr(r, "status_code", 0) != 200:
                self.stats["member_detail_miss"] += 1
                continue
            # The detail payload is WRAPPED: {"Members": [ {...} ], "Success": ...} — not the flat object.
            # An earlier version read the top level directly and silently produced empty districts on live
            # data while its golden (built on a flat fake) passed. The miss counter is what caught it; the
            # fix is to reuse the same wrapper-tolerant unwrap as every other call here.
            rows = _first_list(r.json(), "Members", "MemberList")
            d = rows[0] if rows else {}
            m["district"] = str(d.get("DistrictName") or "").strip()
            if not m["district"]:
                self.stats["member_detail_miss"] += 1
        return members

    def committees(self):
        r = self._request(COMMITTEE_LIST_URL, {"sessionCode": self.session_code})
        if getattr(r, "status_code", 0) != 200:
            self.stats["committee_miss"] += 1
            return []
        out = []
        for c in _first_list(r.json(), "Committees", "CommitteeList"):
            cid = c.get("CommitteeID")
            if cid is None:
                continue
            out.append({"committee_id": cid,
                        "number": (c.get("CommitteeNumber") or "").strip(),   # H01/S02 — the structural code
                        "name": (c.get("Name") or "").strip(),
                        "chamber": (c.get("ChamberCode") or "").strip(),
                        "parent_id": c.get("ParentCommitteeID")})
        self.stats["committees"] = len(out)
        return out

    def roster_for(self, committee_id):
        """Who sits on this committee, and in what ROLE. `committeeID` is required — passing only
        `committeeNumber` returns HTTP 400 (probed 2026-07-17)."""
        r = self._request(COMMITTEE_MEMBERS_URL,
                          {"committeeID": committee_id, "sessionCode": self.session_code})
        if getattr(r, "status_code", 0) != 200:
            self.stats["committee_miss"] += 1
            return []
        out = []
        for m in _first_list(r.json(), "MemberList", "CommitteeMembers", "Members"):
            role = (m.get("CommitteeRoleTitle") or "").strip()
            if role and role not in KNOWN_ROLES:
                # Surface, never flatten: a new leadership role silently mapped to "Member" would make the
                # whip board wrong about who controls whether a bill is even heard.
                self.unknown_roles.add(role)
                self.stats["unknown_roles"] += 1
            out.append({
                "committee_id": committee_id,
                "member_number": (m.get("MemberNumber") or "").strip(),
                "member_id": m.get("MemberID"),
                "name": (m.get("MemberDisplayName") or "").strip(),
                "role": role,
                "role_id": m.get("CommitteeRoleID"),      # structural — never parse the title
                "voting_sequence": m.get("VotingSequence"),
                "seniority": m.get("Seniority"),
            })
        self.stats["assignments"] += len(out)
        return out


def chair_of(assignments):
    """The single most important field on the whip board: the chair decides whether a bill is heard at all.
    Returns None when LIS lists no chair — ABSENT, never a guess at the most senior member."""
    for a in assignments:
        if a.get("role") == "Chair":
            return a
    return None


def party_split(assignments, members):
    """The committee's party arithmetic — the thing that turns "need 8 of 15" from decoration into strategy.
    Members whose party is unknown are counted SEPARATELY rather than folded into a side, so the totals can
    never quietly imply a majority we cannot support."""
    counts: dict = {}
    for a in assignments:
        p = (members.get(a.get("member_number"), {}) or {}).get("party", "")
        counts[p or "unknown"] = counts.get(p or "unknown", 0) + 1
    return counts


def snapshot(fetcher, committee_ids=None, with_districts=True):
    """One session's roster picture. Returns the shape the War Room needs plus honest miss counters."""
    members = fetcher.members()
    committees = fetcher.committees()
    if committee_ids is not None:
        committees = [c for c in committees if c["committee_id"] in set(committee_ids)]
    rosters = {}
    seen: set = set()
    for c in committees:
        assigns = fetcher.roster_for(c["committee_id"])
        rosters[c["committee_id"]] = assigns
        seen.update(a["member_number"] for a in assigns if a.get("member_number"))
    if with_districts:
        fetcher.enrich_districts(members, only=seen)
    return {
        "session_code": fetcher.session_code,
        "fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "members": members,
        "committees": committees,
        "rosters": rosters,
        "stats": dict(fetcher.stats),
        "unknown_roles": sorted(fetcher.unknown_roles),
        "requests_made": fetcher.requests_made,
    }
