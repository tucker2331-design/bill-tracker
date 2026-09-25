#!/usr/bin/env python3
"""Predict every legislator's vote at a bill's FIRST recorded roll call -- the one a lobbyist needs before
the room votes. Owner, 2026-09-25: focus on the first vote ("after that we know its a lot easier"), don't
build something accurate where it is least useful, test dynamically, and try to break 95%.

PROTOCOL (borrowed from how model builders evaluate):
  train   first votes of 2020, 2021, 2022, 2024        (history for each = strictly before that vote)
  tune    2025  -- every feature / model choice is judged here
  TEST    2026  -- locked; scored ONCE, after all choices are frozen (see --final)
  slices  always reported: same-party vs OTHER-party legislators, venue, and a party-position score,
          so a gain on the easy majority of ballots cannot hide a loss where it matters.
Every feature is knowable before the vote: earlier years, or earlier DATES in the same session.
"""
from __future__ import annotations
import sys, os, re, collections, pickle, math, random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
from corpus import load, _party_lookup
import content_votes as CVT
import summary_memory as SM

PARTIES = CVT.PARTIES
CACHE = os.path.join(HERE, "first_vote_cache.pkl")
REF = re.compile(r"^referred to committee (?:on|for) (.+?)\.?$", re.I)
K = 15


def first_room(bill):
    for _d, t, _c in bill["actions"]:
        m = REF.match(t.strip())
        if m:
            return f'{bill["chamber"]}:{m.group(1)}'
    return None


def assemble():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    d = CVT.build()
    corpus = {(r["session"], r["bill"]): r for r in load()["bills"]}
    party, person = _party_lookup()
    rc = collections.defaultdict(list)                       # (s,b) -> sorted roll calls
    VORD = {"sub": 0, "com": 1, "floor": 2}
    for s, b, vid, date, ven, ballots in d["rolls"]:
        rc[(s, b)].append((date or "9999", VORD[ven], vid, ven, ballots))
    for k in rc:
        rc[k].sort()
    # content neighbours: earlier years AND the same session (date-filtered at use time)
    summ = SM.summaries()
    keys = [k for k in corpus if k in summ and k[0] in CVT.YEARS]
    sh = {k: SM.shingles(summ[k], corpus[k]["title"]) for k in keys}
    df = collections.Counter(g for k in keys for g in sh[k])
    inv = collections.defaultdict(list)
    for k in keys:
        for g in sh[k]:
            if df[g] <= 40:
                inv[g].append(k)
    nb = {}
    for k in keys:
        S = sh[k]
        if len(S) < 8:
            continue
        yr = int(k[0][:4])
        cand = {c for g in S if df[g] <= 40 for c in inv[g]
                if c != k and int(c[0][:4]) <= yr and not (c[1] == k[1] and 0 < yr - int(c[0][:4]) <= 1)}
        sc = sorted(((len(S & sh[c]) / len(S | sh[c]), c) for c in cand), reverse=True)[:K]
        nb[k] = [(c, j) for j, c in sc if j >= 0.05]
    data = {"rc": dict(rc), "nb": nb, "corpus_keys": list(corpus)}
    pickle.dump(data, open(CACHE, "wb"))
    return data


if __name__ == "__main__":
    import time
    t = time.time(); D = assemble(); print(f"assembled in {time.time()-t:.0f}s: {len(D['rc'])} bills with roll calls, "
                                          f"{len(D['nb'])} with content neighbours")


def _rate(s, n, prior, a):
    return (s + a * prior) / (n + a)


