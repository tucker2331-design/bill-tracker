#!/usr/bin/env python3
"""Re-test every rejected stacked signal WITHOUT 2021 as a learning year (owner, 2026-10-23: "is there anyway you can use
these negative z values ... for reverse stats").

Finding that triggered it (scratch per-year fits, in-sample): co-sponsor ties, fund load and the governor's party all
point one way in 2022/2024/2025 and the OTHER way in 2021 -- the COVID session (House met virtually, special rules).
accept.stacked_year_ahead learns its first weights from 2021, so 2021's reversal turned real signals negative.
RULE, fixed BEFORE any re-run and applied to every signal alike: learning years are 2022 onward only.
  score 2024 (learned on 2022) and 2025 (learned on 2022 + 2024): pooled per-bill log-loss z, accept at z >= 3;
  replication: 2026 (learned on 2022 + 2024 + 2025; base = p2026.pkl), reported, never used to choose.
Each module's own signal function is captured by temporarily replacing accept.stacked_year_ahead, so the signals
are exactly the ones that were rejected. Plus one new regime signal (governor's party x trifecta / divided).
Run: python3 rerun_no2021.py <module>:<function> [...]    or    python3 rerun_no2021.py governor_regime
"""
from __future__ import annotations
import sys, os, math, pickle, importlib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, stats as ST

lo = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
FIT_YEARS = (2022, 2024, 2025)


def _logit(X, y, names, ridge):
    """stats.logit; on non-convergence retry with 10x and 100x ridge, and SAY so (counted in the printed label)."""
    for k, rr in enumerate((ridge, ridge * 10, ridge * 100)):
        try:
            return ST.logit(X, y, names, ridge=rr, tol=1e-7, max_iter=300), k
        except RuntimeError:
            continue
    # last resort: a properly penalised Newton fit (penalty in the gradient as well as the Hessian; stats.logit puts it
    # in the Hessian only, so sparse / near-separating inputs never settle). Same output shape as stats.logit.
    Xc = np.column_stack([np.ones(len(y)), np.asarray(X, float)]); b = np.zeros(Xc.shape[1])
    pen = np.full(len(b), ridge); pen[0] = 1e-6
    for _ in range(100):
        pr = 1 / (1 + np.exp(-np.clip(Xc @ b, -30, 30)))
        st = np.linalg.solve(Xc.T @ (Xc * (pr * (1 - pr))[:, None]) + np.diag(pen), Xc.T @ (y - pr) - pen * b)
        b += st
        if np.max(np.abs(st)) < 1e-7:
            return {n: (float(v), float("nan"), float("nan"), float("nan")) for n, v in zip(["const"] + list(names), b)}, 3
    raise RuntimeError("logit did not converge even with the penalised fallback")


def evaluate(signal, label, ridge=10.0):
    B = {t: v for t, v in AC.base_preds().items() if t >= 2022}
    B[2026] = pickle.load(open(os.path.join(HERE, ".cache", "p2026.pkl"), "rb"))
    data = {}
    for t, (te, p) in B.items():
        S = [signal(r) for r in te]; names = sorted(S[0])
        data[t] = (te, p, lo(p), np.array([[s[n] for n in names] for s in S], float), names)
    diffs, lines = {}, []
    for t in (2024, 2025, 2026):
        fy = [u for u in FIT_YEARS if u < t]
        Xb = np.concatenate([np.column_stack([data[u][2], data[u][3]]) for u in fy])
        ya = np.concatenate([[r["y"] for r in data[u][0]] for u in fy]).astype(float)
        te, p, lg, F, names = data[t]; y = np.array([r["y"] for r in te], float)
        f, bumps = _logit(Xb, ya, ["lg"] + names, ridge)
        b = np.array([f[n][0] for n in ["const", "lg"] + names])
        Xa = np.concatenate([data[u][2][:, None] for u in fy])
        f0, _b0 = _logit(Xa, ya, ["lg"], ridge); b0 = np.array([f0[n][0] for n in ["const", "lg"]])
        with np.errstate(all="ignore"):
            p0 = 1 / (1 + np.exp(-(b0[0] + b0[1] * lg)))
            p1 = 1 / (1 + np.exp(-(np.column_stack([np.ones(len(te)), lg, F]) @ b)))
        g = collections.defaultdict(float)
        for r, a, c in zip(te, AC._ll(p0, y), AC._ll(p1, y)):
            g[str(r["bill"])] += a - c
        d = np.array(list(g.values())); diffs[t] = d
        hard = np.argsort(np.abs(p - .5))[:len(p) // 3]
        r0 = (p0 >= .5) == (y == 1); r1 = (p1 >= .5) == (y == 1)
        lines.append(f"    {t}: member {r0.mean():.4f}->{r1.mean():.4f}  hardest third {r0[hard].mean():.4f}->{r1[hard].mean():.4f}  "
                     f"z {d.mean() / (d.std(ddof=1) / math.sqrt(len(d))):+.1f}{('  [PENALISED FALLBACK]' if bumps == 3 else '  [RIDGE RAISED x' + str(10 ** bumps) + ']') if bumps else ''}  weights " +
                     ", ".join(f"{n} {f[n][0]:+.2f}" for n in names))
    d = np.concatenate([diffs[2024], diffs[2025]]); z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    print(label); print("\n".join(lines))
    print(f"    POOLED 2024+2025 (no 2021 in learning): z = {z:+.1f} -> {'ACCEPT' if z >= 3 else 'reject'}; "
          f"2026 replication z {diffs[2026].mean() / (diffs[2026].std(ddof=1) / math.sqrt(len(diffs[2026]))):+.1f}", flush=True)


def capture(modfn):
    mod, fn = modfn.split(":")
    got = []
    real = AC.stacked_year_ahead
    AC.stacked_year_ahead = lambda signal, label, only_covered=False, ridge=1.0: got.append((signal, label, ridge)) or (0.0, 0.0)
    try:
        m = importlib.import_module(mod)
        getattr(m, fn)() if fn != "-" else None
        if fn == "-":
            got.append((m.sig, mod, 10.0))
    finally:
        AC.stacked_year_ahead = real
    return got


def governor_regime():
    import private_traces as PT
    TRI = {2021: 1, 2022: 0, 2023: 0, 2024: 0, 2025: 0, 2026: 1}       # governor's party also holds both chambers
    def sig(r):
        g = PT.GOV.get(r["yr"]); t = TRI.get(r["yr"], 0); v = float(r["party"] == g)
        pg = float(PT.corpus[r["bill"]]["chief_party"] == g)
        return {"vg_tri": v * t, "vg_div": v * (1 - t), "pg_tri": pg * t, "pg_div": pg * (1 - t)}
    evaluate(sig, "GOVERNOR'S PARTY x TRIFECTA / DIVIDED (voter, patron)")


if __name__ == "__main__":
    for a in sys.argv[1:]:
        if a == "governor_regime":
            governor_regime(); continue
        for signal, label, ridge in capture(a):
            evaluate(signal, f"[{a}] {label}", ridge=max(ridge, 10.0))
