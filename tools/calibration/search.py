#!/usr/bin/env python3
"""Candidate-stat SEARCH: score every fact we could know about a bill BEFORE its committee decides.

Owner, 2026-08-01: *"we aren't just trying to see if our existing ideas are valid and correlate but also
see if any stats could be useful."* Correct — the earlier pass tested one stat we had already decided to
show, which is grading our own homework. This searches the space instead.

METHOD (identical for every candidate, so nothing gets a favourable ruleset):
  1. Fit  on 2023: for each bucket of a feature, the observed pass rate.
  2. Predict 2024 using ONLY those 2023 rates.
  3. Score against the NULL — "assume every bill behaves like the 2023 average".
  Improvement = how much mean absolute error drops vs that null. Negative means the stat is WORSE
  than knowing nothing, which is a real and useful outcome.

LEAKAGE RULE: only features knowable at the moment the question is asked. A bill that passes accumulates
more history rows, so "number of actions" would score brilliantly and predict nothing — it is the outcome
wearing a feature's clothes. Excluded by construction, not by hoping.

Unseen buckets (a committee or subject present in 2024 but not 2023) fall back to the 2023 base rate and
are COUNTED, never dropped — dropping them would quietly grade the stat only where it happens to be
confident.
"""
import sys, csv, io, re, collections, statistics, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "historical_cache"))
from fetch import read_cached

def norm(b):
    m = re.match(r"^([A-Z]+)0*(\d+)$", (b or "").strip().upper())
    return f"{m.group(1)}{m.group(2)}" if m else (b or "").strip().upper()

def load(code):
    B = {norm(r["Bill_id"]): r for r in csv.DictReader(io.StringIO(read_cached(code, "Bills.csv")))
         if (r.get("Bill_id") or "").strip()}
    spon = collections.defaultdict(list)
    for r in csv.DictReader(io.StringIO(read_cached(code, "Sponsors.csv"))):
        if (r.get("BILL_NUMBER") or "").strip():
            spon[norm(r["BILL_NUMBER"])].append(r)
    subj = collections.defaultdict(list)
    try:
        for r in csv.DictReader(io.StringIO(read_cached(code, "CiBillSubjects.csv"))):
            if (r.get("Bill_Number") or "").strip():
                subj[norm(r["Bill_Number"])].append((r.get("Subject_Name") or "").strip())
    except FileNotFoundError:
        pass
    cmem = collections.defaultdict(set)          # committee -> {member ids}
    for r in csv.DictReader(io.StringIO(read_cached(code, "CommitteeMembers.csv"))):
        cmem[(r.get("CMB_COMNO") or "").strip()].add((r.get("CMB_MBRNO") or "").strip())
    return B, spon, subj, cmem

def outcome(bill):
    """Did it pass its chamber of origin? Structural flags only."""
    col = "Passed_house" if bill["Bill_id"].strip().upper().startswith("H") else "Passed_senate"
    return 1 if (bill.get(col) or "").strip().upper() == "Y" else 0

def committee_of(bill):
    h = bill.get("Last_house_committee_id", "").strip()
    s = bill.get("Last_senate_committee_id", "").strip()
    return (h if bill["Bill_id"].strip().upper().startswith("H") else s) or ""

def chief(spon_rows):
    for r in spon_rows:
        if (r.get("PATRON_TYPE") or "").startswith("1001"):
            return (r.get("MEMBER_ID") or "").strip()
    return ""

def build(code, prior_patron_rate=None):
    B, spon, subj, cmem = load(code)
    out = []
    for bid, b in B.items():
        rows = spon.get(bid, [])
        npat = len(rows)
        ch = chief(rows)
        com = committee_of(b)
        kind = re.match(r"^([A-Z]+)", bid).group(1)
        intro = (b.get("Introduction_date") or "").strip()
        subs = subj.get(bid, [])
        feats = {
            "bill_type":        kind,
            "chamber":          bid[0],
            "committee":        com or "(none)",
            "patron_count":     "1" if npat <= 1 else "2-3" if npat <= 3 else "4-9" if npat <= 9 else "10+",
            "emergency":        "Y" if (b.get("Emergency") or "").strip().upper() == "Y" else "N",
            "prefiled":         "prefiled" if intro[:2] in ("11", "12") else "in-session",
            "bill_number_band": ("1-99" if int(re.sub(r"\D", "", bid) or 0) < 100
                                 else "100-499" if int(re.sub(r"\D", "", bid) or 0) < 500
                                 else "500+"),
            "subject_primary":  subs[0] if subs else "(none)",
            "subject_count":    "0" if not subs else "1" if len(subs) == 1 else "2-3" if len(subs) <= 3 else "4+",
            "patron_on_cmte":   ("Y" if ch and com and ch in cmem.get(com, set()) else "N"),
        }
        if prior_patron_rate is not None:
            r = prior_patron_rate.get(ch)
            feats["patron_prior_rate"] = ("unknown" if r is None else
                                          "<40%" if r < .4 else "40-70%" if r < .7 else "70%+")
        out.append((feats, outcome(b), bid))
    return out

def patron_rates(code):
    B, spon, _, _ = load(code)
    agg = collections.defaultdict(lambda: [0, 0])
    for bid, b in B.items():
        ch = chief(spon.get(bid, []))
        if not ch:
            continue
        agg[ch][0] += outcome(b); agg[ch][1] += 1
    return {k: y / n for k, (y, n) in agg.items() if n >= 3}   # >=3 bills or the "rate" is one coin flip

def score(train, test, feat):
    base = statistics.mean(y for _, y, _ in train)
    agg = collections.defaultdict(lambda: [0, 0])
    for f, y, _ in train:
        a = agg[f[feat]]; a[0] += y; a[1] += 1
    rate = {k: y / n for k, (y, n) in agg.items() if n >= 5}    # a bucket needs >=5 to state a rate
    err_s = err_n = 0.0; unseen = 0
    for f, y, _ in test:
        p = rate.get(f[feat])
        if p is None:
            p = base; unseen += 1
        err_s += abs(p - y); err_n += abs(base - y)
    n = len(test)
    return (err_n - err_s) / err_n * 100, len(rate), unseen / n * 100, err_s / n

if __name__ == "__main__":
    pr = patron_rates("231")
    train = build("231")
    test = build("241", prior_patron_rate=pr)
    train_pp = build("231", prior_patron_rate=patron_rates("231"))  # placeholder key so the feature exists
    base = statistics.mean(y for _, y, _ in train)
    print(f"fit on 2023 ({len(train):,} bills) -> tested on 2024 ({len(test):,} bills)")
    print(f"null model = the 2023 base rate, {base:.1%} of bills pass their chamber of origin\n")
    print(f"{'candidate stat':22} {'better than null':>16} {'buckets':>8} {'unseen':>8}")
    print("-" * 58)
    feats = [k for k in train[0][0] if k != "patron_prior_rate"]
    res = []
    for f in feats:
        imp, nb, un, mae = score(train, test, f)
        res.append((imp, f, nb, un))
    imp, nb, un, mae = score(train_pp, test, "patron_prior_rate")
    res.append((imp, "patron_prior_rate", nb, un))
    for imp, f, nb, un in sorted(res, reverse=True):
        flag = "  <-- signal" if imp >= 5 else ("  (noise)" if imp < 1 else "")
        print(f"{f:22} {imp:>14.1f}% {nb:>8} {un:>7.0f}%{flag}")
