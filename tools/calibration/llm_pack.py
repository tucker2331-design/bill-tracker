#!/usr/bin/env python3
"""Pack block packets into a few combined files per year so one helper agent reads ONE file (fewer tool round trips,
about half the usage per bill). Batches never hold two bills where one packet shows the other's tally
(.cache/llm_block/refs.json). Run: python3 llm_pack.py <packet dir> <year> <bills per file> [exclude codes ...]
"""
from __future__ import annotations
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))


def main(d, yr, size, exclude):
    man = json.load(open(os.path.join(d, "manifest.json"))); ref = json.load(open(os.path.join(HERE, ".cache", "llm_block", "refs.json")))
    codes = sorted(c for c, v in man.items() if v["yr"] == yr and c not in exclude)
    conf = {c: set() for c in codes}
    for c in codes:
        for x in ref.get(c, []):
            if x in conf:
                conf[c].add(x); conf[x].add(c)
    n_files = -(-len(codes) // size); B = [[] for _ in range(n_files)]
    for c in sorted(codes, key=lambda c: -len(conf[c])):
        for b in sorted(B, key=len):
            if len(b) < size and not (conf[c] & set(b)):
                b.append(c); break
        else:
            B.append([c])
    for i, b in enumerate(B):
        with open(os.path.join(d, f"pack_{yr}_{i:02d}.txt"), "w") as fh:
            for c in sorted(b):
                fh.write("=" * 20 + f" PACKET {c} " + "=" * 20 + "\n" + open(os.path.join(d, yr, f"{c}.txt")).read() + "\n")
        print(f"pack_{yr}_{i:02d}.txt  {len(b)} packets  {os.path.getsize(os.path.join(d, f'pack_{yr}_{i:02d}.txt')) // 1000} KB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), set(sys.argv[4:]))
