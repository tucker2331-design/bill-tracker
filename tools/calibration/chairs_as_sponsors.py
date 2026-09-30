"""Party power centres as co-sponsors (2025): committee chairs among a bill's patrons. Do they reveal the lineup, and
does the model already know? Uses the saved 2025 member-level predictions (p2025.npy)."""
import sys, gzip, json, collections, pickle, numpy as np
sys.path.insert(0, "tools/calibration")
import first_vote as FV
from corpus import load, _party_lookup
party, person = _party_lookup()
S = "/private/tmp/claude-501/-Users-tuckerward-Documents-Projects-bill-tracker/d2c029e9-acd9-410e-81ec-5347fd755620/scratchpad"
ros = json.load(gzip.open("tools/historical_cache/va_rosters/20251.json.gz"))["rows"]
chairs = {person(r["member_name"]) or r["member_name"] for r in ros if r["role"] == "Chair"}
room_chair = {}
for r in ros:
    if r["role"] == "Chair": room_chair[("H:" if r["committee_no"].startswith("H") else "S:") + r["committee_name"].strip().lower()] = person(r["member_name"]) or r["member_name"]
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["yr"] == 2025 and r["y"] >= 0]
p = np.load(f"{S}/p2025.npy"); y = np.array([r["y"] for r in rows]); right = (p >= .5) == (y == 1)
same = np.array([r["same"] for r in rows])
def pats(b): return {person(b["chief"]) or b["chief"]} | {person(c) or c for c in b["cops"]}
n_ch = np.array([len(pats(corpus[r["bill"]]) & chairs) for r in rows])
rc = []
for r in rows:
    b = corpus[r["bill"]]; room = (FV.first_room(b) or "").lower()
    rc.append(room_chair.get(room.replace("h:", "h:").replace("s:", "s:")) in pats(b))
rc = np.array(rc)
print(f"2025 ballots {len(rows)}; chairs known {len(chairs)}; hearing-room chair matched for {np.mean([bool(room_chair.get((FV.first_room(corpus[r['bill']]) or '').lower())) for r in rows]):.0%} of ballots")
for lab, m in (("no committee chair among patrons", n_ch == 0), ("1+ committee chairs among patrons", n_ch >= 1),
               ("3+ committee chairs among patrons", n_ch >= 3), ("the HEARING committee's chair is a patron", rc)):
    if m.sum():
        print(f"  {lab:44s} ballots {m.sum():5d} | yes {y[m].mean():.0%} | other-party yes {y[m & (same == 0)].mean():.0%} | model right {right[m].mean():.1%} (other-party {right[m & (same == 0)].mean():.1%})")

# within-2025, 5-fold cross-validation grouped by BILL (no bill in both train and test), base vs + chair inputs
import gbm
for r, k in zip(rows, n_ch):
    b = corpus[r["bill"]]; r["ch_n"] = float(k); r["ch_chief"] = float((person(b["chief"]) or b["chief"]) in chairs)
bills = sorted({r["bill"] for r in rows}); rng = np.random.default_rng(3); fold_of = {b: i for i, b in zip(rng.integers(0, 5, len(bills)), bills)}
fold = np.array([fold_of[r["bill"]] for r in rows])
X = lambda cs: np.array([[r[c] for c in cs] for r in rows], float)
res = {}
for name, cs in (("GBM", FV.NUM), ("GBM + chairs among sponsors", FV.NUM + ["ch_n", "ch_chief"])):
    Xa = X(cs); pp = np.zeros(len(rows))
    for f in range(5):
        tr, te = fold != f, fold == f
        pp[te] = gbm.GBM(depth=6, lr=.03, rounds=260).fit(Xa[tr], y[tr].astype(float)).predict(Xa[te])
    res[name] = pp
o = np.argsort(np.abs(res["GBM"] - .5)); hf = o[:len(o) // 3]
for name, pp in res.items():
    rt = (pp >= .5) == (y == 1)
    print(f"  [2025, 5-fold by bill] {name:30s} all {rt.mean():.4f}  other-party {rt[same == 0].mean():.4f}  fixed-hard {rt[hf].mean():.4f}")
