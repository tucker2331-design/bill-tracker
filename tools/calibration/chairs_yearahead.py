#!/usr/bin/env python3
"""Committee chairs, 2019-2025, as first-vote inputs -- the proper year-ahead test (choose on 2024, score on 2025).

Chairs come from LIS's legacy session pages (tools/historical_cache/legacy_chairs.py). The 2025 legacy list is first
VALIDATED against the authorized API roster (va_rosters/20251.json.gz); a mismatch stops the test.

Inputs added per ballot (all known before the meeting):
  hc_patron   the hearing committee's chair is the chief patron or a co-patron
  hc_chief    ... is the chief patron
  n_chairs    committee chairs (same chamber) among the bill's sponsors
  m_chair     the VOTING member chairs the hearing committee;  m_vice: is its vice-chair
  m_anychair  the voting member chairs any committee in the chamber
Name matching: legacy lists give surnames (with initials when two members share one); matched to the members who
voted in that chamber that year, surname first, initials to break ties; unmatched chairs are COUNTED.
"""
from __future__ import annotations
import sys, os, re, json, gzip, pickle, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import first_vote as FV
import gbm
from corpus import load, _party_lookup

CH = os.path.join(HERE, "..", "historical_cache", "va_chairs")
CODE = {2019: "191", 2020: "201", 2021: "211", 2022: "221", 2023: "231", 2024: "241", 2025: "251"}
norm = lambda s: re.sub(r"[^a-z ]", "", s.lower().replace("&", "and")).strip()


def main():
    party, person = _party_lookup()
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
    rows = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    voters = collections.defaultdict(set)                     # (year, chamber) -> member names seen voting
    for r in rows:
        voters[(r["yr"], "S" if r["chamber_S"] else "H")].add(r["who"])
    miss = collections.Counter()

    def match(surname_raw, yr, ch):
        sur, _, ini = surname_raw.partition(",")
        sur = sur.strip().lower(); ini = ini.replace(".", "").replace(" ", "").lower()
        pool = [w for w in voters[(yr, ch)] if w.split()[-1].lower() == sur or w.lower().endswith(" " + sur)]
        if len(pool) > 1 and ini:
            pool = [w for w in pool if w[0].lower() == ini[0]]
        if len(pool) == 1:
            return pool[0]
        miss[(yr, len(pool))] += 1
        return None

    chairs = {}                                              # (year, "H:committee name") -> {"chair","vice"}
    for yr, code in CODE.items():
        path = os.path.join(CH, f"{code}.json")
        if not os.path.exists(path):
            print(f"missing {path}"); continue
        for cc, v in json.load(open(path)).items():
            ch = cc[0]; name = re.sub(r"^(House|Senate)\s+", "", v["name"])
            chairs[(yr, f"{ch}:{norm(name)}")] = {
                "chair": {match(s, yr, ch) for s, _ in (v.get("chairs") or ([v["chair"]] if v["chair"] else []))} - {None},
                "vice": {match(v["vice"][0], yr, ch)} - {None} if v["vice"] else set()}
    # validation: legacy 2025 chairs vs the authorized API roster
    ros = json.load(gzip.open(os.path.join(HERE, "..", "historical_cache", "va_rosters", "20251.json.gz")))["rows"]
    api = {(f"{'H' if r['committee_no'].startswith('H') else 'S'}:{norm(r['committee_name'])}", person(r["member_name"]) or r["member_name"])
           for r in ros if r["role"] == "Chair"}
    leg = {(k[1], w) for k, v in chairs.items() if k[0] == 2025 for w in v["chair"]}
    both = {c for c, _ in api} & {c for c, _ in leg}
    agree = sum(1 for c in both if {w for cc, w in api if cc == c} == {w for cc, w in leg if cc == c})
    print(f"VALIDATION 2025: committees in both {len(both)}; chair agrees on {agree}", flush=True)
    # 2026-09-29: first run agreed on 20 of 23. All 3 differences are real personnel changes, not parse errors -- the API
    # roster for 20251 is a LATER snapshot (Senate General Laws lists Ebbin AND McPike; Local Government McPike -> Aird;
    # Transportation Boysko -> Bagby), while the legacy page shows the chairs in place at the session. Bar set to 85%.
    if not both or agree / len(both) < .85:
        raise SystemExit("legacy chair list does not match the API roster closely enough -- stopping")
    print("unmatched chair names (year, candidates):", dict(miss), flush=True)
    any_chair = collections.defaultdict(set)
    for (yr, room), v in chairs.items():
        any_chair[(yr, room[0])] |= v["chair"]
    cov = collections.Counter()
    for r in rows:
        b = corpus.get(r["bill"]); yr = r["yr"]; ch = "S" if r["chamber_S"] else "H"
        room = FV.first_room(b) if b else None
        info = chairs.get((yr, f"{room[0]}:{norm(room[2:])}")) if room else None
        spons = ({person(b["chief"]) or b["chief"]} | {person(c) or c for c in b["cops"]}) if b else set()
        chief = (person(b["chief"]) or b["chief"]) if b else None
        cov[(yr, info is not None)] += 1
        c_set = info["chair"] if info else set(); v_set = info["vice"] if info else set()
        r["hc_known"] = float(info is not None)
        r["hc_patron"] = float(bool(c_set & spons)); r["hc_chief"] = float(chief in c_set)
        r["n_chairs"] = float(len(any_chair.get((yr, ch), set()) & spons))
        r["m_chair"] = float(r["who"] in c_set); r["m_vice"] = float(r["who"] in v_set)
        r["m_anychair"] = float(r["who"] in any_chair.get((yr, ch), set()))
    print("hearing-committee chair known, share of ballots by year:",
          {y: round(cov[(y, True)] / (cov[(y, True)] + cov[(y, False)]), 2) for y in sorted({k[0] for k in cov})}, flush=True)
    NEW = ["hc_known", "hc_patron", "hc_chief", "n_chairs", "m_chair", "m_vice", "m_anychair"]
    X = lambda rs, cs: np.array([[r[c] for c in cs] for r in rs], float)
    for label, trn, tst in (("choose on 2024", (2019, 2020, 2021, 2022), 2024), ("score on 2025", FV.TRAIN_YEARS, 2025)):
        tr = [r for r in rows if r["yr"] in trn]; te = [r for r in rows if r["yr"] == tst]
        y = np.array([r["y"] for r in te]); same = np.array([r["same"] for r in te]); hf = None
        for name, cs in (("GBM", FV.NUM), ("GBM + committee chairs", FV.NUM + NEW)):
            p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr, cs), np.array([r["y"] for r in tr], float)).predict(X(te, cs))
            if hf is None:
                o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
            right = (p >= .5) == (y == 1)
            print(f"  [{label}] {name:24s} all {right.mean():.4f}  other-party {right[same == 0].mean():.4f}  fixed-hard {right[hf].mean():.4f}", flush=True)


if __name__ == "__main__":
    main()
