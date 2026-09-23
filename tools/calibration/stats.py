#!/usr/bin/env python3
"""Small, exact statistics with no dependency beyond numpy — so every number in this folder can be rerun
on any machine that has the corpus. scipy/statsmodels are NOT installed here; do not import them.

logit()   Logistic regression by Newton-Raphson (IRLS). Standard errors from the inverse Hessian at the
          optimum, two-sided p from the normal approximation. Converges in <25 iterations on everything in
          this project; raises rather than returning a half-fitted model.
"""
from __future__ import annotations
import math
import numpy as np


def _p_normal(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def logit(X, y, names, max_iter=50, tol=1e-9, ridge=1e-8):
    """Returns {name: (coef, se, z, p)} plus '_n', '_ll', '_ll0' (null log-likelihood).

    FLOATING-POINT FLAGS ARE SILENCED AND REPLACED BY A HARD CHECK. numpy 2.0 on Apple's Accelerate BLAS
    raises spurious 'divide by zero encountered in matmul' on perfectly finite products (verified: the
    self-test recovers +0.5/+1.2/-0.7 as +0.485/+1.222/-0.703 while emitting them). Leaving them on trains
    the reader to ignore warnings; silencing them blindly would hide a real failure. So they are silenced
    AND every intermediate is asserted finite -- a genuine overflow still raises (Standard #4)."""
    with np.errstate(all="ignore"):
        return _logit(X, y, names, max_iter, tol, ridge)


def _finite(a, what):
    if not np.all(np.isfinite(a)):
        raise FloatingPointError(f"non-finite {what} in logit -- a real numerical failure, not the BLAS flag")
    return a


def _logit(X, y, names, max_iter, tol, ridge):
    X = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    y = np.asarray(y, float)
    names = ["const"] + list(names)
    b = np.zeros(X.shape[1])
    for _ in range(max_iter):
        eta = _finite(X @ b, "linear predictor")
        p = 1.0 / (1.0 + np.exp(-eta))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + ridge * np.eye(X.shape[1])
        g = X.T @ (y - p)
        step = _finite(np.linalg.solve(_finite(H, "Hessian"), g), "Newton step")
        b = b + step
        if np.max(np.abs(step)) < tol:
            break
    else:
        raise RuntimeError("logit did not converge")
    p = 1.0 / (1.0 + np.exp(-(X @ b)))
    H = X.T @ (X * (p * (1 - p))[:, None])
    se = _finite(np.sqrt(np.diag(np.linalg.inv(H))), "standard errors")
    eps = 1e-12
    ll = float(np.sum(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))
    pbar = y.mean()
    ll0 = float(len(y) * (pbar * math.log(pbar + eps) + (1 - pbar) * math.log(1 - pbar + eps)))
    out = {n: (float(bi), float(si), float(bi / si), _p_normal(bi / si)) for n, bi, si in zip(names, b, se)}
    out["_n"], out["_ll"], out["_ll0"] = len(y), ll, ll0
    return out


def show(res, title):
    print(f"  {title}   n={res['_n']:,}   McFadden R2={1 - res['_ll'] / res['_ll0']:.3f}")
    for k, v in res.items():
        if k.startswith("_"):
            continue
        c, se, z, p = v
        print(f"    {k:28s} {c:+8.3f}  se {se:6.3f}  z {z:+6.2f}  p {p:.2g}   OR {math.exp(c):6.2f}")
