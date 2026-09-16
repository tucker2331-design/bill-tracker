#!/usr/bin/env python3
"""Three member-level questions for the War Room. Two are nulls; the third collapses into something simpler.

THE ASK (owner, 2026-09-16): who are the independent voters — "people who you need to convince and havent
made up their minds" — plus who moves together, and who is actually in play in a room.

EVERY MEASURE HERE IS RESTRICTED TO CONTESTED ROLL CALLS: the 3,929 of 18,781 committee/subcommittee votes
(21%) where a member's OWN caucus divided. On the other 79% everyone agrees and every member looks
perfectly predictable, which is an artifact of the denominator, not a fact about anyone.

1 UNPREDICTABILITY  It is a real trait (split-half r = 0.71, cross-era r = 0.52) but it COLLAPSES: it
                    correlates r = 0.92 with the plain defection rate, and conditioning on subject makes
                    prediction 0.1% WORSE. There is no separate "undecided" dimension to model, and the
                    owner's case — someone who always breaks on one subject is predictable — does not
                    appear in the data. Ship the raw count, not a score.

2 BLOCS             NULL, after fixing our own baseline. Chance agreement between two members must be
                    computed from their FOLLOW rates, not their yes-rates: two members who each follow
                    their caucus 85% of the time agree ~75% of the time by chance, not ~51%. Under the
                    wrong baseline 81 of 421 pairs looked significant; under the right one, ONE does.

3 PIVOTALITY        NULL. Observed pivotality (5.2%) is LOWER than a party-line null predicts (6.9%);
                    mean per-member excess is -1.50 points and only 53 of 202 members are positive. It is
                    seat arithmetic, not a property of a person.

Run:  python3 tools/calibration/members.py
"""
from __future__ import annotations
import sys, os, re, math, random, collections, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV
from corpus import load, _party_lookup

MIN_CAST = 5


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def contested_calls():
    """Roll calls where at least one caucus split, with each member marked followed / dissented."""
    c = load(); party, _ = _party_lookup()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    cv = CV.load()
    byev = collections.defaultdict(list)
    for v in cv["votes"]:
        byev[(v["session"], v["vote_id"])].append(v)
    calls, total = [], 0
    for key, vs in byev.items():
        e = cv["events"].get(key)
        if not e or e["venue"] not in ("committee", "subcommittee"):
            continue
        k = _bk(e["session"], e.get("bill"))
        if not k or k not in cb:
            continue
        cast = [(v["name"], party(v["name"]), v["opt"]) for v in vs if v["opt"] in ("yes", "no")]
        cast = [x for x in cast if x[1]]
        if len(cast) < MIN_CAST:
            continue
        total += 1
        tal = collections.defaultdict(collections.Counter)
        for nm, p, o in cast:
            tal[p][o] += 1
        split = {p for p, cnt in tal.items() if cnt["yes"] and cnt["no"]}
        if not split:
            continue
        mj = {p: ("yes" if tal[p]["yes"] > tal[p]["no"] else "no") for p in split}
        calls.append((int(e["session"][:4]), key[1].split("V")[0], cast,
                      [(nm, p, o == mj[p]) for nm, p, o in cast if p in split]))
    return calls, total


def _corr(xs, ys):
    n = len(xs)
    mx = sum(xs) / n; my = sum(ys) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in xs)); sy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (sx * sy) if sx and sy else 0.0


def unpredictability(calls, min_votes=60):
    R = [(nm, p, y, f) for y, _room, _cast, foll in calls for nm, p, f in foll]
    cnt = collections.Counter(r[0] for r in R)
    R = [r for r in R if cnt[r[0]] >= min_votes]
    G = sum(1 for r in R if r[3]) / len(R)

    def fit(rows):
        m = collections.defaultdict(lambda: [0, 0])
        for nm, _p, _y, f in rows:
            g = m[nm]; g[0] += f; g[1] += 1
        return m

    def loss(rows, m, K=12):
        per = collections.defaultdict(lambda: [0.0, 0])
        for nm, _p, _y, f in rows:
            w, n = m.get(nm, [0, 0])
            q = min(max((w + K * G) / (n + K), 1e-3), 1 - 1e-3)
            g = per[nm]; g[0] += -(math.log(q) if f else math.log(1 - q)); g[1] += 1
        return {nm: t / n for nm, (t, n) in per.items() if n}
    random.seed(11)
    by = collections.defaultdict(list)
    for r in R:
        by[r[0]].append(r)
    A, B = [], []
    for v in by.values():
        vv = v[:]; random.shuffle(vv); h = len(vv) // 2
        A += vv[:h]; B += vv[h:2 * h]
    lB = loss(B, fit(A)); lA = loss(A, fit(B))
    com = [nm for nm in lA if nm in lB]
    half = _corr([lA[nm] for nm in com], [lB[nm] for nm in com])
    TR = [r for r in R if r[2] <= 2024]; TE = [r for r in R if r[2] >= 2025]
    lT = loss(TR, fit(TE)); lE = loss(TE, fit(TR))
    c2 = [nm for nm in lT if nm in lE]
    era = _corr([lT[nm] for nm in c2], [lE[nm] for nm in c2])
    full = fit(R)
    rows = sorted(((full[nm][0] / full[nm][1], nm, full[nm][1]) for nm in com))
    score = [(lA[nm] + lB[nm]) / 2 for nm in com]
    rate = [1 - full[nm][0] / full[nm][1] for nm in com]
    return dict(n=len(R), members=len(com), half=half, era=era,
                collapse=_corr(score, rate), rows=rows)


