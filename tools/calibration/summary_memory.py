#!/usr/bin/env python3
"""Room memory, re-tested on CONTENT instead of titles.

Owner, 2026-09-24: "the titles mean nothing they are performative and often hide the real controversial
text." So [[testing/room_memory]]'s title match cannot be the product basis. This uses the official LIS
bill SUMMARY ("summary as introduced" -- what the bill does, written by legislative staff), already in the
cached Open States zips, with the title text stripped out of it so a match cannot ride on the title.

Similarity: Jaccard on word 3-shingles after normalisation, candidates found through an inverted index on
rare shingles (document frequency <= 40) so this runs on 14k bills in seconds. Pairs: every bill against
its MOST similar summary from an EARLIER year. Then, per similarity band, does the earlier bill's fate in
the SAME first committee predict this bill's fate there? Patron standing held fixed.

Scope 2020-2026 (committee record; [[failures/openstates_committee_gap]]). 2023 has no summaries in the
source, so 2023 bills are neither matched nor used as earlier versions. INTERNAL ONLY until the owner's
Standard #3 call: a summary is official LIS content, but similarity is a derived, probabilistic claim.
"""
from __future__ import annotations
import sys, os, re, io, csv, glob, zipfile, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load, norm
from room_memory import first_room, cleared, odds

ZIPS = os.path.join(HERE, "..", "historical_cache", "openstates_va")
STOP = set("the a an of to and or in on for by with as at be is are this that such any shall may from "
           "which its it who under than other not no".split())


def summaries():
    """(session, 'HB 12') -> introduced summary text. Rows whose note is 'title' are the title again."""
    out = {}
    for z in sorted(glob.glob(os.path.join(ZIPS, "VA_20*.zip"))):
        s = os.path.basename(z)[3:-4]
        if not s[:4].isdigit() or int(s[:4]) < 2020 or "S" in s:
            continue
        zf = zipfile.ZipFile(z)
        names = zf.namelist()
        ab = [n for n in names if n.endswith("_bill_abstracts.csv")]
        if not ab:
            continue
        ident = {r["id"]: r["identifier"] for r in csv.DictReader(io.TextIOWrapper(
            zf.open([n for n in names if n.endswith("_bills.csv")][0]), "utf-8"))}
        for r in csv.DictReader(io.TextIOWrapper(zf.open(ab[0]), "utf-8")):
            note = (r["note"] or "").lower()
            if "introduced" not in note:
                continue
            b = ident.get(r["bill_id"], "")
            if b[:3] in ("HB ", "SB "):
                out.setdefault((s, b), r["abstract"])
    return out


def shingles(text, title):
    t = norm(text)
    tl = norm(title)
    if tl and t.startswith(tl[:40]):
        t = t[len(tl):]                      # the summary usually opens with the title; drop it
    w = [x for x in re.findall(r"[a-z0-9]+", t) if x not in STOP]
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def best_earlier(bills, sh):
    df = collections.Counter(g for r in bills for g in sh[id(r)])
    inv = collections.defaultdict(list)
    for r in bills:
        for g in sh[id(r)]:
            if df[g] <= 40:
                inv[g].append(r)
    out = []
    for r in bills:
        S = sh[id(r)]
        if len(S) < 8:
            continue
        # CARRYOVER TWINS ARE ONE BILL, NOT A PRIOR VERSION. A bill continued from 2024 into 2025 appears in
        # both files with the SAME summary, and Open States never updates the 2025 copy -- so its outcome is
        # the 2024 outcome by construction. Unexcluded, the >=0.80 band read 99.0% "dies again" (n=389).
        cand = {id(x): x for g in S if df[g] <= 40 for x in inv[g]
                if x["year"] < r["year"] and not (x["bill"] == r["bill"] and r["year"] - x["year"] <= 1)}
        best, bj = None, 0.0
        for x in cand.values():
            T = sh[id(x)]
            j = len(S & T) / len(S | T)
            if j > bj:
                best, bj = x, j
        if best is not None:
            out.append((best, r, bj))
    return out


def main():
    summ = summaries()
    bills = [r for r in load()["bills"] if r["year"] >= 2020 and r["session"] in
             {s for s, _b in summ} and (r["session"], r["bill"]) in summ and first_room(r) and r["standing"]]
    bills = [r for r in bills if r["session"] != "2027"]
    sh = {id(r): shingles(summ[(r["session"], r["bill"])], r["title"]) for r in bills}
    pairs = best_earlier(bills, sh)
    print(f"{len(bills)} bills with an introduced summary; {len(pairs)} have an earlier-year match\n")
    print("SAME first committee, patron standing held fixed, by how closely the SUMMARIES match")
    print(f"  {'similarity':12s} {'n':>5s}  {'room killed it before -> dies':>30s}  {'cleared before -> dies':>23s}  OR")
    bands = ((0.8, 1.01), (0.5, 0.8), (0.3, 0.5), (0.15, 0.3), (0.05, 0.15))
    for lo, hi in bands:
        g = [(cleared(A), cleared(B)) for A, B, j in pairs if lo <= j < hi and first_room(A) == first_room(B)
             and A["standing"] == B["standing"] and norm(A["title"]) != norm(B["title"]) or False]
        allg = [(cleared(A), cleared(B)) for A, B, j in pairs if lo <= j < hi and first_room(A) == first_room(B)
                and A["standing"] == B["standing"]]
        for lbl, rows in (("all", allg), ("titles DIFFER", g)):
            if len(rows) < 25:
                print(f"  {lo:.2f}-{min(hi,1):.2f} {lbl:13s} n={len(rows):4d}  (too few)")
                continue
            o = odds(rows)
            print(f"  {lo:.2f}-{min(hi,1):.2f} {lbl:13s} n={o['n']:4d}  {o['die_after_die']:6.1%} (n={o['n_died']:4d})"
                  f"      {o['die_after_clear']:6.1%} (n={o['n_cleared']:4d})   {o['or']:5.1f} [{o['lo']:.1f}-{o['hi']:.1f}]")
    return pairs


if __name__ == "__main__":
    main()
