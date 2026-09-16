#!/usr/bin/env python3
"""How often does any of this actually apply to a lobbyist's situation?

THE OBJECTION (owner, 2026-09-16): "finding how often this will actually apply to a lobbyists situation
is the right direction."

A validated signal that fires on 1% of real cases is not a product. This measures COVERAGE and INCREMENT
for two candidate surfaces, both trained on early sessions and evaluated on held-out ones.

  A. THE MEMBER x SUBJECT SCREEN ([[testing/member_subject]]) -- narrow but sharp.
     Coverage is measured against the real unit: one bill arriving in one room, with the roster who
     actually cast a vote standing in for the room. A flag is only USEFUL if the flagged member is in
     the party OPPOSITE the patron -- a flag on someone already voting your way is worth nothing.

  B. BILL-LEVEL TRIAGE AT REFERRAL -- 100% coverage by construction, so the only question is whether it
     beats what a lobbyist already knows. THE BASELINE TO BEAT IS "I know my patron's party."

BOTH ANSWERS ARE NEGATIVE-LEANING AND BOTH ARE REPORTED. Run:
  python3 tools/calibration/coverage.py
"""
from __future__ import annotations
import sys, os, re, json, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV, votes as V
from corpus import load, _party_lookup

FATAL = ("laying on the table", "striking from", "passing by indefinitely", "passed by indefinitely",
         "continued to", "tabled")


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def _subjects():
    lab = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1)
        lab[(s, b)] = tuple(v)
    return lab


def auc(sc, ys):
    """Tie-aware Mann-Whitney. The naive rank version scores a CONSTANT model at 1.000, which is how
    this nearly shipped with a meaningless 'base rate only' row at the top of the table."""
    idx = sorted(range(len(sc)), key=lambda i: sc[i])
    ranks = [0.0] * len(sc); i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and sc[idx[j + 1]] == sc[idx[i]]:
            j += 1
        rr = (i + j) / 2 + 1
        for t in range(i, j + 1):
            ranks[idx[t]] = rr
        i = j + 1
    pos = sum(ys); neg = len(ys) - pos
    if not pos or not neg:
        return 0.5
    return (sum(ranks[i] for i in range(len(ys)) if ys[i]) - pos * (pos + 1) / 2) / (pos * neg)


def rooms_and_flags():
    """Room roll calls (who was present, who crossed) plus the member x subject flags from 2017-2023."""
    c = load(); party, _ = _party_lookup(); lab = _subjects()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    cv = CV.load()
    byev = collections.defaultdict(list)
    for v in cv["votes"]:
        byev[(v["session"], v["vote_id"])].append(v)
    rooms = []
    for key, vs in byev.items():
        e = cv["events"].get(key)
        if not e or e["venue"] not in ("committee", "subcommittee"):
            continue
        k = _bk(e["session"], e.get("bill"))
        if not k or k not in cb or not lab.get(k):
            continue
        cast = [(v["name"], party(v.get("name") or ""), v["opt"]) for v in vs
                if v["opt"] in ("yes", "no") and party(v.get("name") or "")]
        if len(cast) < 5:
            continue
        tal = collections.defaultdict(collections.Counter)
        for nm, p, o in cast:
            tal[p][o] += 1
        dfc = set()
        for p, cnt in tal.items():
            if cnt["yes"] + cnt["no"] < 3:
                continue
            mj = "yes" if cnt["yes"] > cnt["no"] else ("no" if cnt["no"] > cnt["yes"] else None)
            if mj:
                dfc |= {nm for nm, pp, o in cast if pp == p and o != mj}
        t = e["desc"].lower()
        fatal = any(f in t for f in FATAL) and "failed to recommend" not in t
        y = sum(1 for _n, _p, o in cast if o == "yes"); n = len(cast) - y
        rooms.append(dict(k=k, year=int(e["session"][:4]), cast=cast, defectors=dfc,
                          subs=lab[k], patron_party=cb[k]["chief_party"], standing=cb[k]["standing"],
                          lost=(fatal if y > n else not fatal), margin=abs(y - n),
                          against=[(nm, p) for nm, p, o in cast if o == ("yes" if fatal else "no")]))
    # flags, fitted on member-votes through 2023 from BOTH corpora
    cellc = collections.defaultdict(lambda: [0, 0]); memc = collections.defaultdict(lambda: [0, 0])

    def add(nm, year, subs, d):
        if year > 2023:
            return
        memc[nm][0] += d; memc[nm][1] += 1
        for s in subs:
            g = cellc[(nm, s)]; g[0] += d; g[1] += 1
    for r in rooms:
        for nm, _p, _o in r["cast"]:
            add(nm, r["year"], r["subs"], nm in r["defectors"])
    for v in V.load()["votes"]:
        k = _bk(v["session"], v.get("bill"))
        if k and lab.get(k) and v.get("party") and v.get("defect") is not None:
            add(v["member"], int(v["session"][:4]), lab[k], bool(v["defect"]))
    return rooms, cellc, memc


