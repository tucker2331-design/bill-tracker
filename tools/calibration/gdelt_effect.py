#!/usr/bin/env python3
"""GDELT news attention (2025 pilot) -- does it add anything the model does not already know?

Source: GDELT GKG 2.1 bulk files, 2025-01-01..2025-03-15, filtered to Virginia-legislature articles by
tools/historical_cache/gdelt_gkg_stream.py (28,124 unique articles). GKG carries names, themes, URL and tone -- not
text, so bills are not identifiable (22 bill numbers appear in URLs). Measured per bill, dated strictly BEFORE the
decision:
    pat_news     articles naming the bill's patron            (log1p)
    mem_news     articles naming the voting member            (log1p, ballot test only)
    topic_news   articles whose URL slug shares a word with the bill's subject line  (log1p)
    *_14         the same counted over the 14 days before

Contamination handled: the stream kept rows whose location read "Virginia, United States", which also matches
"West Virginia, United States". West Virginia outlets are dropped by source (list below, counted), and person
matches require an exact full-name match to a 2025 legislator.

Only 2025 exists, so the test is WITHIN 2025, stacked on the existing models: 5 folds by bill; a logistic layer on
[logit(model p)] vs [logit(model p) + news inputs], out-of-fold per-bill log loss, z over bills. Two targets:
    ballots      first-vote ballots, model = one-stage GBM trained 2019-2024
    fate         did the bill ADVANCE from its first committee, model = fate.py blend trained 2020-2024
Decision rule written before running: download more years (~40 GB each) only if either target shows z >= 3.
"""
from __future__ import annotations
import sys, os, re, gzip, json, glob, math, pickle, collections, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import first_vote as FV, stats as ST

WV = {"wvnews.com", "wvgazettemail.com", "wvmetronews.com", "theintelligencer.net", "weirtondailytimes.com",
      "herald-dispatch.com", "register-herald.com", "wvpublic.org", "wchstv.com", "wboy.com", "wsaz.com",
      "wtrf.com", "wdtv.com", "newsandsentinel.com", "journal-news.net", "statejournal.com", "lootpress.com",
      "theet.com", "wowktv.com", "timeswv.com", "wajr.com", "wvnstv.com", "wdtv.com", "dominionpost.com"}
STOP = {"the", "and", "for", "of", "to", "in", "on", "a", "an", "by", "with", "or", "from", "at", "as", "is",
        "virginia", "va", "bill", "bills", "state", "new", "law", "laws", "general", "assembly", "certain"}


def articles():
    arts, dropped = {}, collections.Counter()
    for f in sorted(glob.glob(os.path.join(HERE, "..", "historical_cache", "va_gdelt", "gkg_*.jsonl.gz"))):
        for line in gzip.open(f, "rt"):
            r = json.loads(line)
            if r["src"] in WV:
                dropped["West Virginia outlet"] += 1; continue
            if r["url"] not in arts:
                arts[r["url"]] = (r["date"][:4] + "-" + r["date"][4:6] + "-" + r["date"][6:8],
                                  {p.lower() for p in r["persons"]},
                                  set(re.findall(r"[a-z]{3,}", r["url"].rsplit("/", 1)[-1].lower())) - STOP)
    print(f"articles kept {len(arts)}; dropped {dict(dropped)}")
    return list(arts.values())


def counter(arts, names):
    """name -> sorted list of dates it appears."""
    by = collections.defaultdict(list)
    for d, ps, _w in arts:
        for p in ps & names:
            by[p].append(d)
    return {k: sorted(v) for k, v in by.items()}


def n_before(dates, day, window=None):
    import bisect
    hi = bisect.bisect_left(dates, day)
    if window is None:
        return hi
    lo = bisect.bisect_left(dates, (dt.date.fromisoformat(day) - dt.timedelta(days=window)).isoformat())
    return hi - lo


def topic_index(arts):
    by = collections.defaultdict(list)
    for d, _p, ws in arts:
        for w in ws:
            by[w].append(d)
    return {k: sorted(v) for k, v in by.items()}


def subject_words(title):
    return set(re.findall(r"[a-z]{3,}", (title or "").split(";")[0].lower())) - STOP


def news_feats(title, patron, member, day, P, T):
    f = {}
    pw = P.get((patron or "").lower(), []); mw = P.get((member or "").lower(), []) if member else []
    tw = [T.get(w, []) for w in subject_words(title)]
    f["pat_news"] = math.log1p(n_before(pw, day)); f["pat_news_14"] = math.log1p(n_before(pw, day, 14))
    if member is not None:
        f["mem_news"] = math.log1p(n_before(mw, day)); f["mem_news_14"] = math.log1p(n_before(mw, day, 14))
    f["topic_news"] = math.log1p(sum(n_before(x, day) for x in tw))
    f["topic_news_14"] = math.log1p(sum(n_before(x, day, 14) for x in tw))
    return f


