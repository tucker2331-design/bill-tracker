#!/usr/bin/env python3
"""Supervised ideal points: every legislator x every kind of bill, learned as latent factors -- on top of the GBM.

Owner, 2026-09-28: "i still dont feel like you gotten into complicated statistics that a statistician would ...
combinations ... like if a legislators district is mostly white college educated and they tend to vote pro
abortion then they will likely vote pro abortion again if the historical votes alone didnt tell us."

The GBM already searches combinations of up to six NUMERIC inputs. What it cannot do is combine an IDENTITY (this
member) with a CONTENT (this kind of bill): each member x topic cell is too sparse for a tree. The standard tool is
a latent-factor ("ideal point with bill text") model:

    logit P(yes) = GBM offset + < u_m , v_b > + c_m
    u_m = E[m] + D . d_m          member position: personal part + part predicted from district & party
                                  (so a brand-new member still gets a position from their district)
    v_b = V . z_b                 bill location, from its content: summary words (hashed tf-idf), subject,
                                  committee, patron, patron's party, venue -- known BEFORE the vote
    c_m = member's own lean, shrunk hard toward 0

PROTOCOL (the stacking trap from round 1 is designed out):
  * The GBM offset for each training year comes from a GBM trained ONLY on earlier years (expanding window),
    so the factor stage learns from honest out-of-sample residuals, never from in-sample fits.
  * Hyper-parameters are chosen on 2024 (offset: GBM 2019-2022; factors: 2020-2022). Scored once on 2025
    (offset: GBM on TRAIN_YEARS; factors: 2020-2024). 2026 stays locked.
  * "Hardest third" is reported two ways: re-ranked by the new model, and on the FIXED set of ballots the GBM
    found hardest -- moving the goalposts cannot flatter the number.

numpy only (no scipy on this machine). Run: python3 tools/calibration/ideal_factors.py
"""
from __future__ import annotations
import sys, os, re, math, zlib, pickle, collections, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import first_vote as FV
import gbm
from summary_memory import summaries

H = 4096                       # hashed word buckets
STOP = set("the a an of to and or in on for by with from as at is are be that this any such shall may which "
           "bill provides requires relating certain code virginia section sections".split())
OUT = os.environ.get("IF_OUT", "/tmp")


def _tok(text):
    return [w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in STOP]


def bill_features(keys, corpus):
    """(session,bill) -> (idx int array, val float array): hashed tf-idf words + categorical one-hots."""
    summ = summaries()
    subj = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1); subj[(s, b)] = v
    docs = {k: _tok(summ.get(k, "") or (corpus.get(k) or {}).get("title", "")) for k in keys}
    df = collections.Counter(w for d in docs.values() for w in set(d))
    n = len(docs)
    cat_index = {}
    def cat(name):
        if name not in cat_index: cat_index[name] = H + len(cat_index)
        return cat_index[name]
    feats = {}
    for k in keys:
        d = docs[k]; b = corpus.get(k) or {}
        tf = collections.Counter(d)
        w = {}
        for t, c in tf.items():
            j = zlib.crc32(t.encode()) % H
            w[j] = w.get(j, 0.0) + (1 + math.log(c)) * math.log((n + 1) / (df[t] + 1))
        norm_ = math.sqrt(sum(v * v for v in w.values())) or 1.0
        idx = list(w); val = [v / norm_ for v in w.values()]
        for s_ in subj.get(k, []): idx.append(cat("subj:" + s_)); val.append(1.0)
        room = FV.first_room(b) if b else None
        idx.append(cat("room:" + str(room))); val.append(1.0)
        idx.append(cat("patron:" + str(b.get("chief")))); val.append(1.0)
        idx.append(cat("pparty:" + str(b.get("chief_party")))); val.append(1.0)
        feats[k] = (np.array(idx, np.int64), np.array(val, np.float64))
    return feats, H + len(cat_index)


