#!/usr/bin/env python3
"""Train the member model on LATER committee votes too (owner, 2026-10-21: "keep working on the goal").

The model learns only from each bill's FIRST vote (129k ballots 2019+). The same bills have 281k later ballots in
committee and subcommittee (and 1.0M on the floor, not used here). Members' later committee votes show the same habits.
Here every committee/subcommittee roll call gets the same feature row a first vote gets (state BEFORE that day), plus
`first` (1 = first vote) and `roll` (its index). The model is still SCORED on first votes only.

first_vote.py is hashed by frozen/prereg_2027.json, so it is NOT edited: features() and add_room_aggregates() are
re-built from its source with two textual switches (featurise later sub/com votes; group room aggregates per roll call)
and run in its own namespace. Any change to first_vote.py's source that breaks a switch raises -- no silent fallback.
Cache: .cache/fv_rows_all.pkl.   Run: python3 fv_all.py build
"""
from __future__ import annotations
import sys, os, inspect, pickle
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import first_vote as FV

OUT = os.path.join(HERE, ".cache", "fv_rows_all.pkl")
SWITCHES = {
    "features": [("            if i != 0:\n                continue\n",
                  "            if i != 0 and ven not in (\"sub\", \"com\"):\n                continue\n"),
                 ('"room": R, "who": who, "bill": (s, b), "party": pp,',
                  '"room": R, "who": who, "bill": (s, b), "party": pp, "roll": i, "first": int(i == 0),')],
    "add_room_aggregates": [('        g[r["bill"]].append(r)\n', '        g[(r["bill"], r.get("roll", 0))].append(r)\n')],
}


def _rebuilt(name):
    src = inspect.getsource(getattr(FV, name))
    for old, new in SWITCHES[name]:
        if src.count(old) != 1:
            raise RuntimeError(f"fv_all: switch not found exactly once in first_vote.{name} -- source changed: {old!r}")
        src = src.replace(old, new)
    ns = dict(FV.__dict__); exec(compile(src, f"<fv_all.{name}>", "exec"), ns)
    return ns[name]


def build():
    feats, agg = _rebuilt("features"), _rebuilt("add_room_aggregates")
    rows = agg(FV.add_districts(FV.add_ideal(FV.add_text(feats()))))
    rows = [r for r in rows if r["yr"] >= 2019]
    pickle.dump(rows, open(OUT, "wb"))
    n1 = sum(r["first"] for r in rows)
    print(f"rows {len(rows):,}: first votes {n1:,}, later committee/sub votes {len(rows) - n1:,}")


if __name__ == "__main__":
    {"build": build}[sys.argv[1]]()
