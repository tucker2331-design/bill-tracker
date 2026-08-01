#!/usr/bin/env python3
"""Every candidate stat the vault proposed, plus the ones the first pass was missing.

Sources for the list (not invented here):
  ideas/predictive_lane §"objects and the stats each would carry" — member / committee / subject / patron
  ideas/lobbyist_jtbd_ideation C3 committee math · C5 patron scouting · D2 mortality tables · D4 bills-like-this
  war_room_v8 subject profile · M6 panel slots

LEAKAGE RULE: only what is knowable BEFORE the committee decides. Anything computed from the bill's own
later history is the outcome in disguise.
"""
import csv, io, re, sys, os, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "historical_cache"))
from fetch import read_cached

def norm(b):
    m = re.match(r"^([A-Z]+)0*(\d+)$", (b or "").strip().upper())
    return f"{m.group(1)}{m.group(2)}" if m else (b or "").strip().upper()

def party_map(code):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "historical_cache", "va", f"party_{code}.json")
    return json.load(open(p)) if os.path.exists(p) else {}

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
    cmem = collections.defaultdict(set)
    for r in csv.DictReader(io.StringIO(read_cached(code, "CommitteeMembers.csv"))):
        cmem[(r.get("CMB_COMNO") or "").strip()].add((r.get("CMB_MBRNO") or "").strip())
    cnames = {(r.get("COM_COMNO") or "").strip(): (r.get("COM_NAME") or "").strip()
              for r in csv.DictReader(io.StringIO(read_cached(code, "Committees.csv")))}
    hist = collections.defaultdict(list)
    for r in csv.DictReader(io.StringIO(read_cached(code, "History.csv"))):
        b = norm(r.get("Bill_id", ""))
        if b: hist[b].append(r)
    return B, spon, subj, cmem, cnames, hist, party_map(code)

def survived_committee(b):
    """Structural: Last_*_actid ending in '94' is 'Left in <committee>'. Verified 621/621 (2023),
    487/488 (2024) — no text parsing."""
    h = b["Bill_id"].strip().upper().startswith("H")
    aid = (b.get("Last_house_actid" if h else "Last_senate_actid") or "").strip()
    return 0 if aid.endswith("94") else 1

def passed_origin(b):
    h = b["Bill_id"].strip().upper().startswith("H")
    return 1 if (b.get("Passed_house" if h else "Passed_senate") or "").strip().upper() == "Y" else 0

MONEY = re.compile(r"appropriat|finance", re.I)

