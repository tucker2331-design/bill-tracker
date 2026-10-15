#!/usr/bin/env python3
"""Replication on 2026 -- a year none of these findings was chosen on (owner, 2026-10-14: "figure out if this all applies
to more than a sample"). Every model is trained on 2020-2025 only and scored on 2026 once.
  1. the chair co-sponsoring the bill -- same patron, same session, 2026
  2. chair alignment (chair_alignment.py) added to the fate model -- per-bill log-loss gain on 2026 and its z
  3. the testimony lineup -- run testimony_lineup.py with LINEUP_YEARS ending in 2026 (separate step; needs 2026 HODSpeak)
2026's fate test was already scored once (prereg_fate_2026.json); this adds inputs to it, so it is reported as a
replication year, not as a new locked score.
"""
from __future__ import annotations
import sys, os, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import fate as FT, influence_fate as IF, chair_alignment as CA
from math import comb

R, _ = FT.bills(tuple(range(2020, 2027))); R = [r for r in R if r["standing"] in ("majority", "minority")]
built = IF.build(); G = IF.featurise(R, built); norm = built[0]
adv = [FT._m(r) == "ADVANCED" for r in R]
g = collections.defaultdict(lambda: {True: [], False: []})
for r, f, a in zip(R, G, adv):
    if r["year"] == 2026 and f["ch_known"]:
        g[norm(r["chief"])][f["ch_on_bill"] > 0].append(a)
both = {k: d for k, d in g.items() if d[True] and d[False]}
at = sum(sum(d[True]) for d in both.values()); nt = sum(len(d[True]) for d in both.values())
af = sum(sum(d[False]) for d in both.values()); nf = sum(len(d[False]) for d in both.values())
more = sum(np.mean(d[True]) > np.mean(d[False]) for d in both.values()); less = sum(np.mean(d[True]) < np.mean(d[False]) for d in both.values())
n = int(more + less); k = int(max(more, less)); p = 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1
print(f"1. CHAIR CO-SPONSORS THE BILL, 2026, same patron: {at}/{nt} ({at/max(nt,1):.0%}) vs {af}/{nf} ({af/max(nf,1):.0%}); "
      f"patrons better {more}, worse {less}, p = {p:.2g}")
A = CA.alignment(R, built, CA.chair_records())
F = FT.featurise(R); cols = sorted(F[0])
Y = np.array([FT.MCLASSES.index(FT._m(r)) for r in R]); yr = np.array([r["year"] for r in R])
X0 = np.array([[f[c] for c in cols] for f in F], float)
acol = ["al_known", "al_pat_rate", "al_pat_n", "al_sim_rate", "al_sim_n", "al_ip_dist", "al_ip_has", "al_same_party"]
X1 = np.column_stack([X0, np.array([[a[c] for c in acol] for a in A], float)])
tr, te = yr < 2026, yr == 2026
Bp = FT.baseline([r for r, m in zip(R, tr) if m], [r for r, m in zip(R, te) if m])
p0 = FT.BLEND * FT.fit_predict(X0[tr], Y[tr], X0[te]) + (1 - FT.BLEND) * Bp
p1 = FT.BLEND * FT.fit_predict(X1[tr], Y[tr], X1[te]) + (1 - FT.BLEND) * Bp
d = FT._mll(p0, Y[te]) - FT._mll(p1, Y[te])
print(f"2. CHAIR ALIGNMENT, 2026 (trained 2020-2025): log-loss gain {d.mean():+.4f}, z = {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):.1f} "
      f"on {te.sum()} bills")
