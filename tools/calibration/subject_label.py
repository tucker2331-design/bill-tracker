#!/usr/bin/env python3
"""Extend LIS subject labels from the 2 sessions that publish them to all 18 in the corpus.

THE PROBLEM
-----------
`CiBillSubjects.csv` exists for 2023 and 2024 only. Every subject-cut finding is therefore stuck at 2 of 18
sessions, which is not enough to say anything about a topic across regimes.

HOW ACCURACY IS MEASURED — read this before trusting any number here
---------------------------------------------------------------------
Seed on 2024 ONLY, label 2023 cold, score against 2023's real labels. A random 75/25 split of the two
labelled sessions scores the SAME model ~6 points higher (95.9% vs 89.9%), because a held-out bill can be
labelled from its same-session companion — a shortcut no 2017 bill has. Only the cold-session number is
reported. `--eval` never reads a 2023 label except to score.

WHY AGREEMENT, NOT A BETTER CLASSIFIER
---------------------------------------
Four predictors are computed independently, and CONFIDENCE IS HOW MANY OF THEM CONCUR. Measured cold, the
best single route (exact catalogue head) tops out at 96.4%/36%; requiring three routes to agree gives
97.5%/43%. Single-route thresholds were swept exhaustively (48 combinations) and the frontier was flat at
43-58% coverage — tuning was exhausted, so the gain had to come from combining evidence.

  head   exact catalogue heading ("Elections; early voting." -> "elections"), majority subject
  headnb Naive Bayes over head TOKENS — generalises where the exact phrase is unseen (96% of an unseen
         session's heads share a token with the seed, vs 45% that match exactly)
  near   nearest labelled title by Jaccard over content tokens
  abs    nearest labelled ABSTRACT by Jaccard — available for 75% of the corpus
  cmte   majority subject of the committee of first referral (structural `referral-committee` class)

A ROUTE THAT THE HONEST TEST CANNOT SEE
----------------------------------------
2023 is the only session with no abstracts, and it is the cold-session test set. So `--eval` measures the
model with `abs` permanently silent, and its coverage figure applies only to a session that has no
abstracts. On a companion-safe split of 2024 (which does have them) the same model gained 6 points of
coverage at the same 95% accuracy, 56% -> 62%. Both numbers are reported by `--write` because neither
alone describes the corpus: 2023 is the floor, an abstract-bearing session is the typical case.

WHY SELF-TRAINING, AND WHY IT IS GATED
---------------------------------------
The learning curve is NOT saturated — coverage at 95% went 37 -> 46 -> 52 -> 57% as the seed grew 501 ->
2,004. The binding constraint is seed size, and no more ground truth exists. So high-confidence predictions
are promoted to training evidence. That is only safe above the band where precision was measured at 99%+
(top ~25% of the confidence ranking); promoting indiscriminately is what broke the earlier version, where
companion propagation from GUESSED labels cloned errors into the twin and scored 83.3% — the worst route in
the cascade.

  PROMOTE_CONF   a label must score at least this to become training evidence
  ACCEPT_CONF    a label must score at least this to be emitted at all

WHY NOT SEMANTICS
-----------------
LIS files a bill by which Title of the Code of Virginia it amends, not by topic — wetlands under Fisheries
(28.2), kratom under Professions (54.1). Reading bills by hand scored 80%; applying the code-location rule
deliberately scored 76%; these structural keys score 95%+.

Usage:
    python3 tools/calibration/subject_label.py --eval     # cold-session accuracy (the honest number)
    python3 tools/calibration/subject_label.py --curve    # precision/coverage curve
    python3 tools/calibration/subject_label.py --write    # label the corpus -> subject_labels.json
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subjects import load_subjects          # noqa: E402

HEAD_PURITY = 0.60       # a catalogue head below this has no usable majority
CMTE_PURITY = 0.60
CMTE_MIN = 30            # committees with fewer labelled bills have no stable majority
CAND_CAP = 800           # a token in more than this many labelled titles carries no signal
ABS_CAND_CAP = 1500      # abstracts are ~10x longer than titles, so the same cap would gut recall
TOPK = 40
NB_MARGIN_CAP = 6.0      # log-odds gap saturates; beyond this it adds no information
VOCAB_CONF = 0.99        # measured precision of the head-is-a-subject-name rule (465 labelled cases)

# The DEPLOYMENT bar is 95% on any session, and `--write` refuses unless BOTH measured directions clear
# it. No safety margin is added on top: at 0.95 the pooled measurements are 96.9% (cold) and 95.2%
# (abstract-bearing), and raising the target only buys precision nobody asked for at real cost in
# coverage — 0.955 and 0.960 give up 3 and 7 points of corpus respectively.
#
# A margin WAS added here briefly, for a bad reason. A single-fold estimate of the abstract session read
# 94.8% at target 0.950 and 94.7% at 0.955, which looked like a genuine shortfall; it was sampling noise
# on ~300 accepted bills. Pooling the folds (see abstract_eval) removed it. Tuning a threshold to make a
# noisy statistic pass is fitting to the noise, not to the problem.
TARGET_PRECISION = 0.95
DEPLOY_MIN = 0.95
ACCEPT_CONF = 3.20
PROMOTE_CONF = 4.90      # the 99%-precision band; only these become training evidence
ROUNDS = 5


def _top(counter):
    """Most common key, ties broken ALPHABETICALLY — never by insertion order.

    `Counter.most_common(1)` breaks ties by insertion order, and insertion order here follows iteration
    over frozensets of strings, whose order depends on PYTHONHASHSEED. That made the pipeline
    non-reproducible: two identical runs produced accept cutoffs of 3.50 and 3.33, and different corpus
    coverage. A number nobody can reproduce cannot be audited, so every tie in this file resolves here."""
    if not counter:
        return None, 0
    k = min(counter, key=lambda x: (-counter[x], x))
    return k, counter[k]


class Model:
    """The predictors, fitted on whatever labels are currently trusted (except `vocab`, which is fixed)."""

    def __init__(self, idx, labels, vocab=None):
        self.idx = idx
        self.vocab = vocab or {}
        cnt = collections.defaultdict(collections.Counter)
        prior = collections.Counter()
        hs = collections.defaultdict(collections.Counter)
        cs = collections.defaultdict(collections.Counter)
        self.items, self.inv = [], collections.defaultdict(list)
        self.ainv = collections.defaultdict(list)
        for k, v in labels.items():
            r = idx.get(k)
            if r is None:
                continue
            self.items.append((r, v))
            for w in r["t"]:
                self.inv[w].append(len(self.items) - 1)
            for w in r["a"]:
                self.ainv[w].append(len(self.items) - 1)
            for s in v:
                prior[s] += 1
                for w in r["h"].split():
                    cnt[s][w] += 1
                if r["h"]:
                    hs[r["h"]][s] += 1
                cs[r["cm"]][s] += 1
        self.cnt, self.prior = cnt, prior
        self.tot = {s: sum(c.values()) for s, c in cnt.items()}
        self.V = max(1, len({w for c in cnt.values() for w in c}))
        self.N = max(1, sum(prior.values()))
        self.ph = {h: (_top(c)[0], _top(c)[1] / sum(c.values())) for h, c in hs.items()}
        self.pc = {c: (_top(v)[0], _top(v)[1] / sum(v.values()))
                   for c, v in cs.items() if sum(v.values()) >= CMTE_MIN}

    def _near(self, r, field, index, cap):
        """Nearest labelled bill by Jaccard over `field`. Returns (subject, similarity) or (None, 0.0)."""
        tk = r[field]
        if not tk:
            return None, 0.0
        cand = collections.Counter()
        for w in sorted(tk):
            hits = index[w]
            if len(hits) <= cap:
                for i in hits:
                    cand[i] += 1
        best, bs = None, 0.0
        # Ties on shared-token count resolve by item index, not insertion order — see _top().
        for i in sorted(cand, key=lambda x: (-cand[x], x))[:TOPK]:
            s = self.items[i][0][field]
            if not s:
                continue
            j = len(tk & s) / len(tk | s)
            if j > bs:
                bs, best = j, i
        if best is None:
            return None, 0.0
        return sorted(self.items[best][1])[0], bs

    def predict(self, r):
        """-> (subject, confidence, routes_that_agreed) or (None, 0.0, ()) when nothing fires.

        FAIL CLOSED: a bill no predictor fires on returns None and is left UNLABELLED. It never falls
        back to a corpus-wide most-common subject — a plausible-looking wrong label is worse than a gap,
        because the gap is countable and the wrong label is not."""
        votes = collections.Counter()
        conf = 0.0
        routes = []

        ws = r["h"].split()
        if ws and self.prior:
            sc = sorted(((sum(math.log((self.cnt[s][w] + 0.1) / (self.tot[s] + 0.1 * self.V))
                              for w in ws) + math.log(self.prior[s] / self.N), s)
                         for s in self.prior), reverse=True)
            gap = (sc[0][0] - sc[1][0]) if len(sc) > 1 else NB_MARGIN_CAP
            votes[sc[0][1]] += 1
            routes.append("headnb")
            conf += min(gap, NB_MARGIN_CAP) / NB_MARGIN_CAP

        he = self.ph.get(r["h"])
        if he and he[1] >= HEAD_PURITY:
            votes[he[0]] += 1
            routes.append("head")
            conf += he[1]

        # The head IS an LIS subject name. Independent of every trained route — it comes from the
        # publisher's own vocabulary, so it fires for heads the seed sessions never used.
        vs = self.vocab.get(r["h"])
        if vs:
            votes[vs] += 1
            routes.append("vocab")
            conf += VOCAB_CONF

        s, j = self._near(r, "t", self.inv, CAND_CAP)
        if s is not None:
            votes[s] += 1
            routes.append("near")
            conf += j

        # A bill with no abstract simply does not vote here. The route is SILENT, not defaulted —
        # 2023 has no abstracts at all, and a default would fabricate agreement for a whole session.
        if r["a"]:
            s, j = self._near(r, "a", self.ainv, ABS_CAND_CAP)
            if s is not None:
                votes[s] += 1
                routes.append("abs")
                conf += j

        cv = self.pc.get(r["cm"])
        if cv and cv[1] >= CMTE_PURITY:
            votes[cv[0]] += 1
            routes.append("cmte")
            conf += cv[1]

        if not votes:
            return None, 0.0, ()
        subj, agree = _top(votes)
        return subj, conf + agree, tuple(routes)


def run(idx, seed, rounds=ROUNDS, accept=ACCEPT_CONF, promote=PROMOTE_CONF, vocab=None):
    """Iterated, confidence-gated. Returns {key: (subject_set, conf, routes)} for accepted labels."""
    trusted = dict(seed)
    out = {}
    for _ in range(rounds):
        m = Model(idx, trusted, vocab)
        out, promoted = {}, 0
        for k, r in idx.items():
            if k in seed:
                continue
            s, c, routes = m.predict(r)
            if s is None or c < accept:
                continue
            out[k] = ({s}, c, routes)
        newtrust = dict(seed)
        for k, (v, c, _r) in out.items():
            if c >= promote:
                newtrust[k] = v
                promoted += 1
        if set(newtrust) == set(trusted):
            break
        trusted = newtrust
    return out, trusted


def _companion_folds(idx, labels, seed_val, held=4):
    """Split `labels` into folds by COMPANION GROUP, so a bill's same-text twin can never sit on the
    other side of the split. Without this the split leaks: the twin carries the answer."""
    import random
    grp, nxt = {}, 0
    for k in labels:
        r = idx[k]
        ck = (r["session"], r["companion"]) if r["companion"] else None
        g = grp.get(ck)
        if g is None:
            g, nxt = nxt, nxt + 1
        grp[k] = g
        if ck:
            grp[ck] = g
    gs = sorted({grp[k] for k in labels})
    random.Random(seed_val).shuffle(gs)
    test_g = set(gs[:max(1, len(gs) // held)])
    tr = {k: v for k, v in labels.items() if grp[k] not in test_g}
    te = {k: v for k, v in labels.items() if grp[k] in test_g}
    return tr, te


def calibrate_cross(idx, truth, calib_session, vocab, target=TARGET_PRECISION):
    """Fit the accept cutoff on the OTHER cross-session direction.

    THE BUG THIS FIXES. Fitting the cutoff on folds inside one session gave 3.86, which scored 97.8% on
    the cold session — overshooting a 95% target by 3 points and giving up 12 points of coverage (47% vs
    the 59% the same model could reach). The cause is a distribution shift, not noise: a held-out bill
    from 2024 sits in the same session as most of its training evidence, so it scores systematically
    HIGHER confidence than a 2023 bill labelled from a 2024 seed. Transferring an absolute confidence
    number across that shift transfers a number that means something different on each side.

    So calibrate on a task with the SAME shape as the task being scored. With two labelled sessions each
    can calibrate the other, and neither direction ever sees its own outcomes:

        cutoff fitted on   seed 2023 -> predict 2024
        accuracy reported  seed 2024 -> predict 2023

    Both are cross-session, so the confidence scale is comparable, and 2023's labels play no part in
    choosing the threshold that 2023 is then scored against."""
    seed = {k: v for k, v in truth.items() if k[0] == calib_session}
    test = {k: v for k, v in truth.items() if k[0] != calib_session}
    if not seed or not test:
        return None
    out, _t = run(idx, seed, accept=0.0, vocab=vocab)
    sc = sorted(((out[k][1], bool(out[k][0] & v)) for k, v in test.items() if k in out),
                key=lambda x: -x[0])
    hit, cut = 0, None
    for i, (c, ok) in enumerate(sc, 1):
        hit += ok
        if hit / i >= target:
            cut = c
    return cut


def calibrate(idx, seed, vocab=None, target=TARGET_PRECISION, folds=3):
    """Choose the accept cutoff using ONLY the seed, on a companion-safe internal split.

    WHY NOT calibrate on the cold-session curve: that curve is also the reported accuracy. Picking the
    cutoff that makes 2023 hit 95% and then reporting 'we hit 95% on 2023' is fitting the threshold to
    the test set. Averaging the cutoff over internal folds keeps the cold session genuinely untouched.

    CALIBRATE THE PIPELINE YOU DEPLOY. The first version fitted the cutoff on a plain `Model` built from
    one fold, then applied it to the self-trained model from `run()`. A model fitted on more evidence
    scores every bill higher, so the same numeric cutoff selected a smaller, more confident slice: aiming
    at 95% precision landed at 97.0%, throwing away coverage that had already been earned. Calibration now
    goes through `run()`, exactly as production does."""
    cuts = []
    for f in range(folds):
        tr, te = _companion_folds(idx, seed, seed_val=17 + f)
        out, _t = run(idx, tr, accept=0.0, vocab=vocab)
        sc = []
        for k, v in te.items():
            if k in out:
                sc.append((out[k][1], bool(out[k][0] & v)))
        sc.sort(key=lambda x: -x[0])
        hit, cut = 0, None
        for i, (c, ok) in enumerate(sc, 1):
            hit += ok
            if hit / i >= target:
                cut = c
        if cut is not None:
            cuts.append(cut)
    if not cuts:
        return None
    return sum(cuts) / len(cuts)


def cold_eval(idx_all, truth, accept=ACCEPT_CONF, promote=PROMOTE_CONF, rounds=ROUNDS, vocab=None):
    """Seed 2024, label everything else INCLUDING 2023, score on 2023's real labels.
    2023's labels are never placed in the seed, so they cannot leak into the model."""
    seed = {k: v for k, v in truth.items() if k[0] == "2024"}
    test = {k: v for k, v in truth.items() if k[0] == "2023"}
    out, _tr = run(idx_all, seed, rounds=rounds, accept=accept, promote=promote, vocab=vocab)
    hit = n = 0
    by = {}
    for k, v in test.items():
        if k not in out:
            continue
        ok = bool(out[k][0] & v)
        n += 1
        hit += ok
        tag = "+".join(out[k][2])
        a = by.setdefault(tag, [0, 0])
        a[1] += 1
        a[0] += ok
    return (hit / n if n else 0.0), (n / len(test)), by, n, len(test), out


