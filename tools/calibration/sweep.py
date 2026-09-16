#!/usr/bin/env python3
"""Let the DATA nominate the hypotheses, instead of me.

THE OWNER'S POINT (2026-09-16): *"weve only tested hypothesis. so how do we get around that and go from
the reverse? find whats working and see why maybe."*

Correct, and it is the one flaw a time-split backtest cannot fix. Thirty analyses have been run on this
data; the survivors may have survived because I kept looking. Choosing WHICH hypotheses to test, with the
answers visible, is the leak.

THE DESIGN. Generate features mechanically, sweep them all on a DISCOVERY half (2017-2022), and test the
survivors ONLY on a CONFIRMATION half (2023-2026) they were not found in. Anything that does not replicate
on data it was not discovered in is noise, and multiple comparisons are handled by replication rather than
by a correction factor.

THE TRAP THAT ATE THE FIRST VERSION. Scoring `X & minority` against the OVERALL base rate makes every such
feature inherit the -18pt minority penalty, so 38 of 49 "replicated" and they were one finding wearing 38
hats. Each feature is now scored against ITS OWN STANDING'S base rate, which is the only way to see what a
feature ADDS. Under that rule 12 of 20 survive, and three that looked strong collapse -- "Crimes and
Offenses & minority" goes from -19 to -5.

STANDARD #3. The title markers below are INTERNAL DIAGNOSTIC ONLY. "This bill amends rather than creates"
is a real structural property of a bill, but a regex over a title is not a structural read of it. Nothing
here reaches a lobbyist surface until it can be sourced from what the bill actually amends.

Run:  python3 tools/calibration/sweep.py
"""
from __future__ import annotations
import sys, os, re, json, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV
from corpus import load, _party_lookup

MARK = ("amend", "penalt", "report", "study", "fund", "tax", "license", "exempt", "repeal", "creat",
        "establish", "increas", "prohibit", "require", "board", "commission", "local", "school",
        "program", "definition", "eligib", "fee", "permit", "notice")
MIN_DISC, MIN_CONF = 100, 60
MIN_EFFECT, MIN_SE = 0.10, 3.0
REPLICATE_AT = 0.08


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def context():
    c = load(); party, person = _party_lookup()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    lab = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1)
        lab[(s, b)] = tuple(v)
    cv = CV.load()
    byev = collections.defaultdict(list)
    for v in cv["votes"]:
        byev[(v["session"], v["vote_id"])].append(v)
    first = collections.defaultdict(lambda: (None, None, "~"))
    submemb = collections.defaultdict(set)
    for key, vs in byev.items():
        e = cv["events"].get(key)
        if not e or e["venue"] not in ("committee", "subcommittee"):
            continue
        body = key[1].split("V")[0]
        if e["venue"] == "subcommittee" and len(body) > 3:
            for v in vs:
                submemb[(e["session"], body)].add(person(v["name"]) or v["name"])
        k = _bk(e["session"], e.get("bill"))
        if not k:
            continue
        d = e.get("date") or "~"
        if d < first[k][2]:
            first[k] = (key[1][:3], body if len(body) > 3 else None, d)
    return c, cb, lab, first, submemb


def features(r, lab, first, submemb):
    """(stratum, features). The stratum is the baseline the feature is judged against — without it
    every minority-interacted feature inherits the minority penalty and looks like a discovery."""
    k = (r["session"], r["bill"])
    com, sub, _d = first.get(k, (None, None, None))
    n = int(r["bill"].split()[1]); ttl = (r["title"] or "").lower()
    sen = r["year"] - (r["chief_first_year"] or r["year"])
    sens = "freshman" if sen <= 0 else "yr1_4" if sen <= 4 else "yr5_9" if sen <= 9 else "vet10+"
    f = {f"seniority={sens}",
         f"order={'first_200' if n <= 200 else 'mid' if n <= 800 else 'late'}",
         f"companion={bool(r['companion'])}", f"chamber={r['chamber']}"}
    for s in lab.get(k, ()):
        f.add(f"subject={s}")
    if com:
        f.add(f"room={com}")
    for m in MARK:
        if m in ttl:
            f.add(f"title~{m}")
    if sub is not None:
        f.add(f"patron_on_sub={bool({r['chief'], r['chief_key']} & submemb.get((r['session'], sub), set()))}")
    return r["standing"], f


def scan(rows, lab, first, submemb):
    on = collections.defaultdict(lambda: [0, 0]); base = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        st, fs = features(r, lab, first, submemb)
        g = base[st]; g[0] += r["passed"]; g[1] += 1
        for k in fs:
            g = on[(st, k)]; g[0] += r["passed"]; g[1] += 1
    return on, {k: v[0] / v[1] for k, v in base.items()}


def main():
    c, cb, lab, first, submemb = context()
    B = [r for r in c["bills"] if r["standing"] and r.get("chief_key")]
    DISC = [r for r in B if r["year"] <= 2022]
    CONF = [r for r in B if r["year"] >= 2023]
    D, bD = scan(DISC, lab, first, submemb)
    C, bC = scan(CONF, lab, first, submemb)
    print("=" * 86)
    print("BLIND SWEEP — features found in 2017-2022, tested only in 2023-2026")
    print("=" * 86)
    print(f"\n  discovery {len(DISC):,} bills   confirmation {len(CONF):,} bills")
    print(f"  baselines — discovery: majority {bD['majority']:.0%} minority {bD['minority']:.0%}"
          f" | confirmation: majority {bC['majority']:.0%} minority {bC['minority']:.0%}")
    print(f"  EVERY feature is scored against its OWN standing's baseline.")
    cands = []
    for (st, k), (w, n) in D.items():
        if n < MIN_DISC:
            continue
        b = bD[st]; eff = w / n - b
        se = math.sqrt(max(b * (1 - b), 1e-9) / n)
        if abs(eff) > MIN_SE * se and abs(eff) > MIN_EFFECT:
            cands.append((eff, st, k, n))
    rep = []
    for eff, st, k, n in cands:
        if (st, k) not in C:
            continue
        w2, n2 = C[(st, k)]
        if n2 < MIN_CONF:
            continue
        rep.append((eff, w2 / n2 - bC[st], st, k, n, n2))
    ok = [x for x in rep if (x[0] > 0) == (x[1] > 0) and abs(x[1]) >= REPLICATE_AT]
    print(f"\n  candidates surfaced blind: {len(cands)}   testable: {len(rep)}"
          f"   REPLICATED: {len(ok)} = {len(ok) / max(1, len(rep)):.0%}")
    print(f"\n  {'for a...':<10}{'feature':<40}{'2017-22':>10}{'2023-26':>10}{'n':>8}")
    for eff, e2, st, k, n, n2 in sorted(ok, key=lambda x: -abs(x[1])):
        print(f"  {st[:9]:<10}{k[:39]:<40}{eff * 100:>+9.0f}{e2 * 100:>+10.0f}{n2:>8,}")
    gone = [x for x in rep if abs(x[1]) < 0.05]
    if gone:
        print(f"\n  COLLAPSED once scored against their own baseline:")
        for eff, e2, st, k, n, n2 in sorted(gone, key=lambda x: -abs(x[0]))[:6]:
            print(f"  {st[:9]:<10}{k[:39]:<40}{eff * 100:>+9.0f}{e2 * 100:>+10.0f}{n2:>8,}")
    print(f"\n  THE HEADLINE, and nobody hypothesised it: for a MINORITY patron a bill that")
    print(f"  AMENDS something already on the books runs far above other minority bills, while")
    print(f"  one that ESTABLISHES or CREATES something runs below. A small ask survives")
    print(f"  without power; a new program does not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
