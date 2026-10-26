#!/usr/bin/env python3
"""Compare block-level AI answer sets on the SAME bills (2026-10-26): v1 (.cache/llm_block/answers_v1_*) vs v2
(.cache/llm_block_v2/answers_v2_*). Per year, on can't-call votes of bills answered by BOTH: block accuracy, member
accuracy (AI alone and arm C + AI with a weight fit on the OTHER year), and the confidence-ranked top-k accuracy.
Excluded: B139 (leak), recognized bills, and the 8 2026 bills read while writing instructions_v2.
Run: python3 llm_compare.py
"""
from __future__ import annotations
import sys, os, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import llm_member as M, knn_own as K

SEEN = {"B139", "B384", "B295", "B356", "B347", "B355", "B359", "B367", "B288"}


def _leaks():
    out = set()
    for f in ("llm_block_v2/leak_2025.json", "llm_block_v2/leak_2026.json"):
        f = os.path.join(HERE, ".cache", f)
        if os.path.exists(f):
            out |= set(json.load(open(f)))
    return out


def answers(pattern):
    A = {}
    for f in glob.glob(os.path.join(HERE, ".cache", pattern)):
        for line in open(f):
            if line.strip().startswith("{"):
                d = json.loads(line); A[d["id"]] = d
    return {c: d for c, d in A.items() if not d.get("recognized")}


def main():
    man = json.load(open(os.path.join(HERE, ".cache", "llm_block", "manifest.json")))
    S = {"v1": answers("llm_block/answers_v1_*.jsonl"), "v2": answers("llm_block_v2/answers_v2_*.jsonl")}
    both = {c for c in S["v1"] if c in S["v2"] and c not in SEEN | _leaks()}
    D = {v: collections.defaultdict(list) for v in S}
    for v, A in S.items():
        for c in sorted(both):
            for p, y, pc in man[c]["members"]:
                if p in A[c]["p"]:
                    D[v][man[c]["yr"]].append((c, y, M.lo(pc), M.lo(min(max(A[c]["p"][p], 1), 99) / 100)))
    for v in S:
        for yr in sorted(D[v]):
            other = "2026" if yr == "2025" else "2025"
            arr = lambda Z: (np.array([a[2] for a in Z]), np.array([[a[3]] for a in Z]), np.array([a[1] for a in Z], float))
            o, X, y = arr(D[v][yr]); w = K.fit(*arr(D[v][other])) if D[v][other] else np.array([0.45])
            p0 = 1 / (1 + np.exp(-o)); pa = 1 / (1 + np.exp(-X[:, 0])); p1 = 1 / (1 + np.exp(-(o + X @ w)))
            acc = lambda p: ((p >= .5) == (y == 1)).mean()
            oo = np.argsort(-np.abs(p1 - .5)); r = ((p1 >= .5) == (y == 1))[oo]
            print(f"{v} {yr}: {len(y)} votes on {len({a[0] for a in D[v][yr]})} bills | arm C {acc(p0):.3f}  AI {acc(pa):.3f}  "
                  f"C+AI (w {w[0]:.2f} from {other}) {acc(p1):.3f} | top50 {r[:50].mean():.2f} top100 {r[:100].mean():.2f} top150 {r[:150].mean():.2f}")


if __name__ == "__main__":
    main()
