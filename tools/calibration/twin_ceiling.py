"""Natural experiments for the ceiling: near-identical bills voted separately. How often do they get the same
party lines at their first votes? That concordance bounds what bill content can ever tell us."""
import sys, collections, numpy as np
sys.path.insert(0, "tools/calibration")
import first_vote as FV
from corpus import load
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
D = FV.assemble(); rc, nb = D["rc"], D["nb"]
def shape(key):
    lst = rc.get(key)
    if not lst: return None
    b = corpus.get(key)
    if not b or b["chief_party"] not in FV.PARTIES: return None
    _d, _vo, _vid, ven, ballots = lst[0]
    by = collections.defaultdict(lambda: [0, 0])
    for _w, pp, sup in ballots: by["same" if pp == b["chief_party"] else "other"][int(sup)] += 1
    pos = {k: (v[1] > v[0]) for k, v in by.items() if sum(v) >= 2}
    if len(pos) < 2: return None
    return pos["same"], pos["other"], ven, b["standing"]
pairs = []
for k, lst in nb.items():
    for c, j in lst:
        if j >= 0.8 and k < c:
            a, b = shape(k), shape(c)
            if a and b: pairs.append((k, c, j, a, b))
print(f"near-identical pairs (Jaccard >= 0.8) with first votes on both: {len(pairs)}")
def conc(sel, label):
    P = [p for p in pairs if sel(p)]
    if not P: return
    both = np.mean([p[3][:2] == p[4][:2] for p in P]); other = np.mean([p[3][1] == p[4][1] for p in P]); same = np.mean([p[3][0] == p[4][0] for p in P])
    print(f"  {label:58s} pairs {len(P):4d} | both parties' positions match {both:.0%} | patron's party {same:.0%} | other party {other:.0%}")
conc(lambda p: True, "all near-identical pairs")
conc(lambda p: p[0][0] != p[1][0], "different sessions (reintroduced)")
conc(lambda p: p[0][0] == p[1][0], "same session (twins, e.g. House + Senate)")
conc(lambda p: p[0][0] == p[1][0] and corpus[p[0]]["chamber"] != corpus[p[1]]["chamber"], "same session, opposite chambers")
conc(lambda p: p[3][3] == p[4][3], "same patron standing (majority/minority)")
conc(lambda p: p[3][2] == p[4][2] and p[3][3] == p[4][3], "same venue AND same patron standing")
