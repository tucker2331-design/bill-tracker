#!/usr/bin/env python3
"""AI test on the HARD THIRD only, member-centric (owner 2026-10-25: "exclusively targeting the last 1/3 ... if we get
the criteria to a sufficient level llms should be able to predict outcomes with an accuracy over 80% in that final
1/3"; "idk that its abt the lobbyist as much as the rep since we are predicting the reps vote").
INTERNAL ONLY until the owner's Standard #3 call.

Scope: the 150 + 150 pilot bills of 2025 / 2026 (.cache/llm_pilot_ids_{yr}.json, the same bills the bill-level rating
test used, so the two tests compare directly), minus the four bills the model said it recognized. Only votes arm C
cannot call (|p - .5| < .31) are asked; every other member is context.

One blinded packet per bill (.cache/llm_member/{yr}/Bxxx.txt), all facts public BEFORE the vote date:
  - the bill: title + introduced summary, blinded (no numbers, names, years, dates, committee names)
  - the room: size by party, patron's party, whether the patron sits in the room, co-patron counts by party,
    how many members of each party the model already calls yes / no (it does not show the asked member's chance)
  - one card per asked member, anonymous (M1, M2 ...): party, same party as patron, co-patron or not, years served,
    district make-up, own record (yes rate on this patron's bills, on this subject, in this room, how often the
    member votes against own party), and the member's OWN first votes on the 6 most similar earlier bills
    (TF-IDF on blinded summaries, strictly earlier date) with how the member's party voted on each.
Scoring (llm_member.py score): accuracy on the asked votes, AI alone and AI + arm C (equal log-odds average, no
fitting), and calls at 81 / 19 with wrong calls. Year-ahead weight: fit on 2025, test on 2026.
Run: python3 llm_member.py build [n_bills_per_year]  |  python3 llm_member.py score
"""
from __future__ import annotations
import sys, os, re, json, math, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np

OUT = os.path.join(HERE, ".cache", "llm_member")
RECOGNIZED = {"B176", "B282", "B283", "B391"}
SPLIT = {"2025": "confirm", "2026": "repeat"}
WORD = re.compile(r"[a-z]{3,}")
STOP = set("the and for that this with shall any such from which its are not who under than other may been have has "
           "into upon also each bill provides".split())


def blind(text):
    from llm_pilot import blind as b
    return b(text)


def _tfidf(docs):
    df = collections.Counter(w for d in docs.values() for w in set(d))
    n = len(docs); vec = {}
    for k, d in docs.items():
        tf = collections.Counter(d); v = {w: (1 + math.log(c)) * math.log(n / df[w]) for w, c in tf.items() if df[w] > 1}
        z = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vec[k] = {w: x / z for w, x in v.items()}
    return vec


def _cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def _pct(x):
    return f"{100 * x:.0f}%"


