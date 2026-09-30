#!/usr/bin/env python3
"""The bill's FATE at its first committee -- the quantity the first-vote model never sees.

Five-perspective panel, 2026-09-29 ([[testing/panel_2026-09-29]]): most bills that die never produce a named roll
call, so a model of first-vote ballots is fitted on a censored sample. This names every outcome a bill can have in
its ORIGIN chamber's committee stage (the first decisive action, subcommittee recommendations included) and models
them as competing outcomes, scored at the bill level.

    ADVANCED         reported / recommended for reporting / re-referred onward
    KILLED_RECORDED  tabled, passed by indefinitely, failed to report, defeated -- with a Y-N count
    KILLED_VOICE     the same verbs by voice vote or with no count
    CONTINUED        continued to next year (special-session continuances are EXCLUDED: that bill's fate is in
                     another session record, days later)
    WITHDRAWN        stricken from the docket / at the patron's request
    MERGED           incorporated into another bill (its text survives elsewhere)
    NEVER            no decisive action: "Left in <committee>" or nothing at all

Internal research only (Standard #3): the labels read LIS action descriptions, which are a fixed clerk vocabulary;
coverage is asserted per year and anything unclassified is counted, never dropped silently.
Committee-stage actions are absent before 2020 (bill_states.FIRST_GOOD_YEAR) -- years start there.
Carried-over records (first action before September of the prior year) are excluded: their fate belongs to the
session that filed them.

Run:  python3 tools/calibration/fate.py            diagnostics + roll rates + model (choose 2024, score 2025 once)
"""
from __future__ import annotations
import sys, os, re, json, collections, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
from corpus import load, _party_lookup
from bill_states import FIRST_GOOD_YEAR

YEARS = (2020, 2021, 2022, 2023, 2024, 2025)          # 2026 stays locked
CLASSES = ["ADVANCED", "KILLED_RECORDED", "KILLED_VOICE", "CONTINUED", "WITHDRAWN", "MERGED", "NEVER"]
COUNT = re.compile(r"\(\s*\d+-Y\s+\d+-N", re.I)
VOICE = re.compile(r"voice vote", re.I)
SPSESS = re.compile(r"sp\.?\s*sess", re.I)
FLOOR = re.compile(r"^(read (second|third) time|passed (house|senate)|vote: passage|engrossed)", re.I)
RULES = [   # (class, pattern) -- first match wins within one action
    ("MERGED", re.compile(r"^incorporated by\b|^subcommittee recommends incorporating", re.I)),
    ("WITHDRAWN", re.compile(r"^stricken\b|stricken from (the )?docket|stricken at (the )?request", re.I)),
    ("CONTINUED", re.compile(r"^continued to (\d{4}|next session)|^subcommittee recommends continuing", re.I)),
    ("KILL", re.compile(r"laying on the table|^tabled in\b|passed by indefinitely|^failed to report|"
                        r"failed to recommend|^defeated by\b", re.I)),
    ("ADVANCED", re.compile(r"^reported from\b|^subcommittee recommends reporting|^rereferred to\b|"
                            r"^subcommittee recommends referring|^referred from\b", re.I)),
]
LEFT = re.compile(r"^left in\b", re.I)
REF = re.compile(r"^referred to committee (?:on|for) (.+?)\.?$", re.I)


def classify(bill):
    """(class, first committee) for one bill record, or (None, reason) if it is out of scope."""
    acts = bill["actions"]
    if not acts:
        return "NEVER", None
    comm = None
    for _d, t, _c in acts:
        t = t.strip()
        m = REF.match(t)
        if m and comm is None:
            comm = m.group(1).strip()
        if FLOOR.match(t):                      # left committee without a recorded committee decision
            return "ADVANCED", comm
        for cls, pat in RULES:
            if pat.search(t):
                if cls == "CONTINUED" and SPSESS.search(t):
                    return None, "special-session continuance"
                if cls == "KILL":
                    cls = "KILLED_RECORDED" if COUNT.search(t) and not VOICE.search(t) else "KILLED_VOICE"
                return cls, comm
        if LEFT.match(t):
            return "NEVER", comm
    return "NEVER", comm


def bills(years=YEARS):
    """One row per in-scope HB/SB record, with its fate. Counts every exclusion by reason (no silent drop)."""
    out, skipped = [], collections.Counter()
    for b in load()["bills"]:
        if not b["session"].isdigit() or int(b["session"]) not in years:
            continue
        if not re.match(r"^[HS]B \d+$", b["bill"]):
            continue
        y = int(b["session"])
        if y < FIRST_GOOD_YEAR:
            raise SystemExit(f"committee-stage actions are absent before {FIRST_GOOD_YEAR}")
        if b["actions"] and b["actions"][0][0] < f"{y - 1}-09-01":
            skipped["carried over from an earlier session"] += 1
            continue
        cls, comm = classify(b)
        if cls is None:
            skipped[comm] += 1
            continue
        out.append({**b, "fate": cls, "comm": comm})
    return out, skipped


