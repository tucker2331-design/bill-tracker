#!/usr/bin/env python3
"""Add the 2023 session -- missing from training because Open States has no 2023 committee record -- from LIS's own
legacy files (va/231: Vote.csv member-level ballots, History.csv refid -> bill/date/motion, Members.csv, Sponsors.csv),
then measure whether one more year of data moves the first-vote model.

Joins, each checked below:
  * Vote.csv row = refid, then (member id, Y/N/X/A) pairs. History.csv gives the refid's bill, date and motion text.
  * Motion direction and venue use EXACTLY the rules the other years use (content_votes: PROCEDURAL / ANTI / PRO /
    venue), so 2023 ballots mean what every other year's ballots mean.
  * Carryover guard as elsewhere: history lines dated outside 2023 are dropped.
  * Member ids -> "Last, First M." -> the shared person/party resolver.
  * 2023 CO-PATRONS from LIS Sponsors.csv. Open States has none for 2023; left empty, every 2023 bill would look like a
    no-co-patron bill and teach the model a false lesson about co-patrons.

Protocol: settings fixed; choose on 2024 (train 2019-2022 [+2023]), score once on 2025 (TRAIN_YEARS [+2023]).
Run: python3 tools/calibration/add_2023.py
"""
from __future__ import annotations
import sys, os, re, csv, gzip, io, pickle, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import first_vote as FV
import content_votes as CVT
import gbm
from corpus import load as _load, _party_lookup

LEG = os.path.join(HERE, "..", "historical_cache", "va", "231")
OUT = os.environ.get("IF_OUT", "/tmp")


def rd(name):
    return csv.reader(io.TextIOWrapper(gzip.open(os.path.join(LEG, name + ".gz")), "latin-1"))


def clean_bill(b):
    m = re.match(r"^(HB|SB)0*(\d+)$", b.strip().upper())
    return f"{m.group(1)} {int(m.group(2))}" if m else None


def build_2023():
    party, person = _party_lookup()
    # Name cascade -- LIS writes "Last, First M., Jr." and nicknames in quotes ('Sullivan, Richard C."Rip," Jr.').
    # Each step is tried in order; the first that the shared resolver knows wins; unresolved members are COUNTED.
    known = collections.defaultdict(set)                  # surname -> resolver names (for the last-resort step)
    for r0 in pickle.load(open(FV.ROWS, "rb")):
        known[r0["who"].split()[-1].lower()].add(r0["who"])
    SUFFIX = re.compile(r",?\s*\b(Jr|Sr|II|III|IV)\.?\s*$", re.I)
    def resolve(raw):
        last, _, first = raw.strip().partition(",")
        first = SUFFIX.sub("", first.strip()).strip().rstrip(",")
        nick = re.search(r'"([^"]+?),?"', first)
        first_clean = re.sub(r'"[^"]*"', "", first).replace(",", " ").split()
        last = last.strip()
        cands = [f"{' '.join(first_clean)} {last}"]
        if nick: cands.append(f"{nick.group(1).strip()} {last}")
        if first_clean: cands.append(f"{first_clean[0]} {last}")
        if len(first_clean) > 1: cands.append(f"{first_clean[-1]} {last}")
        for c in cands:
            if party(c) in FV.PARTIES:
                return person(c) or c, party(c), "name"
        pool = known.get(last.split()[-1].lower(), set())
        if len(pool) == 1:
            w = next(iter(pool)); return w, party(w), "unique surname"
        return None, None, "unresolved"
    mem, how = {}, collections.Counter()
    r = rd("Members.csv"); next(r)
    for row in r:
        who, pp, via = resolve(row[2])
        how[via] += 1
        if who:
            mem[row[1].strip()] = (who, pp)
    print("2023 member names:", dict(how), flush=True)
    hist = {}
    r = rd("History.csv"); next(r)
    for bill_id, date, desc, refid in r:
        refid = refid.strip()
        if not refid:
            continue
        mm, dd, yy = date.split("/")
        if yy != "23":                                    # carryover guard (2022 lines in the 2023 file)
            continue
        hist[refid] = (clean_bill(bill_id), f"20{yy}-{mm}-{dd}", desc)
    stats = collections.Counter()
    rc = collections.defaultdict(list)
    VORD = {"sub": 0, "com": 1, "floor": 2}
    for row in rd("Vote.csv"):
        refid = row[0].strip()
        if refid not in hist:
            stats["no history line"] += 1; continue
        key, date, desc = hist[refid]
        if not key:
            stats["not HB/SB"] += 1; continue
        t = re.sub(r"^[HS]\s+", "", desc)
        if CVT.PROCEDURAL.search(t):
            stats["procedural"] += 1; continue
        anti = bool(CVT.ANTI.search(t))
        if not anti and not CVT.PRO.search(t):
            stats["unclassified"] += 1; continue
        ballots = []
        for i in range(1, len(row) - 1, 2):
            mid, v = row[i].strip(), row[i + 1].strip()
            if v not in ("Y", "N") or mid not in mem:
                continue
            who, pp = mem[mid]
            if pp not in FV.PARTIES:
                stats["member party unresolved"] += 1; continue
            ballots.append((who, pp, (v == "Y") != anti))
        if len(ballots) < 5:
            stats["fewer than 5 ballots"] += 1; continue
        ven = CVT.venue(t)
        rc[("2023", key)].append((date, VORD[ven], refid, ven, ballots)); stats["kept"] += 1
    for k in rc:
        rc[k].sort()
    cops = collections.defaultdict(list)
    r = rd("Sponsors.csv"); header = next(r)
    h = {c.strip().upper(): i for i, c in enumerate(header)}
    for row in r:
        key = clean_bill(row[h["BILL_NUMBER"]])
        role = row[h["PATRON_TYPE"]]
        if key and "Chief Patron" not in role:
            nm = row[h["MEMBER_NAME"]].strip()
            cops[("2023", key)].append(nm)
    return dict(rc), cops, stats


