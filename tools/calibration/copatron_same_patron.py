"""Same-patron test: within each patron, subcommittee first votes with vs without co-patrons."""
import sys, collections, numpy as np
sys.path.insert(0, "tools/calibration")
exec(open("tools/calibration/consensus_kills.py").read().split('print(f"first votes')[0])   # builds R
sub = [r for r in R if r["ven"] == "sub"]
g = collections.defaultdict(lambda: {True: [], False: []})
for r in sub: g[r["b"]["chief"]][bool(r["b"]["cops"])].append(r["ukill"])
both = {p: d for p, d in g.items() if d[True] and d[False]}
w_diff, w = 0.0, 0.0; nt = nf = kt = kf = 0
for p, d in both.items():
    a, b = np.mean(d[True]), np.mean(d[False]); n = min(len(d[True]), len(d[False]))
    w_diff += n * (b - a); w += n
    nt += len(d[True]); nf += len(d[False]); kt += sum(d[True]); kf += sum(d[False])
print(f"patrons with subcommittee bills both with and without co-patrons: {len(both)}")
print(f"  their bills WITH co-patrons:    {nt:5d}  consensus-kill rate {kt/nt:.1%}")
print(f"  their bills WITHOUT co-patrons: {nf:5d}  consensus-kill rate {kf/nf:.1%}")
print(f"  within-patron difference (weighted): {w_diff/w:+.1%} points more kills without co-patrons")
# sign test across patrons: how many patrons lose MORE of their no-co-patron bills
more = sum(np.mean(d[False]) > np.mean(d[True]) for d in both.values()); less = sum(np.mean(d[False]) < np.mean(d[True]) for d in both.values())
from math import comb
n = more + less; k = max(more, less)
p = 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
print(f"  patrons worse off without co-patrons: {more}, better off: {less}, tied: {len(both)-n}  (sign test p = {p:.2g})")