def diagnostics(rows, skipped):
    print("excluded:", dict(skipped))
    print("\nFATE AT FIRST COMMITTEE, share of bills (n)")
    print(f"{'year':6s} {'standing':9s} " + " ".join(f"{c[:9]:>9s}" for c in CLASSES) + "      n")
    for y in YEARS:
        for st in ("majority", "minority"):
            rs = [r for r in rows if r["year"] == y and r["standing"] == st]
            if not rs:
                continue
            c = collections.Counter(r["fate"] for r in rs)
            print(f"{y:<6d} {st:9s} " + " ".join(f"{c[k] / len(rs):9.1%}" for k in CLASSES) + f" {len(rs):6d}")
    rs = [r for r in rows if r["standing"] in ("majority", "minority")]
    for st in ("majority", "minority"):
        s = [r for r in rs if r["standing"] == st]
        rec = sum(r["fate"] in ("ADVANCED", "KILLED_RECORDED") for r in s) / len(s)
        print(f"all years {st}: {len(s)} bills; reach a recorded decision (advanced or recorded kill) {rec:.1%}; "
              f"die without a recorded vote {sum(r['fate'] in ('KILLED_VOICE', 'CONTINUED', 'NEVER') for r in s) / len(s):.1%}")


def roll_rates():
    """Cox & McCubbins roll rate: a roll call where a MAJORITY OF THE MAJORITY PARTY is on the losing side.
    Low majority roll rates with high minority roll rates = the majority keeps bills it opposes off the recorded
    agenda (agenda control), i.e. the recorded sample is filtered. Majority party of a room = the party with more
    ballots in that roll call (committee seats follow the chamber majority)."""
    import content_votes as CVT
    d = CVT.build()
    rc = collections.defaultdict(list)
    for s, b, vid, date, ven, ballots in d["rolls"]:
        rc[(s, b)].append((date or "9999", {"sub": 0, "com": 1, "floor": 2}[ven], ven, ballots))
    tab = collections.Counter()
    for (s, b), lst in rc.items():
        if not s.isdigit() or int(s) not in YEARS:
            continue
        lst.sort()
        for i, (_d, _o, ven, ballots) in enumerate(lst):
            parties = collections.Counter(p for _w, p, _s in ballots)
            if len(parties) < 2:
                continue
            (maj, nm), (mino, nn) = parties.most_common(2)
            if nm == nn:
                continue
            won = sum(x[2] for x in ballots) > len(ballots) / 2
            def rolled(pt):
                sh = [x[2] for x in ballots if x[1] == pt]
                return (sum(sh) > len(sh) / 2) != won if sh else False
            for tag in ("all", "first" if i == 0 else None):
                if tag:
                    k = (tag, ven)
                    tab[k + ("n",)] += 1; tab[k + ("maj",)] += rolled(maj); tab[k + ("min",)] += rolled(mino)
    print("\nROLL RATES (share of roll calls where a party's majority was on the losing side), 2020-2025")
    for tag in ("first", "all"):
        for ven in ("sub", "com", "floor"):
            n = tab[(tag, ven, "n")]
            if n:
                print(f"  {tag:5s} votes, {ven:5s}: n {n:6d}  majority rolled {tab[(tag, ven, 'maj')] / n:5.1%}  "
                      f"minority rolled {tab[(tag, ven, 'min')] / n:5.1%}")


# ------------------------------------------------------------------------------------------------------
# THE MODEL. Everything is knowable at filing (or by the filing deadline, before committees meet):
# earlier sessions only for any rate, this session only for what is on the filed bill.
# KILLED_VOICE is merged into KILLED: measured ~0 bills in every year (Virginia committees record kill counts).
# ------------------------------------------------------------------------------------------------------
MCLASSES = ["ADVANCED", "KILLED", "CONTINUED", "WITHDRAWN", "MERGED", "NEVER"]
MONEY = re.compile(r"appropriations|finance", re.I)
# Governor's party by session year -- a documented research constant (not on any product path).
GOV = {2020: "Democratic", 2021: "Democratic", 2022: "Republican", 2023: "Republican", 2024: "Republican",
       2025: "Republican", 2026: "Democratic"}


def _m(r):
    return "KILLED" if r["fate"].startswith("KILLED") else r["fate"]


