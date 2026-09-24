#!/usr/bin/env python3
"""Virginia campaign-finance filings from ELECT — the agency, not an aggregator.

SOURCE AND TERMS. `https://apps.elections.virginia.gov/SBE_CSV/CF/<YYYY_MM>/` — the Virginia Department
of Elections, where candidates and committees actually file. No key, no registration, no attestation;
monthly directories from 1999. The reasoning for using the agency rather than VPAP is already settled in
[[knowledge/campaign_finance_source]]: an aggregator's terms govern their compilation, not the underlying
public records.

WHICH FILES MATTER, AND WHY ScheduleH IS THE ONE TO REACH FOR FIRST
  Report.csv     6 MB   filing metadata: CandidateName, Party, OfficeSought, District, ElectionCycle
  ScheduleH.csv  0.8 MB SUMMARY — carries `TotalReceiptsThisElectionCycle`, i.e. the whole race in one
                        small file. Use this for money totals instead of summing 30 MB of ScheduleA.
  ScheduleA.csv 20-30 MB every individual contribution: donor name, EMPLOYER, OCCUPATION, amount.
                        Only needed when you want WHO gave, not HOW MUCH.

THREE FIELD TRAPS, ALL MEASURED
  * `IsGeneralAssembly` is **always False** in these files — a dead column. Filtering on it returns zero
    rows. `OfficeSought` ("Member, House Of Delegates" / "Member, Senate Of Virginia") is the only route.
  * `OfficeSought` is FREE TEXT WITH 28 SPELLINGS of the two chambers -- "Member, House Of Delegates",
    "Delegate", "State Senator", "Senate", "Hous of Delegates", "Member Senate Of Virginia - Old", ...
    The two canonical strings cover ~44% of legislative reports. CORRECTION 2026-09-24: the earlier note
    blamed BLANK offices for dropping Ebbin, Rouse and Lopez; measured, only 7 candidate committees ever
    file a blank office (the ~5,000 blanks are PACs). Ebbin files as "State Senate", Rouse as "Senate",
    Lopez as "Delegate". Audit point #1 (every form), in a campaign-finance costume.
    `ga_chamber()` below classifies all 28 plus the bare codes "SD"/"HD" (Bagby, Carroll Foy and
    VanValkenburg file as "SD"); "- Old" / "2001 ... Lines" rows are flagged as OLD MAPS.
  * `OfficeSought` reads "0.00" on some report types (e.g. Large Contribution Reports) -- a PLACEHOLDER,
    not a column shift: the row has the correct 39 fields. Barry Knight files nothing else in these months.
    Such committees are kept with chamber=None and may match a sitting member on NAME ALONE, flagged.

  `District` is free text: "93", "#59", "086" all appear. Normalise before joining.

Run:  python3 tools/historical_cache/finance.py <YYYY_MM> [<YYYY_MM> ...]
"""
from __future__ import annotations
import gzip, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "va_finance")
BASE = "https://apps.elections.virginia.gov/SBE_CSV/CF"
FILES = ("Report.csv", "ScheduleH.csv", "ScheduleA.csv")
DELAY = 1.5
UA = "va-bill-tracker/1.0 (research)"