def build(n_bills=None):
    import levers as L, gains as G, first_vote as FV, summary_memory as SM
    from corpus import load
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    summ = SM.summaries(); rc = FV.assemble()["rc"]
    date = {k: v[0][0] for k, v in rc.items() if v and v[0][0] != "9999"}
    text = {k: blind(corpus[k]["title"] + ". " + summ[k]) for k in summ if k in corpus}
    vec = _tfidf({k: [w for w in WORD.findall(t.lower()) if w not in STOP] for k, t in text.items()})
    R = [r for r in L.rows() if r["yr"] >= 2019 and r["bill"] in date]
    by_bill = collections.defaultdict(list); by_who = collections.defaultdict(list)
    for r in R:
        by_bill[r["bill"]].append(r); by_who[r["who"]].append(r)
    first_year = {w: min(r["yr"] for r in rs) for w, rs in by_who.items()}
    block = {}                                                     # (bill, party) -> yes share of that party
    for k, rs in by_bill.items():
        for p in ("Democratic", "Republican"):
            ys = [r["y"] for r in rs if r["party"] == p]
            block[(k, p)] = (sum(ys) / len(ys), len(ys)) if ys else (None, 0)
    manifest = {}; skipped = collections.Counter()
    for yr, split in SPLIT.items():
        ids = json.load(open(os.path.join(HERE, ".cache", f"llm_pilot_ids_{yr}.json")))
        te, _p0, _pA = G.load(split)
        pC = np.load(os.path.join(L.PRED, f"session_booster_{split}_r30_d2_lr0.05_gated.npy"))
        idx = collections.defaultdict(list)
        for i, r in enumerate(te):
            idx[r["bill"]].append(i)
        codes = sorted(c for c in ids if c not in RECOGNIZED)
        if n_bills:
            codes = sorted(random.Random(int(yr)).sample(codes, min(n_bills, len(codes))))
        os.makedirs(os.path.join(OUT, yr), exist_ok=True)
        for code in codes:
            k = tuple(ids[code]); I = idx.get(k, [])
            ask = [i for i in I if abs(pC[i] - .5) < .31 and te[i]["party"] in ("Democratic", "Republican")]
            if not ask or k not in text:
                skipped["no can't-call vote" if not ask else "no summary"] += 1   # counted and printed below
                continue
            b = corpus[k]; d0 = date[k]; v0 = vec.get(k, {})
            cops = collections.Counter(b.get("cop_parties") or [])
            called = collections.Counter((te[i]["party"], "yes" if pC[i] >= .5 else "no") for i in I if abs(pC[i] - .5) >= .31)
            party_n = collections.Counter(te[i]["party"] for i in I)
            room = te[I[0]]["room"]; ven = "subcommittee" if te[I[0]]["ven_sub"] else ("committee" if te[I[0]]["ven_com"] else "floor")
            lines = [f"BILL {code}", "", "What the bill does (official summary as introduced, names and numbers removed):",
                     text[k], "",
                     f"THE VOTE: first recorded vote, in a {ven} of the {'Senate' if b['chamber'] == 'S' else 'House'}. "
                     f"Majority party in the chamber: {b['majority']}.",
                     f"Members voting: {party_n['Democratic']} Democrats, {party_n['Republican']} Republicans"
                     + (f", {sum(party_n.values()) - party_n['Democratic'] - party_n['Republican']} other" if sum(party_n.values()) > party_n['Democratic'] + party_n['Republican'] else "") + ".",
                     f"Patron (chief sponsor): a {b['chief_party'].replace('Democratic', 'Democrat')}, {'a member of this room' if te[I[0]]['pat_in_room'] else 'not a member of this room'}, "
                     f"{'in the majority' if b['chief_party'] == b['majority'] else 'in the minority'}.",
                     f"Co-patrons: {cops.get('Democratic', 0)} Democrats, {cops.get('Republican', 0)} Republicans.",
                     "Members the statistical model is already sure of: "
                     + "; ".join(f"{'Democrats' if p == 'Democratic' else 'Republicans'}: {called[(p, 'yes')]} yes, {called[(p, 'no')]} no" for p in ("Democratic", "Republican")) + ".",
                     "", "MEMBERS TO PREDICT (the statistical model is NOT sure of these):"]
            keys = []
            for j, i in enumerate(ask, 1):
                r = te[i]; m = f"M{j}"; keys.append([m, r["who"], int(r["y"]), float(pC[i])])
                past = [q for q in by_who[r["who"]] if date[q["bill"]] < d0 and q["bill"] in vec and q["bill"] != k]
                sims = sorted(((_cos(v0, vec[q["bill"]]), q) for q in past), key=lambda t: -t[0])[:6]
                yrs = max(0, int(yr) - first_year.get(r["who"], int(yr)))
                own = []
                for nm, kk, nn in (("bills by this patron", "k_mpat", "n_mpat"), ("bills on this subject", "k_msubj", "n_msubj"),
                                   ("bills in this room", "k_mroom", "n_mroom")):
                    if r.get(nn):
                        own.append(f"{nm}: yes {r[kk]} of {r[nn]}")
                lines += ["", f"{m}: {r['party']}; {'same party as the patron' if r['same'] else 'other party from the patron'}"
                          + ("; a co-patron of this bill" if r.get("own_cops") else "") + (f"; about {yrs} years of recorded votes before this session" if yrs else "; first session or first year with recorded votes"),
                          f"  District: {_pct(r['d_white'])} white, {_pct(r['d_black'])} Black, {_pct(r['d_hisp'])} Hispanic; "
                          f"{_pct(r['d_college'])} of adults with a college degree; {_pct(r['d_poverty'])} in poverty; "
                          f"{_pct(r['d_owner'])} home owners." if r.get("d_has") else "  District: not known",
                          f"  Record: votes against most of own party on {_pct(r['defect'])} of contested votes; " + "; ".join(own) + ".",
                          "  Own first votes on the most similar earlier bills (newest data allowed is the day before this vote):"]
                for s, q in sims:
                    sh, n = block[(q["bill"], r["party"])]; ry = sum(x["y"] for x in by_bill[q["bill"]])
                    lines.append(f"    - [{'YES' if q['y'] else 'NO'}] (whole room {ry} yes of {len(by_bill[q['bill']])}; own party {_pct(sh)} yes of {n}; patron {'same' if q['same'] else 'other'} party; "
                                 f"similarity {s:.2f}) {text[q['bill']][:260]}")
                if not sims:
                    lines.append("    - none on record")
            open(os.path.join(OUT, yr, f"{code}.txt"), "w").write("\n".join(lines) + "\n")
            manifest[code] = {"yr": yr, "bill": list(k), "members": keys}
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"))
    n_m = sum(len(v["members"]) for v in manifest.values())
    print(f"{len(manifest)} bill packets, {n_m} asked votes -> {OUT}; bills skipped: {dict(skipped)}")
    for yr in SPLIT:
        ms = [m for v in manifest.values() if v["yr"] == yr for m in v["members"]]
        if ms:
            acc = np.mean([(m[3] >= .5) == (m[2] == 1) for m in ms])
            print(f"  {yr}: {sum(v['yr'] == yr for v in manifest.values())} bills, {len(ms)} asked votes, arm C right on them {acc:.3f}")


