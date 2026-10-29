"""Can a bill's pre-meeting traces predict a CONSENSUS KILL at its first vote? Bill-level model; train <=2024, test 2025."""
import sys, re, collections, pickle, numpy as np
sys.path.insert(0, "tools/calibration")
import first_vote as FV, gbm
from corpus import load
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
D = FV.assemble(); rc, nb = D["rc"], D["nb"]
rows = pickle.load(open(FV.ROWS, "rb"))
bill_x = {}                                           # bill-level model inputs, from any ballot row of that bill
BC = [c for c in FV.BILL_COLS if c not in ("same",)]
for r in rows:
    if r["bill"] not in bill_x: bill_x[r["bill"]] = [r[c] for c in BC]
sess_start = collections.defaultdict(lambda: "9999")
for (s, b), lst in rc.items():
    for d, *_ in lst:
        if d and d != "9999": sess_start[s] = min(sess_start[s], d)
def days(a, b):
    import datetime as dt
    f = lambda x: dt.date(int(x[:4]), int(x[5:7]), int(x[8:10]))
    return (f(a) - f(b)).days
def supported(ballots): return sum(s for *_x, s in ballots) > len(ballots) / 2
# first-vote outcomes per bill, in date order, for the patron-history feature
first = {}
for key, lst in rc.items():
    d, _vo, vid, ven, ballots = lst[0]
    first[key] = (d, all(not s for *_x, s in ballots), ven)
pat_hist = collections.defaultdict(lambda: [0, 0])    # (patron) -> [first votes, consensus kills] in EARLIER sessions
by_session = collections.defaultdict(list)
for key in first: by_session[key[0]].append(key)
X, y, meta = [], [], []
for s in sorted(by_session):
    if s not in {"2019", "2020", "2021", "2022", "2024", "2025"}:
        for key in by_session[s]:
            b = corpus.get(key)
            if b: h = pat_hist[b["chief"]]; h[0] += 1; h[1] += first[key][1]
        continue
    for key in by_session[s]:
        b = corpus.get(key)
        if not b or key not in bill_x or first[key][0] == "9999": continue
        d, ukill, ven = first[key]
        # a near-twin in THIS session that was already SUPPORTED at a vote before this one
        twin_adv, twin_sim, twin_other = 0, 0.0, 0
        for c, j in nb.get(key, []):
            if c[0] != s: continue
            twin_sim = max(twin_sim, j)
            for dd, _vo, _v, _ven, bl in rc.get(c, []):
                if dd and dd < d and supported(bl):
                    twin_adv = max(twin_adv, 1 if j >= .3 else 0)
                    if corpus.get(c, {}).get("chief") != b["chief"]: twin_other = max(twin_other, 1 if j >= .3 else 0)
                    break
        h = pat_hist[b["chief"]]
        n_pat_bills = sum(1 for k in by_session[s] if corpus.get(k, {}).get("chief") == b["chief"])
        num = int(re.sub(r"\D", "", key[1]) or 0)
        extra = [twin_adv, twin_other, twin_sim, (h[1] + .1) / (h[0] + 1), np.log1p(h[0]), n_pat_bills,
                 num / 2500, days(d, sess_start[s]) / 60, int(ven == "sub"), len(b["cops"])]
        X.append(bill_x[key] + extra); y.append(int(ukill)); meta.append((key, d, ven))
    for key in by_session[s]:                         # update patron history AFTER the session
        b = corpus.get(key)
        if b: h = pat_hist[b["chief"]]; h[0] += 1; h[1] += first[key][1]
X, y = np.array(X, float), np.array(y)
yr = np.array([int(m[0][0][:4]) for m in meta])
tr, te = yr <= 2024, yr == 2025
def auc(p, yy):
    o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1 = yy.sum(); n0 = len(yy) - n1; return (r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
for label, cols in (("existing bill inputs only", slice(0, len(BC))), ("+ twin / patron history / timing", slice(None))):
    m = gbm.GBM(depth=4, lr=.05, rounds=300).fit(X[tr][:, cols], y[tr].astype(float))
    p = m.predict(X[te][:, cols]); yt = y[te]
    o = np.argsort(-p); top = o[:max(1, len(o) // 10)]
    print(f"{label:36s} 2025 bills {len(yt)}, kills {yt.sum()} ({yt.mean():.1%}) | AUC {auc(p, yt):.3f} | "
          f"top 10% flagged: {yt[top].mean():.0%} are kills, catching {yt[top].sum() / yt.sum():.0%} of all kills")
# which new traces carry the signal (2025, simple rates)
E = X[te][:, len(BC):]; yt = y[te]
for i, nm in enumerate(["similar bill already advanced", "…by a different patron", None, None, None, None, None, None, "subcommittee vote", None]):
    if nm:
        m = E[:, i] > 0
        print(f"  {nm:36s} bills {m.sum():4d}  kill rate {yt[m].mean():.1%}  vs {yt[~m].mean():.1%} otherwise")