def features():
    """Replay every roll call in DATE order. Features for a bill's first vote are computed from the state
    BEFORE that day; the state is updated only after every first vote of the day has been featurised."""
    D = assemble()
    corpus = {(r["session"], r["bill"]): r for r in load()["bills"]}
    party, person = _party_lookup()
    rc, nb = D["rc"], D["nb"]
    events = collections.defaultdict(list)
    for (s, b), lst in rc.items():
        for i, (date, vo, vid, ven, ballots) in enumerate(lst):
            if date and date != "9999":
                events[date].append((s, b, i, ven, ballots))
    # rolling state
    defect = collections.Counter()                       # (who,'n'|'d')
    room = collections.Counter()                         # (room, same, 'n'|'s')
    pat = collections.Counter()                          # (patron, same, 'n'|'s')
    mroom = collections.Counter()                        # (who, room, 'n'|'s')
    first_sup = {}                                       # (s,b) -> {party: support share} at first vote
    import json
    SUBJ = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        ss, bb = k.split("|", 1); SUBJ[(ss, bb)] = v
    sp = collections.Counter()                           # (subject, voter party, patron party, 'n'|'s')
    msub = collections.Counter()                         # (who, subject, same, 'n'|'s')
    rows = []
    for date in sorted(events):
        todays = events[date]
        # 1) featurise today's FIRST votes from yesterday's state
        for s, b, i, ven, ballots in todays:
            if i != 0:
                continue
            bill = corpus.get((s, b))
            if not bill or bill["chief_party"] not in PARTIES or not bill["standing"]:
                continue
            R = first_room(bill) or "?"
            P = person(bill["chief"]) or bill["chief"]
            patrons = {P} | {person(c) or c for c in bill["cops"]}
            copc = collections.Counter(p for p in bill["cop_parties"] if p in PARTIES)
            # content, date-filtered: neighbours' roll calls strictly before today
            no_w = w = 0.0
            psup = {p: [0.0, 0.0] for p in PARTIES}
            msup = collections.defaultdict(lambda: [0.0, 0.0])
            for c, j in nb.get((s, b), []):
                for cd, _vo, _vid, _ven, cb in rc.get(c, []):
                    if not cd or cd >= date:
                        continue
                    opp = 1 - sum(x[2] for x in cb) / len(cb)
                    no_w += opp * j; w += j
                    for who, pp, sup in cb:
                        psup[pp][0] += sup * j; psup[pp][1] += j
                        msup[who][0] += sup * j; msup[who][1] += j
            c_opp = no_w / w if w else None
            # ROOM MEMORY: neighbours whose FIRST vote was in this same room, before today -> party support
            rm = {p: [0.0, 0.0] for p in PARTIES}
            for c, j in nb.get((s, b), []):
                cb = corpus.get(c)
                if not cb or (first_room(cb) or "?") != R:
                    continue
                lst = rc.get(c, [])
                if lst and lst[0][0] and lst[0][0] < date:
                    for who2, pp2, sup2 in lst[0][4]:
                        rm[pp2][0] += sup2 * j; rm[pp2][1] += j
            # the bill's OWN history strictly before today (structural action records)
            before = [(d_, t.lower()) for d_, t, _c in bill["actions"] if d_ and d_ < date]
            refd = [d_ for d_, t in before if t.startswith("referred to committee") or t.startswith("rereferred")]
            import datetime as _dt
            def _days(a, b_):
                try:
                    return (_dt.date.fromisoformat(b_[:10]) - _dt.date.fromisoformat(a[:10])).days
                except ValueError:
                    return 0
            jan = _dt.date(int(s[:4]), 1, 1); start = jan + _dt.timedelta(days=(2 - jan.weekday()) % 7 + 7)
            # DUPLICATES in the same session (knowable at filing): the consensus-kill signal. A near-copy carried
            # by a MAJORITY patron is the one that survives (incorporation contest, 83%) -- so this one is
            # tabled or folded in, by everyone, including its own patron's party.
            dup_sim = dup_maj_other = dup_same_pat = comp_sim = 0.0
            for c, j in nb.get((s, b), []):
                if c[0] != s:
                    continue
                cb = corpus.get(c)
                if not cb:
                    continue
                if cb["chamber"] == bill["chamber"]:
                    if j > dup_sim:
                        dup_sim = j
                        cp_ = person(cb["chief"]) or cb["chief"]
                        dup_same_pat = float(cp_ == P)
                        dup_maj_other = float(cb.get("standing") == "majority" and cp_ != P
                                              and bill["standing"] != "majority")
                else:
                    comp_sim = max(comp_sim, j)
            pre = {"dup_sim": dup_sim, "dup_maj_other": dup_maj_other, "dup_same_pat": dup_same_pat,
                   "comp_sim": comp_sim,
                   "n_actions": min(len(before), 40) / 40,
                   "fiscal": int(any("impact statement" in t for _d, t in before)),
                   "sub_offered": int(any("substitute" in t or " offered" in t for _d, t in before)),
                   "n_refs": min(len(refd), 4),
                   "wait": min(_days(refd[0], date), 60) / 60 if refd else 0.0,
                   "day": min(max((_dt.date.fromisoformat(date[:10]) - start).days, -60), 90) / 90,
                   "senior": min(int(s[:4]) - (bill.get("chief_first_year") or int(s[:4])), 30) / 30,
                   "n_cops": min(len(bill["cops"]), 40) / 40,
                   "pat_in_room": int(mroom[(P, R, "n")] > 0)}
            subs = SUBJ.get((s, b), [])
            def _sp(pp):
                n_ = sum(sp[(x, pp, bill["chief_party"], "n")] for x in subs)
                s_ = sum(sp[(x, pp, bill["chief_party"], "s")] for x in subs)
                return _rate(s_, n_, .75, 20), math.log1p(n_)
            for who, pp, sup in ballots:
                same = int(pp == bill["chief_party"])
                cp = psup[pp][0] / psup[pp][1] if psup[pp][1] else None
                sub_rate, sub_n = _sp(pp)
                mn = sum(msub[(who, x, same, "n")] for x in subs); ms_ = sum(msub[(who, x, same, "s")] for x in subs)
                ms = msup.get(who)
                dev = ((ms[0] + 3 * cp) / (ms[1] + 3) - cp) if (cp is not None and ms and ms[1]) else 0.0
                rows.append({
                    "yr": int(s[:4]), "y": int(sup), "same": same, "maj": int(bill["standing"] == "majority"),
                    "chamber_S": int(bill["chamber"] == "S"),
                    "ven_sub": int(ven == "sub"), "ven_com": int(ven == "com"),
                    "defect": _rate(defect[(who, "d")], defect[(who, "n")], .05, 20),
                    "room_rate": _rate(room[(R, same, "s")], room[(R, same, "n")], .85 if same else .55, 30),
                    "room_n": math.log1p(room[(R, same, "n")]),
                    "pat_rate": _rate(pat[(P, same, "s")], pat[(P, same, "n")], .85 if same else .55, 20),
                    "pat_n": math.log1p(pat[(P, same, "n")]),
                    "mroom_rate": _rate(mroom[(who, R, "s")], mroom[(who, R, "n")], .8, 10),
                    "mroom_n": math.log1p(mroom[(who, R, "n")]),
                    "has_c": int(c_opp is not None and cp is not None), "c_opp": c_opp or 0.0,
                    "c_party": cp if cp is not None else 0.5, "dev": dev, "has_mem": int(bool(ms and ms[1])),
                    "is_patron": int(who in patrons), "own_cops": min(copc.get(pp, 0), 10) / 10,
                    "other_cops": min(sum(v for k, v in copc.items() if k != pp), 10) / 10,
                    "companion": int(bool(bill.get("companion"))),
                    "rm_has": int(rm[pp][1] > 0),
                    "rm_party": rm[pp][0] / rm[pp][1] if rm[pp][1] else 0.5,
                    "rm_other": (rm[[q for q in PARTIES if q != pp][0]][0] / rm[[q for q in PARTIES if q != pp][0]][1])
                                if rm[[q for q in PARTIES if q != pp][0]][1] else 0.5,
                    **pre,
                    "subj_has": int(bool(subs)), "subj_party": sub_rate, "subj_n": sub_n,
                    "msubj": _rate(ms_, mn, sub_rate, 5), "msubj_n": math.log1p(mn),
                    "room": R, "who": who, "bill": (s, b), "party": pp,
                })
        # 2) then learn from EVERY roll call of the day
        for s, b, i, ven, ballots in todays:
            bill = corpus.get((s, b))
            maj = {}
            for p in PARTIES:
                xs = [x[2] for x in ballots if x[1] == p]
                if xs:
                    maj[p] = sum(xs) / len(xs) >= .5
            for who, pp, sup in ballots:
                if pp in maj:
                    defect[(who, "n")] += 1; defect[(who, "d")] += sup != maj[pp]
            if not bill or bill["chief_party"] not in PARTIES:
                continue
            R = first_room(bill) or "?"
            P = person(bill["chief"]) or bill["chief"]
            subs = SUBJ.get((s, b), [])
            for who, pp, sup in ballots:
                same = int(pp == bill["chief_party"])
                for x in subs:
                    sp[(x, pp, bill["chief_party"], "n")] += 1; sp[(x, pp, bill["chief_party"], "s")] += sup
                    msub[(who, x, same, "n")] += 1; msub[(who, x, same, "s")] += sup
                if ven in ("sub", "com"):
                    room[(R, same, "n")] += 1; room[(R, same, "s")] += sup
                    mroom[(who, R, "n")] += 1; mroom[(who, R, "s")] += sup
                if i == 0:
                    pat[(P, same, "n")] += 1; pat[(P, same, "s")] += sup
    return rows


