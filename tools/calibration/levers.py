#!/usr/bin/env python3
"""New modelling techniques for the member vote and the room result (owner, 2026-10-16: "try things in ways you dont
normally ... make use of your advanced stat mapping and model weighting ... to make a llm accurate they use thousands of
tuned levers").

One test frame for every technique, so the results compare directly:
  CHOOSE    learn 2019-2022, score 2024          (settings are chosen here only)
  CONFIRM   learn 2019-2022 + 2024, score 2025
  REPEAT    learn 2019-2022 + 2024 + 2025, score 2026   (already-scored test year: a replication)
Measures per split: member accuracy, log loss, the FIXED hardest third (the third the base model is least sure of),
room result (most members yes) accuracy. The base model is the locked one (depth 6, lr .03, 260 rounds).

Techniques (python3 levers.py <name> [json settings]):
  gbm      the gradient-boosted trees with given settings, incl. row/column subsampling and bagging (L1, L2, L6)
  room     joint room model: second stage reads the first-stage predictions of the other members in the room (L3)
  mlp      neural network with learned codes for member, patron and committee (L4)
  direct   room result predicted directly per vote, blended with the member total (L5)
Results are appended to .cache/levers.jsonl.
"""
from __future__ import annotations
import sys, os, json, math, pickle, time, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, gbm, accept as AC

SPLITS = {"choose": ((2019, 2020, 2021, 2022), 2024), "confirm": ((2019, 2020, 2021, 2022, 2024), 2025),
          "repeat": ((2019, 2020, 2021, 2022, 2024, 2025), 2026)}
OUT = os.path.join(HERE, ".cache", "levers.jsonl")
PRED = os.path.join(HERE, ".cache", "levers_preds")
CUR_SPLIT = None
_rows = None


def _key(settings):
    import hashlib
    return hashlib.sha1(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:10]


def rows():
    global _rows
    if _rows is None:
        _rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    return _rows


def base_p(split):
    """The locked model's predictions for the test year (cached) -- defines the fixed hardest third."""
    if split == "repeat":
        te, p = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    else:
        te, p = AC.base_preds()[SPLITS[split][1]]
    return te, p


