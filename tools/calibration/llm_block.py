#!/usr/bin/env python3
"""AI test on the HARD THIRD at the PARTY-BLOCK level (2026-10-25). Why: on "can't call" votes, knowing the member's
party-block majority on the bill is right 95.5% (2025) / 94.3% (2026) -- the hard third is "which way does each party
in the room go", two answers per bill (see docs/testing/first_vote.md). INTERNAL ONLY until the owner's Standard #3 call.

Same 296 bills as llm_member.py. One blinded packet per bill (.cache/llm_block/{yr}/Bxxx.txt), facts public BEFORE
the vote: the bill; the room (size by party, venue, chamber majority, governor's party); patron party / majority /
in-room; co-patrons by party; THIS ROOM's first votes on the 8 most similar earlier bills (party-by-party tallies,
patron party, similarity); the 4 most similar bills voted EARLIER THIS SESSION anywhere (same tallies).
Asked: for each party block that has a "can't call" member, the chance most of that block votes yes.
Scoring: every can't-call member gets its block's chance; accuracy vs arm C; AI + arm C (equal log-odds average).
Run: python3 llm_block.py build  |  python3 llm_block.py score [answers glob tag]
"""
from __future__ import annotations
import sys, os, json, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import llm_member as M

OUT = os.path.join(HERE, ".cache", "llm_block")
GOVERNOR = {"2019": "Democratic", "2020": "Democratic", "2021": "Democratic", "2022": "Republican", "2024": "Republican",
            "2025": "Republican", "2026": "Democratic"}   # Northam 2018-22, Youngkin 2022-26, Spanberger 2026-


def _tally(rs):
    d = [r["y"] for r in rs if r["party"] == "Democratic"]; g = [r["y"] for r in rs if r["party"] == "Republican"]
    return f"Democrats {sum(d)} of {len(d)} yes, Republicans {sum(g)} of {len(g)} yes"


def _room_so_far(by_bill, bills, k, date, d0):
    sofar = [c for c in bills if c[0] == k[0] and date.get(c, "9999") < d0]
    if not sofar:
        return "This room has not voted on any other bill yet this session."
    yes = [sum(r["y"] for r in by_bill[c]) for c in sofar]; n = [len(by_bill[c]) for c in sofar]
    dead = sum(1 for a in yes if a == 0); allyes = sum(1 for a, m in zip(yes, n) if a == m)
    return (f"This room so far this session: {len(sofar)} first votes; {allyes} unanimous yes, {dead} unanimous no, "
            f"{len(sofar) - dead - allyes} split.")


