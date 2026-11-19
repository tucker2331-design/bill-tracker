"""California committee rosters — who sits on the committee a bill is in, for the War Room's bill page.

pubinfo carries no committee membership. The source is Open States' `people` repository (public domain, CC0 — "all
copyright waived"), read as a plain git checkout of `data/ca` (no API, no key): `committees/*.yml` (chamber
lower/upper/legislature, name, members with role) and `legislature/*.yml` (each sitting member's party and district).
Open States maintains it from the Assembly's and Senate's own committee pages; the CI job checks it out fresh each run.

THE JOIN (measured on 2025-26: every one of the 4,846 bills sitting in a committee joined). A roster committee is keyed
exactly as the adapter keys a bill's `last_committee` — "{house} {pubinfo committee name}" ("Assembly Appropriations").
Open States' (chamber, name) meets pubinfo's (house, LONG_DESCRIPTION) on a normalised name (case, "&" = "and",
commas, spacing). This is a NAME join between two sources, so it is CHECKED every run: bills whose committee has no
roster are counted (`bills_committee_without_roster`, a Health check, limit 0). Open States committees that hear no
bills (select and most joint committees) are counted (`roster_committees_not_in_pubinfo`), not written.

A broken or missing checkout never holds back the bills: the job publishes `roster_status` and leaves the old tab.
"""
from __future__ import annotations

import collections
import datetime
import glob
import os
from typing import Any, Counter, Dict, Iterable, List, Optional, Tuple

from .ca_committees import Committees
from .pa_roster import ROSTER_HEADER   # the shared Committee_Roster layout the site reads

CHAMBER = {"lower": "Assembly", "upper": "Senate", "legislature": "Joint"}
# Open States' role words (measured 2026-11-19) -> what the page shows; a plain member shows no role (as for PA)
ROLE = {"chair": "Chair", "co-chair": "Co-Chair", "vice chair": "Vice Chair", "vice-chair": "Vice Chair",
        "democratic alternate": "Democratic Alternate", "republican alternate": "Republican Alternate", "member": ""}
ROLE_ORDER = {"Chair": 0, "Co-Chair": 0, "Vice Chair": 1, "": 2, "Democratic Alternate": 3, "Republican Alternate": 3}
PARTY = {"Democratic": "D", "Republican": "R", "Independent": "I"}


def norm(name: str) -> str:
    """'Aging and Long-Term Care' and 'Aging and Long Term Care' meet; so do 'Growth, & Household' / 'Growth and
    Household' and an Oxford comma or none."""
    return " ".join(name.upper().replace("&", " AND ").replace(",", " ").replace("-", " ").split())