def featurise(rows):
    party, person = _party_lookup()
    subj = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        ss, bb = k.split("|", 1); subj[(ss, bb)] = v
    import first_vote as FV
    nb = FV.assemble()["nb"]
    fate_of = {(r["session"], r["bill"]): _m(r) for r in rows}
    by_key = {(r["session"], r["bill"]): r for r in rows}
    pat = collections.defaultdict(collections.Counter)       # (patron, year) -> class counts
    com = collections.defaultdict(collections.Counter)       # (committee, standing, year)
    sub = collections.defaultdict(collections.Counter)       # (subject, standing, year)
    filed = collections.Counter()
    for r in rows:
        P = person(r["chief"]) or r["chief"]; y = r["year"]; c = _m(r)
        pat[(P, y)][c] += 1; com[(r["comm"], r["standing"], y)][c] += 1; filed[(P, y)] += 1
        for t in subj.get((r["session"], r["bill"]), []):
            sub[(t, r["standing"], y)][c] += 1
    # smoothing prior per target year from EARLIER years only (the first version used every year, so the scored
    # year's own class mix leaked into its features through the prior)
    by_year = collections.defaultdict(collections.Counter)
    for r in rows:
        by_year[r["year"]][_m(r)] += 1
    priors = {}
    for y0 in sorted(by_year):
        agg = collections.Counter()
        for yy in by_year:
            if yy < y0:
                agg.update(by_year[yy])
        tot = sum(agg.values())
        priors[y0] = {c: (agg[c] + 1) / (tot + len(MCLASSES)) for c in MCLASSES}
    def hist(table, key_fn, y, a=5.0):
        prior = priors[y]
        agg = collections.Counter()
        for yy in range(2020, y):
            agg.update(table.get(key_fn(yy), {}))
        n = sum(agg.values())
        return [(agg[c] + a * prior[c]) / (n + a) for c in MCLASSES], n
    out = []
    for r in rows:
        y = r["year"]; P = person(r["chief"]) or r["chief"]; prior = priors[y]
        f = {"maj": int(r["standing"] == "majority"), "chamber_S": int(r["bill"].startswith("SB")),
             "long_session": int(y % 2 == 0), "gov_same": int(r["chief_party"] == GOV.get(y)),
             "n_cops": math.log1p(len(r["cops"]))}
        cp = [p for p in r["cop_parties"] if p]
        f["own_cops"] = math.log1p(sum(p == r["chief_party"] for p in cp))
        f["other_cops"] = math.log1p(sum(p != r["chief_party"] for p in cp))
        f["bipartisan"] = int(any(p != r["chief_party"] for p in cp))
        comp = by_key.get((r["session"], r["companion"])) if r.get("companion") else None
        f["companion"] = int(bool(r.get("companion")))
        f["companion_other_party"] = int(bool(comp) and comp["chief_party"] != r["chief_party"])
        f["money"] = int(bool(MONEY.search(r["comm"] or "")))
        f["tenure"] = float(y - (r.get("chief_first_year") or y))
        f["n_filed_now"] = math.log1p(filed[(P, y)])
        d0 = r["actions"][0][0] if r["actions"] else f"{y}-01-15"
        f["prefiled"] = int(d0 < f"{y}-01-01")
        ph, pn = hist(pat, lambda yy: (P, yy), y)
        ch, cn = hist(com, lambda yy: (r["comm"], r["standing"], yy), y)
        f.update({f"pat_{c}": v for c, v in zip(MCLASSES, ph)}); f["pat_n"] = math.log1p(pn)
        f.update({f"com_{c}": v for c, v in zip(MCLASSES, ch)}); f["com_n"] = math.log1p(cn)
        ts = subj.get((r["session"], r["bill"]), [])
        if ts:
            sh = [hist(sub, lambda yy, t=t: (t, r["standing"], yy), y)[0] for t in ts]
            f.update({f"sub_{c}": float(np.mean([h[i] for h in sh])) for i, c in enumerate(MCLASSES)})
        else:
            f.update({f"sub_{c}": prior[c] for c in MCLASSES})
        f["sub_has"] = int(bool(ts))
        earlier = [(c, j) for c, j in nb.get((r["session"], r["bill"]), []) if c[0].isdigit() and int(c[0]) < y
                   and c in fate_of]
        f["nb_has"] = int(bool(earlier))
        f["nb_max"] = max((j for _c, j in earlier), default=0.0)
        w = sum(j for _c, j in earlier)
        f["nb_adv"] = (sum(j * (fate_of[c] == "ADVANCED") for c, j in earlier) / w) if w else prior["ADVANCED"]
        top = max(earlier, key=lambda x: x[1]) if earlier else None
        f["nb_top_adv"] = float(fate_of[top[0]] == "ADVANCED") if top else prior["ADVANCED"]
        f["nb_same_patron"] = int(bool(top) and (person(by_key[top[0]]["chief"]) or by_key[top[0]]["chief"]) == P)
        out.append(f)
    return out