def metrics(p, te, p_base):
    y = np.array([r["y"] for r in te], float); right = (p >= .5) == (y == 1)
    hard = np.argsort(np.abs(p_base - .5))[:len(p) // 3]
    g = collections.defaultdict(list)
    for i, r in enumerate(te):
        g[r["bill"]].append(i)
    room = np.mean([(p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2) for I in map(np.array, g.values())])
    oth = np.array([not r["same"] for r in te])
    return {"acc": float(right.mean()), "hard": float(right[hard].mean()), "other": float(right[oth].mean()),
            "room": float(room), "logloss": float(AC._ll(p, y).mean())}


def per_bill_gain(p0, p1, te):
    y = np.array([r["y"] for r in te], float); d = collections.defaultdict(float)
    for r, a, b in zip(te, AC._ll(p0, y), AC._ll(p1, y)):
        d[str(r["bill"])] += a - b
    d = np.array(list(d.values()))
    return float(d.mean()), float(d.mean() / (d.std(ddof=1) / math.sqrt(len(d))))


def run(name, fn, settings, splits=("choose",)):
    for sp in splits:
        trn, ty = SPLITS[sp]
        tr = [r for r in rows() if r["yr"] in trn]; te_b, p0 = base_p(sp)
        te = [r for r in rows() if r["yr"] == ty]
        assert [r["who"] for r in te] == [r["who"] for r in te_b], "row order must match the cached base predictions"
        global CUR_SPLIT
        CUR_SPLIT = sp
        t0 = time.time(); p1 = fn(tr, te, settings)
        m0, m1 = metrics(p0, te, p0), metrics(p1, te, p0); g, z = per_bill_gain(p0, p1, te)
        rec = {"technique": name, "settings": settings, "split": sp, "base": m0, "new": m1, "gain": g, "z": z,
               "seconds": round(time.time() - t0)}
        # keep the predictions so blends of two techniques cost seconds, not another 30-minute refit
        os.makedirs(PRED, exist_ok=True)
        np.save(os.path.join(PRED, f"{name}_{sp}_{_key(settings)}.npy"), p1)
        with open(OUT, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"{name} {json.dumps(settings)} [{sp} {ty}] member {m0['acc']:.4f}->{m1['acc']:.4f}  hard {m0['hard']:.4f}->"
              f"{m1['hard']:.4f}  room {m0['room']:.4f}->{m1['room']:.4f}  z {z:+.1f}", flush=True)


# ---------------- L1 / L2 / L6: gradient-boosted trees with more levers ----------------
class GBMX(gbm.GBM):
    """gbm.GBM plus row subsampling, column subsampling per tree, and sample weights. Same tree-growing code."""
    def __init__(self, subsample=1.0, colsample=1.0, seed=0, **kw):
        super().__init__(**kw); self.subsample, self.colsample, self.seed = subsample, colsample, seed

    def fit(self, X, y, w=None):
        X = np.asarray(X, float); y = np.asarray(y, float); n, k = X.shape
        w = np.ones(n) if w is None else np.asarray(w, float)
        self.cuts = [np.unique(np.quantile(X[:, j], np.linspace(0, 1, self.nbins + 1)[1:-1])) for j in range(k)]
        B = self._bin(X); rng = np.random.default_rng(self.seed)
        p0 = np.clip(np.average(y, weights=w), 1e-4, 1 - 1e-4); self.base = np.log(p0 / (1 - p0))
        F = np.full(n, self.base); self.trees = []; self.tree_cols = []
        for _ in range(self.rounds):
            p = 1 / (1 + np.exp(-F)); g = (p - y) * w; h = np.maximum(p * (1 - p), 1e-6) * w
            rows_ = rng.random(n) < self.subsample if self.subsample < 1 else np.ones(n, bool)
            cols = np.sort(rng.choice(k, max(1, int(round(k * self.colsample))), replace=False)) if self.colsample < 1 else np.arange(k)
            gm = np.where(rows_, g, 0.0); hm = np.where(rows_, h, 0.0)
            tree = self._grow(B[:, cols], gm, hm)
            F += self.lr * self._apply(tree, B[:, cols])
            self.trees.append(tree); self.tree_cols.append(cols)
        return self

    def predict(self, X):
        B = self._bin(np.asarray(X, float)); F = np.full(len(B), self.base)
        for tree, cols in zip(self.trees, self.tree_cols):
            F += self.lr * self._apply(tree, B[:, cols])
        return 1 / (1 + np.exp(-F))


def cols_of(s):
    """FV.NUM minus s["drop"] (research: test a model without some inputs)."""
    return [c for c in FV.NUM if c not in s.get("drop", [])] + list(s.get("extra", []))


def gbm_fn(tr, te, s):
    C = cols_of(s)
    X = lambda rs: np.array([[r[c] for c in C] for r in rs], float)
    Xtr, ytr, Xte = X(tr), np.array([r["y"] for r in tr], float), X(te)
    w = None
    if s.get("recency"):                         # L8: recent years count more (members, chairs, majority change)
        last = max(r["yr"] for r in tr)
        w = np.array([s["recency"] ** (last - r["yr"]) for r in tr], float); w *= len(w) / w.sum()
    if s.get("hard_weight"):                     # L6: weight uncertain training votes more (from a quick pilot model)
        pilot = gbm.GBM(depth=4, lr=.1, rounds=80).fit(Xtr, ytr).predict(Xtr)
        w = (1 if w is None else w) * (1 + s["hard_weight"] * (1 - 2 * np.abs(pilot - .5)))
    preds = []
    for b in range(s.get("bags", 1)):
        m = GBMX(depth=s.get("depth", 6), lr=s.get("lr", .03), rounds=s.get("rounds", 260), lam=s.get("lam", 5.0),
                 min_h=s.get("min_h", 20.0), bins=s.get("bins", 32), subsample=s.get("subsample", 1.0),
                 colsample=s.get("colsample", 1.0), seed=b)
        preds.append(m.fit(Xtr, ytr, w).predict(Xte))
    return np.mean(preds, axis=0)


# ---------------- L3: joint room model ----------------
def room_fn(tr, te, s):
    """Stage 1: the base trees. Stage 2: the same inputs plus what stage 1 predicts for the OTHER members of the room
    (own party mean / min / max, other party mean, predicted yes count share). Stage-1 predictions for the training
    rows come from models that did not see that year (leave-one-year-out), so stage 2 learns from honest inputs."""
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    kw = dict(depth=6, lr=.03, rounds=260)
    years = sorted({r["yr"] for r in tr}); p_tr = np.zeros(len(tr))
    for y in years:
        a = [i for i, r in enumerate(tr) if r["yr"] != y]; b = [i for i, r in enumerate(tr) if r["yr"] == y]
        m = gbm.GBM(**kw).fit(X([tr[i] for i in a]), np.array([tr[i]["y"] for i in a], float))
        p_tr[b] = m.predict(X([tr[i] for i in b]))
    p_te = gbm.GBM(**kw).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te))
    def ctx(rs, p):
        g = collections.defaultdict(list)
        for i, r in enumerate(rs):
            g[r["bill"]].append(i)
        out = np.zeros((len(rs), 5))
        for I in g.values():
            for i in I:
                own = [p[j] for j in I if j != i and rs[j]["same"] == rs[i]["same"]]
                oth = [p[j] for j in I if rs[j]["same"] != rs[i]["same"]]
                allp = [p[j] for j in I if j != i]
                out[i] = [np.mean(own) if own else .5, min(own) if own else .5, max(own) if own else .5,
                          np.mean(oth) if oth else .5, (np.mean(np.array(allp) >= .5) if allp else .5)]
        return out
    for _ in range(s.get("iterations", 1)):
        X2tr = np.column_stack([X(tr), ctx(tr, p_tr), p_tr]); X2te = np.column_stack([X(te), ctx(te, p_te), p_te])
        m2 = gbm.GBM(depth=s.get("depth", 4), lr=.05, rounds=s.get("rounds", 200)).fit(X2tr, np.array([r["y"] for r in tr], float))
        p_te_new = m2.predict(X2te); p_tr = m2.predict(X2tr); p_te = p_te_new
    return p_te


