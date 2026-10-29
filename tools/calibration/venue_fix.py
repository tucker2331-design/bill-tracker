#!/usr/bin/env python3
"""Re-measure the member model with the corrected roll-call venue (content_votes VENUE_FIX, 2026-10-27).

The text rule in content_votes.venue() labels 2,086 committee roll calls "floor" and 138 floor roll calls "committee";
the fix reads the venue from the ballot count. first_vote.py and the default training rows are pinned by
frozen/prereg_2027*.json, so this script never touches them: it points first_vote's caches at separate files,
rebuilds the rows there, and scores the reference model (the locked GBM) on both row sets, year-ahead.

  python3 venue_fix.py rebuild     # VENUE_FIX rows -> .cache/fv_rows_venuefix.pkl (slow: replays every vote)
  python3 venue_fix.py score       # reference model, old rows vs fixed rows, confirm (2025) and repeat (2026)
  python3 venue_fix.py armc        # frozen arm C code (booster_2027.predict_boosted) on the FIXED rows -> preds + metrics
  python3 venue_fix.py rubric      # AI checklist (rubric_eval) re-measured on top of fixed-venue arm C
  python3 venue_fix.py freeze      # write frozen/prereg_2027_venuefix.json ONCE (needs armc output; no 2027 rows allowed)
"""
from __future__ import annotations
import os, sys, pickle, collections
os.environ["VENUE_FIX"] = "1"                      # must be set before content_votes is imported
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import content_votes as CVT
import first_vote as FV

assert CVT.VENUE_FIX and CVT.CACHE.endswith("_venuefix.pkl"), "VENUE_FIX did not take effect"
OLD_ROWS = FV.ROWS
FV.CACHE = os.path.join(HERE, "first_vote_cache_venuefix.pkl")
FV.ROWS = os.path.join(FV.CACHE_DIR, "fv_rows_venuefix.pkl")
SPLITS = {"confirm": ((2019, 2020, 2021, 2022, 2024), 2025), "repeat": ((2019, 2020, 2021, 2022, 2024, 2025), 2026)}


def rebuild():
    rows = FV.rebuild_rows()
    print(f"rebuilt {len(rows):,} rows -> {FV.ROWS}")


def _venue_mix(rows, yr):
    c = collections.Counter("sub" if r["ven_sub"] else "com" if r["ven_com"] else "floor" for r in rows if r["yr"] == yr)
    return dict(c)