def build(code, prior=None):
    B, spon, subj, cmem, cnames, hist, party = load(code)
    # chamber majority party, computed from the roster we derived (not assumed)
    chamber_party = collections.defaultdict(collections.Counter)
    for mid, p in party.items():
        chamber_party[mid[0]][p] += 1
    majority = {ch: c.most_common(1)[0][0] for ch, c in chamber_party.items()}
    # committee majority party
    cmaj = {}
    for com, members in cmem.items():
        c = collections.Counter(party[m] for m in members if m in party)
        if c: cmaj[com] = c.most_common(1)[0][0]

    rows = []
    for bid, b in B.items():
        ch = bid[0]
        h = ch == "H"
        com = (b.get("Last_house_committee_id" if h else "Last_senate_committee_id") or "").strip()
        sp = spon.get(bid, [])
        chief = next((r["MEMBER_ID"].strip() for r in sp if (r.get("PATRON_TYPE") or "").startswith("1001")), "")
        cops = [r for r in sp if not (r.get("PATRON_TYPE") or "").startswith("1001")]
        cop_ids = [r["MEMBER_ID"].strip() for r in cops]
        pparty = party.get(chief, "")
        cop_parties = collections.Counter(party.get(m, "") for m in cop_ids if party.get(m))
        subs = subj.get(bid, [])
        # days from introduction to the FIRST recorded action (speed) — knowable early
        dates = sorted((r.get("History_date") or "").strip() for r in hist.get(bid, []) if r.get("History_date"))
        f = {
            "bill_type": re.match(r"^([A-Z]+)", bid).group(1),
            "chamber": ch,
            "committee": com or "(none)",
            "patron_count": "1" if len(sp) <= 1 else "2-3" if len(sp) <= 3 else "4-9" if len(sp) <= 9 else "10+",
            "emergency": "Y" if (b.get("Emergency") or "").strip().upper() == "Y" else "N",
            "prefiled": "prefiled" if (b.get("Introduction_date") or "")[:2] in ("11", "12") else "in-session",
            "subject_primary": subs[0] if subs else "(none)",
            "subject_count": "0" if not subs else "1" if len(subs) == 1 else "2-3" if len(subs) <= 3 else "4+",
            "patron_on_cmte": "Y" if chief and com and chief in cmem.get(com, set()) else "N",
            # --- NEW: party, the gap the first pass could not test ---
            "patron_party": pparty or "unknown",
            "patron_in_majority": ("unknown" if not pparty else
                                   "majority" if pparty == majority.get(ch) else "minority"),
            "patron_matches_cmte_majority": ("unknown" if not (pparty and com in cmaj) else
                                             "same" if pparty == cmaj[com] else "opposed"),
            # --- NEW: co-patron structure (the PATRON_TYPE vocabulary, not just a count) ---
            "has_chief_copatron": "Y" if any((r.get("PATRON_TYPE") or "").startswith(("1041", "2041", "1042", "1043", "1044")) for r in cops) else "N",
            "bipartisan_copatrons": ("none" if not cop_parties else
                                     "bipartisan" if len(cop_parties) > 1 else "one-party"),
            "cross_chamber_copatrons": "Y" if any((r.get("PATRON_TYPE") or "").startswith("2") for r in cops) else "N",
            # --- NEW: committee character ---
            "money_committee": "Y" if MONEY.search(cnames.get(com, "")) else "N",
            "committee_size": ("small" if len(cmem.get(com, ())) <= 12 else
                               "medium" if len(cmem.get(com, ())) <= 20 else "large") if com in cmem else "unknown",
            # --- NEW: patron workload ---
            "patron_volume": "",   # filled below (needs the full pass)
        }
        rows.append((f, {"survived": survived_committee(b), "passed": passed_origin(b)}, bid, chief, com, subs))
    vol = collections.Counter(chief for _, _, _, chief, _, _ in rows if chief)
    for f, _, _, chief, _, _ in rows:
        n = vol.get(chief, 0)
        f["patron_volume"] = "1-5" if n <= 5 else "6-15" if n <= 15 else "16-30" if n <= 30 else "31+"
    if prior:
        pr, pc, sc = prior
        for f, _, _, chief, com, subs in rows:
            r = pr.get(chief)
            f["patron_prior_rate"] = ("unknown" if r is None else "<40%" if r < .4 else "40-70%" if r < .7 else "70%+")
            r = pc.get((chief, com))
            f["patron_prior_in_this_cmte"] = ("unknown" if r is None else "poor" if r < .5 else "good")
            k = (com, subs[0]) if subs else None
            r = sc.get(k) if k else None
            f["cmte_prior_on_this_subject"] = ("unknown" if r is None else "<50%" if r < .5 else "50-80%" if r < .8 else "80%+")
    return rows

def priors(code, outcome="survived"):
    rows = build(code)
    pr = collections.defaultdict(lambda: [0, 0]); pc = collections.defaultdict(lambda: [0, 0])
    sc = collections.defaultdict(lambda: [0, 0])
    for f, y, _, chief, com, subs in rows:
        v = y[outcome]
        if chief: pr[chief][0] += v; pr[chief][1] += 1
        if chief and com: pc[(chief, com)][0] += v; pc[(chief, com)][1] += 1
        if com and subs: sc[(com, subs[0])][0] += v; sc[(com, subs[0])][1] += 1
    f3 = lambda d, k: {a: y / n for a, (y, n) in d.items() if n >= k}
    return f3(pr, 3), f3(pc, 3), f3(sc, 5)
