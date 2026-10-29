#!/usr/bin/env python3
"""H3 (fiscal cost) and H5 (what members said in committee) against member votes -- the hardest third.

Both sources exist only for 2025-2026, so these are not the 2021-2025 rolling test:
  H3 FISCAL      fit on 2025 first votes (base = year-ahead model trained 2019-2024), score 2026 (base trained 2019-2025).
                 Inputs, only if the DPB statement was published BEFORE the vote: log yearly cost, budget amendment needed,
                 "no state fiscal impact" -- each x voter side.
  H5 SPEECH      within 2026 (transcripts are mostly 2026), time-forward: fit on votes before the session's median vote
                 date, score votes after it. Inputs from caption segments dated strictly BEFORE the vote: how often the
                 voter was named in earlier debates on bills of the same subject, and how many of those debates carried
                 stated opposition -- x voter side.
2026 is the already-scored test year; these are exploratory and reported as such.
"""
from __future__ import annotations
import sys, os, json, math, pickle, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV, stats as ST, fiscal_effect as FE

lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
rc = FV.assemble()["rc"]


def stack(tr_rows, tr_p, tr_F, te_rows, te_p, te_F, names, label):
    ytr = np.array([r["y"] for r in tr_rows], float); y = np.array([r["y"] for r in te_rows], float)
    preds = []
    for use in (False, True):
        Xtr = np.column_stack([lg(tr_p)] + ([tr_F] if use else [])); Xte = np.column_stack([lg(te_p)] + ([te_F] if use else []))
        nm = ["lg"] + (names if use else [])
        f = ST.logit(Xtr, ytr, nm, ridge=10.0, tol=1e-7, max_iter=200)
        b = np.array([f[n][0] for n in ["const"] + nm])
        preds.append(1 / (1 + np.exp(-(np.column_stack([np.ones(len(Xte)), Xte]) @ b))))
    p0, p1 = preds
    ll = lambda p: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
    d = collections.defaultdict(float)
    for r, a, c in zip(te_rows, ll(p0), ll(p1)):
        d[str(r["bill"])] += a - c
    d = np.array(list(d.values())); z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    hard = np.argsort(np.abs(te_p - .5))[:len(te_p) // 3]
    r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1)
    cov = np.any(te_F != 0, axis=1)
    print(f"{label}: scored {len(y)} ballots ({cov.mean():.0%} with the signal); accuracy {r0.mean():.4f} -> {r1.mean():.4f}; "
          f"hardest third {r0[hard].mean():.4f} -> {r1[hard].mean():.4f}; per-bill log-loss gain {d.mean():+.5f}, z = {z:.1f}")


def fiscal():
    st = {y: json.load(open(os.path.join(FE.FIS, f"{y}.json"))) for y in (2025, 2026)}
    sd = {y: FE.statement_dates(y) for y in (2025, 2026)}
    def feats(r):
        y = int(r["bill"][0]); b = r["bill"][1]; f = st[y].get(b.replace(" ", ""))
        vote_day = rc[r["bill"]][0][0]
        if not f or "parse_error" in f or sd[y].get(b, "9999") >= vote_day:
            return [0.0] * 6
        amt = max(f.get("gf_cost_max", 0), f.get("ngf_cost_max", 0), f.get("summary_amount_max", 0))
        s = float(r["same"]); c = math.log1p(amt / 1e5); a = float(f.get("budget_amendment") or 0); n = float(f.get("no_impact", 0))
        return [c * s, c * (1 - s), a * s, a * (1 - s), n * s, n * (1 - s)]
    tr_rows, tr_p = AC.base_preds()[2025]
    te_rows, te_p = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    stack(tr_rows, tr_p, np.array([feats(r) for r in tr_rows]), te_rows, te_p, np.array([feats(r) for r in te_rows]),
          ["cost_same", "cost_other", "amend_same", "amend_other", "noimpact_same", "noimpact_other"],
          "H3 FISCAL COST x side (fit 2025 -> score 2026)")


def speech():
    segs = json.load(open(os.path.join(HERE, "..", "historical_cache", "va_transcripts", "segments.json")))
    subj = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1); subj[(s, b)] = v
    spoke = collections.defaultdict(list)          # (SURNAME, subject) -> [(date, opposition stated in that debate)]
    for m in segs.values():
        for bill, f in m["bills"].items():
            for t in subj.get((m["session"], bill), []):
                for name in f["members"]:
                    spoke[(name.replace("'S", ""), t)].append((m["date"], f["oppose"] > 0))
    te_rows, te_p = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    def feats(r):
        d = rc[r["bill"]][0][0]; sur = r["who"].split()[-1].upper().replace("-", "")
        n = o = 0
        for t in subj.get(r["bill"], []):
            for dd, opp in spoke.get((sur, t), []):
                if dd < d:
                    n += 1; o += opp
        s = float(r["same"])
        return [math.log1p(n) * s, math.log1p(n) * (1 - s), (o / n if n else 0.0) * s, (o / n if n else 0.0) * (1 - s)]
    F = np.array([feats(r) for r in te_rows]); days = np.array([rc[r["bill"]][0][0] for r in te_rows])
    med = sorted(days)[len(days) // 2]; a = days < med; b = ~a
    stack([r for r, m in zip(te_rows, a) if m], te_p[a], F[a], [r for r, m in zip(te_rows, b) if m], te_p[b], F[b],
          ["spoke_same", "spoke_other", "opp_share_same", "opp_share_other"],
          f"H5 WHAT MEMBERS SAID ON THIS TOPIC BEFORE x side (2026: fit before {med}, score after)")


if __name__ == "__main__":
    fiscal()
    speech()
