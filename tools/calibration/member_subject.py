#!/usr/bin/env python3
"""Does a legislator stray from their caucus on PARTICULAR SUBJECTS, reliably enough to act on?

THE OBJECTION (owner, 2026-09-14): "you havent gotten into things like if this committee almost kills
everything but this person is better on this subject and tends to stray from their party. this may not
exist or it may not hold up statistically but we need to find some version of this informative set up
that proves its self as signifigantly better then a guess."

THE GUESS TO BEAT is the member's OWN overall defection rate. A subject-specific claim has to add
something on top of "this person crosses the aisle a lot".

TRAIN 2017-2023, TEST 2024-2026. Nothing from the test era touches the fit.

TWO RESULTS, AND THEY POINT OPPOSITE WAYS -- both are reported because only one of them is good news:

  AS A GENERAL MODEL IT FAILS. Scored over all 1,088,729 held-out votes, member x subject is 0.46% WORSE
  on log-loss than the member's own rate. Most cells carry no signal, and modelling them adds noise
  everywhere to buy accuracy in a handful of places.

  AS A SPARSE SCREEN IT WORKS. Flag only cells whose training residual clears 3 SE above that member's own
  baseline AND where they cross at least 8% of the time: 71 flags, 76% still above baseline in the
  held-out era against a 41% null, p = 1.3e-09.

THE NULL IS 41%, NOT 50%. Cells regress downward on average, so a coin-flip framing would overstate every
screen by nine points.

Run:  python3 tools/calibration/member_subject.py
"""
from __future__ import annotations
import sys, os, re, json, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV, votes as V
from corpus import load, _party_lookup

TRAIN_END = 2023


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def records():
    """(member, party, year, subjects, defected) from BOTH vote corpora.

    Defection = voting against one's own party's majority on that roll call, computed per roll call from
    the members actually present, never from a static party line."""
    c = load(); party, _ = _party_lookup()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    lab = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1)
        lab[(s, b)] = tuple(v)
    out = []
    cv = CV.load()
    byev = collections.defaultdict(list)
    for v in cv["votes"]:
        byev[(v["session"], v["vote_id"])].append(v)
    for key, vs in byev.items():
        e = cv["events"].get(key)
        if not e:
            continue
        k = _bk(e["session"], e.get("bill"))
        if not k or k not in cb or not lab.get(k):
            continue
        tal = collections.defaultdict(collections.Counter); prs = {}
        for v in vs:
            p = party(v.get("name") or "")
            if p and v["opt"] in ("yes", "no"):
                prs[v["name"]] = p; tal[p][v["opt"]] += 1
        for v in vs:
            p = prs.get(v["name"])
            if not p or v["opt"] not in ("yes", "no"):
                continue
            cnt = tal[p]
            if cnt["yes"] + cnt["no"] < 3:
                continue
            mj = "yes" if cnt["yes"] > cnt["no"] else ("no" if cnt["no"] > cnt["yes"] else None)
            if mj:
                out.append((v["name"], p, int(e["session"][:4]), lab[k], v["opt"] != mj))
    for v in V.load()["votes"]:
        k = _bk(v["session"], v.get("bill"))
        if k and k in cb and v.get("party") and v.get("defect") is not None and lab.get(k):
            out.append((v["member"], v["party"], int(v["session"][:4]), lab[k], bool(v["defect"])))
    return out


def tabulate(rs):
    cell = collections.defaultdict(lambda: [0, 0]); mem = collections.defaultdict(lambda: [0, 0])
    for nm, _p, _y, subs, dfc in rs:
        mem[nm][0] += dfc; mem[nm][1] += 1
        for sj in subs:
            g = cell[(nm, sj)]; g[0] += dfc; g[1] += 1
    return cell, mem