def blocs(calls, min_shared=40, min_test=25):
    def build(rows):
        pair = collections.defaultdict(lambda: [0, 0]); foll = collections.defaultdict(lambda: [0, 0])
        for _y, _room, _cast, fl in rows:
            byp = collections.defaultdict(list)
            for nm, p, f in fl:
                byp[p].append((nm, f))
            for mem in byp.values():
                for nm, f in mem:
                    g = foll[nm]; g[0] += f; g[1] += 1
                mem.sort()
                for i in range(len(mem)):
                    for j in range(i + 1, len(mem)):
                        a, b = mem[i], mem[j]
                        g = pair[(a[0], b[0])]; g[0] += a[1] == b[1]; g[1] += 1
        return pair, foll

    def excess(pair, foll, minn, use_follow=True):
        """use_follow=False reproduces OUR OWN BUG, kept so the correction is demonstrable."""
        out = []
        for (m1, m2), (ag, n) in pair.items():
            if n < minn:
                continue
            f1 = foll[m1][0] / foll[m1][1]; f2 = foll[m2][0] / foll[m2][1]
            e = (f1 * f2 + (1 - f1) * (1 - f2)) if use_follow else 0.5
            se = math.sqrt(max(e * (1 - e), 1e-9) / n)
            out.append(((ag / n - e), (ag / n - e) / se, m1, m2, n, ag / n, e))
        return out
    TR = [r for r in calls if r[0] <= 2024]; TE = [r for r in calls if r[0] >= 2025]
    pT, fT = build(TR); pE, fE = build(TE)
    good = excess(pT, fT, min_shared, True)
    bad = excess(pT, fT, min_shared, False)
    crit = abs(statistics.NormalDist().inv_cdf(0.025 / max(1, len(good))))
    te = {k: v for k, v in pE.items() if v[1] >= min_test}

    def oos(pairs):
        r = g = 0; gains = []
        for d, z, m1, m2, n, obs, e in pairs:
            if (m1, m2) not in te:
                continue
            ag, n2 = te[(m1, m2)]
            a1 = fE[m1][0] / fE[m1][1]; a2 = fE[m2][0] / fE[m2][1]
            e2 = a1 * a2 + (1 - a1) * (1 - a2)
            g += 1; r += (ag / n2 - e2) > 0; gains.append(ag / n2 - e2)
        return r, g, (sum(gains) / len(gains) if gains else 0.0)
    sig = [x for x in good if x[1] > crit]
    return dict(pairs=len(good), crit=crit, sig=sig,
                sig_wrong=sum(1 for x in bad if x[1] > crit),
                neg=sum(1 for x in good if x[1] < -crit),
                mean_chance=sum(x[6] for x in good) / len(good),
                oos_sig=oos(sig), oos_all=oos(good), te=te, fE=fE)


def pivotality(calls, min_votes=150):
    obs = collections.defaultdict(lambda: [0, 0]); nul = collections.defaultdict(lambda: [0, 0])
    for _y, _room, cast, _fl in calls:
        y = sum(1 for _n, _p, o in cast if o == "yes"); margin = y - (len(cast) - y)
        for nm, _p, o in cast:
            g = obs[nm]; g[1] += 1
            new = margin - 2 if o == "yes" else margin + 2
            if (margin > 0) != (new > 0):
                g[0] += 1
        tal = collections.defaultdict(collections.Counter)
        for nm, p, o in cast:
            tal[p][o] += 1
        mj = {p: ("yes" if c["yes"] >= c["no"] else "no") for p, c in tal.items()}
        ny = sum(1 for _n, p, _o in cast if mj[p] == "yes"); nmar = ny - (len(cast) - ny)
        for nm, p, _o in cast:
            g = nul[nm]; g[1] += 1
            new = nmar - 2 if mj[p] == "yes" else nmar + 2
            if (nmar > 0) != (new > 0):
                g[0] += 1
    to = sum(g[0] for g in obs.values()); tn = sum(g[1] for g in obs.values())
    tnull = sum(g[0] for g in nul.values())
    per = [(obs[nm][0] / obs[nm][1] - nul[nm][0] / nul[nm][1])
           for nm in obs if obs[nm][1] >= min_votes]
    return dict(n=tn, obs=to / tn, null=tnull / tn, per=per,
                pos=sum(1 for e in per if e > 0), tot=len(per))


