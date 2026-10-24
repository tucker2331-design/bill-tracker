#!/usr/bin/env python3
"""Adaptive 'can't call' cutoff inside the session (owner 2026-10-24: fewer wrong calls first; "go straight for what
works"). Adaptive conformal inference (Gibbs & Candes 2021) keeps a coverage target under distribution shift by
nudging the threshold after each step: here, before each session day, the cutoff on |p - .5| moves by
gamma * (wrong-call rate among calls made earlier in the session - target), clipped to [0.20, 0.49]; it starts at
the guaranteed cutoff learned on earlier years (.31). Uses only votes from earlier days. Arm C predictions.
Compared, at the SAME number of calls, with the fixed cutoff (ranking by confidence), so fewer calls alone can't win.
Run: python3 adaptive_calls.py
"""
from __future__ import annotations
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import levers as L, gains as G, first_vote as FV

TARGET = 0.045


def run(split, gamma, window):
    rc = FV.assemble()["rc"]; te, p0, p1 = G.load(split)
    p = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
    y = np.array([r["y"] for r in te]); c = np.abs(p - .5); w = (p >= .5) != (y == 1)
    day = np.array([rc[r["bill"]][0][0] for r in te]); days = sorted(set(day))
    t = 0.31; call = np.zeros(len(p), bool); hist = []
    for d in days:
        m = day == d; call[m] = c[m] >= t
        hist.append((int((call & m & w).sum()), int((call & m).sum())))
        recent = hist[-window:]; k = sum(a for a, _ in recent); n = sum(b for _, b in recent)
        if n >= 50:
            t = float(np.clip(t + gamma * (k / n - TARGET), 0.20, 0.49))
    n = int(call.sum()); top = np.argsort(-c)[:n]
    return n / len(p), int((call & w).sum()), int(w[top].sum()), 1 - w[call].mean()


def main():
    for gamma in (0.5, 1.0, 2.0):
        for window in (3, 7):
            out = []
            for split in ("choose", "confirm", "repeat"):
                cov, wa, wf, acc = run(split, gamma, window)
                out.append(f"{L.SPLITS[split][1]}: called {cov:.1%} right {acc:.2%} wrong {wa} (fixed cutoff, same calls: {wf})")
            print(f"gamma {gamma} window {window} days | " + " | ".join(out), flush=True)


if __name__ == "__main__":
    main()
