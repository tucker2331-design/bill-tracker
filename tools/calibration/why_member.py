"""Why each member gets the first-vote guess they get -- in reasons a volunteer can read, each with a size.

Owner, 2026-09-28, on the member card: "to a amateur lobbyist it seems like a odd stat to include, moreover they
dont know how much it really matters anyway ... i dont think those 2 frankly are enough evidence."

METHOD (interventional, one reason at a time): score the member, then for each reason swap that reason's inputs
for the values of K=300 REAL training ballots from members of the same party on the same side of the bill, and
average. effect = p - mean(p_swapped): + pushes toward yes. The first attempt swapped in the per-feature MEAN
instead; that builds an "average member" who does not exist, and on a tree model it produced nonsense (a typical
Democrat on their own party's bill at 45%, against an observed 88%). Real peers fix it: peers on their own bills
score 87-90 (D) and 63 (R), matching the observed base rates 88.4% and 60.9%.
Effects are NOT additive (the model has interactions), so the card shows strength words, never a sum.

Run: python3 tools/calibration/why_member.py   (edit the members/bill at the bottom of the setup)
Default subject: HB 1515's five Rules Studies Subcommittee members, first vote assumed 2027-01-20."""
import sys, json, collections, numpy as np
sys.path.insert(0, "tools/calibration")
import first_vote as FV, gbm
from corpus import _party_lookup

REASONS = {
  "party":     ["same", "maj", "chamber_S"],
  "patron":    ["mpat_rate", "mpat_n", "pat_rate", "pat_n", "senior", "pat_in_room"],
  "committee": ["mroom_rate", "mroom_n", "room_rate", "room_n", "is_subroom", "subroom_rate", "subroom_n"] + [c for c in FV.NUM if c.startswith("ra_") or c.startswith("rm_")],
  "similar":   ["has_c", "c_opp", "c_party", "dev", "has_mem", "dup_sim", "dup_maj_other", "dup_same_pat", "comp_sim"],
  "subject":   ["subj_has", "subj_party", "subj_n", "msubj", "msubj_n"],
  "wording":   ["txt_has", "txt_party", "txt_other"],
  "record":    ["defect", "mdef_ses", "ses_rate", "ses_n"] + FV.IP_COLS,
  "district":  FV.DIST_COLS,
  # the bill's own situation -- where it sits, how it has moved, who signed on (same for every member)
  "bill":      ["ven_sub", "ven_com", "n_actions", "fiscal", "sub_offered", "n_refs", "wait", "day",
                "own_cops", "other_cops", "n_cops", "companion", "is_patron", "comp_has", "comp_party"],
  "backing":   ["own_cops", "other_cops", "n_cops", "companion", "comp_has", "comp_party", "is_patron"],
  "path":      ["ven_sub", "ven_com", "n_actions", "fiscal", "sub_offered", "n_refs", "wait", "day"],
}
MEMBER = [g for g in REASONS if g not in ("bill", "backing", "path", "party")]
party, person = _party_lookup()
names = ["Rip Sullivan", "Cliff Hayes", "Kathy Tran", "Dan Helmer", "Terry Kilgore"]
members = [(person(n) or n, party(n)) for n in names]
rows = FV.features(future=[("2026", "HB 1515", "sub", members, "2027-01-20")])
rows = FV.add_room_aggregates(FV.add_districts(FV.add_ideal(FV.add_text(rows))))
tr = [r for r in rows if r["yr"] in FV.TRAIN_YEARS + (2025,) and r["y"] >= 0]
fut = [r for r in rows if r["y"] < 0]
X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
m = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float))
col = {c: i for i, c in enumerate(FV.NUM)}
Xtr = X(tr)
# typical value per (party, same) in training
key = lambda r: (r["party"], r["same"])
groups = collections.defaultdict(list)
for i, r in enumerate(tr): groups[key(r)].append(i)
typ = {k: Xtr[v].mean(axis=0) for k, v in groups.items()}
def rate(rs, k, n):
    v = [r[k] / r[n] for r in rs if r.get(n, 0) >= 5]
    return round(float(np.mean(v)), 3) if v else None
