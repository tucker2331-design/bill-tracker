#!/usr/bin/env python3
"""The patron drops the bill: the largest block of misses left (owner, 2026-10-19: "analyze what we are able to predict
and why and what we arent").

`gains.py` shows the patron's OWN party is called right only ~1 time in 3 on unanimous-no first votes, and those are
22-25% of all member-vote misses. The first-vote text says what they are: "Subcommittee recommends striking from the
docket" and "laying on the table" (unanimous), "continued to next session" -- mostly the patron's own request, a
private decision. Public traces checked here, all knowable BEFORE the vote date (structural records only):
  copy_moved   a near-copy in the same session (same chamber, content similarity from first_vote's neighbour table)
               already had its first vote BEFORE this one -- the copy goes forward, this one is struck / folded in
  copy_won     ... and most members voted yes on that copy
  comp_moved   the other-chamber near-copy had its first vote before this one
  strike_hab   the patron's own past share of bills struck / withdrawn at their request (earlier sessions only)
  load         the number of bills the patron filed this session (log)
Mode `describe`: unanimous-no rate per signal, and how far the base model already sees it (own-party mean p).
Mode `test`: accept.stacked_year_ahead on member votes, each signal x voter side.
"""
from __future__ import annotations
import sys, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV, shape_first as SF
from corpus import load, _party_lookup

corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
_party, person = _party_lookup()
D = FV.assemble(); rc, nb = D["rc"], D["nb"]
STRIKE = re.compile(r"strik(e|ing|en) from (the )?docket|stricken at the request|withdrawn|at the request of (the )?patron",
                    re.I)
load_ = collections.Counter((s, person(b["chief"]) or b["chief"]) for (s, _), b in corpus.items() if b["chief"])


def _habit():
    """patron -> list of (session, struck?) for every bill they carried; read as earlier-sessions-only at use."""
    h = collections.defaultdict(list)
    for (s, _), b in corpus.items():
        if b["chief"]:
            h[person(b["chief"]) or b["chief"]].append((s, any(STRIKE.search(t) for _d, t, _c in b["actions"])))
    return h


HAB = _habit()


def signals(key):
    b = corpus[key]; s = key[0]; d = rc[key][0][0]; P = person(b["chief"]) or b["chief"]
    cm = cw = om = 0.0
    for c, j in nb.get(key, []):
        if c[0] != s or j < 0.3 or c not in rc:
            continue
        cd, _o, _v, _ven, ballots = rc[c][0]
        if not cd or cd >= d:
            continue
        if corpus[c]["chamber"] == b["chamber"]:
            cm = max(cm, j)
            if ballots and np.mean([x[2] for x in ballots]) > .5:
                cw = max(cw, j)
        else:
            om = max(om, j)
    past = [x for ss, x in HAB.get(P, []) if ss < s]
    hab = (sum(past) + 0.5) / (len(past) + 5) if past else 0.1
    return {"copy_moved": cm, "copy_won": cw, "comp_moved": om, "strike_hab": hab,
            "load": float(np.log1p(load_[(s, P)]))}


_cache = {}


def sig_of(key):
    if key not in _cache:
        _cache[key] = signals(key)
    return _cache[key]


def describe():
    B = AC.base_preds()
    for t, (te, p) in B.items():
        g = collections.defaultdict(list)
        for i, r in enumerate(te):
            g[r["bill"]].append(i)
        rows = []
        for k, I in g.items():
            own = [i for i in I if te[i]["same"]]
            if not own:
                continue
            rows.append((SF.shape_of([te[i] for i in I]) == 3, float(np.mean(p[own])), sig_of(k)))
        y = np.array([r[0] for r in rows]); pm = np.array([r[1] for r in rows])
        print(f"{t}: {len(rows)} bills, unanimous no {y.mean():.1%}; base own-party mean p on them {pm[y].mean():.2f} "
              f"(others {pm[~y].mean():.2f})")
        for name, cut in (("copy_moved", .3), ("copy_won", .3), ("comp_moved", .3), ("strike_hab", .15), ("load", np.log1p(25))):
            v = np.array([r[2][name] for r in rows]); m = v >= cut
            if m.any():
                print(f"   {name:10s} >= {cut:.2f}: {m.sum():4d} bills, unanimous no {y[m].mean():.1%} vs {y[~m].mean():.1%};"
                      f" base own-party p there {pm[m & y].mean() if (m & y).any() else float('nan'):.2f}")


def test():
    def sig(r):
        f = sig_of(r["bill"]); s = float(r["same"])
        # own-party side only, three inputs: copy_moved / copy_won touch < 1% of bills and stopped the fit converging
        return {"hab_same": (f["strike_hab"] - .1) * 10 * s, "load_same": (f["load"] - 2) * s, "comp_same": f["comp_moved"] * s}
    AC.stacked_year_ahead(sig, "W  THE PATRON DROPS THE BILL: near-copy moved first / strike habit / load x side", ridge=10.0)


if __name__ == "__main__":
    {"describe": describe, "test": test}[sys.argv[1]]()