def fetch(month, files=FILES):
    os.makedirs(CACHE, exist_ok=True)
    got = 0
    for name in files:
        path = os.path.join(CACHE, f"{month}_{name}.gz")
        if os.path.exists(path):
            print(f"  cached  {month}/{name}")
            continue
        req = urllib.request.Request(f"{BASE}/{month}/{name}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r:
            if r.status != 200:
                print(f"  FAIL {month}/{name}: HTTP {r.status}")
                return 1
            raw = r.read()
        with gzip.open(path, "wb") as fh:
            fh.write(raw)
        print(f"  fetched {month}/{name}: {len(raw):,}B")
        got += 1
        time.sleep(DELAY)
    return 0


_OLD_MAP = re.compile(r"\b(old|ptr)\b|\d{4}\s+[ls]d\s+lines", re.I)


def ga_chamber(office):
    """'H' / 'S' for a General Assembly office string, else None. Handles all 28 measured spellings.

    'Senate' alone is STATE senate: federal candidates file with the FEC, not ELECT. INTERNAL ONLY --
    this classifies free text, which Standard #3 keeps off the lobbyist path."""
    o = (office or "").strip().lower()
    if o == "sd":
        return "S"
    if o == "hd":
        return "H"
    if re.search(r"senat", o):
        return "S"
    if re.search(r"delegat|\bhous|state house", o):
        return "H"
    return None


def _district(s):
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else None


def committees(months):
    """CommitteeCode -> {chamber, district, candidate, party, old_map}, from cached Report.csv files.
    A committee's identity is its code; the office text only tells us which chamber it is running for."""
    import csv
    out = {}
    for m in months:
        path = os.path.join(CACHE, f"{m}_Report.csv.gz")
        if not os.path.exists(path):
            raise SystemExit(f"not cached: {path} -- run fetch first")
        with gzip.open(path, "rt", errors="replace") as f:
            for r in csv.DictReader(f):
                if not r["CommitteeType"].startswith("Candidate"):
                    continue
                ch = ga_chamber(r["OfficeSought"])
                unreadable = bool(re.fullmatch(r"\s*(-?\d+(\.\d+)?|n/?a)?\s*", r["OfficeSought"] or "", re.I))
                if not ch and not unreadable:
                    continue                    # a real non-legislative office (school board, sheriff...)
                old = bool(_OLD_MAP.search(r["OfficeSought"]))
                cur = out.get(r["CommitteeCode"])
                better = cur is None or (cur["chamber"] is None and ch) or (cur["old_map"] and not old and ch)
                if better:                      # prefer a readable office, then a current-map row
                    out[r["CommitteeCode"]] = {"chamber": ch, "district": _district(r["District"]),
                                               "candidate": r["CandidateName"], "party": r["Party"],
                                               "old_map": old, "office_unreadable": ch is None}
    return out


_HONORIFIC = {"mr", "mrs", "ms", "miss", "hon", "honorable", "delegate", "senator", "rev", "dr", "del", "sen"}


def _name(n):
    """(given, surname) tokens with honorifics and suffixes removed. Surname = the LAST real token, so a
    middle name ("Thomas COLE Wright") can never be mistaken for one."""
    sys.path.insert(0, os.path.join(HERE, "..", "calibration"))
    from corpus import _tk
    t = [x for x in _tk(n) if x not in _HONORIFIC]
    return (t[0], t[-1]) if len(t) >= 2 else (None, None)


# Explicit, short, and auditable -- not a fuzzy matcher. Each entry is a nickname seen on the 2026 roster.
_NICK = {"mike": "michael", "bill": "william", "will": "william", "bob": "robert", "jim": "james",
         "jay": "james", "danny": "daniel", "cliff": "clifton", "jackie": "jacqueline", "lily": "lillian",
         "tim": "timothy", "tom": "thomas", "joe": "joseph", "chris": "christopher", "dave": "david"}


def _given_tokens(n):
    sys.path.insert(0, os.path.join(HERE, "..", "calibration"))
    from corpus import _tk
    t = [x for x in _tk(n) if x not in _HONORIFIC]
    return {_NICK.get(x, x) for x in t[:-1] if len(x) >= 2}


def _same_person(member, candidate):
    """Some given name must agree -- exactly, by nickname, or by a 3-letter prefix. 'M. Keith Hodges' ~
    'MYRON KEITH HODGES' (keith); 'Mike A. Cherry' ~ 'Michael A. Cherry' (nickname)."""
    a, b = _given_tokens(member), _given_tokens(candidate)
    return any(x == y or (len(x) >= 3 and len(y) >= 3 and x[:3] == y[:3]) for x in a for y in b)


def join_members(coms, members):
    """Sitting member -> committee code. Key: chamber + SURNAME (last token only). Several committees
    sharing it are narrowed by a 3-letter given-name prefix ("Lily" ~ "Lillian"), then by preferring a
    current-map committee. Ambiguity is RETURNED, never resolved by a guess.

    `members` is [(chamber, name)] from LIS Members.csv. Returns (matched, ambiguous, missing)."""
    by = {}
    for code, c in coms.items():
        g, sur = _name(c["candidate"])
        if sur:
            by.setdefault((c["chamber"], sur), []).append((code, g))   # chamber None = office unreadable
    matched, ambiguous, missing = {}, {}, []
    for ch, name in members:
        g, sur = _name(name)
        cands = by.get((ch, sur), [])
        if not cands:                   # fall back to office-unreadable committees, NAME must agree fully
            cands = [(c, cg) for c, cg in by.get((None, sur), []) if _same_person(name, coms[c]["candidate"])]
        # NO surname-only fallback. It gave Gretchen Bulova David Bulova's committee, Nicole Cole Joshua
        # Cole's, Wren Williams LeOtis Williams's. A donor record on the wrong legislator is worse than a gap.
        cands = [(c, cg) for c, cg in cands if _same_person(name, coms[c]["candidate"])]
        codes = [c for c, _g in cands]
        cur = [c for c in codes if not coms[c]["old_map"]] or codes
        if len(cur) == 1:
            matched[(ch, name)] = cur[0]
        elif cur:
            ambiguous[(ch, name)] = cur
        else:
            missing.append((ch, name))
    return matched, ambiguous, missing


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for m in argv[1:]:
        if fetch(m):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