rng = np.random.default_rng(7)
K = 300
out = []
for r in fut:
    x = X([r])[0]; p = float(m.predict(x[None])[0])
    idx = groups[key(r)]
    samp = Xtr[rng.choice(idx, size=min(K, len(idx)), replace=False)]     # REAL ballots, same party & side
    def swapped(cols_list):
        xs = np.repeat(x[None], len(samp), axis=0)
        for c in cols_list:
            if c in col: xs[:, col[c]] = samp[:, col[c]]
        return float(m.predict(xs).mean())
    eff = {g: round(p - swapped(REASONS[g]), 3) for g in REASONS}
    # EVIDENCE per reason (owner 2026-09-30: "not clear why those specifically matter"): the ONE input inside the
    # reason that moves the guess most on its own, with this member's value and the typical value among the same
    # real peers. A reason whose inputs are all "no data" flags (has_c / has_mem / txt_has / subj_has / d_has /
    # ip_has = 0) is an ABSENCE, not a finding -- the swap then measures "peers had data", so it is marked.
    ABSENT = {"similar": ["has_c", "has_mem"], "wording": ["txt_has"], "subject": ["subj_has"], "district": ["d_has"]}
    evid = {}
    for g in REASONS:
        cols = [c for c in REASONS[g] if c in col]
        per = {c: p - swapped([c]) for c in cols}
        top = max(per, key=lambda c: abs(per[c]))
        evid[g] = {"input": top, "effect": round(per[top], 3), "member": round(float(x[col[top]]), 3),
                   "all": {c: [round(per[c], 3), round(float(x[col[c]]), 3), round(float(samp[:, col[c]].mean()), 3)]
                           for c in cols if abs(per[c]) >= 0.01},
                   "typical": round(float(samp[:, col[top]].mean()), 3),
                   "absent": all(x[col[f]] == 0 for f in ABSENT.get(g, [])) if g in ABSENT else False}
    anchor = round(swapped([c for g in MEMBER for c in REASONS[g]]), 3)          # a real peer, on THIS bill
    peer_all = round(float(m.predict(samp).mean()), 3)                             # real peers, their own bills
    out.append({"who": r["who"], "party": r["party"], "same": r["same"], "p": round(p, 3), "anchor": anchor,
        "peer_all": peer_all, "effects": eff, "evidence": evid,
        "counts": {k: [r.get("k_" + k), r.get("n_" + k)] for k in ("mpat", "mroom", "sim", "msubj")},
        "defect": round(r["defect"], 3), "backing_vals": {c: r.get(c) for c in ["own_cops","other_cops","n_cops","companion","comp_has"]},
        "path_vals": {c: r.get(c) for c in ["ven_sub","n_actions","fiscal","sub_offered","n_refs","wait","day"]}, "txt_party": round(float(r.get("txt_party", 0)), 3), "txt_has": r.get("txt_has")})
# EVIDENCE for the "overall voting record" reason (owner 2026-09-30: show why a reason matters, not prose): where the
# member's votes place them among their own party's House members on the left-right map (ideal points fitted on
# earlier years only, first_vote.ideal_points). 0 = furthest left, 100 = furthest right.
IP = FV.ideal_points()
house26 = {(r["who"], r["party"]) for r in rows if r["yr"] == 2026 and r["y"] >= 0 and not r["chamber_S"]}
for o in out:
    pts = IP.get(2026, {})
    peers = sorted(pts[w][0] for w, pp in house26 if pp == o["party"] and w in pts)
    me = pts.get(o["who"])
    o["ip_right_of"] = (round(100 * sum(v < me[0] for v in peers) / len(peers)) if me and peers else None)
    o["ip_peers"] = len(peers)
print(json.dumps(out, indent=1))