def main():
    rs = records()
    TR = [r for r in rs if r[2] <= TRAIN_END]; TE = [r for r in rs if r[2] > TRAIN_END]
    ctr, mtr = tabulate(TR); cte, mte = tabulate(TE)
    GLOB = sum(1 for r in TR if r[4]) / len(TR)
    print("=" * 74)
    print("DOES A MEMBER STRAY ON PARTICULAR SUBJECTS, RELIABLY ENOUGH TO ACT ON?")
    print("=" * 74)
    print(f"\n  {len(rs):,} member-votes with a party and a subject label")
    print(f"  TRAIN 2017-{TRAIN_END}: {len(TR):,}   TEST {TRAIN_END + 1}-2026: {len(TE):,}")
    print(f"  baseline defection rate: {GLOB:.2%}")

    def mrate(nm, K=150):
        w, n = mtr.get(nm, [0, 0]); return (w + K * GLOB) / (n + K)

    def srate(nm, sj, K=60):
        b = mrate(nm); w, n = ctr.get((nm, sj), [0, 0]); return (w + K * b) / (n + K)

    def ll(f):
        s = 0.0; n = 0
        for nm, _p, _y, subs, dfc in TE:
            if nm not in mtr or mtr[nm][1] < 300:
                continue
            q = min(max(f(nm, subs), 1e-6), 1 - 1e-6)
            s += -(math.log(q) if dfc else math.log(1 - q)); n += 1
        return s / n, n
    g, n = ll(lambda nm, subs: GLOB)
    m, _ = ll(lambda nm, subs: mrate(nm))
    s, _ = ll(lambda nm, subs: sum(srate(nm, sj) for sj in subs) / len(subs) if subs else mrate(nm))
    print("\n" + "=" * 74)
    print("1. AS A GENERAL MODEL IT FAILS — out-of-sample log-loss, both EB-shrunk")
    print("=" * 74)
    print(f"\n  scored votes: {n:,}")
    print(f"    global rate for everyone       {g:.5f}")
    print(f"    THE GUESS: the member's rate   {m:.5f}")
    print(f"    member x subject               {s:.5f}   "
          f"{'WORSE' if s > m else 'better'} by {abs(m - s) / m * 100:.2f}%")
    print(f"\n  Do not ship a model that scores every member x subject cell. Most carry no signal")
    print(f"  and pricing them adds noise everywhere to buy accuracy in a few places.")

    keys = [k for k in ctr if ctr[k][1] >= 40 and cte.get(k, [0, 0])[1] >= 40
            and mtr[k[0]][1] >= 300 and mte[k[0]][1] >= 300]

    def res_te(k):
        return cte[k][0] / cte[k][1] - mte[k[0]][0] / mte[k[0]][1]
    null = sum(1 for k in keys if res_te(k) > 0) / len(keys)
    print("\n" + "=" * 74)
    print("2. AS A SPARSE SCREEN IT WORKS")
    print("=" * 74)
    print(f"\n  {len(keys):,} cells have >=40 votes in BOTH eras.")
    print(f"  THE NULL: {null:.0%} of them sit above the member's own baseline in the held-out era.")
    print(f"  Cells regress downward, so 50% would overstate every screen below by 9 points.\n")

    def p_vs(w, n_, p0):
        if not n_:
            return 1.0
        z = (w - n_ * p0) / math.sqrt(n_ * p0 * (1 - p0))
        return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

    def screen(se_mult, minrate):
        out = []
        for k in keys:
            w, n_ = ctr[k]; b = mtr[k[0]][0] / mtr[k[0]][1]
            se = math.sqrt(max(b * (1 - b), 1e-9) / n_)
            if (w / n_ - b) > se_mult * se and w / n_ >= minrate:
                out.append(k)
        return out
    print(f"  {'screen, fitted on TRAIN only':<42}{'flags':>7}{'replicate':>11}{'vs null':>9}{'p':>10}")
    for lbl, sm, mr in (("residual > 1 SE", 1, 0.0), ("residual > 2 SE", 2, 0.0),
                        ("residual > 2 SE, crosses >=8% there", 2, 0.08),
                        ("residual > 3 SE, crosses >=8% there", 3, 0.08),
                        ("residual > 3 SE, crosses >=15% there", 3, 0.15)):
        fl = screen(sm, mr)
        if len(fl) < 15:
            print(f"  {lbl:<42}{len(fl):>7}{'too few':>11}")
            continue
        rep = sum(1 for k in fl if res_te(k) > 0)
        print(f"  {lbl:<42}{len(fl):>7}{rep / len(fl):>10.0%}{rep / len(fl) - null:>+9.0%}"
              f"{p_vs(rep, len(fl), null):>10.1e}")

    fl = screen(3, 0.08)
    tw = sum(cte[k][0] for k in fl); tn = sum(cte[k][1] for k in fl)
    bw = sum(mte[k[0]][0] for k in fl); bn = sum(mte[k[0]][1] for k in fl)
    print(f"\n  EFFECT SIZE inside the surviving flags ({len(fl)} cells, {tn:,} held-out votes)")
    print(f"    they cross there                  {tw / tn:.1%}")
    print(f"    their own overall rate            {bw / bn:.1%}   ({(tw / tn) / (bw / bn):.1f}x)")
    print(f"    chamber-wide rate                 {sum(1 for r in TE if r[4]) / len(TE):.1%}"
          f"   ({(tw / tn) / (sum(1 for r in TE if r[4]) / len(TE)):.1f}x)")
    print(f"\n  {'member':<22}{'subject':<32}{'train':>7}{'test':>7}{'own base':>10}")
    for k in sorted(fl, key=lambda k: -(cte[k][0] / cte[k][1]))[:12]:
        print(f"  {k[0][:21]:<22}{k[1][:31]:<32}{ctr[k][0] / ctr[k][1]:>6.0%}"
              f"{cte[k][0] / cte[k][1]:>7.0%}{mte[k[0]][0] / mte[k[0]][1]:>10.0%}")
    top = collections.Counter(k[0] for k in fl).most_common(3)
    print(f"\n  CONCENTRATION: {len({k[0] for k in fl})} distinct members hold {len(fl)} flags; "
          f"the busiest is {top[0][0]} with {top[0][1]}.")
    print(f"  A member who crosses often overall will collect several flags -- read the 'own base'")
    print(f"  column, not just the flag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
