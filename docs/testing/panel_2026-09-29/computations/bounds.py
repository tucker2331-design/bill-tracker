"""Mathematician's checks: proper scores, cluster-bootstrap noise, room-level metrics, rolling origin."""
import sys, os, pickle, collections, time
import numpy as np
sys.path.insert(0, "/Users/tuckerward/Documents/Projects/bill-tracker/tools/calibration")
import first_vote as FV, gbm
t0 = time.time()
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
print("rows", len(rows), "years", sorted(collections.Counter(r["yr"] for r in rows).items()), flush=True)
X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
def fit(trn, tst, cs):
    tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == tst]
    p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
    return np.clip(p, 1e-6, 1-1e-6), te
cs_full = FV.NUM
cs_noRA = [c for c in FV.NUM if c not in FV.RA_COLS]
p, te = fit(FV.TRAIN_YEARS, 2025, cs_full)
y = np.array([r["y"] for r in te], float); bills = [r["bill"] for r in te]; same = np.array([r["same"] for r in te])
print(f"fit done {time.time()-t0:.0f}s  n={len(y)} bills={len(set(bills))}", flush=True)
yh = (p >= .5); right = (yh == (y == 1)).astype(float)
ll = -(y*np.log(p) + (1-y)*np.log(1-p)); br = (p - y)**2
base = y.mean()
print(f"acc {right.mean():.4f}  E[max(p,1-p)] {np.maximum(p,1-p).mean():.4f}  logloss {ll.mean():.4f} (base-rate {-(base*np.log(base)+(1-base)*np.log(1-base)):.4f})  brier {br.mean():.4f} (base {base*(1-base):.4f})")
o = np.argsort(np.abs(p-.5)); hf = o[:len(o)//3]
print(f"hardest third acc {right[hf].mean():.4f}  E[max] there {np.maximum(p,1-p)[hf].mean():.4f}  p-range {np.abs(p-.5)[hf].max()+.5:.3f}")
# cluster bootstrap by bill
ub = sorted(set(bills)); idx = collections.defaultdict(list)
for i, b in enumerate(bills): idx[b].append(i)
ix = [np.array(idx[b]) for b in ub]
rng = np.random.default_rng(0)
def boot(stat, B=1000):
    out = []
    for _ in range(B):
        s = rng.integers(0, len(ix), len(ix)); I = np.concatenate([ix[k] for k in s]); out.append(stat(I))
    return np.std(out), np.percentile(out, [2.5, 97.5])
naive = np.sqrt(right.mean()*(1-right.mean())/len(y))
se, ci = boot(lambda I: right[I].mean())
print(f"acc SE naive {naive:.4f}  cluster {se:.4f}  deff {(se/naive)**2:.2f}  95%CI {ci}")
hmask = np.zeros(len(y), bool); hmask[hf] = True
se, ci = boot(lambda I: right[I][hmask[I]].mean())
print(f"hard-third (fixed set) cluster SE {se:.4f} CI {ci}")
# paired comparison vs model without room aggregates
p2, _ = fit(FV.TRAIN_YEARS, 2025, cs_noRA)
r2 = ((p2 >= .5) == (y == 1)).astype(float); ll2 = -(y*np.log(p2)+(1-y)*np.log(1-p2))
print(f"noRA: acc {r2.mean():.4f} logloss {ll2.mean():.4f} hard(fixed) {r2[hf].mean():.4f}")
d_acc = right - r2; d_ll = ll2 - ll
se, ci = boot(lambda I: d_acc[I].mean()); print(f"paired acc diff full-noRA {d_acc.mean():+.4f} SE {se:.4f} CI {ci}")
se, ci = boot(lambda I: d_ll[I].mean()); print(f"paired logloss gain full-vs-noRA {d_ll.mean():+.4f} SE {se:.4f} CI {ci}")
print("decisions that differ:", int(((p>=.5)!=(p2>=.5)).sum()), "of", len(y))
# room-level: outcome = majority of ballots yes at the first vote; party-position groups
g = collections.defaultdict(list)
for i, b in enumerate(bills): g[b].append(i)
pass_true = []; pass_pred = []; pass_prob_sum = []
for b, I in g.items():
    I = np.array(I); pass_true.append(y[I].sum() > len(I)/2); pass_pred.append(p[I].sum() > len(I)/2)
pass_true = np.array(pass_true); pass_pred = np.array(pass_pred)
print(f"ROOM outcome (majority yes at first vote): base pass {pass_true.mean():.3f}; model right {np.mean(pass_true==pass_pred):.4f} of {len(pass_true)} rooms")
pg = collections.defaultdict(list)
for i, r in enumerate(te): pg[(r["bill"], r["same"])].append(i)
sizes = np.array([len(v) for v in pg.values()])
hits = np.array([(p[v].mean() >= .5) == (y[v].mean() >= .5) for v in pg.values()])
print(f"party groups {len(pg)} mean size {sizes.mean():.2f}; party-position right unweighted {hits.mean():.4f}, ballot-weighted {np.average(hits, weights=sizes):.4f}")
# member errors concentrated? share of errors in groups where the party position was missed
miss_grp = np.zeros(len(y), bool)
for v, h in zip(pg.values(), hits):
    if not h: miss_grp[v] = True
print(f"ballots in missed party groups {miss_grp.mean():.4f}; share of all member errors there {(1-right)[miss_grp].sum()/(1-right).sum():.4f}")
# pivotal: rooms decided by <=1 vote
marg = np.array([abs(2*y[np.array(I)].sum()-len(I)) for I in g.values()])
print(f"rooms with margin <=1 vote (|yes-no|<=1): {np.mean(marg<=1):.3f}; <=3: {np.mean(marg<=3):.3f}")
print(f"elapsed {time.time()-t0:.0f}s", flush=True)
# rolling origin, each year scored by training on all earlier years
for t, trn in ((2021,(2019,2020)), (2022,(2019,2020,2021)), (2024,(2019,2020,2021,2022))):
    pt, tt = fit(trn, t, cs_full); yt = np.array([r["y"] for r in tt], float)
    rt = ((pt>=.5)==(yt==1)); ot = np.argsort(np.abs(pt-.5)); h = ot[:len(ot)//3]
    print(f"ROLLING {t}: n {len(yt)} base-yes {yt.mean():.3f} acc {rt.mean():.4f} hard {rt[h].mean():.4f} logloss {(-(yt*np.log(pt)+(1-yt)*np.log(1-pt))).mean():.4f}", flush=True)