NUM = ["same", "maj", "chamber_S", "ven_sub", "ven_com", "defect", "room_rate", "room_n", "pat_rate", "pat_n",
       "mroom_rate", "mroom_n", "has_c", "c_opp", "c_party", "dev", "has_mem", "is_patron", "own_cops",
       "other_cops", "companion", "rm_has", "rm_party", "rm_other", "n_actions", "fiscal", "sub_offered",
       "n_refs", "wait", "day", "senior", "n_cops", "pat_in_room", "dup_sim", "dup_maj_other", "dup_same_pat",
       "comp_sim", "txt_has", "txt_party", "txt_other", "subj_has", "subj_party", "subj_n", "msubj", "msubj_n"]
GROUPS = {
    "party & standing": ["same", "maj", "chamber_S"],
    "venue": ["ven_sub", "ven_com"],
    "general defection": ["defect"],
    "the committee's record": ["room_rate", "room_n"],
    "the patron's record": ["pat_rate", "pat_n"],
    "legislator in this committee": ["mroom_rate", "mroom_n"],
    "content (bill, party, legislator)": ["has_c", "c_opp", "c_party", "dev", "has_mem"],
    "co-patrons & companion": ["is_patron", "own_cops", "other_cops", "companion", "n_cops"],
    "room memory (similar bills, this room)": ["rm_has", "rm_party", "rm_other"],
    "the bill's own history before the vote": ["n_actions", "fiscal", "sub_offered", "n_refs", "wait", "day"],
    "patron seniority & seat on committee": ["senior", "pat_in_room"],
    "duplicates & companion match": ["dup_sim", "dup_maj_other", "dup_same_pat", "comp_sim"],
    "summary words (party-position classifier)": ["txt_has", "txt_party", "txt_other"],
    "subject (party and legislator)": ["subj_has", "subj_party", "subj_n", "msubj", "msubj_n"],
}


