#!/usr/bin/env python3
"""Co-sponsorship ties between the voter and this bill's sponsors (owner, 2026-10-22: fewer wrong calls, more calls).

Public at filing, before any vote: who signed which bills. A member who has signed bills WITH this bill's patron (or its
co-patrons) has a working alliance with them -- across party lines this is the clearest public trace of it. The member
model reads co-patron COUNTS by party, never the voter-to-sponsor tie. Inputs (sessions before this one, plus this
session's bills filed before the vote date):
  tie_pat     log(1 + bills the voter and the patron both signed)
  tie_any     log(1 + bills the voter signed with ANY of this bill's sponsors)
  tie_ses     the voter and the patron both signed a bill THIS session (0/1)
each x voter side. Tested as a stacked layer (accept.stacked_year_ahead, year-ahead, z >= 3 to accept).
Run: python3 cosponsor_ties.py
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import accept as AC, first_vote as FV
from corpus import load, _party_lookup

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
_party, person = _party_lookup()
rc = FV.assemble()["rc"]


def signers(b):
    return {person(b["chief"]) or b["chief"]} | {person(c) or c for c in b["cops"]} if b["chief"] else set()


def filed(b):
    return next((d for d, _t, _c in b["actions"] if d), "9999")


# per session: list of (filed date, signer set)
by_ses = collections.defaultdict(list)
for (s, _), b in corpus.items():
    S = signers(b)
    if len(S) > 1:
        by_ses[s].append((filed(b), S))
prior = {}                                   # session -> Counter of pairs signed together in EARLIER sessions
acc = collections.Counter()
for s in sorted(by_ses):
    prior[s] = acc.copy()
    for _d, S in by_ses[s]:
        for a in S:
            for c in S:
                if a < c:
                    acc[(a, c)] += 1
_cache = {}


def ties(key, who, date):
    s = key[0]; b = corpus[key]; P = person(b["chief"]) or b["chief"]; S = signers(b) - {who}
    pair = lambda a, c: (a, c) if a < c else (c, a)
    if (s, date) not in _cache:
        cur = collections.Counter()
        for d, T in by_ses[s]:
            if d < date:
                for a in T:
                    for c in T:
                        if a < c:
                            cur[(a, c)] += 1
        _cache[(s, date)] = cur
    cur = _cache[(s, date)]; pr = prior.get(s, collections.Counter())
    own = who in signers(b)                    # this bill itself is in `cur` when filed earlier: not a TIE (is_patron says it)
    n_cur_pat = cur[pair(who, P)] - (1 if own and who != P else 0)
    n_pat = pr[pair(who, P)] + n_cur_pat if who != P else 0
    n_any = sum(pr[pair(who, x)] + cur[pair(who, x)] - (1 if own else 0) for x in S)
    return math.log1p(max(n_pat, 0)), math.log1p(max(n_any, 0)), float(n_cur_pat > 0 and who != P)


def sig(r):
    t_pat, t_any, t_ses = ties(r["bill"], r["who"], rc[r["bill"]][0][0]); s = float(r["same"])
    return {"tp_same": t_pat * s, "tp_other": t_pat * (1 - s), "ta_same": t_any * s, "ta_other": t_any * (1 - s),
            "ts_other": t_ses * (1 - s)}


if __name__ == "__main__":
    AC.stacked_year_ahead(sig, "CO-SPONSORSHIP TIES: voter x this bill's sponsors (earlier sessions + this session so far)", ridge=10.0)
