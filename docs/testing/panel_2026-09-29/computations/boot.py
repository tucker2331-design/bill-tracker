"""Statistician audit: reproduce the 2025 baseline (year-ahead settings), then bill-clustered bootstrap CIs,
proper scores, calibration, and a paired delta (baseline vs baseline minus room aggregates).
2026 rows are NEVER touched (filtered out before anything else)."""
import sys, pickle, collections, time, numpy as np
sys.path.insert(0, "/Users/tuckerward/Documents/Projects/bill-tracker/tools/calibration")
import first_vote as FV, gbm
t0 = time.time()
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] in set(FV.TRAIN_YEARS) | {2025}]
assert not any(r["yr"] == 2026 for r in rows)
tr = [r for r in rows if r["yr"] in FV.TRAIN_YEARS]; te = [r for r in rows if r["yr"] == 2025]
print("RA in NUM:", all(c in FV.NUM for c in FV.RA_COLS), "n features", len(FV.NUM), "train", len(tr), "test", len(te), flush=True)
X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
ytr = np.array([r["y"] for r in tr], float); y = np.array([r["y"] for r in te], float)
def fit(cs):
    return gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), ytr).predict(X(te, cs))
p = fit(FV.NUM); print("fit1", round(time.time()-t0), flush=True)
cols2 = [c for c in FV.NUM if c not in FV.RA_COLS]
p2 = fit(cols2); print("fit2", round(time.time()-t0), flush=True)
np.save("/private/tmp/claude-501/-Users-tuckerward-Documents-Projects-bill-tracker/d2c029e9-acd9-410e-81ec-5347fd755620/scratchpad/panel/stat/preds.npy", np.vstack([p, p2, y]))
bills = np.array([hash(r["bill"]) for r in te]); same = np.array([r["same"] for r in te]).astype(bool)
ub, inv = np.unique(bills, return_inverse=True); nb = len(ub)
print("bills", nb, "ballots/bill", len(te) / nb)
def ll(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
def metrics(p, y, same, idx=None):
    right = (p >= .5) == (y == 1)
    o = np.argsort(np.abs(p - .5)); h = o[: len(o) // 3]
    return dict(acc=right.mean(), other=right[~same].mean(), hard=right[h].mean(),
                brier=np.mean((p - y) ** 2), logloss=ll(p, y))
base = y.mean()
print("always-yes rate", base, "base brier", np.mean((base - y) ** 2), "base logloss", ll(np.full(len(y), base), y))
M1, M2 = metrics(p, y, same), metrics(p2, y, same)
print("baseline", {k: round(v, 4) for k, v in M1.items()}); print("no-RA   ", {k: round(v, 4) for k, v in M2.items()})
# fixed hard set (baseline's) for the delta, as the repo does
o = np.argsort(np.abs(p - .5)); hf = o[: len(o) // 3]
r1 = ((p >= .5) == (y == 1)); r2 = ((p2 >= .5) == (y == 1))
print("fixed-hard: base", r1[hf].mean(), "noRA", r2[hf].mean(), "disagree share", np.mean((p >= .5) != (p2 >= .5)))
# naive SE
n = len(y); a = r1.mean(); print("naive 95% half-width acc (pp)", 196 * np.sqrt(a * (1 - a) / n))
# calibration by label
lab = np.where(np.abs(p - .5) >= .3, "Likely", np.where(np.abs(p - .5) >= .1, "Leans", "Toss-up"))
for L in ("Likely", "Leans", "Toss-up"):
    m = lab == L; print(L, "share", round(m.mean(), 3), "acc", round(r1[m].mean(), 3), "mean conf", round(np.maximum(p[m], 1 - p[m]).mean(), 3), "n", m.sum())
# ECE 10 bins
bins = np.clip((p * 10).astype(int), 0, 9); ece = sum(abs(p[bins == k].mean() - y[bins == k].mean()) * (bins == k).mean() for k in range(10) if (bins == k).any())
print("ECE(10 bins)", round(ece, 4))
# cluster bootstrap by bill
rng = np.random.default_rng(7); B = 2000
members = [np.where(inv == k)[0] for k in range(nb)]
stats = collections.defaultdict(list)
for b in range(B):
    pick = rng.integers(0, nb, nb); idx = np.concatenate([members[k] for k in pick])
    m1 = metrics(p[idx], y[idx], same[idx])
    for k, v in m1.items(): stats[k].append(v)
    stats["d_acc"].append(r1[idx].mean() - r2[idx].mean())
    hfi = np.isin(idx, hf); stats["d_hardfixed"].append(r1[idx][hfi].mean() - r2[idx][hfi].mean())
    stats["d_ll"].append(ll(p2[idx], y[idx]) - ll(p[idx], y[idx]))
    for L in ("Likely", "Leans", "Toss-up"):
        mm = lab[idx] == L; stats["acc_" + L].append(r1[idx][mm].mean())
for k, v in stats.items():
    v = np.array(v); print(f"{k:14s} 2.5% {np.percentile(v, 2.5):.4f}  97.5% {np.percentile(v, 97.5):.4f}  sd {v.std():.4f}")
sd_acc = np.std(stats["acc"]); print("design effect (var ratio) acc", (sd_acc / np.sqrt(a * (1 - a) / n)) ** 2)
print("point deltas: acc", r1.mean() - r2.mean(), "hardfixed", r1[hf].mean() - r2[hf].mean(), "ll", ll(p2, y) - ll(p, y))
print("done", round(time.time() - t0))
