#!/usr/bin/env python3
"""The lobbyist-facing output: WHO, WHERE, WHY -- for a vote that has NOT happened yet.

Owner, 2026-09-26: "make sure it can be used by a lobbyist to say more then the chances their bill has but who
they need to target where and why etc without writing too much text, bc obviously thats not sustainable."

WHO    the seated members, in the order the model expects them to back the bill; "in play" marks the ones
       whose call is close or who break from their side's expected position. No percentages -- the model
       ranks well but its probabilities run high (docs/testing/first_vote.md).
WHERE  the room and stage of the vote.
WHY    at most two tags per member from ONE fixed vocabulary, each a checkable count ("k of n"). A member's
       tags are the facts where they differ most from their own party's members in this room. Nothing is
       written per member; every tag is the same template with different numbers (P25).
"""
from __future__ import annotations
import sys, os, math, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import first_vote as FV

TAGS = [  # (key, count fields, template)
    ("patron", ("k_mpat", "n_mpat"), "backed this patron's bills {k} of {n}"),
    ("similar", ("k_sim", "n_sim"), "backed similar bills {k} of {n}"),
    ("subject", ("k_msubj", "n_msubj"), "backed bills on this subject {k} of {n}"),
    ("room", ("k_mroom", "n_mroom"), "backed bills in this committee {k} of {n}"),
]


def predict_future(future, train_years=None):
    rows = FV.features(future=future)
    rows = FV.add_room_aggregates(FV.add_districts(FV.add_ideal(FV.add_text(rows))))
    train_years = train_years or FV.TRAIN_YEARS + (2025,)
    tr = [r for r in rows if r["yr"] in train_years and r["y"] >= 0]
    fut = [r for r in rows if r["y"] < 0]
    import gbm
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    m = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float))
    for r, p in zip(fut, m.predict(X(fut))):
        r["p"] = float(p)
    return fut


def table(fut):
    by_side = collections.defaultdict(list)
    for r in fut:
        by_side[r["same"]].append(r)
    side_mean = {s: np.mean([r["p"] for r in rs]) for s, rs in by_side.items()}
    out = []
    for r in sorted(fut, key=lambda r: -r["p"]):
        peers = [q for q in by_side[r["same"]] if q is not r] or by_side[r["same"]]
        cand = []
        if r["is_patron"]:
            cand.append((99, "co-patron of this bill"))
        for key, (kf, nf), tmpl in TAGS:
            k, n = r[kf], r[nf]
            if n < 2:
                continue
            peer_rate = np.mean([q[kf] / q[nf] for q in peers if q[nf] >= 2] or [k / n])
            cand.append((abs(k / n - peer_rate) * math.sqrt(n), tmpl.format(k=int(k), n=int(n))))
        tags = [t for _s, t in sorted(cand, reverse=True)[:2]]
        in_play = abs(r["p"] - .5) < .2 or (r["p"] >= .5) != (side_mean[r["same"]] >= .5)
        out.append({"member": r["who"], "party": r["party"][0], "in_play": in_play, "why": tags, "p": r["p"]})
    return out


if __name__ == "__main__":
    import pickle
    from corpus import _party_lookup
    party, person = _party_lookup()
    names = ["Rip Sullivan", "Cliff Hayes", "Kathy Tran", "Dan Helmer", "Terry Kilgore"]
    members = [(person(n) or n, party(n)) for n in names]
    print("members:", members)
    fut = predict_future([("2026", "HB 1515", "sub", members, "2027-01-20")])
    for row in table(fut):
        print(f"  {row['member']:16s} {row['party']}  {'IN PLAY' if row['in_play'] else '       '}  "
              f"p={row['p']:.2f}  | " + " · ".join(row["why"]))
