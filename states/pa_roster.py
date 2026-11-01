"""Pennsylvania committee rosters — who sits on each standing committee, from PA's own bulk feeds (2026-11-01).

Feeds (bulk RSS on www.palegis.us, fetched through states/pa_fetch.PoliteFetcher — never a member or committee page):
  * /{house,senate}/rss/committee/assignments — one <item> per MEMBER: <link> carries the structural `memberId`,
    each <parss:Committee position="Chair|Vice Chair|Secretary|"> names a standing committee, <parss:District>.
  * /{house,senate}/rss/session/members — one <item> per member: the same `memberId` in <link>, <parss:Party>.
    Party is joined on memberId (structural), never read out of the assignments title "(D)".

THE ONE NAME JOIN (documented heuristic, Standard #1). PA publishes no committee id. The roster feed names a committee
"Aging & Older Adult Services"; the Bill History export's <committee> names the same room "AGING AND OLDER ADULT
SERVICES". Both are the publisher's own committee identifiers, so the key is exact equality after ONE fixed mapping:
upper case, "&" -> "AND", whitespace collapsed (`committee_key`). Nothing fuzzy, no partial matches.
  * Assumes: the two feeds keep spelling a committee the same apart from "&"/"AND" and case.
  * Breaks if: PA renames a committee in one feed only, or a bill sits in a committee the roster feed omits.
  * Runtime check: `bills_committee_without_roster` (bills whose current committee has no roster row) is published
    in the completeness payload and shown on Health with limit 0 — a drift is visible, never a silent empty list.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Tuple

NS = "{https://www.legis.state.pa.us/RSS}"
CHAMBERS = {"house": "House", "senate": "Senate"}
_MEMBER_ID = re.compile(r"[?&]memberId=(\d+)")
ROSTER_HEADER = ["Chamber", "CommitteeKey", "Committee", "MemberId", "Member", "Party", "District", "Role"]
# The order a committee's members are listed in: officers first, in the source's own ranks, then members.
ROLE_ORDER = {"Chair": 0, "Vice Chair": 1, "Secretary": 2, "": 3}


def committee_key(chamber: str, name: str) -> str:
    """'House' + 'Aging & Older Adult Services' -> 'House AGING AND OLDER ADULT SERVICES' — the same string the
    adapter stores as a bill's `last_committee` ("{chamber} {export <committee>}")."""
    norm = " ".join(name.upper().replace("&", " AND ").split())
    return f"{chamber} {norm}".strip()


def _member_id(item) -> str:
    m = _MEMBER_ID.search(item.findtext("link") or "")
    return m.group(1) if m else ""


def parse_members(xml_bytes: bytes) -> Dict[str, str]:
    """memberId -> party code, from the session/members feed."""
    out = {}
    for it in ET.fromstring(xml_bytes).iter("item"):
        mid = _member_id(it)
        if mid:
            out[mid] = (it.findtext(NS + "Party") or "").strip()
    return out


def _display_name(title: str) -> str:
    # "Abney, Aerion (D) District 19" -> "Aerion Abney". The title is the feed's display string; the party and
    # district in it are NOT used (those come from structural fields). Only the name part is shown.
    name = title.split(" (")[0].strip()
    last, _, first = name.partition(", ")
    return f"{first} {last}".strip() if first else name


def parse_assignments(xml_bytes: bytes, chamber: str, party_by_id: Dict[str, str]) -> Tuple[List[dict], dict]:
    rows, counts = [], {"members": 0, "members_without_id": 0, "members_without_party": 0, "committees_empty": 0}
    for it in ET.fromstring(xml_bytes).iter("item"):
        counts["members"] += 1
        mid = _member_id(it)
        if not mid:
            counts["members_without_id"] += 1   # counted; such a member still appears, by name only
        party = party_by_id.get(mid, "") if mid else ""
        if not party:
            counts["members_without_party"] += 1
        who = _display_name(it.findtext("title") or "")
        district = (it.findtext(NS + "District") or "").strip().lstrip("0")
        for c in it.findall(NS + "Committee"):
            name = (c.text or "").strip()
            if not name:
                counts["committees_empty"] += 1
                continue   # counted (roster_committee_names_empty): an empty element names no room to place
            rows.append({"chamber": chamber, "key": committee_key(chamber, name), "committee": name,
                         "member_id": mid, "member": who, "party": party, "district": district,
                         "role": (c.get("position") or "").strip()})
    return rows, counts


def build_roster(feeds: Dict[str, Dict[str, bytes]]) -> Tuple[List[dict], dict]:
    """feeds = {"house": {"assignments": b"...", "members": b"..."}, "senate": {...}}."""
    rows: List[dict] = []
    stats = {"roster_members": 0, "roster_members_without_id": 0, "roster_members_without_party": 0,
             "roster_committee_names_empty": 0}
    for ch, f in feeds.items():
        chamber = CHAMBERS[ch]
        r, c = parse_assignments(f["assignments"], chamber, parse_members(f["members"]))
        rows += r
        stats["roster_members"] += c["members"]
        stats["roster_members_without_id"] += c["members_without_id"]
        stats["roster_members_without_party"] += c["members_without_party"]
        stats["roster_committee_names_empty"] += c["committees_empty"]
    rows.sort(key=lambda x: (x["key"], ROLE_ORDER.get(x["role"], 9), x["member"]))
    stats["roster_rows"] = len(rows)
    stats["roster_committees"] = len({x["key"] for x in rows})
    return rows, stats


def coverage(records: Iterable[dict], rows: List[dict]) -> dict:
    """The runtime check on the name join: bills whose current committee has no roster."""
    keys = {x["key"] for x in rows}
    missing = sorted({r["last_committee"] for r in records if r.get("last_committee") and r["last_committee"] not in keys})
    n = sum(1 for r in records if r.get("last_committee") and r["last_committee"] not in keys)
    return {"bills_committee_without_roster": n, "committees_without_roster_sample": missing[:10]}


def roster_rows(rows: List[dict]) -> List[List[str]]:
    return [ROSTER_HEADER] + [[x["chamber"], x["key"], x["committee"], x["member_id"], x["member"], x["party"],
                               x["district"], x["role"]] for x in rows]


def run_roster(fetcher, urls: Dict[str, str]):
    feeds = {ch: {"assignments": fetcher.get(urls["committee_assignments"].format(chamber=ch)),
                  "members": fetcher.get(urls["members"].format(chamber=ch))} for ch in CHAMBERS}
    return build_roster(feeds)
