#!/usr/bin/env python3
"""The locked 2027 forward test (owner approved the blend 2026-10-19 and the weekly session refit 2026-10-20).

2024 chose, and 2025 and 2026 have now judged many approaches, so the only clean test left is the 2027 session.
Two pre-declared arms, both in blend_2027.py (hashed here):
  A  predict()          bagged trees + 20% linear model, learned on every year before 2027
  B  predict_online()   the same, with the linear half refit weekly on 2027's earlier votes (>= 3,000), 70/30
Reference: the old locked model (gbm.GBM depth 6, lr .03, 260 rounds) -- what prereg_2026 scored.

  --freeze   writes frozen/prereg_2027.json and prints its SHA-256. Refuses if it exists.
  --score    refuses unless the code is unchanged and 2027 rows exist; scores every arm ONCE with
             prereg_2026._metrics (same definitions as 2026), writes frozen/score_2027.json. Refuses if it exists.
"""
from __future__ import annotations
import sys, os, json, hashlib, pickle, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np

SPEC = os.path.join(HERE, "frozen", "prereg_2027.json")
SCORE = os.path.join(HERE, "frozen", "score_2027.json")
CODE = ("blend_2027.py", "first_vote.py", "gbm.py", "prereg_2026.py")
TEST = 2027


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _train_rows_sha(rows):
    """Hash of the training rows' values (the rows file itself will change when 2027 is added)."""
    import first_vote as FV
    h = hashlib.sha256()
    for r in sorted((r for r in rows if r["yr"] < TEST), key=lambda r: (r["yr"], str(r["bill"]), r["who"])):
        h.update(json.dumps([r["yr"], str(r["bill"]), r["who"], r["y"]] + [round(float(r[c]), 9) for c in FV.NUM]).encode())
    return h.hexdigest()


def freeze():
    import first_vote as FV, blend_2027 as B
    if os.path.exists(SPEC):
        raise SystemExit(f"already frozen: {SPEC} -- written ONCE; never overwrite")
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    if any(r["yr"] == TEST for r in rows):
        raise SystemExit("2027 rows already exist -- freezing now would not be a forward test")
    spec = {"frozen_on": datetime.date.today().isoformat(), "test_year": TEST,
            # 2019+ as in every research split (levers.SPLITS): 2017-18 roll calls carry no member names
            "train_years": sorted({r["yr"] for r in rows if r["yr"] >= 2019}),
            "arms": {"A": {"fn": "blend_2027.predict", "trees": B.TREES, "linear": B.LINEAR, "w_linear": B.W_LINEAR},
                     "B": {"fn": "blend_2027.predict_online", "trees": B.TREES, "linear": B.LINEAR, "online": B.ONLINE},
                     "reference": {"fn": "gbm.GBM", "depth": 6, "lr": .03, "rounds": 260}},
            "features": list(FV.NUM), "code_sha256": {f: _sha(os.path.join(HERE, f)) for f in CODE},
            "train_rows_sha256": _train_rows_sha(rows),
            "metrics": "prereg_2026._metrics: accuracy, log loss, other-party, room result, hardest third, labels, slices",
            "primary": "member accuracy, hardest third, room result -- arm vs reference, same ballots",
            "expected_from_2024_2026": {"A_member": [0.8512, 0.8650], "A_hard": [0.6712, 0.6847],
                                        "B_member": [0.8531, 0.8709], "B_hard": [0.6771, 0.7002]}}
    blob = json.dumps(spec, indent=1, sort_keys=True).encode()
    open(SPEC, "wb").write(blob)
    print(f"froze -> {SPEC}\nsha256 {hashlib.sha256(blob).hexdigest()}")


def score():
    import first_vote as FV, gbm, blend_2027 as B, prereg_2026 as P6
    if os.path.exists(SCORE):
        raise SystemExit(f"already scored: {SCORE}")
    spec_blob = open(SPEC, "rb").read(); spec = json.loads(spec_blob)
    for f, h in spec["code_sha256"].items():
        if _sha(os.path.join(HERE, f)) != h:
            raise SystemExit(f"{f} changed since pre-registration -- refusing to score")
    if list(FV.NUM) != spec["features"]:
        raise SystemExit("feature list changed since pre-registration -- refusing to score")
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    if _train_rows_sha(rows) != spec["train_rows_sha256"]:
        raise SystemExit("training rows changed since pre-registration -- refusing to score")
    tr = [r for r in rows if r["yr"] in spec["train_years"]]; te = [r for r in rows if r["yr"] == TEST]
    if not te:
        raise SystemExit("no 2027 rows yet -- rebuild rows after the 2027 session (first_vote.rebuild_rows)")
    rc = FV.assemble()["rc"]
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    preds = {"reference": gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te)),
             "A": B.predict(tr, te), "B": B.predict_online(tr, te, lambda r: rc[r["bill"]][0][0])}
    y = np.array([r["y"] for r in te], float)
    bill = np.array([f'{r["bill"][0]}|{r["bill"][1]}' for r in te]); same = np.array([bool(r["same"]) for r in te])
    ven = np.array(["sub" if r["ven_sub"] else "com" if r["ven_com"] else "floor" for r in te])
    cham = np.array(["S" if r["chamber_S"] else "H" for r in te])
    doc = {"scored_on": datetime.date.today().isoformat(), "spec_sha256": hashlib.sha256(spec_blob).hexdigest(),
           "arms": {k: P6._metrics(p, y, bill, same, ven, cham) for k, p in preds.items()}}
    open(SCORE, "w").write(json.dumps(doc, indent=1, sort_keys=True))
    print(json.dumps(doc, indent=1, sort_keys=True))


if __name__ == "__main__":
    {"--freeze": freeze, "--score": score}[sys.argv[1]]()
