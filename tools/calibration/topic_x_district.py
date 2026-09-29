"""District x topic: give the trees each bill's raw subject so they can form (district profile x topic) combinations.
Scored on all ballots and on MIXED-SPLIT votes (where a party splits internally). Choose 2024, score 2025."""
import sys, json, collections, pickle, numpy as np
sys.path.insert(0, "tools/calibration")
import first_vote as FV, gbm
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
L = json.load(open("tools/calibration/subject_labels.json"))["labels_coarse"]
subj = {}
for k, v in L.items():
    s, b = k.split("|", 1); subj[(s, b)] = v
top = [s for s, _ in collections.Counter(x for v in subj.values() for x in v).most_common(20)]
SC = [f"subj_{i}" for i in range(len(top))]
for r in rows:
    have = set(subj.get(r["bill"], []))
    for i, s in enumerate(top): r[SC[i]] = float(s in have)
D = FV.assemble()
from corpus import load
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
def mixed(key):
    b = corpus.get(key); lst = D["rc"].get(key)
    if not b or not lst: return False
    by = collections.defaultdict(lambda: [0, 0])
    for _w, pp, sup in lst[0][4]: by[pp][int(sup)] += 1
    return any(v[0] and v[1] for v in by.values())
X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
print("top subjects:", top[:8], "...", flush=True)
for label, trn, tst in (("choose on 2024", (2019, 2020, 2021, 2022), 2024), ("score on 2025", FV.TRAIN_YEARS, 2025)):
    tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == tst]
    y = np.array([r["y"] for r in te]); mx = np.array([mixed(r["bill"]) for r in te]); hf = None
    for name, cs in (("GBM", FV.NUM), ("GBM + raw topic (district x topic)", FV.NUM + SC)):
        p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
        if hf is None: o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
        right = (p >= .5) == (y == 1)
        print(f"  [{label}] {name:36s} all {right.mean():.4f}  fixed-hard {right[hf].mean():.4f}  MIXED-SPLIT votes {right[mx].mean():.4f} (n={mx.sum()})", flush=True)
