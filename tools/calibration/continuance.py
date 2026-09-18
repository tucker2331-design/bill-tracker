#!/usr/bin/env python3
"""A committee continuance is a soft kill with a twelve-day clock on it.

WHY THIS EXISTS. 429 bills are sitting "continued to next session" right now (Sept 2026), and every
lobbyist tracking one of them believes they are tracking a live bill. Nothing in the product told them
otherwise, because nobody had ever counted what a continuance is worth.

THE ANSWER. Of 1,346 bills continued by a committee across five sessions, 25 ever moved again -- and
every one of the 25 moved within TWELVE DAYS, twelve of them the same day. The mechanism is visible in
the descriptions: the committee "Reconsidered by <committee>" while it was still sitting. Nothing comes
back after the session ends.

THE ARTEFACT THAT ALMOST SHIPPED AS THE FINDING. The obvious way to ask this is "of bills continued to
the next session, how many passed in that next session?" and the obvious answer is ZERO OF 901 -- which
is a MEASUREMENT ARTEFACT, not a finding. Open States never updates a carried-over record: the next
session's copy is the previous session's history plus one "Continued from last session" stub, so the
numerator is structurally unreachable and the denominator looks authoritative. Verified: of 891 carried
records across three pairs, exactly ZERO carry ANY action dated in the following year.

WHAT RESCUES IT IS A CAPABILITY CHECK ON A SECOND SOURCE. LIS's own 20251 HISTORY.CSV keeps the whole
biennium, so ask it the same question and then ask whether the file was CAPABLE of answering:

    bills continued out of 2024, with any 2025 action ...........   0 of 333
    NON-continued bills with 2024 activity, with a 2025 action ... 132 of 169   <- the file can see it

and LIS writes the epitaph itself: all 333 carry "Left in <committee>", dated 18-19 Nov 2024, seven
weeks before the session opened.

AUDIT POINT #1 (verb/phrase forms) BIT HERE TOO. The 2026 session writes "Continued to next session in
Rules"; 2018 through 2024 write "Continued to 2019 in Finance", "Continued to 2025 in ...". A pattern
matching only the 2026 wording finds 429 bills and reports 0 for every earlier session -- which reads as
a clean result rather than as a broken pattern. Both forms are matched below.

NOT THE SAME EVENT: "Subcommittee recommends continuing to ..." is a RECOMMENDATION, and "Continued to
2022 Sp. Sess. 1 pursuant to HJR455" is a move to a special session convening days later. Both are
excluded -- the first because the full committee's action supersedes it, the second because it is not a
carryover at all.

Run:  python3 tools/calibration/continuance.py
"""
from __future__ import annotations
import sys, os, re, csv, gzip, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load

LIS = os.path.join(HERE, "..", "historical_cache", "va")

# Every wording the sessions actually use, and the " in <committee>" tail is what separates a real
# carryover from a move to a special session.
CONT = re.compile(r"^continued to (?:\d{4}|next session)\b.*\bin\b", re.I)
# NOT a carryover: "Continued to 2021 Sp. Sess. 1 in Education and Health" moves the bill to a session
# convening DAYS later. There are 340, they pass, and they drag the recovery rate from 0.9% to 13.3%.
# This module is only safe without the guard by accident of its even-year session filter — make it explicit.
SPSESS = re.compile(r"sp\.?\s*sess", re.I)
LEFT = re.compile(r"\bleft in\b", re.I)
# A later action that is not the continuance restating itself, and not paperwork.
NOISE = re.compile(r"impact statement|bill text|blank action|left in|acts of assembly", re.I)
SELF = re.compile(r"^subcommittee recommends continu|^continued to", re.I)
PAIRS = [("2018", "2019"), ("2020", "2021"), ("2022", "2023"), ("2024", "2025"), ("2026", "2027")]


def _carryover(desc):
    """A real carryover, with the special-session look-alike excluded."""
    return bool(CONT.search(desc)) and not SPSESS.search(desc)


