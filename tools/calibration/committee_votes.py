#!/usr/bin/env python3
"""COMMITTEE and SUBCOMMITTEE roll calls, linked to bills — the venue Open States does not carry.

WHY THIS EXISTS
---------------
[[testing/persuadability]] measures how legislators vote on the FLOOR, because that is all Open States has
for Virginia: 0 of its 69,422 roll calls carry a committee classification. But most bills never reach a
floor. They die in committee, and more quietly still in SUBCOMMITTEE, which is the least-observed room in
the building and the one a lobbyist most needs to understand.

LIS publishes those votes itself, in `Vote.csv`, and this project had never opened the file.

THE THREE-WAY JOIN — verified, not assumed (2026-08-07, session 241)
---------------------------------------------------------------------
    Vote.csv        "H0101V0001","H0317","Y","H0327","Y",...   headerless, positional member/response pairs
    History.csv     Bill_id -> History_refid                    **9,283 of 9,283 refids match a Vote.csv id**
    Members.csv     MBR_MBRID + chamber                         140 of 141 match after zero-normalisation

`History_description` names the venue in the same row ("H Subcommittee recommends reporting (5-Y 3-N)",
"H Reported from Labor and Commerce (12-Y 10-N)", "H VOTE: Passage (51-Y 49-N)"), so committee, subcommittee
and floor are separable WITHOUT parsing the vote id's internal structure.

  The vote id DOES encode venue — "H0101V0001" is House committee 01, subcommittee 01 — but that is a
  positional convention nobody has documented to us, so it is used only as a cross-check on the
  description, never as the primary source. If the two ever disagree the row is counted, not guessed.

MEMBER IDS ARE ZERO-PADDED IN ONE FILE AND NOT THE OTHER
---------------------------------------------------------
`Members.csv` writes `H108`; `Vote.csv` writes `H0108`. Joined raw, **0 of 141 members match** — a total
join failure that produces an empty result rather than an error, which is the exact shape of the
`20251` vs `2025` bug in [[failures/assumptions_audit]] #114. Normalised, 140 of 141 match; the one that
does not is `H0000`, a placeholder, and it is counted.

COVERAGE LIMIT — state it before using any number
--------------------------------------------------
Only the sessions in the legacy CSV cache carry these files: **2023 and 2024**. The modern blob publishes
`VOTE.CSV` for authorized sessions (2025/2026) and the calendar worker already consumes it, so extending
forward is a fetch, not a new capability. Pre-2023 does not exist on any route we have.
"""
from __future__ import annotations

import collections
import csv
import io
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "historical_cache"))

# PINNED per session, and the two ERAS do not agree on anything but the idea. Not discovered by a loop: a
# session without these files must be an explicit absence, never a silently empty result.
#
#   file names   legacy writes Vote.csv / History.csv / Members.csv
#                modern writes VOTE.CSV / HISTORY.CSV / Members.csv   (casing is PER FILE, no rule)
#   member key   legacy Members.csv has MBR_MBRID (H108, unpadded) -> needs normalising against the
#                zero-padded ids in the vote rows; modern has NO MBR_MBRID at all, only MBR_MBRNO,
#                which is already padded and matches raw. Reading MBR_MBRID on a modern file is a KeyError,
#                not a silent miss — which is the good outcome.
#   vote id      legacy "H0101V0001" ENCODES the venue (chamber, committee, subcommittee) and gives a free
#                structural cross-check on the description. Modern "2510002" encodes none of it, so the
#                cross-check is UNAVAILABLE there and is recorded as unavailable rather than faked.
#   refid        legacy History_refid holds vote ids only. Modern OVERLOADS the column — bill numbers,
#                PDF filenames, subcommittee codes AND vote ids all appear in it, so a modern refid counts
#                only when it actually matches a vote id.
SESSIONS = {
    "231":   {"year": "2023", "era": "legacy",
              "vote": "Vote.csv", "history": "History.csv", "members": "Members.csv",
              "member_col": "MBR_MBRID", "id_encodes_venue": True},
    "241":   {"year": "2024", "era": "legacy",
              "vote": "Vote.csv", "history": "History.csv", "members": "Members.csv",
              "member_col": "MBR_MBRID", "id_encodes_venue": True},
    "20251": {"year": "2025", "era": "modern",
              "vote": "VOTE.CSV", "history": "HISTORY.CSV", "members": "Members.csv",
              "member_col": "MBR_MBRNO", "id_encodes_venue": False},
    "20261": {"year": "2026", "era": "modern",
              "vote": "VOTE.CSV", "history": "HISTORY.CSV", "members": "Members.csv",
              "member_col": "MBR_MBRNO", "id_encodes_venue": False},
}

