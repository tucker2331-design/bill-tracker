#!/usr/bin/env python3
"""Personal profile of each VOTING member, beyond their voting record (owner, 2026-09-29: "how often they submit bills
in that category ... more personal explorations"). Year-ahead: choose on 2024, score once on 2025.

Per ballot, from the member's own legislative activity (earlier sessions unless stated):
  own_topic_prior   bills the member FILED (chief) on this bill's topics in earlier sessions
  cop_topic_prior   bills the member CO-SPONSORED on these topics in earlier sessions
  own_topic_now     bills the member filed on these topics THIS session (filed in January, before first votes)
  topic_share       the member's filing share on these topics across their career (specialist vs generalist)
  tenure            sessions the member has served before this one
  own_pass_rate     share of the member's own earlier bills that passed (effectiveness)
Not testable year-ahead: speaking on bills -- no floor transcripts; committee minutes only in the 2025-26 data.
"""
import sys, os, json, pickle, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import first_vote as FV, gbm
from corpus import load, _party_lookup
party, person = _party_lookup()
norm = lambda n: person(n) or n
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
subj = {}
for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
    s, b = k.split("|", 1); subj[(s, b)] = v
own = collections.Counter(); cop = collections.Counter(); own_all = collections.Counter()
passed = collections.Counter(); filed_n = collections.Counter(); served = collections.defaultdict(set)
for (s, bno), b in corpus.items():
    y = int(s[:4]); c = norm(b["chief"])
    served[c].add(y); filed_n[(c, y)] += 1; passed[(c, y)] += int(bool(b["passed"]))
    for t in subj.get((s, bno), []):
        own[(c, t, y)] += 1; own_all[(c, y)] += 1
        for x in b["cops"]: cop[(norm(x), t, y)] += 1
D = FV.assemble()
for (s, bno), lst in D["rc"].items():
    for *_q, ballots in lst:
        for w, _p, _s in ballots: served[w].add(int(s[:4]))
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
def before(counter, key_fn, yr):   # sum over earlier years
    return sum(counter[key_fn(y)] for y in range(2010, yr))
for r in rows:
    m, yr = r["who"], r["yr"]; topics = subj.get(r["bill"], [])
    r["own_topic_prior"] = float(np.log1p(sum(before(own, lambda y, t=t: (m, t, y), yr) for t in topics)))
    r["cop_topic_prior"] = float(np.log1p(sum(before(cop, lambda y, t=t: (m, t, y), yr) for t in topics)))
    r["own_topic_now"] = float(np.log1p(sum(own[(m, t, yr)] for t in topics)))
    tot = before(own_all, lambda y: (m, y), yr)
    r["topic_share"] = (sum(before(own, lambda y, t=t: (m, t, y), yr) for t in topics) / tot) if tot else 0.0
    r["tenure"] = float(sum(1 for y in served.get(m, ()) if y < yr))
    fn = before(filed_n, lambda y: (m, y), yr)
    r["own_pass_rate"] = (before(passed, lambda y: (m, y), yr) + 1) / (fn + 3)
NEW = ["own_topic_prior", "cop_topic_prior", "own_topic_now", "topic_share", "tenure", "own_pass_rate"]
X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
for label, trn, tst in (("choose on 2024", (2019, 2020, 2021, 2022), 2024), ("score on 2025", FV.TRAIN_YEARS, 2025)):
    tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == tst]
    y = np.array([r["y"] for r in te]); same = np.array([r["same"] for r in te]); hf = None
    for name, cs in (("GBM", FV.NUM), ("GBM + personal profile", FV.NUM + NEW)):
        p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
        if hf is None: o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
        rt = (p >= .5) == (y == 1)
        print(f"  [{label}] {name:24s} all {rt.mean():.4f}  other-party {rt[same == 0].mean():.4f}  fixed-hard {rt[hf].mean():.4f}", flush=True)
