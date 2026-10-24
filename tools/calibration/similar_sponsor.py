#!/usr/bin/env python3
"""Do members vote for bills like the ones THEY sponsor? (owner, 2026-09-30: "are members votes at all correlated to
wether they have introduced similar language or introduce in the same topic?")

For every first-vote ballot of 2021 / 2022 / 2024 / 2025, from the public record only, dated before the vote:
    sim_spon     the voter was chief patron or co-patron of a bill with near-identical summary wording (the
                 content-neighbour list, summary Jaccard >= SIM) filed in an EARLIER session or earlier this session
    topic_spon   the voter filed (as chief) a bill on the same coarse subject in an earlier session
Three questions, answered separately:
    1. RAW       yes rate with vs without, split by whether the voter is in the patron's party (n shown)
    2. ALREADY   the same split on the model's MISSES: model p is year-ahead out-of-sample (accept.base_preds), so
       KNOWN?    mean(y - p) ~ 0 means the model already accounts for it
    3. NEW INFO? accept.stacked_year_ahead -- fitted on earlier years, scored on the next, pooled per bill, z >= 3
"""
from __future__ import annotations
import sys, os, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import accept as AC, first_vote as FV
from corpus import load, _party_lookup

SIM = 0.30


def build():
    party, person = _party_lookup()
    norm = lambda n: person(n) or n
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    spons = {k: {norm(b["chief"])} | {norm(c) for c in b["cops"]} for k, b in corpus.items()}
    chief = {k: norm(b["chief"]) for k, b in corpus.items()}
    filed = {k: (b["actions"][0][0] if b["actions"] else "9999") for k, b in corpus.items()}
    subj = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1); subj[(s, b)] = set(v)
    own_topic = collections.defaultdict(set)                  # (member, subject) -> years filed
    for k, b in corpus.items():
        if k[0].isdigit():
            for t in subj.get(k, ()):
                own_topic[(chief[k], t)].add(int(k[0]))
    D = FV.assemble(); nb, rc = D["nb"], D["rc"]
    def sig(r):
        k = r["bill"]; day = rc[k][0][0]; m = r["who"]; yr = int(k[0])
        sim = any(j >= SIM and m in spons.get(c, ()) and c != k and
                  (int(c[0]) < yr or (c[0] == k[0] and filed.get(c, "9999") < day))
                  for c, j in nb.get(k, []) if c[0].isdigit())
        top = any(y < yr for t in subj.get(k, ()) for y in own_topic.get((m, t), ()))
        same = float(r["same"])
        # one "sim" input, not sim x side: 97% of near-identical sponsors are in the patron's party, so the split pair
        # was nearly collinear and the fit crawled without converging; the raw rates are +3 points on both sides
        return {"sim": float(sim), "top_same": float(top) * same, "top_other": float(top) * (1 - same), "top": float(top)}
    return sig


def main():
    sig = build()
    B = AC.base_preds()
    tab = collections.defaultdict(lambda: [0, 0.0, 0.0])      # (feature, value, side) -> n, sum y, sum (y - p)
    for t, (te, p) in B.items():
        for r, q in zip(te, p):
            s = sig(r)
            for f in ("sim", "top"):
                c = tab[(f, int(s[f]), int(r["same"]))]
                c[0] += 1; c[1] += r["y"]; c[2] += r["y"] - q
    names = {"sim": "sponsored a near-identical bill", "top": "filed a bill on the same topic before"}
    for f in ("sim", "top"):
        print(f"\n{names[f].upper()} (2021/2022/2024/2025 first votes)")
        for side, lab in ((1, "patron's party"), (0, "other party")):
            for v in (1, 0):
                n, sy, sr = tab[(f, v, side)]
                print(f"  {lab:15s} {'yes' if v else 'no ':3s}  ballots {n:6d}  voted yes {sy / n:6.1%}   "
                      f"model's miss (actual - predicted) {sr / n:+.3f}")
    print()
    AC.stacked_year_ahead(lambda r: {"sim": sig(r)["sim"]}, "NEAR-IDENTICAL SPONSORSHIP", ridge=10.0)
    AC.stacked_year_ahead(lambda r: {k: sig(r)[k] for k in ("top_same", "top_other")},
                          "SAME-TOPIC FILING x side", ridge=10.0)


if __name__ == "__main__":
    main()