def _by_session():
    d = collections.defaultdict(dict)
    for r in load()["bills"]:
        d[r["session"]][r["bill"]] = r
    return d


def recovery(B):
    """How often a continued bill moves again, and how long it takes when it does."""
    tot, gaps = 0, []
    for s, _ in PAIRS:
        for r in B[s].values():
            i = [j for j, x in enumerate(r["actions"]) if _carryover(x[1])]
            if not i:
                continue
            i = i[-1]
            tot += 1
            nxt = [x for x in r["actions"][i + 1:] if not NOISE.search(x[1]) and not SELF.search(x[1])]
            if nxt:
                gaps.append((datetime.date.fromisoformat(nxt[0][0])
                             - datetime.date.fromisoformat(r["actions"][i][0])).days)
    return tot, sorted(gaps)


def openstates_is_blind(B):
    """THE ARTEFACT CHECK. A carried-over record is never updated, so 'did it pass next session?' is
    unanswerable from this source and any zero it returns is the source, not the legislature."""
    out = []
    for a, b in PAIRS[:-1]:
        car = [r for r in B[a].values()
               if any(_carryover(x[1]) for x in r["actions"])
               and r["bill"] in B[b] and B[b][r["bill"]]["title"] == r["title"]]
        upd = sum(1 for r in car if any(x[0][:4] >= b for x in B[b][r["bill"]]["actions"]))
        out.append((a, b, len(car), upd))
    return out


def _lis(session):
    p = os.path.join(LIS, session, "HISTORY.CSV.gz")
    if not os.path.exists(p):                       # FAILS LOUD: never silently skip the second source
        raise SystemExit(f"missing cached LIS history: {p}")
    by = collections.defaultdict(list)
    with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                d = datetime.datetime.strptime(r["History_date"].strip(), "%m/%d/%Y").date().isoformat()
            except ValueError:
                d = ""
            by[r["Bill_id"].strip()].append((d, (r["History_description"] or "").strip()))
    for k in by:
        by[k].sort()
    return by


def lis_2025():
    """The same question against LIS, WITH the capability check that makes a zero mean something.

    Authorization: 20251 and 20261 only ([[knowledge/lis_api_authorization]]). Both are already on disk;
    this function reads the cache and never touches the network.
    """
    by = _lis("20251")
    bills = [b for b in by if re.match(r"^[HS]B\d+$", b)]
    cont = [b for b in bills if any(re.search(r"continued to 2025 in ", t, re.I) for _d, t in by[b])]
    has24 = {b for b in bills if any(d[:4] == "2024" for d, _t in by[b])}
    other = has24 - set(cont)
    acted = lambda s: sum(1 for b in s if any(d[:4] == "2025" for d, _t in by[b]))
    epitaph = collections.Counter(d for b in cont for d, t in by[b] if LEFT.search(t))
    return len(cont), acted(cont), len(other), acted(other), epitaph


def main():
    B = _by_session()
    tot, gaps = recovery(B)
    print(f"CONTINUED BILLS THAT EVER MOVED AGAIN   {len(gaps)} of {tot} = {len(gaps)/tot:.1%}")
    print(f"  days from the continuance to that next action: {gaps}")
    print(f"  longest: {gaps[-1]} days.  Same day: {sum(1 for g in gaps if g == 0)}.\n")

    print("OPEN STATES CANNOT ANSWER 'DID IT PASS NEXT SESSION' -- carried records are never updated:")
    for a, b, n, upd in openstates_is_blind(B):
        print(f"  {a}->{b}: {n} carried into the {b} file, {upd} of them carry ANY {b}-dated action")

    n, a, no, ao, ep = lis_2025()
    print(f"\nLIS 20251, the same question WITH a capability check:")
    print(f"  continued out of 2024, any 2025 action ....... {a:4d} of {n}")
    print(f"  NOT continued but active in 2024, any 2025 ... {ao:4d} of {no}   <- the file can see it")
    print(f"  'Left in <committee>' written on {sum(ep.values())} of {n}, dated {dict(ep)}")


if __name__ == "__main__":
    main()