lo = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4)))


def score():
    man = json.load(open(os.path.join(OUT, "manifest.json")))
    ans = {}
    for f in sorted(os.listdir(OUT)):
        if f.startswith("answers") and f.endswith(".jsonl"):
            for line in open(os.path.join(OUT, f)):
                line = line.strip()
                if line.startswith("{"):
                    d = json.loads(line)
                    if d.get("recognized"):
                        ans[d["id"]] = None; continue
                    ans.setdefault(d["id"], d)
    data = {}
    for code, v in man.items():
        a = ans.get(code)
        if not a:
            continue
        for m, who, y, pc in v["members"]:
            if m in a["p"]:
                data.setdefault(v["yr"], []).append((code, y, pc, a["p"][m] / 100))
    skipped = sum(1 for c in ans if ans[c] is None)
    print(f"answers: {len(ans)} bills ({skipped} recognized, dropped)")
    w = {}
    for yr in sorted(data):
        D = data[yr]; y = np.array([x[1] for x in D]); pc = np.array([x[2] for x in D]); pa = np.array([x[3] for x in D])
        pm = 1 / (1 + np.exp(-(np.array([lo(a) for a in pc]) + np.array([lo(a) for a in pa])) / 2))
        print(f"\n{yr}: {len(D)} asked votes on {len({x[0] for x in D})} bills")
        for nm, p in (("arm C", pc), ("AI alone", pa), ("AI + arm C (equal)", pm)):
            r = (p >= .5) == (y == 1); c = np.abs(p - .5) >= .31
            print(f"  {nm:20s} right {r.mean():.3f}   calls {c.sum():4d} ({c.mean():.0%}) right {r[c].mean() if c.any() else float('nan'):.3f} wrong {(c & ~r).sum()}")
        # year-ahead weight for the AI on top of arm C, learned on the other year
        X = np.array([lo(a) for a in pa]); off = np.array([lo(a) for a in pc]); b = 0.0
        for _ in range(50):
            p = 1 / (1 + np.exp(-(off + b * X))); b += (((y - p) * X).sum() - b) / ((p * (1 - p) * X * X).sum() + 1)
        w[yr] = b
    if "2025" in w and "2026" in data:
        D = data["2026"]; y = np.array([x[1] for x in D]); off = np.array([lo(x[2]) for x in D]); X = np.array([lo(x[3]) for x in D])
        p = 1 / (1 + np.exp(-(off + w["2025"] * X))); r = (p >= .5) == (y == 1); c = np.abs(p - .5) >= .31
        print(f"\nyear-ahead: weight fit on 2025 = {w['2025']:+.2f}; 2026 right {r.mean():.3f}, calls {c.sum()} right "
              f"{r[c].mean() if c.any() else float('nan'):.3f} wrong {(c & ~r).sum()}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    if mode == "build":
        build(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif mode == "score":
        score()