def build():
    import levers as L, gains as G, first_vote as FV, summary_memory as SM
    from corpus import load
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    summ = SM.summaries(); rc = FV.assemble()["rc"]
    date = {k: v[0][0] for k, v in rc.items() if v and v[0][0] != "9999"}
    text = {k: M.blind(corpus[k]["title"] + ". " + summ[k]) for k in summ if k in corpus}
    vec = M._tfidf({k: [w for w in M.WORD.findall(t.lower()) if w not in M.STOP] for k, t in text.items()})
    R = [r for r in L.rows() if r["yr"] >= 2019 and r["bill"] in date]
    by_bill = collections.defaultdict(list); by_room = collections.defaultdict(set)
    for r in R:
        by_bill[r["bill"]].append(r); by_room[r["room"]].add(r["bill"])
    manifest = {}; skipped = collections.Counter()
    for yr, split in M.SPLIT.items():
        ids = json.load(open(os.path.join(HERE, ".cache", f"llm_pilot_ids_{yr}.json")))
        te, _p0, _pA = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        idx = collections.defaultdict(list)
        for i, r in enumerate(te):
            idx[r["bill"]].append(i)
        os.makedirs(os.path.join(OUT, yr), exist_ok=True)
        for code in sorted(c for c in ids if c not in M.RECOGNIZED):
            k = tuple(ids[code]); I = idx.get(k, [])
            ask = [i for i in I if abs(pC[i] - .5) < .31 and te[i]["party"] in ("Democratic", "Republican")]
            if not ask or k not in text or k not in vec:
                skipped["no can't-call vote" if not ask else "no summary"] += 1   # counted, printed below
                continue
            b = corpus[k]; d0 = date[k]; v0 = vec[k]; room = te[I[0]]["room"]
            ven = "subcommittee" if te[I[0]]["ven_sub"] else ("committee" if te[I[0]]["ven_com"] else "floor")
            party_n = collections.Counter(te[i]["party"] for i in I); cops = collections.Counter(b.get("cop_parties") or [])
            blocks = sorted({te[i]["party"] for i in ask})
            def sims(cands, n):
                s = [(M._cos(v0, vec[c]), c) for c in cands if c != k and c in vec and date.get(c, "9999") < d0]
                return [(x, c) for x, c in sorted(s, key=lambda t: -t[0])[:n] if x > 0.05]
            here = sims(by_room[room], 8)
            sess = sims([c for c in by_bill if c[0] == k[0] and c not in {h for _, h in here}], 4)
            pp = lambda p: p.replace("Democratic", "Democrat")
            lines = [f"BILL {code}", "", "What the bill does (official summary as introduced, names and numbers removed):", text[k], "",
                     f"THE VOTE: first recorded vote, in a {ven} of the {'Senate' if b['chamber'] == 'S' else 'House'}. "
                     f"Chamber majority: {b['majority']}. Governor: {GOVERNOR[yr]}.",
                     f"Members voting: {party_n['Democratic']} Democrats, {party_n['Republican']} Republicans.",
                     f"Patron (chief sponsor): a {pp(b['chief_party'])}, {'in the majority' if b['chief_party'] == b['majority'] else 'in the minority'}, "
                     f"{'a member of this room' if te[I[0]]['pat_in_room'] else 'not a member of this room'}.",
                     f"Co-patrons: {cops.get('Democratic', 0)} Democrats, {cops.get('Republican', 0)} Republicans.",
                     _room_so_far(by_bill, by_room[room], k, date, d0), "",
                     "THIS SAME ROOM's first votes on the most similar earlier bills (any earlier year or earlier this session):"]
            for s, c in here:
                lines.append(f"  - {_tally(by_bill[c])}; patron {pp(corpus[c]['chief_party'])}; "
                             f"{'this session' if c[0] == k[0] else 'an earlier year'}; similarity {s:.2f}: {text[c][:240]}")
            if not here:
                lines.append("  - none on record")
            lines += ["", "Most similar bills voted EARLIER THIS SESSION in other rooms:"]
            for s, c in sess:
                lines.append(f"  - {_tally(by_bill[c])}; patron {pp(corpus[c]['chief_party'])}; similarity {s:.2f}: {text[c][:240]}")
            if not sess:
                lines.append("  - none")
            lines += ["", "QUESTION: for each party block below, the chance (0-100) that MOST of that block voted YES: "
                      + ", ".join(blocks) + "."]
            open(os.path.join(OUT, yr, f"{code}.txt"), "w").write("\n".join(lines) + "\n")
            manifest[code] = {"yr": yr, "bill": list(k), "blocks": blocks,
                              "members": [[te[i]["party"], int(te[i]["y"]), float(pC[i])] for i in ask]}
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"))
    print(f"{len(manifest)} packets -> {OUT}; skipped {dict(skipped)}")


def score(tag="v1"):
    import glob
    man = json.load(open(os.path.join(OUT, "manifest.json"))); A = {}
    for f in glob.glob(os.path.join(OUT, f"answers_{tag}_*.jsonl")):
        for line in open(f):
            if line.strip().startswith("{"):
                d = json.loads(line); A[d["id"]] = d
    lo = M.lo; per = collections.defaultdict(list); rec = 0
    for code, v in man.items():
        a = A.get(code)
        if not a:
            continue
        if a.get("recognized"):
            rec += 1; continue
        for party, y, pc in v["members"]:
            if party in a["p"]:
                per[v["yr"]].append((code, y, pc, a["p"][party] / 100))
    print(f"answers {len(A)} bills, recognized (dropped) {rec}")
    for yr in sorted(per):
        D = per[yr]; y = np.array([x[1] for x in D]); pc = np.array([x[2] for x in D]); pa = np.array([x[3] for x in D])
        pm = 1 / (1 + np.exp(-(np.array([lo(a) for a in pc]) + np.array([lo(a) for a in pa])) / 2))
        print(f"{yr}: {len(D)} can't-call votes on {len({x[0] for x in D})} bills")
        for nm, p in (("arm C", pc), ("AI block chance", pa), ("AI + arm C (equal)", pm)):
            r = (p >= .5) == (y == 1); c = np.abs(p - .5) >= .31
            print(f"  {nm:20s} right {r.mean():.3f}  calls {c.sum():4d} ({c.mean():.0%}) right {r[c].mean() if c.any() else float('nan'):.3f} wrong {(c & ~r).sum()}")


if __name__ == "__main__":
    if (sys.argv[1] if len(sys.argv) > 1 else "build") == "build":
        build()
    else:
        score(sys.argv[2] if len(sys.argv) > 2 else "v1")