class Factors:
    def __init__(self, n_members, n_bill_feats, n_demo, k=8, lam=1e-3, lam_c=1e-2, lr=0.02, seed=0):
        r = np.random.default_rng(seed)
        self.E = r.normal(0, .01, (n_members, k)); self.D = r.normal(0, .01, (n_demo, k))
        self.V = r.normal(0, .01, (n_bill_feats, k)); self.c = np.zeros(n_members)
        self.lam, self.lam_c, self.lr, self.k = lam, lam_c, lr, k
        self.m = {n: np.zeros_like(getattr(self, n)) for n in ("E", "D", "V", "c")}
        self.v2 = {n: np.zeros_like(getattr(self, n)) for n in ("E", "D", "V", "c")}
        self.t = 0

    def _bill_vec(self, bidx):
        """bidx: list of (idx,val) -> (B,k) plus flat index arrays for the gradient."""
        rows = np.concatenate([np.full(len(i), r_) for r_, (i, _v) in enumerate(bidx)])
        idx = np.concatenate([i for i, _v in bidx]); val = np.concatenate([v for _i, v in bidx])
        out = np.zeros((len(bidx), self.k)); np.add.at(out, rows, val[:, None] * self.V[idx])
        return out, rows, idx, val

    def logits(self, mem, demo, bidx, offset):
        u = self.E[mem] + demo @ self.D
        v, *_ = self._bill_vec(bidx)
        return offset + (u * v).sum(1) + self.c[mem]

    def _adam(self, name, g):
        b1, b2 = .9, .999
        self.m[name] = b1 * self.m[name] + (1 - b1) * g
        self.v2[name] = b2 * self.v2[name] + (1 - b2) * g * g
        mh = self.m[name] / (1 - b1 ** self.t); vh = self.v2[name] / (1 - b2 ** self.t)
        setattr(self, name, getattr(self, name) - self.lr * mh / (np.sqrt(vh) + 1e-8))

    def fit(self, mem, demo, bidx, offset, y, epochs=6, batch=4096, seed=0, watch=None, every=None):
        r = np.random.default_rng(seed); N = len(y)
        for _ in range(epochs):
            order = r.permutation(N)                       # a fresh shuffle every epoch
            for s in range(0, N, batch):
                ix = order[s:s + batch]
                self.t += 1
                mb, db, bb = mem[ix], demo[ix], [bidx[i] for i in ix]
                u = self.E[mb] + db @ self.D
                v, rows, idx, val = self._bill_vec(bb)
                z = offset[ix] + (u * v).sum(1) + self.c[mb]
                g = (1 / (1 + np.exp(-z)) - y[ix]) / len(ix)                 # dLoss/dlogit
                gu = g[:, None] * v; gv = g[:, None] * u
                gE = np.zeros_like(self.E); np.add.at(gE, mb, gu); gE += self.lam * self.E
                gD = db.T @ gu + self.lam * self.D
                gV = np.zeros_like(self.V); np.add.at(gV, idx, val[:, None] * gv[rows]); gV += self.lam * self.V
                gc = np.zeros_like(self.c); np.add.at(gc, mb, g); gc += self.lam_c * self.c
                for name, grad in (("E", gE), ("D", gD), ("V", gV), ("c", gc)):
                    self._adam(name, grad)
                if watch and every and self.t % every == 0:
                    watch(self)
        return self


