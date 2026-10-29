#!/usr/bin/env python3
"""Attacking the hardest third of member votes with the bill-level findings (owner, 2026-10-15: "they dont boost our
overall accuracy though right? what about that final 1/3 ... try more than one or two hypotheses").

Each hypothesis is an outside signal stacked on the member-vote model year-ahead (accept.stacked_year_ahead: fitted on
earlier years' out-of-sample predictions, scored on the next; pooled per bill, z >= 3), and every result reports the
FIXED hardest third. 85% of member misses are a missed PARTY position, so every signal enters by voter side (the
patron's party / the other party).

  H1 viability   the bill-fate model's year-ahead chance the bill gets out of its first committee (logit), x side
  H2 chair       the referred committee's chair co-sponsors the bill; the chair's record on this patron and on similar
                 bills; chair in the patron's party -- each x side
"""
from __future__ import annotations
import sys, os, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import accept as AC, fate as FT, influence_fate as IF, chair_alignment as CA


def fate_oos():
    """(session, bill) -> year-ahead P(advanced from the first committee), each year from a model trained on earlier years."""
    R, _ = FT.bills(tuple(range(2020, 2026))); R = [r for r in R if r["standing"] in ("majority", "minority")]
    F = FT.featurise(R); cols = sorted(F[0]); X = np.array([[f[c] for c in cols] for f in F], float)
    Y = np.array([FT.MCLASSES.index(FT._m(r)) for r in R]); yr = np.array([r["year"] for r in R])
    out = {}
    for t in range(2021, 2026):
        tr, te = yr < t, yr == t
        if not te.any():
            continue
        P = FT.BLEND * FT.fit_predict(X[tr], Y[tr], X[te]) + (1 - FT.BLEND) * FT.baseline(
            [r for r, m in zip(R, tr) if m], [r for r, m in zip(R, te) if m])
        for r, pv in zip([r for r, m in zip(R, te) if m], P[:, 0]):
            out[(r["session"], r["bill"])] = float(pv)
    return out, R


def main():
    FP, R = fate_oos()
    print(f"year-ahead fate predictions for {len(FP)} bills (2021-2025)")
    lg = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4)))

    def h1(r):
        p = FP.get(r["bill"])
        if p is None:
            return {"via_same": 0.0, "via_other": 0.0, "via_has": 0.0}
        s = float(r["same"])
        return {"via_same": lg(p) * s, "via_other": lg(p) * (1 - s), "via_has": 1.0}
    if "--h2-only" not in sys.argv:
        AC.stacked_year_ahead(h1, "H1 BILL VIABILITY (fate model, year-ahead) x voter side", ridge=10.0)

    built = IF.build(); G = IF.featurise(R, built); A = CA.alignment(R, built, CA.chair_records())
    byk = {(r["session"], r["bill"]): (g, a) for r, g, a in zip(R, G, A)}

    def h2(r):
        v = byk.get(r["bill"])
        # four inputs: the first run with eight (adding similar-bill record and chair's party) did not converge --
        # the chair co-sponsors only ~2.5% of bills and chair's party nearly duplicates the patron's standing
        z = {k: 0.0 for k in ("cs_same", "cs_other", "pat_same", "pat_other")}
        if v is None or not v[0]["ch_known"]:
            return z
        g, a = v; s = float(r["same"])
        for name, val in (("cs", g["ch_on_bill"]), ("pat", a["al_pat_rate"] - .5)):
            z[f"{name}_same"] = val * s; z[f"{name}_other"] = val * (1 - s)
        return z
    AC.stacked_year_ahead(h2, "H2 THE CHAIR (co-sponsors the bill; record on this patron) x voter side", ridge=10.0)


if __name__ == "__main__":
    main()