_MID = re.compile(r"^([HS])0*(\d+)$")


def _norm_member(mid: str) -> str:
    """`Members.csv` writes H108, `Vote.csv` writes H0108. Raw, they join 0 of 141."""
    m = _MID.match((mid or "").strip())
    return f"{m.group(1)}{int(m.group(2))}" if m else (mid or "").strip()


def _venue(desc: str) -> str:
    """Which room this vote happened in, from the history description LIS writes beside it.

    ORDER IS THE WHOLE RULE, most specific first: a subcommittee line also contains the word "committee",
    and a committee line ("Reported from Finance") sits in the same sentence space as a floor line
    ("Passed House"). Checked in the wrong order every rule collapses into one bucket.

    A PRECEDENCE BUG lived in the first version: `if "vote:" in d or "passage" in d and "reported" not in d`
    parses as `("vote:" in d) or (("passage" in d) and ...)`, and it looked for "passage" where LIS
    actually writes "passed". 4,915 modern floor votes fell through to "other" as a result — "Read third
    time and passed House", "Passed Senate", "Constitutional reading dispensed".

    Text-derived, therefore INTERNAL DIAGNOSTIC ONLY (Standard #3): it never reaches a lobbyist-facing
    surface, and in the legacy era it is cross-checked against the vote id's own structure.
    """
    d = (desc or "").lower()
    if "subcommittee" in d or " sub:" in d:
        return "subcommittee"
    # A COMMITTEE ROOM acts ON a bill and names itself: "Reported from Finance", "Passed by indefinitely
    # in Courts of Justice". These must be tested BEFORE the floor markers, because "passed by
    # indefinitely in X" contains "passed".
    for marker in ("reported from", "passed by indefinitely in", "tabled in", "stricken from docket by",
                   "continued to", "left in", "incorporated by", "failed to report", "rereferred to",
                   "referred to committee", "assigned "):
        if marker in d:
            return "committee"
    for marker in ("passed house", "passed senate", "read third time", "constitutional reading",
                   "agreed to by house", "agreed to by senate", "concurred in", "vote:",
                   "failed to pass", "defeated by", "conference report agreed"):
        if marker in d:
            return "floor"
    return "other"


def _venue_from_id(vid: str) -> str:
    """Structural cross-check. `H0101V0001` = chamber H, committee 01, subcommittee 01; `H14V0011` has no
    subcommittee segment; `HV0202` has neither, i.e. the floor."""
    body = (vid or "").split("V")[0]
    digits = len(body) - 1
    if digits == 0:
        return "floor"
    if digits <= 2:
        return "committee"
    return "subcommittee"