def _mll(P, Y):
    return -np.log(np.clip(P[np.arange(len(Y)), Y], 1e-9, 1))


# Chosen on 2024 alone (trained 2020-2023), then applied unchanged: depth 3 / 100 rounds / lr .05, averaged 50:50
# with the baseline (2024 log loss: baseline 1.1568, depth-4 model 1.2010, chosen blend 1.1326).
BLEND = 0.5


def fit_predict(Xtr, ytr, Xte, rounds=100, depth=3, lr=.05):
    """One-vs-rest boosted trees, renormalised to sum to 1."""
    import gbm
    cols = []
    for k in range(len(MCLASSES)):
        yk = (ytr == k).astype(float)
        if yk.sum() == 0:
            cols.append(np.zeros(len(Xte))); continue
        cols.append(gbm.GBM(depth=depth, lr=lr, rounds=rounds).fit(Xtr, yk).predict(Xte))
    P = np.clip(np.column_stack(cols), 1e-6, None)
    return P / P.sum(1, keepdims=True)


def baseline(rtr, rte):
    """Class rates by patron standing x chamber x session length, from the training years (Laplace)."""
    cell = lambda r: (r["standing"], r["bill"][:2], r["year"] % 2)
    cnt = collections.defaultdict(collections.Counter)
    for r in rtr:
        cnt[cell(r)][_m(r)] += 1
    P = np.array([[(cnt[cell(r)][c] + 1) / (sum(cnt[cell(r)].values()) + len(MCLASSES)) for c in MCLASSES]
                  for r in rte])
    return P


def evaluate(P, Y, label):
    ll = _mll(P, Y); acc = (P.argmax(1) == Y).mean()
    import first_vote as FV
    adv = Y == 0; pa = P[:, 0]
    dies = np.isin(Y, [MCLASSES.index(c) for c in ("CONTINUED", "NEVER")]); pd_ = P[:, [2, 5]].sum(1)
    print(f"  {label:34s} log loss {ll.mean():.4f}  top-class right {acc:.1%}  "
          f"advance AUC {FV._auc(pa, adv.astype(int)):.3f}  quiet-death AUC {FV._auc(pd_, dies.astype(int)):.3f}")
    return ll


def model():
    R, _S = bills()
    R = [r for r in R if r["standing"] in ("majority", "minority")]
    F = featurise(R)
    cols = sorted(F[0])
    X = np.array([[f[c] for c in cols] for f in F], float)
    Y = np.array([MCLASSES.index(_m(r)) for r in R])
    yr = np.array([r["year"] for r in R])
    print(f"\nFATE MODEL -- {len(R)} bills, {len(cols)} inputs, classes {MCLASSES}")
    pooled = []
    for t in (2022, 2023, 2024, 2025):
        tr = yr < t; te = yr == t
        print(f"year {t} (train {sorted(set(yr[tr]))}, n={te.sum()})")
        Bp = baseline([r for r, m in zip(R, tr) if m], [r for r, m in zip(R, te) if m])
        b = evaluate(Bp, Y[te], "baseline: standing x chamber x length")
        m = evaluate(BLEND * fit_predict(X[tr], Y[tr], X[te]) + (1 - BLEND) * Bp, Y[te], "fate model (blend)")
        pooled.append(b - m)
    d = np.concatenate(pooled)
    z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    print(f"pooled rolling-origin (2022-2025), paired per-bill log-loss gain {d.mean():+.4f}, z = {z:.1f} "
          f"({'ACCEPT' if z >= 3 else 'reject'} at z >= 3)")
    return R, F, cols, X, Y, yr


# ------------------------------------------------------------------------------------------------------
# THE LOCKED 2026 TEST for the fate model -- same discipline as prereg_2026.py: freeze, commit, then score once.
# ------------------------------------------------------------------------------------------------------
import hashlib, datetime
SPEC = os.path.join(HERE, "frozen", "prereg_fate_2026.json")
SCORE = os.path.join(HERE, "frozen", "score_fate_2026.json")


