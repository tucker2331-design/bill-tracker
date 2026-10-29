#!/usr/bin/env python3
"""More attacks on the hardest third, run side by side (owner, 2026-10-15: "test more than one thing at once").

shape_first.py found: 36.5% of the hard third are votes that ended UNANIMOUS YES and 14.4% UNANIMOUS NO -- the model
hedged on bills the room agreed on. 70% of the hard third are other-party members.

  p56    this SESSION's record: how the other party / own party treated THIS PATRON's bills earlier this session, and
         this MEMBER's votes on this patron's bills earlier this session (the model has all-years versions only)
  words  a consensus detector from summary words: per year, from earlier years only, which words go with unanimous-yes
         and unanimous-no first votes (smoothed log-odds per word, averaged over the bill's words); x voter side
  diag   the hard third by subject, time in session, member type, and whether the miss changed the room's outcome
Every signal: accept.stacked_year_ahead (2022/2024/2025 pooled; fixed hardest third reported).
Run: python3 hard_third_more.py p56 | words | diag
"""
from __future__ import annotations
import sys, os, re, json, math, pickle, bisect, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import accept as AC, first_vote as FV
from corpus import load, _party_lookup

rows_all = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] != 2026]
rc = FV.assemble()["rc"]
day = {r["bill"]: rc[r["bill"]][0][0] for r in rows_all}
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
_party, person = _party_lookup()


def p56():
    pat_ev = collections.defaultdict(list)       # (session, patron, same) -> [(date, y)]
    mem_ev = collections.defaultdict(list)       # (session, member, patron) -> [(date, y)]
    for r in rows_all:
        P = person(corpus[r["bill"]]["chief"]) or corpus[r["bill"]]["chief"]
        pat_ev[(r["bill"][0], P, r["same"])].append((day[r["bill"]], r["y"]))
        mem_ev[(r["bill"][0], r["who"], P)].append((day[r["bill"]], r["y"]))
    for d_ in (pat_ev, mem_ev):
        for k in d_: d_[k].sort()
    def before(ev, d):
        i = bisect.bisect_left(ev, (d, -1)); return sum(y for _d, y in ev[:i]), i
    def sig(r):
        P = person(corpus[r["bill"]]["chief"]) or corpus[r["bill"]]["chief"]; d = day[r["bill"]]; s = float(r["same"])
        k1, n1 = before(pat_ev.get((r["bill"][0], P, r["same"]), []), d)
        k2, n2 = before(mem_ev.get((r["bill"][0], r["who"], P), []), d)
        prior = .87 if r["same"] else .62
        a = (k1 + 10 * prior) / (n1 + 10) - prior; b = (k2 + 3 * prior) / (n2 + 3) - prior
        return {"pat_ses_same": a * s, "pat_ses_other": a * (1 - s), "mem_pat_ses_same": b * s, "mem_pat_ses_other": b * (1 - s)}
    AC.stacked_year_ahead(sig, "P5/P6 THIS SESSION: the patron's bills, and this member on this patron's bills", ridge=10.0)


def words():
    import summary_memory as SM
    summ = SM.summaries()
    STOP = set("the a an of to and or in for on by with as be is are that this from at which any such its it shall may "
               "bill provides requires certain".split())
    toks = lambda k: set(re.findall(r"[a-z]{4,}", (summ.get(k, "") + " " + corpus.get(k, {}).get("title", "")).lower())) - STOP
    g = collections.defaultdict(list)
    for r in rows_all:
        g[r["bill"]].append(r["y"])
    shape = {k: (1 if all(v) else -1 if not any(v) else 0) for k, v in g.items()}
    W = {}
    for t in (2021, 2022, 2024, 2025):
        cnt = collections.defaultdict(lambda: [0, 0, 0]); tot = [0, 0, 0]       # word -> [unan yes, unan no, other]
        for k, sh in shape.items():
            if int(k[0]) < t:
                i = {1: 0, -1: 1, 0: 2}[sh]; tot[i] += 1
                for w in toks(k):
                    cnt[w][i] += 1
        W[t] = (cnt, tot)
    def score(k, t):
        cnt, tot = W[t]; ws = [w for w in toks(k) if sum(cnt[w]) >= 5]
        if not ws:
            return 0.0, 0.0
        n = sum(tot)
        yes = np.mean([math.log((cnt[w][0] + 1) / (tot[0] + 2)) - math.log((sum(cnt[w]) + 1) / (n + 2)) for w in ws])
        no = np.mean([math.log((cnt[w][1] + 1) / (tot[1] + 2)) - math.log((sum(cnt[w]) + 1) / (n + 2)) for w in ws])
        return float(yes), float(no)
    cache = {}
    def sig(r):
        t = r["yr"]
        if t not in W:
            return {"wy_same": 0.0, "wy_other": 0.0, "wn_same": 0.0, "wn_other": 0.0}
        if r["bill"] not in cache:
            cache[r["bill"]] = score(r["bill"], t)
        y_, n_ = cache[r["bill"]]; s = float(r["same"])
        return {"wy_same": y_ * s, "wy_other": y_ * (1 - s), "wn_same": n_ * s, "wn_other": n_ * (1 - s)}
    AC.stacked_year_ahead(sig, "P8 CONSENSUS WORDS (unanimous-yes / unanimous-no word scores, earlier years) x voter side",
                          ridge=10.0)


def diag():
    subj = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1); subj[(s, b)] = v
    B = AC.base_preds()
    cells = collections.defaultdict(lambda: [0, 0]); n_hard = 0
    room_right = {}
    for t, (te, p) in B.items():
        y = np.array([r["y"] for r in te]); right = (p >= .5) == (y == 1)
        hard = set(np.argsort(np.abs(p - .5))[:len(p) // 3].tolist())
        gi = collections.defaultdict(list)
        for i, r in enumerate(te):
            gi[r["bill"]].append(i)
        for k, I in gi.items():
            I = np.array(I); room_right[k] = (p[I].sum() > len(I) / 2) == (y[I].sum() > len(I) / 2)
        start = min(day[r["bill"]] for r in te)
        for i, r in enumerate(te):
            if i not in hard:
                continue
            n_hard += 1
            import datetime as dt
            wk = (dt.date.fromisoformat(day[r["bill"]]) - dt.date.fromisoformat(start)).days // 14
            keys = [("weeks into session", f"weeks {2*wk+1}-{2*wk+2}"),
                    ("member", "breaks with party on 6%+ of votes" if r["defect"] >= .06 else "loyal"),
                    ("room outcome", "room outcome called right" if room_right[r["bill"]] else "room outcome MISSED")]
            for sname in (subj.get(r["bill"]) or ["(no subject)"])[:1]:
                keys.append(("subject", sname))
            for k in keys:
                cells[k][0] += 1; cells[k][1] += int(right[i])
    print(f"THE HARD THIRD (2021/2022/2024/2025, {n_hard} ballots) -- share and member-model accuracy")
    for dim in ("room outcome", "member", "weeks into session", "subject"):
        print(f"  by {dim}:")
        items = sorted([(k, v) for k, v in cells.items() if k[0] == dim], key=lambda kv: -kv[1][0])
        for k, v in items[:10]:
            print(f"     {k[1]:38s} {v[0] / n_hard:5.1%}   right {v[1] / v[0]:5.1%}")


if __name__ == "__main__":
    {"p56": p56, "words": words, "diag": diag}[sys.argv[1]]()