def load():
    from fetch import read_cached

    out = {"votes": [], "events": {}, "members": {}, "counters": collections.Counter()}
    for code, cfg in SESSIONS.items():
        year = cfg["year"]
        members = {}
        for r in csv.DictReader(io.StringIO(read_cached(code, cfg["members"]))):
            members[_norm_member(r[cfg["member_col"]])] = {
                "name": r["MBR_NAME"].strip(), "chamber": r["MBR_HOU"].strip(), "session": year}
        out["members"].update({(year, k): v for k, v in members.items()})

        # bill + venue for each vote id
        ref = {}
        for r in csv.DictReader(io.StringIO(read_cached(code, cfg["history"]))):
            rid = (r.get("History_refid") or "").strip()
            if not rid:
                continue
            ref[rid] = {"bill": r["Bill_id"].strip(), "date": r.get("History_date", "").strip(),
                        "desc": r.get("History_description", "").strip()}

        for line in read_cached(code, cfg["vote"]).splitlines():
            if not line.strip():
                continue
            parts = [p.strip().strip('"') for p in line.split(",")]
            vid = parts[0]
            if not vid:
                continue
            meta = ref.get(vid)
            if meta is None:
                # A vote LIS records but no history row references. Counted, never dropped silently:
                # a rising count means the join is decaying.
                out["counters"]["vote_without_history_row"] += 1
                continue
            venue = _venue(meta["desc"])
            structural = _venue_from_id(vid) if cfg["id_encodes_venue"] else None
            if structural is None:
                # Modern vote ids carry no venue. The cross-check is UNAVAILABLE, not passing — recorded
                # so nobody later reads "no disagreements" as "verified".
                if venue == "other":
                    out["counters"][f"venue_unknown_no_structural_check_{cfg['era']}"] += 1
                    continue
            elif venue == "other":
                venue = structural
                out["counters"]["venue_from_id_fallback"] += 1
            elif venue != structural:
                out["counters"][f"venue_disagreement_{venue}_vs_{structural}"] += 1
            pairs = parts[1:]
            cast = []
            for i in range(0, len(pairs) - 1, 2):
                mid, resp = _norm_member(pairs[i]), pairs[i + 1].upper()
                if not mid or resp not in ("Y", "N"):
                    continue
                if mid not in members:
                    # Measured: the ONLY unmatched id is H0 (from the "H0000" placeholder), 1,760 times.
                    # Tracked per-id so a genuinely missing legislator could never hide behind it.
                    out["counters"][f"member_id_not_in_roster:{mid}"] += 1
                    continue
                cast.append((mid, resp))
            if not cast:
                # LIS records the vote id but no member pairs for 1,274 of 9,559 rows in 241 — the roll
                # call exists, the detail was never published. A legitimate absence, distinguished from a
                # parse failure so neither can hide inside the other.
                out["counters"]["roll_call_published_without_member_detail"] += 1
                continue
            yes = sum(1 for _m, r_ in cast if r_ == "Y")
            out["events"][(year, vid)] = {
                "session": year, "bill": meta["bill"], "date": meta["date"], "desc": meta["desc"],
                "venue": venue, "structural_venue": structural,
                "chamber": vid[0] if vid[0] in "HS" else (members[cast[0][0]]["chamber"] if cast else "?"),
                "era": cfg["era"],
                "yes": yes, "no": len(cast) - yes, "n": len(cast),
                "margin": abs(yes - (len(cast) - yes)),
                "result": "pass" if yes > len(cast) - yes else "fail",
            }
            for mid, resp in cast:
                out["votes"].append({"session": year, "vote_id": vid, "member": mid,
                                     "name": members[mid]["name"], "chamber": members[mid]["chamber"],
                                     "opt": "yes" if resp == "Y" else "no", "venue": venue,
                                     "era": cfg["era"],
                                     "bill": meta["bill"], "n": len(cast),
                                     "margin": abs(yes - (len(cast) - yes))})
    return out