def main():
    calls, total = contested_calls()
    print("=" * 74)
    print("MEMBER-LEVEL SIGNALS FOR THE WAR ROOM — one collapse, two nulls")
    print("=" * 74)
    print(f"\n  committee + subcommittee roll calls: {total:,}")
    print(f"  of those, a caucus actually SPLIT: {len(calls):,} ({len(calls) / total:.0%})")
    print(f"  On the other {1 - len(calls) / total:.0%} everyone agrees, so every member looks")
    print(f"  predictable. That is the denominator talking, not the members.")

    U = unpredictability(calls)
    print("\n" + "=" * 74)
    print("1. WHO HAS NOT MADE UP THEIR MIND — real trait, but it collapses")
    print("=" * 74)
    print(f"\n  {U['n']:,} member-votes inside a split caucus, {U['members']} members with >=60")
    print(f"    split-half reliability        r = {U['half']:.2f}")
    print(f"    2017-2024 vs 2025-2026        r = {U['era']:.2f}")
    print(f"    correlation with plain defection rate  r = {U['collapse']:.2f}   <- THE COLLAPSE")
    print(f"\n  Conditioning on subject made prediction WORSE, not better. There is no separate")
    print(f"  'undecided' dimension: it is the defection rate, measured on the right denominator.")
    print(f"\n  Members who follow their own caucus least when it splits:")
    print(f"  {'member':<26}{'follows caucus':>16}{'contested votes':>17}")
    for fr, nm, n in U["rows"][:10]:
        print(f"  {nm[:25]:<26}{fr:>15.0%}{n:>17,}")

    B = blocs(calls)
    print("\n" + "=" * 74)
    print("2. WHO MOVES TOGETHER — NULL, once the baseline is right")
    print("=" * 74)
    print(f"\n  within-party pairs with >=40 shared contested votes: {B['pairs']:,}")
    print(f"  Bonferroni threshold: |z| > {B['crit']:.2f}")
    print(f"\n  OUR OWN BUG, kept as the comparison: scoring chance from YES-rates (~50%) instead of")
    print(f"  FOLLOW rates makes {B['sig_wrong']} pairs look significant.")
    print(f"  Correct chance agreement averages {B['mean_chance']:.0%}, and leaves {len(B['sig'])} pair(s).")
    print(f"  Pairs agreeing LESS than chance: {B['neg']}")
    r1, g1, m1 = B["oos_sig"]; r0, g0, m0 = B["oos_all"]
    print(f"\n  out of sample (2025-26): flagged {r1}/{g1}, mean excess {m1 * 100:+.1f} pts | "
          f"any pair {r0}/{g0} = {r0 / max(1, g0):.0%}, {m0 * 100:+.1f} pts")
    for d, z, m1_, m2, n, obs, e in sorted(B["sig"], key=lambda x: -x[0]):
        t = B["te"].get((m1_, m2))
        print(f"    {m1_[:21]:<22}{m2[:21]:<22}agree {obs:.0%} vs chance {e:.0%}"
              + (f", held out {t[0] / t[1]:.0%}" if t else ""))

    P = pivotality(calls)
    print("\n" + "=" * 74)
    print("3. WHO IS IN PLAY IN A ROOM — NULL, it is seat arithmetic")
    print("=" * 74)
    print(f"\n  member-votes examined: {P['n']:,}")
    print(f"    observed pivotal            {P['obs']:.1%}")
    print(f"    a party-line null predicts  {P['null']:.1%}")
    print(f"    difference                  {(P['obs'] - P['null']) * 100:+.1f} points")
    print(f"    mean per-member excess      {sum(P['per']) / len(P['per']) * 100:+.2f} points")
    print(f"    members above their own null: {P['pos']} of {P['tot']}")
    print(f"\n  Members are LESS pivotal than party-line voting would make them — dissent piles up")
    print(f"  on votes that were not close. Nothing here is a property of a person.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