# ---------------- L4: neural network with learned codes ----------------
def mlp_fn(tr, te, s):
    """A two-layer network (numpy, Adam) on the standardised inputs plus learned codes (embeddings) for the member,
    the patron and the committee. Unseen codes in the test year fall back to an 'unknown' code. Early stopping on the
    last training year. Optionally averaged with the base trees (blend)."""
    from corpus import load
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    pat = lambda r: corpus.get(r["bill"], {}).get("chief_key") or corpus.get(r["bill"], {}).get("chief") or "?"
    room = lambda r: FV.first_room(corpus[r["bill"]]) if r["bill"] in corpus else "?"
    ids = {}
    for name, f in (("m", lambda r: r["who"]), ("p", pat), ("c", room)):
        vals = collections.Counter(f(r) for r in tr)
        ids[name] = ({v: i + 1 for i, (v, c) in enumerate(vals.most_common()) if c >= 20}, f)
    Xn = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    # inputs that never change in the training years (district data starts 2024) got sd ~ 1e-6 and blew up to ~1e6 in
    # the test year -- the first two runs failed that way (2026-10-16). Constant columns get scale 1; values capped +-10.
    Xtr, Xte = Xn(tr), Xn(te); mu, sd = Xtr.mean(0), Xtr.std(0)
    sd = np.where(sd < 1e-6, 1.0, sd)
    Xtr, Xte = np.clip((Xtr - mu) / sd, -10, 10), np.clip((Xte - mu) / sd, -10, 10)
    I = lambda rs: np.array([[ids[k][0].get(ids[k][1](r), 0) for k in ("m", "p", "c")] for r in rs])
    Itr, Ite = I(tr), I(te); ytr = np.array([r["y"] for r in tr], float)
    rng = np.random.default_rng(s.get("seed", 0)); E = s.get("emb", 8); H = s.get("hidden", 64)
    sizes = [len(ids[k][0]) + 1 for k in ("m", "p", "c")]
    P = {"E0": rng.normal(0, .05, (sizes[0], E)), "E1": rng.normal(0, .05, (sizes[1], E)), "E2": rng.normal(0, .05, (sizes[2], E)),
         "W1": rng.normal(0, 1 / math.sqrt(Xtr.shape[1] + 3 * E), (Xtr.shape[1] + 3 * E, H)), "b1": np.zeros(H),
         "W2": rng.normal(0, 1 / math.sqrt(H), (H, 1)), "b2": np.zeros(1)}
    M = {k: np.zeros_like(v) for k, v in P.items()}; V = {k: np.zeros_like(v) for k, v in P.items()}
    last = max(r["yr"] for r in tr); val = np.array([r["yr"] == last for r in tr]); fit_ = ~val
    def forward(X, Ix):
        Z = np.column_stack([X, P["E0"][Ix[:, 0]], P["E1"][Ix[:, 1]], P["E2"][Ix[:, 2]]])
        A = np.maximum(Z @ P["W1"] + P["b1"], 0); o = np.clip((A @ P["W2"] + P["b2"])[:, 0], -30, 30)
        return Z, A, 1 / (1 + np.exp(-o))
    lr, wd, bs, t = s.get("lr", 5e-4), s.get("wd", 1e-4), 1024, 0
    best, best_P, bad = 1e9, None, 0
    idx = np.where(fit_)[0]
    for ep in range(s.get("epochs", 30)):
        rng.shuffle(idx)
        for k0 in range(0, len(idx), bs):
            b = idx[k0:k0 + bs]; Z, A, p = forward(Xtr[b], Itr[b]); d = (p - ytr[b])[:, None] / len(b)
            G = {"W2": A.T @ d + wd * P["W2"], "b2": d.sum(0)}
            dA = (d @ P["W2"].T) * (A > 0); G["W1"] = Z.T @ dA + wd * P["W1"]; G["b1"] = dA.sum(0)
            dZ = dA @ P["W1"].T; nX = Xtr.shape[1]
            for j, key in enumerate(("E0", "E1", "E2")):
                g = np.zeros_like(P[key]); np.add.at(g, Itr[b][:, j], dZ[:, nX + j * E: nX + (j + 1) * E]); G[key] = g + wd * P[key]
            t += 1
            # gradient clipping: the first run diverged (logits overflowed and every prediction fell to 0)
            norm = math.sqrt(sum(float((v ** 2).sum()) for v in G.values()))
            if norm > 5.0:
                G = {k_: v * (5.0 / norm) for k_, v in G.items()}
            for key in P:
                M[key] = .9 * M[key] + .1 * G[key]; V[key] = .999 * V[key] + .001 * G[key] ** 2
                P[key] -= lr * (M[key] / (1 - .9 ** t)) / (np.sqrt(V[key] / (1 - .999 ** t)) + 1e-8)
        _, _, pv = forward(Xtr[val], Itr[val]); l = float(AC._ll(pv, ytr[val]).mean())
        if l < best - 1e-4:
            best, best_P, bad = l, {k: v.copy() for k, v in P.items()}, 0
        else:
            bad += 1
            if bad >= 3:
                break
    P.update(best_P)
    # refit on all training years would change the early-stopping point; keep the validated weights
    _, _, p = forward(Xte, Ite)
    if s.get("blend"):
        p = s["blend"] * p + (1 - s["blend"]) * gbm.GBM(depth=6, lr=.03, rounds=260).fit(
            np.array([[r[c] for c in FV.NUM] for r in tr], float), ytr).predict(np.array([[r[c] for c in FV.NUM] for r in te], float))
    return p


