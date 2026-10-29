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

X = np.array(X, float)
yr = np.array([int(m[0][0][:4]) for m in meta])
def shape_of(key):
    b = corpus[key]; _d, _vo, _v, _ven, ballots = rc[key][0]
    by = collections.defaultdict(lambda: [0, 0])
    for _w, pp, sup in ballots: by["same" if pp == b["chief_party"] else "other"][int(sup)] += 1
    def side(c): return "for" if c[1] and not c[0] else "against" if c[0] and not c[1] else "split"
    s, o = side(by["same"]), side(by["other"])
    if s == o == "for": return 0          # everyone for
    if s == o == "against": return 2      # everyone against (consensus kill)
    if s == "for" and o == "against": return 1   # straight party line
    return 3                               # mixed split
shp = np.array([shape_of(m[0]) for m in meta])
NAMES = ["everyone for", "straight party line", "everyone against", "mixed split"]
tr, te = yr <= 2024, yr == 2025
def auc(p, yy):
    o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1 = yy.sum(); n0 = len(yy) - n1; return (r[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
P = np.zeros((te.sum(), 4))
for c in range(4):
    m = gbm.GBM(depth=4, lr=.05, rounds=300).fit(X[tr], (shp[tr] == c).astype(float))
    P[:, c] = m.predict(X[te])
P = P / P.sum(1, keepdims=True); yt = shp[te]
print(f"2025 bills {len(yt)} | shape mix: " + ", ".join(f"{NAMES[c]} {np.mean(yt == c):.0%}" for c in range(4)))
for c in range(4):
    o = np.argsort(-P[:, c]); top = o[:max(1, len(o) // 10)]
    print(f"  {NAMES[c]:20s} AUC {auc(P[:, c], (yt == c).astype(int)):.3f} | top 10% flagged are this shape {np.mean(yt[top] == c):.0%} (base {np.mean(yt == c):.0%})")
pred = P.argmax(1)
print(f"  shape guessed right overall: {np.mean(pred == yt):.0%} (always guessing the commonest shape: {max(np.mean(yt == c) for c in range(4)):.0%})")
conf = P.max(1); o = np.argsort(-conf)
for q in (.25, .5):
    k = o[:int(len(o) * q)]; print(f"  on the {int(q*100)}% of bills it is surest about: shape right {np.mean(pred[k] == yt[k]):.0%}")
