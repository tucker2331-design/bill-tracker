#!/usr/bin/env python3
"""Which member-card reasons are real determinants? (owner, 2026-09-30: "find more items that meet this criteria")

The three checks a reason must pass before a member card may show it:
  1. changing it moves the prediction            -- why_member.py's swap test, per member
  2. the member actually has data for it          -- why_member.py's absent-data flags, per member
  3. it makes next-year forecasts better          -- THIS file, once per reason
Check 3 = leave-one-group-out, rolling origin: for 2021 / 2022 / 2024 / 2025, a model trained only on earlier years,
with and without the reason's inputs. Per-bill paired log-loss (without - with), pooled over all four years; the reason
passes at z >= 3 (accept.Z_ACCEPT). The full model's predictions come from accept.base_preds() (same settings).

Groups are first_vote.GROUPS, with the mixed "subject (party and legislator)" group split into what it actually holds.

Run: python3 tools/calibration/reason_gate.py run <group-index> ...   (one process per index; results cached)
     python3 tools/calibration/reason_gate.py report
"""
from __future__ import annotations
import sys, os, json, math, pickle, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV, gbm

SPLIT = {
    "the bill's subject": ["subj_has", "subj_party", "subj_n"],
    "the legislator on this subject": ["msubj", "msubj_n"],
    "this subcommittee's record": ["is_subroom", "subroom_rate", "subroom_n"],
    "this room, this session": ["ses_rate", "ses_n"],
    "the legislator on this patron's bills": ["mpat_rate", "mpat_n"],
    "the legislator breaking with party this session": ["mdef_ses"],
    "the companion bill's earlier vote": ["comp_has", "comp_party"],
}
GROUPS = {k: v for k, v in FV.GROUPS.items() if k != "subject (party and legislator)"}
GROUPS.update(SPLIT)
NAMES = list(GROUPS)
assert sorted(c for v in GROUPS.values() for c in v) == sorted(FV.NUM), "groups must cover the inputs exactly once"
OUT = os.path.join(os.path.dirname(FV.ROWS), "reason_gate")


def run(i):
    name = NAMES[i]; drop = set(GROUPS[name]); cols = [c for c in FV.NUM if c not in drop]
    path = os.path.join(OUT, f"{i:02d}.json")
    if os.path.exists(path):
        return
    B = AC.base_preds()
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    X = lambda rs: np.array([[r[c] for c in cols] for r in rs], float)
    res = {"name": name, "inputs": sorted(drop), "years": {}}
    for t, trn in AC.ORIGINS:
        tr = [r for r in rows if r["yr"] in trn]
        te, pfull = B[t]
        pw = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te))
        y = np.array([r["y"] for r in te], float)
        d = collections.defaultdict(float)
        for b, a, c in zip([str(r["bill"]) for r in te], AC._ll(pw, y), AC._ll(pfull, y)):
            d[b] += a - c                                   # + = the reason helps
        res["years"][t] = {"per_bill": list(d.values()),
                           "acc_with": float(((pfull >= .5) == (y == 1)).mean()),
                           "acc_without": float(((pw >= .5) == (y == 1)).mean())}
        print(f"  {name} {t} done", flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(path, "w"))


BASE = FV.GROUPS["party & standing"] + FV.GROUPS["venue"]
OUT_ADD = os.path.join(os.path.dirname(FV.ROWS), "reason_gate_add")


def run_add(i):
    """The other reading of 'adding it makes forecasts better': a bare model (party & standing + venue) with and
    without this ONE group. Leave-one-out (run) measures what a group adds that nothing else carries; this measures
    whether it carries information at all. Groups that overlap (party is carried by the room records) fail
    leave-one-out and pass here."""
    name = NAMES[i]
    if name in ("party & standing", "venue"):
        return
    path = os.path.join(OUT_ADD, f"{i:02d}.json")
    if os.path.exists(path):
        return
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
    res = {"name": name, "years": {}}
    for t, trn in AC.ORIGINS:
        tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == t]
        y = np.array([r["y"] for r in te], float); ytr = np.array([r["y"] for r in tr], float)
        preds = []
        for cols in (BASE, BASE + GROUPS[name]):
            X = lambda rs: np.array([[r[c] for c in cols] for r in rs], float)
            preds.append(gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), ytr).predict(X(te)))
        d = collections.defaultdict(float)
        for b, a, c in zip([str(r["bill"]) for r in te], AC._ll(preds[0], y), AC._ll(preds[1], y)):
            d[b] += a - c
        res["years"][t] = {"per_bill": list(d.values()),
                           "acc_base": float(((preds[0] >= .5) == (y == 1)).mean()),
                           "acc_add": float(((preds[1] >= .5) == (y == 1)).mean())}
        print(f"  +{name} {t} done", flush=True)
    os.makedirs(OUT_ADD, exist_ok=True)
    json.dump(res, open(path, "w"))


def report_add():
    out = []
    for i, name in enumerate(NAMES):
        path = os.path.join(OUT_ADD, f"{i:02d}.json")
        if not os.path.exists(path):
            continue
        r = json.load(open(path))
        d = np.concatenate([np.array(v["per_bill"]) for v in r["years"].values()])
        z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
        yrs = " ".join(f"{t}:{v['acc_add'] - v['acc_base']:+.4f}" for t, v in r["years"].items())
        out.append((z, name, yrs))
    print(f"{'added to party + venue':50s} {'pooled z':>9s}  verdict   accuracy gain by year")
    for z, name, yrs in sorted(out, reverse=True):
        print(f"{name:50s} {z:9.1f}  {'PASS' if z >= AC.Z_ACCEPT else 'fail':7s}  {yrs}")


def report():
    rows = []
    for i, name in enumerate(NAMES):
        path = os.path.join(OUT, f"{i:02d}.json")
        if not os.path.exists(path):
            rows.append((name, None)); continue
        r = json.load(open(path))
        d = np.concatenate([np.array(v["per_bill"]) for v in r["years"].values()])
        z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
        yrs = " ".join(f"{t}:{v['acc_with'] - v['acc_without']:+.4f}" for t, v in r["years"].items())
        rows.append((name, (z, d.mean(), yrs)))
    print(f"{'reason':50s} {'pooled z':>9s}  verdict   accuracy gain by year (with - without)")
    for name, v in sorted(rows, key=lambda x: -(x[1][0] if x[1] else -99)):
        if v is None:
            print(f"{name:50s} {'(not run)':>9s}"); continue
        z, m, yrs = v
        print(f"{name:50s} {z:9.1f}  {'PASS' if z >= AC.Z_ACCEPT else 'fail':7s}  {yrs}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        for a in sys.argv[2:]:
            run(int(a))
    elif sys.argv[1] == "add":
        for a in sys.argv[2:]:
            run_add(int(a))
    elif sys.argv[1] == "report_add":
        report_add()
    elif sys.argv[1] == "list":
        for i, n in enumerate(NAMES):
            print(i, n, GROUPS[n])
    else:
        report()