def _load(path: str, required: Tuple[str, ...]) -> Optional[dict]:
    """One Open States file as a dict carrying `required`, or None when it cannot be read (the caller COUNTS it)."""
    import yaml
    try:
        with open(path, encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(d, dict) or any(not d.get(k) for k in required):
        return None
    return d


def load_people(ca_dir: str, today: datetime.date) -> Tuple[Dict[str, Tuple[str, str]], List[str]]:
    """ocd-person id -> (party letter, district) for every member with a CURRENT legislative role; plus the files that
    could not be read (counted by the caller, never silently dropped)."""
    out, bad = {}, []
    for f in sorted(glob.glob(os.path.join(ca_dir, "legislature", "*.yml"))):
        d = _load(f, ("id",))
        if d is None:
            bad.append(os.path.basename(f))
            continue
        roles = [r for r in (d.get("roles") or []) if isinstance(r, dict)]
        current = [r for r in roles if r.get("type") in ("lower", "upper")
                   and (not r.get("end_date") or str(r["end_date"]) >= today.isoformat())]
        parties = [p["name"] for p in (d.get("party") or []) if isinstance(p, dict) and p.get("name")
                   and (not p.get("end_date") or str(p["end_date"]) >= today.isoformat())]
        party = parties[0] if parties else ""
        out[d["id"]] = (PARTY.get(party, party), str(current[0].get("district", "")) if current else "")
    return out, bad


def build_roster(ca_dir: str, coms: Committees, today: datetime.date) -> Tuple[List[dict], dict]:
    files = sorted(glob.glob(os.path.join(ca_dir, "committees", "*.yml")))
    if not files:
        raise FileNotFoundError(f"no committee files under {ca_dir}/committees — the Open States checkout is missing")
    people, bad_people = load_people(ca_dir, today)
    # pubinfo committees, keyed the way a bill's last_committee is: "{house} {name}" -> that exact display string
    pub: Dict[str, Tuple[str, str]] = {}
    for code, name in coms.names.items():
        h = coms.house.get(code)
        if h:
            pub.setdefault(f"{h} {norm(name)}", (f"{h} {name}", name))
    stats: Counter[str] = collections.Counter()
    unmatched: List[str] = []
    rows: List[dict] = []
    bad_files: List[str] = list(bad_people)
    for f in files:
        d = _load(f, ("name", "chamber"))
        if d is None:
            bad_files.append(os.path.basename(f))      # one unreadable file never sinks the roster: counted, Health
            continue
        house = CHAMBER.get(d["chamber"], d["chamber"])
        match = pub.get(f"{house} {norm(d['name'])}")
        if match is None:
            stats["roster_committees_not_in_pubinfo"] += 1     # select / joint committees: they hear no bills
            unmatched.append(f"{house} {d['name']}")
            continue
        stats["roster_committees"] += 1
        for m in (d.get("members") or []):
            if not isinstance(m, dict) or not m.get("name"):
                stats["roster_members_unreadable"] += 1
                continue
            mapped: Optional[str] = ROLE.get((m.get("role") or "member").lower())
            if mapped is None:
                stats["roster_roles_unrecognised"] += 1        # shown as the source wrote it, counted
            role = mapped if mapped is not None else str(m.get("role", ""))
            party, district = people.get(m.get("person_id", ""), ("", ""))
            if m.get("person_id") and m["person_id"] not in people:
                stats["roster_members_unresolved"] += 1        # no current legislator file: party/district blank
            # key = exactly a bill's last_committee ("Assembly Health"); chamber = the contract key (the site shows
            # its label); committee = the name alone ("Health")
            rows.append({"chamber": "House" if house == "Assembly" else house, "key": match[0], "committee": match[1],
                         "member_id": m.get("person_id", ""), "member": m.get("name", ""), "party": party,
                         "district": district, "role": role})
    rows.sort(key=lambda x: (x["key"], ROLE_ORDER.get(x["role"], 3), x["member"]))
    out: Dict[str, Any] = {k: stats.get(k, 0) for k in ("roster_committees", "roster_committees_not_in_pubinfo",
                                        "roster_members_unresolved", "roster_roles_unrecognised",
                                        "roster_members_unreadable")}
    out["roster_files_unreadable"] = len(bad_files)
    out["roster_files_unreadable_sample"] = bad_files[:10]
    out.update({"roster_seats": len(rows), "roster_committees_not_in_pubinfo_sample": sorted(unmatched)[:10],
                "roster_source": "Open States people data (CC0), data/ca"})
    return rows, out


def coverage(records: Iterable[dict], rows: List[dict]) -> dict:
    """The runtime check on the name join: bills whose current committee has no roster."""
    keys = {x["key"] for x in rows}
    miss = [r["last_committee"] for r in records if r.get("last_committee") and r["last_committee"] not in keys]
    return {"bills_committee_without_roster": len(miss), "committees_without_roster_sample": sorted(set(miss))[:10]}


def roster_rows(rows: List[dict]) -> List[List[str]]:
    return [ROSTER_HEADER] + [[x["chamber"], x["key"], x["committee"], x["member_id"], x["member"], x["party"],
                               x["district"], x["role"]] for x in rows]