def main():
    from corpus import load
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    rows = pickle.load(open(FV.ROWS, "rb"))
    rows = [r for r in rows if r["y"] >= 0 and r["yr"] in (2019, 2020, 2021, 2022, 2024, 2025)]
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    logit = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / np.clip(1 - p, 1e-4, 1))

    # 1) honest GBM offsets: each year predicted by a GBM trained on EARLIER years only
    off_file = os.path.join(OUT, "if_offsets.pkl")
    if os.path.exists(off_file):
        offsets = pickle.load(open(off_file, "rb"))
    else:
        offsets = {}
        for Y, train in [(2020, (2019,)), (2021, (2019, 2020)), (2022, (2019, 2020, 2021)),
                         (2024, (2019, 2020, 2021, 2022)), (2025, FV.TRAIN_YEARS)]:
            tr = [r for r in rows if r["yr"] in train]; te = [r for r in rows if r["yr"] == Y]
            m = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float))
            offsets[Y] = m.predict(X(te)); print(f"  offset {Y} from {train}: done", flush=True)
        pickle.dump(offsets, open(off_file, "wb"))

    keys = sorted({r["bill"] for r in rows})
    feats, n_bf = bill_features(keys, corpus)
    members = sorted({r["who"] for r in rows}); mid = {m: i for i, m in enumerate(members)}
    PARTY = sorted({r["party"] for r in rows})
    def demo(r):
        return [float(r.get(c, 0.0)) for c in FV.DIST_COLS] + [float(r["party"] == p) for p in PARTY] + [float(r["same"])]
    by_year = collections.defaultdict(list)
    for r in rows: by_year[r["yr"]].append(r)
    # standardise the member-side inputs (district shares, incomes) so no one column dominates the projection
    allD = np.array([demo(r) for r in rows], float); mu, sd = allD.mean(0), allD.std(0) + 1e-9
    def arrays(years):
        rs = [r for Y in years for r in by_year[Y]]
        off = np.concatenate([logit(offsets[Y]) for Y in years])
        return rs, np.array([mid[r["who"]] for r in rs]), (np.array([demo(r) for r in rs], float) - mu) / sd, \
            [feats[r["bill"]] for r in rs], off, np.array([r["y"] for r in rs], float)

    def score(p, rs, hard_fixed, label):
        y = np.array([r["y"] for r in rs]); right = (p >= .5) == (y == 1)
        o = np.argsort(np.abs(p - .5)); h = o[:len(o) // 3]
        same = np.array([r["same"] for r in rs])
        print(f"  {label:40s} all {right.mean():.4f}  other-party {right[same == 0].mean():.4f}  "
              f"hardest third (re-ranked) {right[h].mean():.4f}  (fixed GBM set) {right[hard_fixed].mean():.4f}", flush=True)
        return right.mean(), right[hard_fixed].mean()

    def fixed_hard(p):
        o = np.argsort(np.abs(p - .5)); hf = np.zeros(len(p), bool); hf[o[:len(o) // 3]] = True; return hf

    if os.environ.get("IF_CURVE"):
        trs, tm, td, tb, toff, ty = arrays([2020, 2021, 2022])
        vrs, vm, vd, vb, voff, vy = arrays([2024])
        base = ((1 / (1 + np.exp(-voff)) >= .5) == (vy == 1)).mean()
        print(f"CURVE on 2024 -- GBM alone {base:.4f}", flush=True)
        for lam in (1e-2, 3e-2, 1e-1):
            for lr in (0.003,):
                def watch(f, lam=lam, lr=lr):
                    p = 1 / (1 + np.exp(-f.logits(vm, vd, vb, voff)))
                    print(f"  lam={lam} lr={lr} step {f.t:4d}: 2024 all {((p >= .5) == (vy == 1)).mean():.4f}", flush=True)
                Factors(len(members), n_bf, td.shape[1], k=8, lam=lam, lr=lr).fit(tm, td, tb, toff, ty, epochs=3,
                                                                              watch=watch, every=10)
        return

    # 2) choose settings on 2024 (factors learn from 2020-2022)
    trs, tm, td, tb, toff, ty = arrays([2020, 2021, 2022])
    vrs, vm, vd, vb, voff, vy = arrays([2024])
    hf24 = fixed_hard(offsets[2024])
    print("CHOOSE on 2024:")
    score(offsets[2024], vrs, hf24, "GBM alone")
    best = None
    for k in (4, 8):
        for lam in (3e-3, 3e-4):
            for ep in (3, 6):
                f = Factors(len(members), n_bf, td.shape[1], k=k, lam=lam).fit(tm, td, tb, toff, ty, epochs=ep)
                p = 1 / (1 + np.exp(-f.logits(vm, vd, vb, voff)))
                acc, hacc = score(p, vrs, hf24, f"factors k={k} lam={lam} epochs={ep}")
                if best is None or acc > best[0]: best = (acc, k, lam, ep)
    _, k, lam, ep = best
    print(f"chosen on 2024: k={k} lam={lam} epochs={ep}")

    # 3) score once on 2025 (factors learn from 2020-2024)
    trs, tm, td, tb, toff, ty = arrays([2020, 2021, 2022, 2024])
    ers, em, ed, eb, eoff, ey = arrays([2025])
    hf25 = fixed_hard(offsets[2025])
    print("SCORE on 2025:")
    score(offsets[2025], ers, hf25, "GBM alone")
    f = Factors(len(members), n_bf, td.shape[1], k=k, lam=lam).fit(tm, td, tb, toff, ty, epochs=ep)
    p = 1 / (1 + np.exp(-f.logits(em, ed, eb, eoff)))
    score(p, ers, hf25, f"GBM + member x bill factors (k={k})")
    np.save(os.path.join(OUT, "if_p2025.npy"), p)


if __name__ == "__main__":
    main()
