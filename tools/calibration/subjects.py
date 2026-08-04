#!/usr/bin/env python3
"""LIS subject labels: the ground truth, and the structural features used to extend it.

WHY THIS EXISTS
---------------
Only 2023 and 2024 publish `CiBillSubjects.csv` (legacy-only file — see
[[knowledge/legacylis_csv_route]]). Every other session in the corpus has NO subject data at all, which
caps any subject-cut analysis at 2 of 18 sessions. Owner, 2026-08-03: *"these subjects will be important
because we dont have nearly enough info yet to build the war room with so this will help expand our
options."*

So the labels have to be EXTENDED to the other sessions. This module supplies the ground truth plus the
three structural keys that extension leans on. It does NOT do the extending — that is `subject_label.py`.

WHAT LIS SUBJECTS ACTUALLY ARE — the thing that took longest to learn
---------------------------------------------------------------------
They are NOT topics. LIS classifies a bill by **which Title of the Code of Virginia it amends**. A wetlands
bill is filed under Fisheries (Title 28.2); a kratom bill under Professions and Occupations (54.1). Reading
a bill and guessing its topic scores WORSE than the token model (measured blind: 80% semantic, 76% when I
applied the code-location rule deliberately, vs 85% for the model). The residual is a cataloguer's
convention, not a meaning problem, so the leverage is in structural keys, not in understanding.

THE THREE KEYS, and why each is structural rather than semantic
---------------------------------------------------------------
- `companion` — same text, both chambers. Companions share >=1 subject **100.0%** of the time (n measured
  in-session), identical sets 97.2%. Not a heuristic: it is the same bill.
- `head` — Virginia titles are `"Elections; early voting."` The phrase before the semicolon is effectively
  the catalogue heading LIS files under. Measured cold (train 2024, test 2023): **96.4% at 36% coverage**.
- `cm` — committee of first referral, from the structural `referral-committee` action class. Committees map
  to Code Titles by jurisdiction, so a high-purity committee implies its subject.
- `a` — abstract tokens. Present for **75% of the corpus** (100% of 2020-2022 and 2024-2027; 43-53% for
  2017-2019; **ZERO for 2023**). Measured lift on a companion-safe split of 2024: coverage at 95% accuracy
  rose 56% -> 62%, full-coverage accuracy 67.9% -> 73.3%.

  WATCH OUT: because 2023 is the session with no abstracts, the cold-session test (seed 2024 -> label 2023)
  is the one measurement in this project that CANNOT see this lift. Judging abstracts by that test alone
  concludes, wrongly, that they are worthless. They were nearly dropped for exactly that reason.

CAUTION FOR ANY FUTURE CALLER
-----------------------------
`hold_out_session()` is the ONLY honest accuracy test here, and the reason is worth keeping: a random
held-out split of 2023-24 scores ~6 points too high, because a held-out bill can be labelled from its
same-session companion — a shortcut no 2017 bill has. Random-split said 95.9%; cold-session said 89.9% for
the same model. Always report the cold-session number.
"""
from __future__ import annotations

import collections
import csv
import io
import os
import pickle
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "historical_cache"))
sys.path.insert(0, _HERE)

CACHE = os.path.join(_HERE, ".subjects_cache.pkl")

# The two sessions that publish subject files. PINNED, not discovered: 242 (2024 special) 404s on both
# subject CSVs, and no other session publishes them at all. A loop that "finds" more is a bug.
LABELLED = {"2023": "231", "2024": "241"}

ABS_KEEP = 12            # rarest-N abstract tokens kept per bill (see build())
STOP = set("the of and for to in a an or by on with certain relating act other generally".split())
_REF = re.compile(r"referred to (?:committee (?:on|for) )?(.+?)(?:\s*$|\()", re.I)


def tok(s: str) -> frozenset:
    return frozenset(x for x in re.findall(r"[a-z]{3,}", (s or "").lower()) if x not in STOP)


def head(title: str) -> str:
    """The catalogue heading: everything before the first ; : or . in the title."""
    h = re.split(r"[;:.]", (title or "").strip())[0]
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", h.lower())).strip()


def committee(rec) -> str:
    """Committee of FIRST referral, from the structural action class (Standard #3). Falls back to the
    description prefix only when the class is absent, which the legacy files sometimes are."""
    for _, desc, cls in rec["actions"]:
        if "'referral-committee'" in (cls or "") or (desc or "").lower().startswith("referred to"):
            m = _REF.search(desc or "")
            if m:
                return rec["chamber"] + " " + re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".")
    return "?"


def _billkey(b: str) -> str:
    return re.sub(r"\s+", "", b).upper()


