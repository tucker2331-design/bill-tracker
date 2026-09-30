#!/usr/bin/env python3
"""The locked 2026 test: pre-register every rule, THEN score once. Five-perspective panel, 2026-09-29
([[testing/panel_2026-09-29]]): 2025 was used to judge ~35 approaches, so it is a VALIDATION year; the only clean,
quotable number is 2026, and it is only clean if the model, the cutoffs and the metric list are fixed before it is
opened.

  --freeze   writes frozen/prereg_2026.json (the spec) and prints its SHA-256. Refuses if it already exists.
  --score    reads the frozen spec, checks the model code has not changed since, trains once on every year before
             2026, scores 2026 ONCE, writes frozen/score_2026.json. Refuses if a score already exists.

Nothing in --score is chosen at scoring time: the model, training years, feature list, label cutoffs, bootstrap
seed, slices and metric definitions are all read from the frozen spec.
"""
from __future__ import annotations
import sys, os, json, hashlib, pickle, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np

SPEC = os.path.join(HERE, "frozen", "prereg_2026.json")
SCORE = os.path.join(HERE, "frozen", "score_2026.json")
CODE = ("first_vote.py", "gbm.py")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def freeze():
    import first_vote as FV
    if os.path.exists(SPEC):
        raise SystemExit(f"already frozen: {SPEC} -- pre-registration is written ONCE; never overwrite")
    spec = {
        "frozen_on": datetime.date.today().isoformat(),
        "why": "2025 judged ~35 approaches (validation year); 2026 is the only clean external score",
        "target": "each legislator's ballot at a bill's FIRST recorded roll call (sub, committee or floor), "
                  "HB/SB with a resolved patron party; rows built by first_vote.features() replaying day by day",
        "model": {"class": "gbm.GBM", "depth": 6, "lr": 0.03, "rounds": 260, "early_stopping": "none"},
        "train_years": sorted(set(FV.TRAIN_YEARS) | {2025}),
        "test_year": 2026,
        "features": list(FV.NUM),
        "code_sha256": {f: _sha(os.path.join(HERE, f)) for f in CODE},
        "rows_file_sha256": _sha(FV.ROWS),
        "labels": {"Likely": "|p-0.5| >= 0.30", "Leans": "0.10 <= |p-0.5| < 0.30", "Toss-up": "|p-0.5| < 0.10"},
        "decision": "yes if p >= 0.5",
        "metrics": {
            "accuracy": "share of ballots called right",
            "log_loss": "mean -[y ln p + (1-y) ln(1-p)], p clipped to [1e-6, 1-1e-6]",
            "brier": "mean (p-y)^2",
            "other_party_accuracy": "ballots where the voter is not of the patron's party",
            "party_position_accuracy": "per (bill, voter-is-patron's-party) group: mean p >= .5 vs mean y >= .5",
            "room_outcome_accuracy": "per bill: sum p > n/2 vs yes-count > n/2",
            "label_calibration": "accuracy and share within each label",
            "risk_coverage": "accuracy of the most-confident k% of ballots, k = 10..100 step 10, all and other-party",
            "hardest_third": "accuracy on the third of ballots nearest p=0.5 (diagnostic only, no target)",
            "slices": ["all", "other-party", "same-party", "subcommittee", "committee", "floor", "House", "Senate"],
        },
        "baselines": ["always yes", "logistic regression on party & standing + venue (first_vote.GROUPS)"],
        "intervals": {"method": "bill-clustered bootstrap (resample bills with replacement)", "B": 2000, "seed": 2026},
        "expected_from_validation": {
            "note": "written BEFORE scoring; 2026 inside these ranges = the validation numbers held",
            "accuracy_2021_2025_range": [0.8436, 0.8609],
            "accuracy_2025_bill_clustered_95": [0.850, 0.872],
            "Likely_2025_95": [0.936, 0.953], "Leans_2025_95": [0.675, 0.734], "Tossup_2025_95": [0.536, 0.612],
            "room_outcome_2025": 0.884,
        },
        "known_gaps": ["carried-over bills have no summary-wording score (txt_has=0), e.g. HB 1515"],
        "goals_retired": ["break 95", "hardest third > 80%"],
    }
    blob = json.dumps(spec, indent=1, sort_keys=True).encode()
    os.makedirs(os.path.dirname(SPEC), exist_ok=True)
    open(SPEC, "wb").write(blob)
    print(f"froze pre-registration -> {SPEC}\nsha256 {hashlib.sha256(blob).hexdigest()}")