def kill_points(d, bills):
    """Where bills actually stop, and how close those votes are.

    THE CIRCULARITY THAT HAD TO BE REMOVED FIRST. Scoring "deepest venue reached" against `passed` gives
    98% for bills reaching a floor vote — which is nearly a tautology, because in the first chamber the
    floor roll call IS the passage vote. The honest outcome for a committee-stage question is
    **whether the bill ever reached a floor vote at all**, which is a later, separate event.
    """
    byb = collections.defaultdict(list)
    for e in d["events"].values():
        byb[(e["session"], e["bill"])].append(e)
    rows = []
    for k, evs in byb.items():
        r = bills.get(k)
        if not r:
            continue
        sub = [e for e in evs if e["venue"] == "subcommittee"]
        if not sub:
            continue
        rows.append({"won_sub": any(e["result"] == "pass" for e in sub),
                     "reached_floor": any(e["venue"] == "floor" for e in evs),
                     "passed": r["passed"]})
    subs = [e for e in d["events"].values() if e["venue"] == "subcommittee"]
    margins = collections.Counter(e["margin"] for e in subs)
    return {"rows": rows, "subcommittee_roll_calls": len(subs),
            "median_panel": sorted(e["n"] for e in subs)[len(subs) // 2] if subs else 0,
            "close": sum(n for m, n in margins.items() if m <= 2)}


_LABEL = re.compile(
    r"(?:Reported from|Continued to \d+ in|Subcommittee|Passed by indefinitely in|Tabled in|"
    r"Stricken from docket by)\s+([A-Z][A-Za-z ,&/-]+)")


def venue_survival(d, bills, min_n=40):
    """Per-venue survival: of bills voted on in this room, what share ever reached a floor vote.

    THE KEY IS STRUCTURAL, THE NAME IS ONLY A LABEL. Venues are grouped by the vote id's chamber+committee
    prefix (`H10`), which is a code LIS assigns. The human-readable committee name is scraped from the
    history description purely so the output is readable, and it never participates in the grouping —
    Standard #3: text may label an internal diagnostic, never determine it.

    Outcome is REACHED A FLOOR VOTE, not `passed`. In the first chamber the floor roll call IS the passage
    vote, so scoring a committee-stage question against `passed` is very nearly asking whether a bill that
    passed, passed — it reads 98% and means nothing.
    """
    lab = collections.defaultdict(collections.Counter)
    for (_yr, vid), e in d["events"].items():
        m = _LABEL.search(e["desc"])
        if m:
            lab[_ckey(vid)][m.group(1).strip().rstrip(".")[:34]] += 1
    byb = collections.defaultdict(list)
    for (_yr, vid), e in d["events"].items():
        byb[(e["session"], e["bill"])].append((vid, e))
    agg = collections.defaultdict(lambda: [0, 0])
    for k, evs in byb.items():
        r = bills.get(k)
        if not r:
            continue
        floor = any(e["venue"] == "floor" for _v, e in evs)
        for vid, e in evs:
            if e["venue"] not in ("committee", "subcommittee"):
                continue
            a = agg[(_ckey(vid), e["venue"])]
            a[1] += 1
            a[0] += floor
    out = []
    for (ck, kind), (h, n) in agg.items():
        if n < min_n:
            continue
        out.append({"code": ck, "name": lab[ck].most_common(1)[0][0] if lab[ck] else "?",
                    "kind": kind, "bills": n, "reached_floor": h / n})
    out.sort(key=lambda r: r["reached_floor"])
    return out


def _ckey(vid):
    """Structural venue key: chamber + committee number from the vote id (`H0101V0001` -> `H01`)."""
    body = (vid or "").split("V")[0]
    return body[:3] if len(body) >= 3 else body


def main() -> int:
    d = load()
    E, V = d["events"], d["votes"]
    print(f"committee-era roll calls {len(E):,}   member-votes {len(V):,}   "
          f"sessions {sorted(c['year'] for c in SESSIONS.values())}")
    print(f"bills covered: {len({e['bill'] for e in E.values()}):,}")
    by = collections.Counter(e["venue"] for e in E.values())
    print("\nroll calls BY VENUE:")
    for v, n in by.most_common():
        mv = sum(1 for x in V if x["venue"] == v)
        med = sorted(e["n"] for e in E.values() if e["venue"] == v)
        print(f"  {v:<14}{n:>7,} roll calls  {mv:>9,} member-votes   median panel size "
              f"{med[len(med)//2] if med else 0}")
    print("\nintegrity counters (each is a real skip, not a rounding note):")
    for k, n in d["counters"].most_common():
        print(f"  {k}: {n:,}")
    if not d["counters"]:
        print("  none")
    if "--killpoints" in sys.argv:
        from corpus import load as cload
        bills = {(r["session"], r["bill"].replace(" ", "")): r for r in cload()["bills"]}
        k = kill_points(d, bills)
        rows = k["rows"]
        w = [x for x in rows if x["won_sub"]]
        l = [x for x in rows if not x["won_sub"]]
        print(f"\nKILL POINTS — bills with a recorded subcommittee vote: {len(rows):,}")
        print("  outcome is REACHED A FLOOR VOTE, not 'passed' (that is the same event as the floor vote)")
        if w and l:
            print(f"    won >=1 subcommittee vote : {sum(x['reached_floor'] for x in w)/len(w):>5.0%}"
                  f"  (n={len(w):,})")
            print(f"    lost every one            : {sum(x['reached_floor'] for x in l)/len(l):>5.0%}"
                  f"  (n={len(l):,})")
        print(f"  subcommittee roll calls {k['subcommittee_roll_calls']:,}, median panel "
              f"{k['median_panel']} members")
        print(f"  decided by <=2 votes: {k['close']:,} "
              f"({k['close']/max(1,k['subcommittee_roll_calls']):.0%})")
    if "--venues" in sys.argv:
        from corpus import load as cload
        bills = {(r["session"], r["bill"].replace(" ", "")): r for r in cload()["bills"]}
        rows = venue_survival(d, bills)
        print("\nSURVIVAL BY VENUE — of bills voted on here, what share ever reached a floor vote")
        print(f"  {'code':<5}{'venue':<32}{'kind':>13}{'bills':>7}{'survive':>9}")
        for r in rows[:12]:
            print(f"  {r['code']:<5}{r['name'][:30]:<32}{r['kind']:>13}{r['bills']:>7,}"
                  f"{r['reached_floor']:>9.0%}")
        sub = [r for r in rows if r["kind"] == "subcommittee"]
        com = [r for r in rows if r["kind"] == "committee"]
        if sub and com:
            print(f"\n  subcommittee venues: {len(sub)}, survival "
                  f"{min(r['reached_floor'] for r in sub):.0%}-{max(r['reached_floor'] for r in sub):.0%}")
            print(f"  committee venues   : {len(com)}, survival "
                  f"{min(r['reached_floor'] for r in com):.0%}-{max(r['reached_floor'] for r in com):.0%}")
            print("  -> the subcommittee is the gate; the full committee largely ratifies it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