def _auc(p, y):
    idx = np.argsort(p, kind="mergesort"); r = np.empty(len(p)); i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and p[idx[j + 1]] == p[idx[i]]:
            j += 1
        r[idx[i:j + 1]] = (i + j) / 2 + 1; i = j + 1
    n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else float("nan")


def scorecard(p, rows, label):
    y = np.array([r["y"] for r in rows]); yhat = p >= .5
    def s(m):
        yy, pp, hh = y[m], p[m], yhat[m]
        bal = .5 * (hh[yy == 1].mean() + (~hh[yy == 0]).mean())
        return f"acc {(hh == yy).mean():5.1%} (base {max(yy.mean(), 1 - yy.mean()):5.1%}) bal {bal:5.1%} rank {_auc(pp, yy):.3f}"
    same = np.array([bool(r["same"]) for r in rows])
    # party-position score: per roll call x party, does the predicted party majority match the real one?
    grp = collections.defaultdict(list)
    for i, r in enumerate(rows):
        grp[(r["bill"], r["same"])].append(i)
    hits = [((p[ix].mean() >= .5) == (y[ix].mean() >= .5)) for ix in grp.values()]
    print(f"  {label:34s} ALL {s(np.ones(len(y), bool))}")
    print(f"  {'':34s} OTHER-party {s(~same)}")
    print(f"  {'':34s} same-party  {s(same)}   | party-position right {np.mean(hits):5.1%} of {len(hits)}")