def _ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _metrics(p, y, rows_bill, rows_same, ven, cham):
    right = (p >= .5) == (y == 1)
    out = {"n": int(len(y)), "accuracy": float(right.mean()), "log_loss": float(_ll(p, y).mean()),
           "brier": float(np.mean((p - y) ** 2))}
    for name, m in (("other-party", ~rows_same), ("same-party", rows_same), ("subcommittee", ven == "sub"),
                    ("committee", ven == "com"), ("floor", ven == "floor"), ("House", cham == "H"),
                    ("Senate", cham == "S")):
        out[f"acc_{name}"] = float(right[m].mean()) if m.any() else None
    g = collections.defaultdict(list)
    for i, k in enumerate(zip(rows_bill, rows_same)):
        g[k].append(i)
    out["party_position_accuracy"] = float(np.mean([(p[I].mean() >= .5) == (y[I].mean() >= .5)
                                                   for I in map(np.array, g.values())]))
    gb = collections.defaultdict(list)
    for i, b in enumerate(rows_bill):
        gb[b].append(i)
    out["room_outcome_accuracy"] = float(np.mean([(p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2)
                                                 for I in map(np.array, gb.values())]))
    lab = np.where(np.abs(p - .5) >= .3, "Likely", np.where(np.abs(p - .5) >= .1, "Leans", "Toss-up"))
    for L in ("Likely", "Leans", "Toss-up"):
        m = lab == L
        out[f"share_{L}"] = float(m.mean()); out[f"acc_{L}"] = float(right[m].mean()) if m.any() else None
    o = np.argsort(np.abs(p - .5))
    out["hardest_third"] = float(right[o[:len(o) // 3]].mean())
    conf = np.argsort(-np.abs(p - .5), kind="mergesort")
    for k in range(10, 101, 10):
        top = conf[:max(1, len(conf) * k // 100)]
        out[f"rc_all_{k}"] = float(right[top].mean())
        oth = conf[~rows_same[conf]]; topo = oth[:max(1, len(oth) * k // 100)]
        out[f"rc_other_{k}"] = float(right[topo].mean())
    return out


def score():
    if os.path.exists(SCORE):
        raise SystemExit(f"already scored: {SCORE} -- the locked test is scored ONCE")
    spec_blob = open(SPEC, "rb").read(); spec = json.loads(spec_blob)
    for f, h in spec["code_sha256"].items():
        if _sha(os.path.join(HERE, f)) != h:
            raise SystemExit(f"{f} changed since pre-registration -- refusing to score")
    import first_vote as FV, gbm, stats as ST
    if _sha(FV.ROWS) != spec["rows_file_sha256"]:
        raise SystemExit("feature rows changed since pre-registration -- refusing to score")
    if list(FV.NUM) != spec["features"]:
        raise SystemExit("feature list changed since pre-registration -- refusing to score")
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    tr = [r for r in rows if r["yr"] in spec["train_years"]]
    te = [r for r in rows if r["yr"] == spec["test_year"]]
    cols = spec["features"]; M = spec["model"]
    X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
    ytr = np.array([r["y"] for r in tr], float); y = np.array([r["y"] for r in te], float)
    p = gbm.GBM(depth=M["depth"], lr=M["lr"], rounds=M["rounds"]).fit(X(tr, cols), ytr).predict(X(te, cols))
    # baselines
    bcols = FV.GROUPS["party & standing"] + FV.GROUPS["venue"]
    f = ST.logit(X(tr, bcols), ytr, bcols, ridge=1e-3)
    b = np.array([f[k][0] for k in ["const"] + bcols])
    with np.errstate(all="ignore"):
        pb = 1 / (1 + np.exp(-(np.column_stack([np.ones(len(te)), X(te, bcols)]) @ b)))
    bill = np.array([f'{r["bill"][0]}|{r["bill"][1]}' for r in te]); same = np.array([bool(r["same"]) for r in te])
    ven = np.array(["sub" if r["ven_sub"] else "com" if r["ven_com"] else "floor" for r in te])
    cham = np.array(["S" if r["chamber_S"] else "H" for r in te])
    point = _metrics(p, y, bill, same, ven, cham)
    base = {"always_yes_accuracy": float(max(y.mean(), 1 - y.mean())),
            "always_yes_log_loss": float(_ll(np.full(len(y), ytr.mean()), y).mean()),
            "logit_party_standing_venue": _metrics(pb, y, bill, same, ven, cham)}
    ub, inv = np.unique(bill, return_inverse=True)
    members = [np.where(inv == k)[0] for k in range(len(ub))]
    rng = np.random.default_rng(spec["intervals"]["seed"]); draws = collections.defaultdict(list)
    for _ in range(spec["intervals"]["B"]):
        idx = np.concatenate([members[k] for k in rng.integers(0, len(ub), len(ub))])
        m = _metrics(p[idx], y[idx], bill[idx], same[idx], ven[idx], cham[idx])
        for k, v in m.items():
            if isinstance(v, float):
                draws[k].append(v)
        draws["d_log_loss_vs_logit"].append(float(_ll(pb[idx], y[idx]).mean() - _ll(p[idx], y[idx]).mean()))
    ci = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items()}
    doc = {"scored_on": datetime.date.today().isoformat(), "spec_sha256": hashlib.sha256(spec_blob).hexdigest(),
           "n_train": len(tr), "n_bills": int(len(ub)), "point": point, "ci95": ci, "baselines": base}
    open(SCORE, "w").write(json.dumps(doc, indent=1, sort_keys=True))
    print(json.dumps(doc, indent=1, sort_keys=True))


if __name__ == "__main__":
    {"--freeze": freeze, "--score": score}[sys.argv[1]]()