def _abstracts():
    """{(session, bill): abstract} straight from the Open States archives.

    Read here rather than in corpus.py because only the subject work needs them, and corpus.py is the
    shared loader for every other calibration question. A session whose archive has no abstracts file
    contributes nothing and is NOT an error — measured, 2018S1/2019S1-era and 2023 genuinely have none."""
    import csv as _csv
    import io as _io
    import zipfile
    import corpus as _c

    out = {}
    for zf in sorted(f for f in os.listdir(_c.D) if f.endswith(".zip") and f not in _c.SKIP):
        code = zf[3:-4]
        with zipfile.ZipFile(os.path.join(_c.D, zf)) as z:
            names = z.namelist()
            bpath = next((n for n in names if n.endswith("_bills.csv")), None)
            apath = next((n for n in names if n.endswith("_bill_abstracts.csv")), None)
            if not (bpath and apath):
                continue
            b = list(_csv.DictReader(_io.StringIO(z.read(bpath).decode("utf-8", "replace"))))
            rows = list(_csv.DictReader(_io.StringIO(z.read(apath).decode("utf-8", "replace"))))
        idmap = {x["id"]: x["identifier"] for x in b}
        for r in rows:
            bid = idmap.get(r["bill_id"])
            if bid and r.get("abstract"):
                out.setdefault((code, bid), r["abstract"])
    return out


def build():
    from fetch import read_cached
    from corpus import load

    c = load()
    bills = c["bills"]
    abst = _abstracts()

    # Roll the 654 leaf subjects up to their top-level parents. A leaf like "Concealed weapons" is too
    # sparse to learn; its parent "Weapons" is not.
    parent, parents = {}, set()
    for code in LABELLED.values():
        for r in csv.DictReader(io.StringIO(read_cached(code, "CiParentChildSubjects.csv"))):
            parent[r["Child_Subject"].strip()] = r["Parent_Subject"].strip()
            parents.add(r["Parent_Subject"].strip())

    def roll(s):
        seen = set()
        while s in parent and s not in seen:
            seen.add(s)
            s = parent[s]
        return s

    # The LIS subject vocabulary as a DIRECT lookup: a bill whose catalogue head IS a subject name
    # ("Hate crimes", "Child support") can be filed without any training example. Measured on the
    # labelled sessions: fires on 12% of them at 98.9% accuracy — the most precise route available, and
    # the only one that works for a head the two seed sessions never used. That matters because coverage
    # was worst exactly there: hate crimes 24%, abortion 32%, marijuana 31%, unemployment compensation 0%.
    vocab = {}
    for nm in set(parent) | set(parent.values()):
        top = roll(nm)
        if top in parents:
            k = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", nm.lower())).strip()
            if k:
                vocab.setdefault(k, top)

    raw = collections.defaultdict(set)
    for code in LABELLED.values():
        for r in csv.DictReader(io.StringIO(read_cached(code, "CiBillSubjects.csv"))):
            raw[(code, _billkey(r["Bill_Number"]))].add(r["Subject_Name"].strip())

    truth = {}
    for r in bills:
        code = LABELLED.get(r["session"])
        if not code:
            continue
        ss = raw.get((code, _billkey(r["bill"])))
        if ss:
            t = {roll(s) for s in ss} & parents
            if t:
                truth[(r["session"], r["bill"])] = t

    for r in bills:
        r["cm"] = committee(r)
        r["h"] = head(r["title"])
        r["t"] = tok(r["title"])
        r["a"] = tok(abst.get((r["session"], r["bill"]), ""))

    # Keep only the RAREST tokens of each abstract. Two reasons, both measured:
    #   COST — a full abstract carries ~60 tokens against a title's ~5, and the nearest-neighbour scan is
    #   O(tokens x postings). Unpruned, one pass over the corpus did not finish in 10 minutes.
    #   SIGNAL — a token appearing in a third of all abstracts ("shall", "provides", "board") separates
    #   nothing. The rare ones are what distinguish a wetlands bill from a kratom bill.
    df = collections.Counter()
    for r in bills:
        for w in r["a"]:
            df[w] += 1
    for r in bills:
        if r["a"]:
            # (df, word) not df alone: ties on document frequency must not resolve by frozenset
            # iteration order, which varies with PYTHONHASHSEED and made runs unreproducible.
            r["a"] = frozenset(sorted(r["a"], key=lambda w: (df[w], w))[:ABS_KEEP])

    n_abs = sum(1 for r in bills if r["a"])
    return {"bills": bills, "truth": truth, "parents": parents,
            "vocab": vocab, "n_abstracts": n_abs}


def load_subjects(refresh: bool = False):
    if not refresh and os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    d = build()
    with open(CACHE, "wb") as fh:
        pickle.dump(d, fh, protocol=4)
    return d


if __name__ == "__main__":
    d = load_subjects(refresh="--refresh" in sys.argv)
    B, T = d["bills"], d["truth"]
    print(f"bills {len(B):,}   ground-truth labelled {len(T):,}   top-level subjects {len(d['parents'])}")
    print(f"with an abstract {d['n_abstracts']:,} ({d['n_abstracts']/len(B):.0%})")
    n = collections.Counter(len(v) for v in T.values())
    print("subjects per bill:", ", ".join(f"{k}:{v:,}" for k, v in sorted(n.items())[:6]))
    print(f"distinct head phrases {len({r['h'] for r in B if r['h']}):,}   "
          f"committees {len({r['cm'] for r in B}):,}")