def _score(rows, tr_years, te_year):
    import gbm
    rows = [r for r in rows if r["y"] >= 0]
    tr = [r for r in rows if r["yr"] in tr_years]; te = [r for r in rows if r["yr"] == te_year]
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    y = lambda rs: np.array([r["y"] for r in rs], float)
    m = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), y(tr))
    p = m.predict(X(te)); yt = y(te); right = (p >= .5) == (yt == 1)
    hard = np.argsort(np.abs(p - .5))[:len(p) // 3]
    called = np.abs(p - .5) >= .31
    return {"n": len(te), "acc": right.mean(), "hard": right[hard].mean(), "calls": int(called.sum()),
            "call_wrong": int((called & ~right).sum())}


def score():
    old = pickle.load(open(OLD_ROWS, "rb")); new = pickle.load(open(FV.ROWS, "rb"))
    for name, (tr_y, te_y) in SPLITS.items():
        print(f"{name}: venue mix in {te_y} first votes  old {_venue_mix(old, te_y)}  fixed {_venue_mix(new, te_y)}")
        for lab, rows in (("old venue", old), ("fixed venue", new)):
            s = _score(rows, tr_y, te_y)
            print(f"  {lab:12s} {s['n']:,} ballots  accuracy {s['acc']:.2%}  hard third {s['hard']:.2%}  "
                  f"calls {s['calls']:,} ({s['call_wrong']:,} wrong)")


ARMC = os.path.join(FV.CACHE_DIR, "armC_venuefix.pkl")
SPEC = os.path.join(HERE, "frozen", "prereg_2027_venuefix.json")


def _metrics(p, te):
    y = np.array([r["y"] for r in te], float); right = (p >= .5) == (y == 1)
    hard = np.abs(p - .5) < .31; called = ~hard
    return {"member": round(float(right.mean()), 4), "hard": round(float(right[hard].mean()), 4),
            "calls": int(called.sum()), "call_wrong": int((called & ~right).sum()), "n": len(te)}


def armc():
    import booster_2027 as BC
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    rc = FV.assemble()["rc"]; vd = lambda r: rc[r["bill"]][0][0]
    out = {}
    for name, (tr_y, te_y) in SPLITS.items():
        tr = [r for r in rows if r["yr"] in tr_y]; te = [r for r in rows if r["yr"] == te_y]
        p = BC.predict_boosted(tr, te, vd)
        out[name] = {"keys": [(r["bill"], r["who"]) for r in te], "p": p, "metrics": _metrics(p, te)}
        print(f"{name} ({te_y}): arm C, fixed venue  {out[name]['metrics']}")
    pickle.dump(out, open(ARMC, "wb"))


def rubric(lam=30.0):
    import rubric_eval as RE, llm_rubric as RB
    R = RB.load(); A = pickle.load(open(ARMC, "rb"))
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    D = {}
    for name, (_tr, te_y) in SPLITS.items():
        te = [r for r in rows if r["yr"] == te_y]
        assert [(r["bill"], r["who"]) for r in te] == A[name]["keys"], "arm C preds out of order with the rows"
        has = np.array([tuple(r["bill"]) in R and not R[tuple(r["bill"])].get("r") for r in te])
        blank = [0.0] * len(RE.feats(te[0], {"d": 50, "g": 50, "c": 50, "k": 50}))
        X = np.array([RE.feats(r, R[tuple(r["bill"])]) if h else blank for r, h in zip(te, has)])
        p = np.clip(A[name]["p"], 1e-6, 1 - 1e-6)
        D[name] = (np.log(p / (1 - p)), X, np.array([r["y"] for r in te], float), has)
    print(f"checklists: {len(R)} bills; base = arm C on fixed-venue rows")
    for a, b in (("confirm", "repeat"), ("repeat", "confirm")):
        off, X, y, has = D[a]; w = RE.fit(off[has], X[has], y[has], lam)
        off, X, y, has = D[b]
        RE.report(f"learn {a} -> score {b}", 1 / (1 + np.exp(-off)), 1 / (1 + np.exp(-(off + X @ w))), y, has)


def freeze():
    """Addendum to frozen/prereg_2027*.json, written ONCE before any 2027 data. The original arms stay as registered
    (scored with their leaky venue); this adds the same arm C code and the reference model on VENUE_FIX rows."""
    import json, hashlib, datetime, prereg_2027 as P
    if os.path.exists(SPEC):
        raise SystemExit(f"already frozen: {SPEC} -- written ONCE; never overwrite")
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    if any(r["yr"] == P.TEST for r in rows):
        raise SystemExit("2027 rows already exist -- too late for a forward-test addendum")
    A = pickle.load(open(ARMC, "rb"))
    sha = lambda f: hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest()
    pair = {f: hashlib.sha256(open(os.path.join(HERE, "frozen", f), "rb").read()).hexdigest()
            for f in ("prereg_2027.json", "prereg_2027_addendum.json", "prereg_2027_ai.json")}
    spec = {"frozen_on": datetime.date.today().isoformat(), "test_year": P.TEST, "pairs_with_sha256": pair,
            "why": "case law #143: the registered rows read venue from the motion text, which encodes the outcome "
                   "(Senate committee kill motions labelled floor). These arms use the ballot-count venue.",
            "rows": "content_votes VENUE_FIX=1, rebuilt by venue_fix.rebuild (first_vote caches *_venuefix)",
            "train_rows_sha256": P._train_rows_sha(rows),
            "arms": {"C_fixed": {"fn": "booster_2027.predict_boosted", "rows": "VENUE_FIX"},
                     "reference_fixed": {"fn": "gbm.GBM", "depth": 6, "lr": .03, "rounds": 260, "rows": "VENUE_FIX"}},
            "code_sha256": {f: sha(f) for f in ("content_votes.py", "venue_fix.py", "booster_2027.py", "blend_2027.py",
                                                "first_vote.py", "gbm.py")},
            "venue_rule": {"room_max": CVT.ROOM_MAX, "floor_min": CVT.FLOOR_MIN},
            "expected_from_2025_2026": {k: A[k]["metrics"] for k in SPLITS},
            "primary": "member accuracy, hardest third (|p-.5| < .31), calls and wrong calls -- C_fixed vs reference_fixed"}
    blob = json.dumps(spec, indent=1, sort_keys=True).encode()
    open(SPEC, "wb").write(blob)
    print(f"froze -> {SPEC}\nsha256 {hashlib.sha256(blob).hexdigest()}")


if __name__ == "__main__":
    {"rebuild": rebuild, "score": score, "armc": armc, "rubric": rubric, "freeze": freeze}[sys.argv[1] if len(sys.argv) > 1 else "score"]()