def fit_predict(kind, cols, tr, va, te=None, **kw):
    X = lambda rs: np.array([[r[c] for c in cols] for r in rs], float)
    ytr = np.array([r["y"] for r in tr]); yva = np.array([r["y"] for r in va])
    if kind == "logit":
        import stats
        f = stats.logit(X(tr), ytr, cols, ridge=1e-3)
        b = np.array([f[k][0] for k in ["const"] + cols])
        def pr(rs):
            with np.errstate(all="ignore"):          # the known Accelerate false flag; stats.py explains
                return 1 / (1 + np.exp(-(np.column_stack([np.ones(len(rs)), X(rs)]) @ b)))
        return pr(va), (pr(te) if te else None), None
    import gbm
    m = gbm.GBM(**kw).fit(X(tr), ytr, X(va), yva)
    return m.predict(X(va)), (m.predict(X(te)) if te else None), m


def add_text(rows):
    """Attach the summary-word party scores (text_party.py) -- leakage-safe by construction there."""
    import text_party as TP
    sc, _lab, _docs = TP.scores()
    other = {PARTIES[0]: PARTIES[1], PARTIES[1]: PARTIES[0]}
    for r in rows:
        s, b = r["bill"]
        mine = r.get("party")
        a = sc.get((s, b, mine)); o = sc.get((s, b, other.get(mine, "")))
        r["txt_has"] = int(a is not None)
        r["txt_party"] = a if a is not None else 0.5
        r["txt_other"] = o if o is not None else 0.5
    return rows


def tune():
    rows = pickle.load(open(ROWS, "rb")) if os.path.exists(ROWS) else features()
    tr = [r for r in rows if r["yr"] in (2020, 2021, 2022, 2024)]
    va = [r for r in rows if r["yr"] == 2025]
    print(f"train {len(tr)} ballots, tune (2025) {len(va)}   -- 2026 NOT loaded into any model\n")
    base_cols = GROUPS["party & standing"] + GROUPS["venue"]
    p, _, _ = fit_predict("logit", base_cols, tr, va); scorecard(p, va, "logit: party+standing+venue")
    p, _, _ = fit_predict("logit", NUM, tr, va); scorecard(p, va, "logit: everything")
    p, _, m = fit_predict("gbm", NUM, tr, va); scorecard(p, va, f"GBM: everything ({len(m.trees)} trees)")
    imp = m.importance(len(NUM)); order = np.argsort(-imp)
    print("  GBM split share: " + ", ".join(f"{NUM[i]} {imp[i]/imp.sum():.0%}" for i in order[:10]))
    return rows


ROWS = "/private/tmp/claude-501/-Users-tuckerward-Documents-Projects-bill-tracker/d2c029e9-acd9-410e-81ec-5347fd755620/scratchpad/fv_rows.pkl"


BILL_COLS = [c for c in NUM if c not in ("defect", "mroom_rate", "mroom_n", "dev", "has_mem", "is_patron")]


def two_stage(tr, va, te=None, **kw):
    """Stage 1: one row per (bill, party) -> P(that party's majority backs the bill). Bill-level features only,
    averaged over the party's ballots (they are identical per party except member columns, which are dropped).
    Stage 2: per ballot, the stage-1 score + the member's own columns -> P(this legislator backs it)."""
    import gbm
    def party_rows(rows):
        g = collections.defaultdict(list)
        for r in rows:
            g[(r["bill"], r["party"])].append(r)
        keys = list(g)
        X = np.array([[g[k][0][c] for c in BILL_COLS] for k in keys], float)
        y = np.array([np.mean([r["y"] for r in g[k]]) >= .5 for k in keys], float)
        w = np.array([len(g[k]) for k in keys], float)
        return keys, X, y, w
    ktr, Xtr, ytr, _ = party_rows(tr); kva, Xva, yva, _ = party_rows(va)
    m1 = gbm.GBM(**kw).fit(Xtr, ytr, Xva, yva)
    def attach(rows, keys, m):
        sc = dict(zip(keys, m.predict(np.array([[next(r for r in rows if (r["bill"], r["party"]) == k)[c]
                                                 for c in BILL_COLS] for k in keys], float)))) if False else None
        return sc
    s_tr = dict(zip(ktr, m1.predict(Xtr))); s_va = dict(zip(kva, m1.predict(Xva)))
    mem = ["same", "defect", "mroom_rate", "mroom_n", "dev", "has_mem", "is_patron", "ven_sub", "ven_com"]
    X2 = lambda rows, sc: np.array([[sc[(r["bill"], r["party"])]] + [r[c] for c in mem] for r in rows], float)
    y2tr = np.array([r["y"] for r in tr], float); y2va = np.array([r["y"] for r in va], float)
    m2 = gbm.GBM(depth=3, **{k: v for k, v in kw.items() if k != "depth"}).fit(X2(tr, s_tr), y2tr, X2(va, s_va), y2va)
    pva = m2.predict(X2(va, s_va))
    pte = None
    if te:
        kte, Xte, _yte, _ = party_rows(te); s_te = dict(zip(kte, m1.predict(Xte)))
        pte = m2.predict(X2(te, s_te))
    return pva, pte, (m1, m2)