def freeze():
    if os.path.exists(SPEC):
        raise SystemExit(f"already frozen: {SPEC}")
    spec = {"frozen_on": datetime.date.today().isoformat(),
            "target": "fate at the first committee in the origin chamber, 6 classes " + ",".join(MCLASSES),
            "train_years": list(YEARS), "test_year": 2026,
            "model": {"one_vs_rest_gbm": {"depth": 3, "rounds": 100, "lr": 0.05}, "blend_with_baseline": BLEND},
            "baseline": "class rates by patron standing x chamber x session length (training years, Laplace)",
            "code_sha256": {"fate.py": hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
                            "gbm.py": hashlib.sha256(open(os.path.join(HERE, "gbm.py"), "rb").read()).hexdigest()},
            "metrics": ["multiclass log loss (model, baseline, paired gain + bootstrap 95%)",
                        "top-class accuracy", "AUC of P(ADVANCED)", "AUC of P(CONTINUED or NEVER)",
                        "P(ADVANCED) calibration in bands <20 / 20-40 / 40-60 / 60-80 / 80+ : share that advanced"],
            "intervals": {"method": "bootstrap over bills", "B": 2000, "seed": 2026},
            "expected_from_validation_2025": {"log_loss_model": 0.9621, "log_loss_baseline": 1.0064,
                                              "advance_auc": 0.809, "quiet_death_auc": 0.801},
            "note": "2026 is an even (long) session: continuances happen again (0% in 2021/2023/2025)"}
    blob = json.dumps(spec, indent=1, sort_keys=True).encode()
    open(SPEC, "wb").write(blob)
    print(f"froze {SPEC}\nsha256 {hashlib.sha256(blob).hexdigest()}")


def score():
    import first_vote as FV
    if os.path.exists(SCORE):
        raise SystemExit(f"already scored: {SCORE}")
    spec_blob = open(SPEC, "rb").read(); spec = json.loads(spec_blob)
    for f, h in spec["code_sha256"].items():
        if hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest() != h:
            raise SystemExit(f"{f} changed since pre-registration -- refusing to score")
    R, _S = bills(tuple(spec["train_years"]) + (spec["test_year"],))
    R = [r for r in R if r["standing"] in ("majority", "minority")]
    F = featurise(R); cols = sorted(F[0])
    X = np.array([[f[c] for c in cols] for f in F], float)
    Y = np.array([MCLASSES.index(_m(r)) for r in R]); yr = np.array([r["year"] for r in R])
    tr, te = yr < spec["test_year"], yr == spec["test_year"]
    Bp = baseline([r for r, m in zip(R, tr) if m], [r for r, m in zip(R, te) if m])
    P = BLEND * fit_predict(X[tr], Y[tr], X[te]) + (1 - BLEND) * Bp
    y = Y[te]; lm, lb = _mll(P, y), _mll(Bp, y)
    adv = (y == 0).astype(int); dies = np.isin(y, [2, 5]).astype(int)
    rng = np.random.default_rng(spec["intervals"]["seed"]); n = len(y); gains = []
    for _ in range(spec["intervals"]["B"]):
        i = rng.integers(0, n, n); gains.append(float((lb[i] - lm[i]).mean()))
    bands = {}
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)):
        m = (P[:, 0] >= lo) & (P[:, 0] < hi)
        bands[f"{int(lo*100)}-{int(min(hi,1)*100)}"] = {"bills": int(m.sum()),
                                                        "advanced": float(adv[m].mean()) if m.any() else None}
    doc = {"scored_on": datetime.date.today().isoformat(), "spec_sha256": hashlib.sha256(spec_blob).hexdigest(),
           "n_bills": int(n), "class_shares": {c: float((y == k).mean()) for k, c in enumerate(MCLASSES)},
           "log_loss_model": float(lm.mean()), "log_loss_baseline": float(lb.mean()),
           "gain": float((lb - lm).mean()), "gain_ci95": [float(np.percentile(gains, 2.5)),
                                                           float(np.percentile(gains, 97.5))],
           "top_class_accuracy": float((P.argmax(1) == y).mean()),
           "baseline_top_class_accuracy": float((Bp.argmax(1) == y).mean()),
           "advance_auc": float(FV._auc(P[:, 0], adv)), "baseline_advance_auc": float(FV._auc(Bp[:, 0], adv)),
           "quiet_death_auc": float(FV._auc(P[:, [2, 5]].sum(1), dies)),
           "advance_calibration": bands}
    open(SCORE, "w").write(json.dumps(doc, indent=1, sort_keys=True))
    print(json.dumps(doc, indent=1, sort_keys=True))


if __name__ == "__main__":
    if "--freeze" in sys.argv:
        freeze()
    elif "--score" in sys.argv:
        score()
    else:
        R, S = bills()
        diagnostics(R, S)
        roll_rates()
        model()