def screen(cellc, memc, se_mult, minrate, minn=40, minmem=300):
    out = set()
    for k, (w, n) in cellc.items():
        if n < minn or memc[k[0]][1] < minmem:
            continue
        b = memc[k[0]][0] / memc[k[0]][1]
        se = math.sqrt(max(b * (1 - b), 1e-9) / n)
        if (w / n - b) > se_mult * se and w / n >= minrate:
            out.add(k)
    return out


def part_a(rooms, cellc, memc):
    TE = [r for r in rooms if r["year"] >= 2024]
    print("=" * 76)
    print("A. THE MEMBER x SUBJECT SCREEN — does the flag sit in the room you walked into?")
    print(f"   {len(TE):,} bill-in-a-room situations 2024-2026; flags fitted on 2017-2023 only")
    print("=" * 76)
    print(f"\n  {'screen':<30}{'flags':>7}{'flag in room':>14}{'USEFUL':>9}{'crosses vs peers':>19}")
    for lbl, sm, mr in (("3 SE + crosses >=15%", 3, .15), ("3 SE + crosses >=8%", 3, .08),
                        ("2 SE + crosses >=8%", 2, .08), ("2 SE, no rate floor", 2, 0.),
                        ("1 SE, no rate floor", 1, 0.)):
        F = screen(cellc, memc, sm, mr)
        anyf = use = 0
        fw = fn = uw = un = 0
        for r in TE:
            hit = [(nm, p) for nm, p, _o in r["cast"] if any((nm, sj) in F for sj in r["subs"])]
            if hit:
                anyf += 1
            if any(p != r["patron_party"] for nm, p in hit):
                use += 1
            for nm, _p, _o in r["cast"]:
                d = nm in r["defectors"]
                if any((nm, sj) in F for sj in r["subs"]):
                    fw += d; fn += 1
                else:
                    uw += d; un += 1
            lift = f"{(fw / fn) / (uw / un):.1f}x" if fn >= 200 else "thin"
        print(f"  {lbl:<30}{len(F):>7}{anyf / len(TE):>13.0%}{use / len(TE):>9.0%}{lift:>19}")
    F = screen(cellc, memc, 2, .08)
    step = collections.Counter()
    for r in TE:
        step["situations"] += 1
        if not r["lost"]:
            continue
        step["the bill LOST this vote"] += 1
        if r["margin"] <= 2:
            step["...by <=2 votes, so one member flips it"] += 1
        fl = [nm for nm, p in r["against"] if any((nm, sj) in F for sj in r["subs"])]
        if fl:
            step["...a FLAGGED member voted against it"] += 1
        if fl and r["margin"] <= 2:
            step["...BOTH: flippable AND a named target present"] += 1
    print(f"\n  THE FUNNEL, on the 2 SE + 8% screen ({len(F)} flags):")
    b = step["situations"]
    for k in ("situations", "the bill LOST this vote", "...by <=2 votes, so one member flips it",
              "...a FLAGGED member voted against it", "...BOTH: flippable AND a named target present"):
        print(f"    {k:<50}{step[k]:>7,}{step[k] / b:>8.1%}")
    print(f"    -> of LOSSES, "
          f"{step['...BOTH: flippable AND a named target present'] / step['the bill LOST this vote']:.1%} "
          f"had a flippable margin AND a named target.")
    print(f"    A sharp signal that fires this rarely is a research result, not a feature.")