def tune2():
    rows = pickle.load(open(ROWS, "rb"))
    tr = [r for r in rows if r["yr"] in (2020, 2021, 2022, 2024)]
    va = [r for r in rows if r["yr"] == 2025]
    for kw in ({"depth": 6, "lr": .03},):
        p, _, m = fit_predict("gbm", NUM, tr, va, **kw)
        scorecard(p, va, f"ONE-STAGE GBM {kw} ({len(m.trees)})")


def add_fulltext(rows):
    import text_features as TF
    cache = {}
    for r in rows:
        k = r["bill"]
        if k not in cache:
            cache[k] = TF.features(k[0], k[1]) if k[0] in ("2025", "2026") else None
        r.update(cache[k] or TF.EMPTY)
    return rows


def text_layer_tune(base_kw=None):
    """Full text exists only for 2025-26, so its effects can only be LEARNED from 2025.
       base  : GBM on 2020-24 (no text)  -> a live-like score for every 2025 ballot
       layer : GBM on [base score + text + key features], trained on 2025 first votes BEFORE the 2025
               median date, validated on those AFTER it. 2026 is still untouched."""
    import gbm, text_features as TF
    base_kw = base_kw or {}
    rows = add_fulltext(pickle.load(open(ROWS, "rb")))
    tr = [r for r in rows if r["yr"] in (2020, 2021, 2022, 2024)]
    y25 = [r for r in rows if r["yr"] == 2025]
    X = lambda rs, cols: np.array([[r[c] for c in cols] for r in rs], float)
    base = gbm.GBM(**base_kw).fit(X(tr, NUM), np.array([r["y"] for r in tr], float),
                                  X(y25, NUM), np.array([r["y"] for r in y25], float))
    for r, p in zip(y25, base.predict(X(y25, NUM))):
        r["base"] = float(p)
    dates = {}
    D = assemble()
    for r in y25:
        dates[r["bill"]] = D["rc"][r["bill"]][0][0]
    med = sorted(dates.values())[len(dates) // 2]
    early = [r for r in y25 if dates[r["bill"]] < med]; late = [r for r in y25 if dates[r["bill"]] >= med]
    print(f"2025 split at {med}: early {len(early)} ballots (text coverage "
          f"{np.mean([r['tx_has'] for r in early]):.0%}), late {len(late)} ({np.mean([r['tx_has'] for r in late]):.0%})")
    cols_no = ["base", "same", "party_D"]
    cols_tx = cols_no + TF.TX_COLS
    for r in y25:
        r["party_D"] = int(r["party"] == PARTIES[0])
    ye = np.array([r["y"] for r in early], float); yl = np.array([r["y"] for r in late], float)
    scorecard(np.array([r["base"] for r in late]), late, "base model alone (late 2025)")
    for name, cols in (("layer WITHOUT text", cols_no), ("layer WITH full text", cols_tx)):
        m = gbm.GBM(depth=3, lr=.05).fit(X(early, cols), ye, X(late, cols), yl)
        scorecard(m.predict(X(late, cols)), late, f"{name} ({len(m.trees)} trees)")
