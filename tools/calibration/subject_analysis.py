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
    python3 tools/calibration/subject_analysis.py             # the findings (tier A, >=95%)
    python3 tools/calibration/subject_analysis.py --fine      # by real LIS subject, for topic cuts
    python3 tools/calibration/subject_analysis.py --tier-b    # add the ~90% long tail, clearly flagged
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
THIN_MIN = 15            # below this even a raw fraction is too thin to be worth a reader's attention


def load_labels(space="coarse", tier="a"):
    """`space` selects which label set to analyse.

      coarse — 43 broad subjects, 68% of the corpus. Use for whole-corpus cuts.
      fine   — 469 actual LIS subjects, 50% of the corpus. The ONLY space that can answer a topic
               question ("how do firearms bills fare"), because the coarse rollup does not contain
               Firearms, Marijuana, Zoning, Workers' Compensation, Police or Unemployment Compensation
               at all — they have no parent in the hierarchy file and were being deleted outright.

    Neither dominates and they are NOT interchangeable. A fine-space accuracy is also not comparable to a
    coarse-space one: bills carry ~2.5 fine subjects vs ~1.3 coarse, and the metric ("predicted subject is
    in the true set") gets easier as true sets grow. Always read accuracy against `null_baseline`."""
    if not os.path.exists(LABELS):
        raise FileNotFoundError(f"{LABELS} missing — run `subject_label.py --write` first.")
    with open(LABELS, encoding="utf-8") as fh:
        d = json.load(fh)
    if space not in ("fine", "coarse"):
        raise ValueError(f"space must be 'fine' or 'coarse', got {space!r}")
    lab = {tuple(k.split("|", 1)): set(v) for k, v in d[f"labels_{space}"].items()}
    if tier == "b":
        # TIER B IS ADDITIVE AND SEPARATELY MEASURED. It is never folded in by default: those bills are
        # the long tail whose titles are near-unique in the corpus, carried at ~90% rather than the 95%
        # bar. Mixing them into a table silently would restate a weaker number as a strong one.
        for k, v in d.get(f"labels_{space}_tier_b", {}).items():
            lab.setdefault(tuple(k.split("|", 1)), set(v))
    truth = {tuple(k.split("|", 1)) for k in d[f"ground_truth_{space}"]}
    return lab, truth, d["measured"][space]


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
    space = "fine" if "--fine" in sys.argv else "coarse"
    tier = "b" if "--tier-b" in sys.argv else "a"
    lab, truth, measured = load_labels(space, tier)
    print(f"[{space.upper()} space — {measured['classes']} subjects, "
          f"{measured['subjects_per_bill']} per bill]")
    print(f"cold-session {measured['cold_session_accuracy']:.1%} accurate at "
          f"{measured['cold_session_coverage']:.0%} coverage; "
          f"null baseline {measured['null_baseline']:.1%}; "
          f"corpus {measured['corpus_coverage']:.0%}")
    if tier == "b":
        tb = measured.get("tier_b", {})
        if "cold_session_accuracy" in tb:
            print(f"INCLUDING TIER B: +{tb['bills_added']:,} bills at {tb['cold_session_accuracy']:.1%} "
                  f"(the long-tail set — weaker, and every rate below is now a MIXED-quality rate)")
        else:
            print(f"tier B requested but empty: {tb.get('note','-')}")
    print()

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

    # BELOW THE POWER BAR — printed, not hidden, and never mixed in with the table above.
    # Omitting them entirely was the wrong call: the owner's own example of a useful stat was
    # "2/198 minority patron gun bills pass" (2026-08-02) — a raw fraction with its denominator. A thin
    # pool is not a false finding, it is a finding whose denominator the reader must see. What would be
    # dishonest is printing a RATE for n=3 as though it were comparable to a rate for n=880, so these
    # carry counts rather than percentages and are labelled as directional.
    thin = []
    for s_, pool in bysub.items():
        maj = [x for x in pool if x["standing"] == "majority"]
        mino = [x for x in pool if x["standing"] == "minority"]
        if not maj or not mino:
            continue
        if len(maj) >= MIN_POOL and len(mino) >= MIN_POOL and not verify.check(
                pool, key=lambda x: x["standing"], outcome="passed", minn=MIN_POOL, label=s_):
            continue
        pm = sum(1 for x in maj if x["passed"])
        pn = sum(1 for x in mino if x["passed"])
        if len(mino) >= THIN_MIN:
            # ranked by EFFECT SIZE, not sample size: a thin pool is only worth a reader's attention if
            # the gap in it is large. Sorting by n instead buried the biggest gap in the corpus
            # (Firearms, 87% vs 5%) below a dozen unremarkable ones.
            gap = (pm / len(maj)) - (pn / len(mino))
            thin.append((gap, s_, pm, len(maj), pn, len(mino)))
    thin.sort(reverse=True)
    if thin:
        print(f"\nDIRECTIONAL ONLY — below the n>={MIN_POOL}-per-standing bar. Counts, not rates.")
        print(f"  {'topic':<32}{'majority passed':>18}{'minority passed':>18}")
        for _g, s_, pm, nm, pn, nmin in thin[:14]:
            print(f"  {s_[:30]:<32}{f'{pm}/{nm}':>18}{f'{pn}/{nmin}':>18}")
        print(f"  ({len(thin)} topics shown of those with >={THIN_MIN} minority bills; treat as a lead to "
              f"confirm, never as a published rate.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