def abstract_eval(idx, truth, accept, vocab, folds=3):
    """Accuracy and coverage on a session that HAS abstracts — which the cold test cannot measure, since
    2023 is the one session without them.

    POOLED OVER FOLDS, deliberately. A single companion-safe split of 2024 accepts only ~300 bills, and at
    that size the accuracy estimate carries roughly +/-2 points of sampling noise. This value gates
    `--write`, and a gate driven by noise passes or fails on luck: successive calibration targets of
    0.950 / 0.955 / 0.960 produced 94.8% / 94.7% / 96.8%, a spread far larger than the change in target
    could explain. Pooling the folds is what makes the gate mean something."""
    lab = {k: v for k, v in truth.items() if k[0] == "2024"}
    hit = n = held = 0
    for f in range(folds):
        tr, te = _companion_folds(idx, lab, seed_val=3 + f)
        out, _t = run(idx, tr, accept=accept, vocab=vocab)   # same pipeline as production
        held += len(te)
        for k, v in te.items():
            if k not in out:
                continue
            n += 1
            hit += bool(out[k][0] & v)
    return (hit / n if n else 0.0), (n / held if held else 0.0), held


def main() -> int:
    d = load_subjects()
    idx = {(r["session"], r["bill"]): r for r in d["bills"]}
    truth = d["truth"]
    vocab = d["vocab"]

    if "--curve" in sys.argv:
        acc, cov, _by, _n, tot, out = cold_eval(idx, truth, accept=0.0, vocab=vocab)
        test = {k: v for k, v in truth.items() if k[0] == "2023"}
        sc = sorted(((out[k][1], bool(out[k][0] & v)) for k, v in test.items() if k in out),
                    key=lambda x: -x[0])
        print(f"{'conf':>7}{'coverage':>10}{'cum. accuracy':>15}   (cold: seed 2024 -> label 2023)")
        hit = 0
        best = None
        for i, (c, ok) in enumerate(sc, 1):
            hit += ok
            if hit / i >= 0.95:
                best = (i / tot, hit / i, c)
            if i % 150 == 0 or i == len(sc):
                print(f"{c:>7.2f}{i/tot:>9.0%}{hit/i:>14.1%}{'  *' if hit/i >= 0.95 else ''}")
        if best:
            print(f"\nmax coverage at >=95%: {best[0]:.0%}, accuracy {best[1]:.1%}, conf cutoff {best[2]:.2f}")
        return 0

    # Fitted on seed-2023 -> predict-2024. The reported accuracy is the other direction, so 2023's
    # outcomes never influence the threshold 2023 is scored against. See calibrate_cross().
    cut = calibrate_cross(idx, truth, calib_session="2023", vocab=vocab)
    if cut is None:
        print(f"REFUSING: no cutoff holds {TARGET_PRECISION:.0%} precision on the calibration "
              f"direction.", file=sys.stderr)
        return 1

    if "--write" in sys.argv:
        acc, cov, _by, _n, _t, _o = cold_eval(idx, truth, accept=cut, vocab=vocab)
        aacc, acov, _an = abstract_eval(idx, truth, cut, vocab)
        # FAIL CLOSED on BOTH directions. Checking only the cold session would have shipped a label set
        # that was 96.9% there and 94.8% on every abstract-bearing session — i.e. below bar on 75% of
        # the corpus, reported as passing.
        if min(acc, aacc) < DEPLOY_MIN:
            print(f"REFUSING TO WRITE: cold session {acc:.1%}, abstract session {aacc:.1%} — "
                  f"one is below the {DEPLOY_MIN:.0%} bar.", file=sys.stderr)
            return 1
        out, _tr = run(idx, truth, accept=cut, vocab=vocab)
        labels = {f"{s}|{b}": sorted(v) for (s, b), (v, _c, _r) in out.items()}
        for (s, b), v in truth.items():
            labels[f"{s}|{b}"] = sorted(v)
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subject_labels.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"measured": {
                "cold_session_accuracy": round(acc, 4),
                "cold_session_coverage": round(cov, 4),
                "cold_session_note": "2023, the only session with NO abstracts — the floor case",
                "abstract_session_accuracy": round(aacc, 4),
                "abstract_session_coverage": round(acov, 4),
                "abstract_session_note": "companion-safe split of 2024; same-session so accuracy runs "
                                         "high, cited for COVERAGE",
                "accept_conf": round(cut, 3), "promote_conf": PROMOTE_CONF,
                "calibration": "cutoff fitted on seed-2023 -> predict-2024; accuracy reported on the "
                               "reverse direction, so 2023 never influenced its own threshold"},
                "ground_truth": sorted(f"{s}|{b}" for s, b in truth),
                "labels": labels}, fh, indent=0, sort_keys=True)
        print(f"accept cutoff {cut:.2f} (fitted on seed-2023 -> predict-2024)")
        print(f"cold session, no abstracts : {acc:.1%} accurate at {cov:.0%} coverage")
        print(f"session with abstracts     : {aacc:.1%} accurate at {acov:.0%} coverage")
        print(f"wrote {len(labels):,} of {len(idx):,} bills ({len(labels)/len(idx):.0%}) -> {path}")
        return 0

    acc, cov, by, n, tot, _o = cold_eval(idx, truth, accept=cut, vocab=vocab)
    aacc, acov, an = abstract_eval(idx, truth, cut, vocab)
    print(f"accept cutoff {cut:.2f}, fitted on seed-2023 -> predict-2024. The direction scored below is "
          f"the reverse, so 2023's labels never influenced it.\n")
    print("COLD SESSION — seed 2024, label 2023 (the ONLY session with no abstracts).")
    print(f"  {acc:.1%} accurate on {n:,} of {tot:,} bills ({cov:.0%} coverage)\n")
    print(f"SESSION WITH ABSTRACTS — companion-safe split of 2024 ({an:,} held out).")
    print(f"  {aacc:.1%} accurate at {acov:.0%} coverage\n")
    print("  cold-session accuracy by which routes agreed:")
    for tag, (h, m) in sorted(by.items(), key=lambda kv: -kv[1][1])[:8]:
        print(f"    {tag:<28} {h/m:>6.1%}  (n={m:,})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