# ---------------- L5: direct room-result model ----------------
def direct_fn(tr, te, s):
    """A bill-level model predicts 'most members vote yes' directly; each member's probability is then shifted so the
    room total agrees with it (weight s['w']). Inputs: the side-averaged inputs (shape_first.bill_table)."""
    import shape_first as SF
    kw = dict(depth=6, lr=.03, rounds=260)
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    if s.get("bags"):                                   # combine with model averaging (L2): the member base is bagged
        p_mem = gbm_fn(tr, te, {k: s[k] for k in ("bags", "subsample", "colsample") if k in s})
    else:
        p_mem = gbm.GBM(**kw).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te))
    ktr, Xb_tr, _Y, _ = SF.bill_table(tr); kte, Xb_te, _Y2, _ = SF.bill_table(te)
    g = collections.defaultdict(list)
    for r in tr:
        g[r["bill"]].append(r["y"])
    ymaj = np.array([float(np.mean(g[k]) > .5) for k in ktr])
    q = dict(zip(kte, gbm.GBM(depth=4, lr=.05, rounds=200).fit(Xb_tr, ymaj).predict(Xb_te)))
    gi = collections.defaultdict(list)
    for i, r in enumerate(te):
        gi[r["bill"]].append(i)
    p = p_mem.copy(); w = s.get("w", .5)
    for k, I in gi.items():
        I = np.array(I); share = p_mem[I].mean()
        target = (1 - w) * share + w * q[k]                      # move the room's mean toward the direct estimate
        lo = np.log(np.clip(p_mem[I], 1e-6, 1 - 1e-6) / (1 - np.clip(p_mem[I], 1e-6, 1 - 1e-6)))
        a, b = -8.0, 8.0                                         # shift every member by the same log-odds amount
        for _ in range(40):
            c = (a + b) / 2
            if (1 / (1 + np.exp(-(lo + c)))).mean() < target: a = c
            else: b = c
        p[I] = 1 / (1 + np.exp(-(lo + (a + b) / 2)))
    return p