def main():
    rc23, cops23, stats = build_2023()
    print("2023 roll calls:", dict(stats), "| bills with roll calls:", len(rc23), "| bills with co-patrons:", len(cops23), flush=True)
    party, person = _party_lookup()
    D = FV.assemble()
    D2 = dict(D); D2["rc"] = {**D["rc"], **rc23}
    base = _load()
    bills2 = []
    for b in base["bills"]:
        if b["session"] == "2023" and (b["session"], b["bill"]) in cops23:
            names = cops23[(b["session"], b["bill"])]
            b = {**b, "cops": [person(n) or n for n in names], "cop_parties": [party(n) for n in names]}
        bills2.append(b)
    data2 = {**base, "bills": bills2}
    FV.assemble = lambda: D2                              # the replay now sees 2023 votes + 2023 co-patrons
    FV.load = lambda: data2
    cache = os.path.join(OUT, "rows_with_2023.pkl")
    if os.path.exists(cache):
        rows = pickle.load(open(cache, "rb"))
    else:
        rows = FV.features()
        rows = FV.add_room_aggregates(FV.add_districts(FV.add_ideal(FV.add_text(rows))))
        pickle.dump(rows, open(cache, "wb"))
    rows = [r for r in rows if r["y"] >= 0]
    print("first-vote ballots by year:", dict(sorted(collections.Counter(r["yr"] for r in rows).items())), flush=True)
    old = [r for r in pickle.load(open(FV.ROWS, "rb")) if r["y"] >= 0]
    X = lambda rs: np.array([[r[c] for c in FV.NUM] for r in rs], float)
    def run(rs, trn, tst, label, hf=None):
        tr = [r for r in rs if r["yr"] in trn]; te = [r for r in rs if r["yr"] == tst]
        p = gbm.GBM(depth=6, lr=.03, rounds=260).fit(X(tr), np.array([r["y"] for r in tr], float)).predict(X(te))
        y = np.array([r["y"] for r in te]); right = (p >= .5) == (y == 1); same = np.array([r["same"] for r in te])
        if hf is None or len(hf) != len(te) // 3 or hf.max() >= len(te):   # a fixed set only when the ballots line up
            if hf is not None: print("   (ballot sets differ; hardest third re-ranked for this line)")
            o = np.argsort(np.abs(p - .5)); hf = o[:len(o) // 3]
        print(f"  {label:58s} all {right.mean():.4f}  other-party {right[same == 0].mean():.4f}  fixed-hard {right[hf].mean():.4f}", flush=True)
        return hf
    for tag, trn, tst in (("choose on 2024", (2019, 2020, 2021, 2022), 2024), ("score on 2025", FV.TRAIN_YEARS, 2025)):
        print(f"[{tag}]")
        hf = run(old, trn, tst, "original pipeline (no 2023 at all)")
        run(rows, trn, tst, "2023 in the history the features read, not trained on", hf)
        run(rows, trn + (2023,), tst, "2023 in the history AND trained on", hf)


if __name__ == "__main__":
    main()