def part_b():
    c = load(); lab = _subjects()
    cv = CV.load()
    first = {}
    for key, e in cv["events"].items():
        if e["venue"] not in ("committee", "subcommittee"):
            continue
        k = _bk(e["session"], e.get("bill"))
        if not k:
            continue
        d = e.get("date") or ""
        if k not in first or d < first[k][1]:
            first[k] = (key[1].split("V")[0], d)
    rows = [r for r in c["bills"] if r["standing"] and r.get("chief_key")
            and (r["session"], r["bill"]) in first and int(r["session"][:4]) >= 2023]
    for r in rows:
        r["room"] = first[(r["session"], r["bill"])][0]
    TR = [r for r in rows if int(r["session"][:4]) <= 2024]
    TE = [r for r in rows if int(r["session"][:4]) >= 2025]
    G = sum(1 for r in TR if not r["passed"]) / len(TR)

    def tab(keyf):
        t = collections.defaultdict(lambda: [0, 0])
        for r in TR:
            for kk in keyf(r):
                g = t[kk]; g[0] += (not r["passed"]); g[1] += 1
        return t
    T_std = tab(lambda r: [r["standing"]]); T_room = tab(lambda r: [r["room"]])
    T_rs = tab(lambda r: [(r["room"], r["standing"])]); T_pat = tab(lambda r: [r["chief_key"]])
    T_sub = tab(lambda r: [(s, r["standing"]) for s in lab.get((r["session"], r["bill"]), ())])

    def rate(t, keys):
        v = [(t[k][0] + 15 * G) / (t[k][1] + 15) for k in keys if k in t]
        return sum(v) / len(v) if v else G

    def lg(p):
        p = min(max(p, 1e-4), 1 - 1e-4); return math.log(p / (1 - p))

    def mk(use):
        out = []
        for r in TE:
            z = lg(G)
            for t, keyf, w in use:
                z += w * (lg(rate(t, keyf(r))) - lg(G))
            out.append(1 / (1 + math.exp(-z)))
        return out
    ys = [0 if r["passed"] else 1 for r in TE]
    print("\n" + "=" * 76)
    print("B. BILL-LEVEL TRIAGE AT REFERRAL — 100% coverage, so the only question is INCREMENT")
    print(f"   train <=2024 ({len(TR):,}), test 2025-26 ({len(TE):,}); base rate {sum(ys) / len(ys):.0%} die")
    print("=" * 76)
    M = [("nothing (the base rate)", []),
         ("WHAT A LOBBYIST ALREADY KNOWS: patron's party", [(T_std, lambda r: [r["standing"]], 1.0)]),
         ("  + which committee it went to", [(T_std, lambda r: [r["standing"]], 1.0),
                                             (T_room, lambda r: [r["room"]], 1.0)]),
         ("  room x standing as one cell", [(T_rs, lambda r: [(r["room"], r["standing"])], 1.0)]),
         ("  + the patron's own track record", [(T_rs, lambda r: [(r["room"], r["standing"])], 1.0),
                                                (T_pat, lambda r: [r["chief_key"]], 0.7)]),
         ("  + subject", [(T_rs, lambda r: [(r["room"], r["standing"])], 1.0),
                          (T_pat, lambda r: [r["chief_key"]], 0.7),
                          (T_sub, lambda r: [(s, r["standing"])
                                             for s in lab.get((r["session"], r["bill"]), ())], 0.6)])]
    print(f"\n  {'model':<46}{'AUC':>7}{'top decile':>12}{'bottom':>9}")
    for nm, use in M:
        sc = mk(use); q = len(sc) // 10
        o = sorted(range(len(sc)), key=lambda i: -sc[i])
        print(f"  {nm:<46}{auc(sc, ys):>7.3f}{sum(ys[i] for i in o[:q]) / q:>11.0%}"
              f"{sum(ys[i] for i in o[-q:]) / q:>9.0%}")
    sk = mk(M[1][1]); sf = mk(M[-1][1]); q = len(sf) // 10
    ok = sorted(range(len(sk)), key=lambda i: -sk[i]); of = sorted(range(len(sf)), key=lambda i: -sf[i])
    print(f"\n  DECILE TABLE (the triage list a lobbyist would read)")
    print(f"    {'decile':<14}{'predicted':>11}{'actually died':>15}{'n':>7}")
    for d in range(10):
        ix = of[d * q:(d + 1) * q]
        print(f"    {('riskiest' if d == 0 else 'safest' if d == 9 else str(d + 1)):<14}"
              f"{sum(sf[i] for i in ix) / len(ix):>10.0%}{sum(ys[i] for i in ix) / len(ix):>14.0%}{len(ix):>7,}")
    print(f"\n  INCREMENT over 'I know my patron's party':")
    print(f"    AUC                  {auc(sk, ys):.3f} -> {auc(sf, ys):.3f}")
    print(f"    riskiest decile      {sum(ys[i] for i in ok[:q]) / q:.0%} -> "
          f"{sum(ys[i] for i in of[:q]) / q:.0%}   (almost nothing)")
    print(f"    SAFEST decile        {sum(ys[i] for i in ok[-q:]) / q:.0%} -> "
          f"{sum(ys[i] for i in of[-q:]) / q:.0%}   (this is where the value is)")
    print(f"\n  The model mostly re-derives 'your patron is in the minority'. What it adds is at the")
    print(f"  SAFE end: telling a lobbyist which bills they can stop working.")
    print(f"\n  NOTE: 'room x standing as one cell' scores WORSE than the additive pair — sparse cells")
    print(f"  overfit. Kept in the table so the interaction is not re-attempted.")


def main():
    rooms, cellc, memc = rooms_and_flags()
    part_a(rooms, cellc, memc)
    part_b()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