# ---------------- L7: a different model family -- penalised logistic with hinges (a smooth additive model) ----------------
def linear_fn(tr, te, s):
    """Every input standardised, plus `hinges` piecewise-linear bends per input at training quantiles (an additive
    model, like a GAM), each also crossed with the voter's side (+1 own party, -1 other). Ridge `lam`, penalised Newton.
    Trees cut inputs into steps; this family draws smooth slopes -- its errors differ, which is what a blend needs."""
    C = cols_of(s)
    def feats(rs, ref=None):
        X = np.array([[r[c] for c in C] for r in rs], float)
        if ref is None:
            mu, sd = X.mean(0), X.std(0); sd = np.where(sd < 1e-6, 1.0, sd)
            Z = np.clip((X - mu) / sd, -10, 10)
            knots = [np.unique(np.quantile(Z[:, j], np.linspace(0, 1, s.get("hinges", 0) + 2)[1:-1])) for j in range(Z.shape[1])]
            ref = (mu, sd, knots)
        mu, sd, knots = ref
        Z = np.clip((X - mu) / sd, -10, 10)
        cols = [Z] + [np.maximum(Z[:, j:j + 1] - k, 0) for j in range(Z.shape[1]) for k in knots[j]]
        F = np.column_stack(cols); side = np.array([1.0 if r["same"] else -1.0 for r in rs])[:, None]
        extra = []
        for v in s.get("cross", []):               # L7d: extra slope sets, e.g. chamber_S / ven_sub (+1 / -1 coded)
            z = np.array([1.0 if r[v] else -1.0 for r in rs])[:, None]; extra.append(F * z)
        return np.column_stack([np.ones(len(rs)), F, F * side] + extra), ref
    Xtr, ref = feats(tr); Xte, _ = feats(te, ref); y = np.array([r["y"] for r in tr], float)
    sw = np.ones(len(tr)) if s.get("sample_w") is None else np.asarray(s["sample_w"], float)   # online refits weight the session
    def newton(X):
        pen = np.full(X.shape[1], s.get("lam", 10.0)); pen[0] = 1e-6; b = np.zeros(X.shape[1])
        for _it in range(60):
            p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
            step = np.linalg.solve(X.T @ (X * (sw * p * (1 - p))[:, None]) + np.diag(pen), X.T @ (sw * (y - p)) - pen * b)
            b += step
            if np.max(np.abs(step)) < 1e-6:
                return b
        raise RuntimeError("linear model did not converge in 60 Newton steps")
    b = newton(Xtr)
    if s.get("pairs"):
        # L7b: products of the k plain inputs with the largest first-pass weight (own + side terms), each pair x side
        # layout from feats(): [const | Z (k inputs) + hinges (m cols in all) | the same m cols x side]
        k = len(C); m = (Xtr.shape[1] - 1) // 2
        w = np.abs(b[1:1 + k]) + np.abs(b[1 + m:1 + m + k])
        top = np.argsort(-w)[:s["pairs"]]
        def pairs(X):
            Z = X[:, 1:1 + k][:, top]
            return np.column_stack([Z[:, i] * Z[:, j] for i in range(len(top)) for j in range(i + 1, len(top))])
        side_tr = np.array([1.0 if r["same"] else -1.0 for r in tr])[:, None]
        side_te = np.array([1.0 if r["same"] else -1.0 for r in te])[:, None]
        Ptr, Pte = pairs(Xtr), pairs(Xte)
        Xtr = np.column_stack([Xtr, Ptr, Ptr * side_tr]); Xte = np.column_stack([Xte, Pte, Pte * side_te])
        b = newton(Xtr)
    if s.get("ids"):
        # L7c: one shift per member x side and per committee (room), learned with the same ridge (unseen -> 0)
        keys = collections.Counter([("m", r["who"], r["same"]) for r in tr] + [("c", r["room"]) for r in tr])
        col = {k_: i for i, k_ in enumerate(k_ for k_, c in keys.items() if c >= s["ids"])}
        def onehot(rs):
            O = np.zeros((len(rs), len(col)))
            for i, r in enumerate(rs):
                for k_ in (("m", r["who"], r["same"]), ("c", r["room"])):
                    if k_ in col:
                        O[i, col[k_]] = 1
            return O
        Xtr = np.column_stack([Xtr, onehot(tr)]); Xte = np.column_stack([Xte, onehot(te)])
        b = newton(Xtr)
    return 1 / (1 + np.exp(-np.clip(Xte @ b, -30, 30)))


# ---------------- blends of saved predictions (seconds, no refit) ----------------
def blend_fn(tr, te, s):
    """s = {"parts": [[name, settings, weight], ...]}; name "base" = the locked model. Averaged in log-odds."""
    lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    tot = 0.0; wsum = 0.0
    for name, st, w in s["parts"]:
        if name == "base":
            p = base_p(CUR_SPLIT)[1]
        else:
            f = os.path.join(PRED, f"{name}_{CUR_SPLIT}_{_key(st)}.npy")
            if not os.path.exists(f):
                raise FileNotFoundError(f"no saved predictions for {name} {st} on {CUR_SPLIT} -- run it first")
            p = np.load(f)
        tot = tot + w * lo(p); wsum += w
    return 1 / (1 + np.exp(-tot / wsum))


if __name__ == "__main__":
    name = sys.argv[1]; settings = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    splits = tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ("choose",)
    fn = {"gbm": gbm_fn, "room": room_fn, "mlp": mlp_fn, "direct": direct_fn, "linear": linear_fn,
          "blend": blend_fn}[name]
    run(name, fn, settings, splits)
