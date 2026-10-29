#!/usr/bin/env python3
"""House subcommittees: the accuracy gap (owner, 2026-10-22: "sub committee is a gap spend time boosting it").

Every subcommittee first vote is in the House; 11-13% of them are unanimous no (patron drops: strike / table /
continue), the biggest miss source there. Two subcommittee-only signals, each stacked on the locked model with
accept.stacked_year_ahead (zero on every non-subcommittee vote, so only subcommittee votes can move):
  drop     the bill's year-ahead risk of a unanimous-no first vote (drop_model.py) x voter side
  memsub   the member's own support rate inside THIS subcommittee (all earlier subcommittee roll calls, this
           session's before the vote date included), this side, shrunk toward the subcommittee's side rate
Run: python3 sub_probe.py drop | memsub
"""
from __future__ import annotations
import sys, os, re, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import accept as AC, first_vote as FV
from corpus import load

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
rc = FV.assemble()["rc"]
SUBASG = re.compile(r"^assigned .+? sub:\s*(.+)$", re.I)
lg = lambda q: math.log(max(q, 1e-4) / max(1 - q, 1e-4))


def subroom(bill, date):
    sr = None
    for d_, t, _c in bill["actions"]:
        if d_ and d_ <= date:
            m = SUBASG.match(t.strip())
            if m:
                sr = m.group(1).strip()
    return f"{FV.first_room(bill) or '?'}/{sr}" if sr else None


def drop():
    P = pickle.load(open(os.path.join(HERE, ".cache", "drop_p.pkl"), "rb"))
    def sig(r):
        if not r["ven_sub"] or r["bill"] not in P:
            return {"dr_same": 0.0, "dr_other": 0.0}
        x = lg(P[r["bill"]]) + 2.5; s = float(r["same"])
        return {"dr_same": x * s, "dr_other": x * (1 - s)}
    AC.stacked_year_ahead(sig, "SUBCOMMITTEE: drop risk x side (subcommittee votes only)", ridge=10.0)


def memsub():
    ev = []                                       # (date, SR, who, same, sup) for every subcommittee ballot
    for k, lst in rc.items():
        b = corpus.get(k)
        if not b or b["chief_party"] not in FV.PARTIES:
            continue
        for date, _vo, _vid, ven, ballots in lst:
            if ven != "sub" or not date or date == "9999":
                continue
            SR = subroom(b, date)
            if SR:
                for who, pp, sup in ballots:
                    ev.append((date, SR, who, int(pp == b["chief_party"]), sup))
    ev.sort()
    # every subcommittee first-vote ballot that will be scored, featurised in date order from counts strictly before
    q = []
    for t, (te, _p) in AC.base_preds().items():
        for r in te:
            if r["ven_sub"]:
                d = rc[r["bill"]][0][0]; q.append((d, r["bill"], r["who"], r["same"], subroom(corpus[r["bill"]], d)))
    q.sort(key=lambda x: x[0]); c = collections.Counter(); j = 0; F = {}
    for d, bill, who, same, SR in q:
        while j < len(ev) and ev[j][0] < d:
            _d, S2, w2, s2, sup = ev[j]; j += 1
            c[(w2, S2, s2, "n")] += 1; c[(w2, S2, s2, "s")] += sup; c[(S2, s2, "n")] += 1; c[(S2, s2, "s")] += sup
        if SR:
            base = (c[(SR, same, "s")] + 10 * (.85 if same else .55)) / (c[(SR, same, "n")] + 10)
            m = (c[(who, SR, same, "s")] + 5 * base) / (c[(who, SR, same, "n")] + 5)
            F[(bill, who)] = lg(m) - lg(base)
    def sig(r):
        x = F.get((r["bill"], r["who"])) if r["ven_sub"] else None
        if x is None:
            return {"ms_same": 0.0, "ms_other": 0.0}
        s = float(r["same"]); return {"ms_same": x * s, "ms_other": x * (1 - s)}
    AC.stacked_year_ahead(sig, "SUBCOMMITTEE: member's own record in this subcommittee x side", ridge=10.0)


if __name__ == "__main__":
    {"drop": drop, "memsub": memsub}[sys.argv[1]]()
