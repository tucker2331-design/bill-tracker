#!/usr/bin/env python3
"""What the extended subject labels actually buy: the minority penalty BY TOPIC, across 18 sessions.

WHY THE BIAS CHECK COMES FIRST
------------------------------
Owner, 2026-08-03: *"can we be sure the data you did collect isnt concentrated in a certain area or what
ever because thats what im worried about is the ones you dont want to touch are a concetrnation of
something that would inform our data."*

That worry was CORRECT the first time it was raised: an earlier labelling pass reached 92-94% in the two
seed sessions and 52-56% everywhere else, and the unlabelled remainder passed at 52% against 46% for the
labelled — so the bills being dropped were systematically the ones that survived. A 95%-accurate label set
that covers a biased half of the corpus produces confidently wrong findings.

So `--bias` runs BEFORE any finding is reported, and every finding carries the labelled share of its pool.
A topic whose coverage is far off the corpus average is printed with its coverage attached, not silently
folded into a table.

WHAT IT REPORTS
---------------
The minority-patron penalty per topic. This is the shape the owner singled out as the useful one
(2026-08-02: *"being able to say patron basically doesnt matter on abc but 2/198 minority patron gun bills
pass is really good info"*) — a per-topic rate, with its denominator, for a pool defined structurally.

Every rate goes through `verify.check()` before it is printed. Nothing that fails the gate is reported.

Usage:
    python3 tools/calibration/subject_analysis.py --bias      # coverage audit; run this first
    python3 tools/calibration/subject_analysis.py             # the findings
"""
from __future__ import annotations

import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subjects import load_subjects          # noqa: E402
import verify                                # noqa: E402

LABELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subject_labels.json")
MIN_POOL = 40            # a topic-by-standing cell below this cannot carry a rate


def load_labels():
    if not os.path.exists(LABELS):
        raise FileNotFoundError(f"{LABELS} missing — run `subject_label.py --write` first.")
    with open(LABELS, encoding="utf-8") as fh:
        d = json.load(fh)
    lab = {tuple(k.split("|", 1)): set(v) for k, v in d["labels"].items()}
    truth = {tuple(k.split("|", 1)) for k in d["ground_truth"]}
    return lab, truth, d["measured"]


def bias(bills, lab):
    A = [r for r in bills if (r["session"], r["bill"]) in lab]
    Z = [r for r in bills if (r["session"], r["bill"]) not in lab]
    print(f"labelled {len(A):,} of {len(bills):,} ({len(A)/len(bills):.0%});  unlabelled {len(Z):,}\n")
    print(f"{'':30}{'labelled':>10}{'unlabelled':>12}{'gap':>8}")
    worst = 0.0
    for name, f in (("passed", lambda r: r["passed"]),
                    ("House bill", lambda r: r["chamber"] == "H"),
                    ("minority patron", lambda r: r["standing"] == "minority"),
                    ("has a companion", lambda r: bool(r["companion"])),
                    ("has an abstract", lambda r: bool(r["a"]))):
        a = sum(1 for x in A if f(x)) / len(A)
        z = sum(1 for x in Z if f(x)) / len(Z) if Z else 0.0
        worst = max(worst, abs(a - z))
        print(f"  {name:<28}{a:>9.0%}{z:>11.0%}{abs(a-z):>8.0%}")
    print(f"\n  {'session':<28}{'labelled':>10}")
    for s in sorted({r["session"] for r in bills}):
        n = [r for r in bills if r["session"] == s]
        if len(n) < 100:
            continue
        c = sum(1 for r in n if (r["session"], r["bill"]) in lab) / len(n)
        print(f"  {s:<28}{c:>9.0%}  ({sum(1 for r in n if (r['session'],r['bill']) in lab):,}/{len(n):,})")
    print(f"\nlargest composition gap between labelled and unlabelled: {worst:.0%}")
    return worst


def main() -> int:
    d = load_subjects()
    bills = d["bills"]
    lab, truth, measured = load_labels()
    print(f"labels: cold-session {measured['cold_session_accuracy']:.1%} accurate "
          f"at {measured['cold_session_coverage']:.0%} coverage "
          f"(abstract sessions {measured['abstract_session_coverage']:.0%})\n")

    if "--bias" in sys.argv:
        bias(bills, lab)
        return 0

    rows = []
    for r in bills:
        k = (r["session"], r["bill"])
        if k not in lab or not r["standing"]:
            continue
        for s in lab[k]:
            rows.append({"subject": s, "standing": r["standing"], "passed": r["passed"],
                         "chamber": r["chamber"], "session": r["session"],
                         "truth": k in truth})

    bysub = collections.defaultdict(list)
    for x in rows:
        bysub[x["subject"]].append(x)

    print(f"{'topic':<34}{'majority':>12}{'minority':>12}{'penalty':>10}{'n':>8}")
    out = []
    for s, pool in bysub.items():
        maj = [x for x in pool if x["standing"] == "majority"]
        mino = [x for x in pool if x["standing"] == "minority"]
        if len(maj) < MIN_POOL or len(mino) < MIN_POOL:
            continue
        w = verify.check(pool, key=lambda x: x["standing"], outcome="passed",
                         minn=MIN_POOL, label=s)
        if w:
            continue
        pm = sum(1 for x in maj if x["passed"]) / len(maj)
        pn = sum(1 for x in mino if x["passed"]) / len(mino)
        out.append((pm - pn, s, pm, pn, len(pool), len(mino)))
    out.sort(reverse=True)
    for gap, s, pm, pn, n, _nm in out:
        print(f"  {s[:32]:<32}{pm:>11.0%}{pn:>12.0%}{gap*100:>9.0f}pt{n:>8,}")
    print(f"\n{len(out)} topics passed the verification gate, of {len(bysub)} with any labels.")
    print(f"Pools below n={MIN_POOL} per standing, or failing verify.check(), are omitted — not zero.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