def stacked(base_p, F, y, groups, label):
    """5 folds by bill. Returns OOF per-bill log-loss gain of adding F, and its z."""
    lg = np.log(np.clip(base_p, 1e-6, 1 - 1e-6) / (1 - np.clip(base_p, 1e-6, 1 - 1e-6)))
    cols = sorted(F[0]); Xf = np.array([[f[c] for c in cols] for f in F], float)
    ub = sorted(set(groups)); rng = np.random.default_rng(11); fold_of = dict(zip(ub, rng.integers(0, 5, len(ub))))
    fo = np.array([fold_of[g] for g in groups])
    p0 = np.zeros(len(y)); p1 = np.zeros(len(y))
    for k in range(5):
        tr, te = fo != k, fo == k
        for X, out, names in ((lg[:, None], p0, ["lg"]), (np.column_stack([lg, Xf]), p1, ["lg"] + cols)):
            fit = ST.logit(X[tr], y[tr], names, ridge=1e-3)
            b = np.array([fit[n][0] for n in ["const"] + names])
            with np.errstate(all="ignore"):
                out[te] = 1 / (1 + np.exp(-(np.column_stack([np.ones(te.sum()), X[te]]) @ b)))
    ll = lambda p: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
    d = collections.defaultdict(float)
    for g, a, b in zip(groups, ll(p0), ll(p1)):
        d[g] += a - b
    d = np.array(list(d.values())); z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    r0 = ((p0 >= .5) == (y == 1)).mean(); r1 = ((p1 >= .5) == (y == 1)).mean()
    cov = np.mean([any(f[c] > 0 for c in cols if not c.startswith("topic")) for f in F])
    print(f"{label}: n {len(y)}; any person-news coverage {cov:.1%}; accuracy {r0:.4f} -> {r1:.4f}; "
          f"per-bill log-loss gain {d.mean():+.5f}, z = {z:.1f} -> {'PASS' if z >= 3 else 'no gain'}")
    return z


def main():
    arts = articles()
    from corpus import load
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0 and r["yr"] in set(FV.TRAIN_YEARS) | {2025}]
    tr = [r for r in rows if r["yr"] in FV.TRAIN_YEARS]; te = [r for r in rows if r["yr"] == 2025]
    names = {r["who"].lower() for r in te} | {(FV._party_lookup()[1](b["chief"]) or b["chief"]).lower()
                                             for (s, _b), b in corpus.items() if s == "2025"}
    P = counter(arts, names); T = topic_index(arts)
    # ballots
    import gbm
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te))
    rc = FV.assemble()["rc"]; person = FV._party_lookup()[1]
    F = []
    for r in te:
        b = corpus[r["bill"]]; day = rc[r["bill"]][0][0]
        F.append(news_feats(b["title"], person(b["chief"]) or b["chief"], r["who"], day, P, T))
    y = np.array([r["y"] for r in te], float)
    zb = stacked(p, F, y, [r["bill"] for r in te], "BALLOTS (2025 first votes)")
    # fate
    import fate as FT
    R, _ = FT.bills(); R = [r for r in R if r["standing"] in ("majority", "minority")]
    Ff = FT.featurise(R); cols = sorted(Ff[0])
    Xf = np.array([[f[c] for c in cols] for f in Ff], float); yr = np.array([r["year"] for r in R])
    Y = np.array([FT.MCLASSES.index(FT._m(r)) for r in R])
    trm, tem = yr < 2025, yr == 2025
    Pm = FT.BLEND * FT.fit_predict(Xf[trm], Y[trm], Xf[tem]) + (1 - FT.BLEND) * FT.baseline(
        [r for r, m in zip(R, trm) if m], [r for r, m in zip(R, tem) if m])
    R25 = [r for r, m in zip(R, tem) if m]
    G = []
    for r in R25:
        # one cutoff for every bill (filing + 14 days): a class-dependent cutoff would let "never acted on" bills
        # (decided at session end) count more news simply by waiting longer
        d0 = r["actions"][0][0] if r["actions"] else "2025-01-08"
        dec = (dt.date.fromisoformat(max(d0, "2025-01-08")) + dt.timedelta(days=14)).isoformat()
        G.append(news_feats(r["title"], person(r["chief"]) or r["chief"], None, dec, P, T))
    zf = stacked(Pm[:, 0], G, (Y[tem] == 0).astype(float), [r["bill"] for r in R25], "FATE (2025, advanced?)")
    print("DECISION:", "download more years" if max(zb, zf) >= 3 else "stop -- pilot shows no gain; no further download")


if __name__ == "__main__":
    main()
