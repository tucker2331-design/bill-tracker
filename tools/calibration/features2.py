#!/usr/bin/env python3
"""Round-2 candidates: the niche signals. Owner's hypothesis, 2026-08-01: *"the real strong signals might
come from even more niche things we didn't expect."*

Owner-named: cross-party patron pairs · district · legislator-to-subject success.
The rest are relational or behavioural signals nothing in the vault proposed — most notably how the PATRON
votes relative to the people who will decide their bill, which is derivable from Vote.csv and which nobody
has looked at.

Same leakage rule: knowable before the committee decides.
"""
import csv, io, re, sys, os, json, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "historical_cache"))
from fetch import read_cached

HERE = os.path.dirname(os.path.abspath(__file__))
VA = os.path.join(HERE, "..", "historical_cache", "va")
SUF = {"jr", "sr", "ii", "iii", "iv", "md", "dr"}

def norm(b):
    m = re.match(r"^([A-Z]+)0*(\d+)$", (b or "").strip().upper())
    return f"{m.group(1)}{m.group(2)}" if m else (b or "").strip().upper()

def _toks(s):
    return [t for t in re.sub(r"[^A-Za-z]", " ", s).lower().split() if t and t not in SUF]

def people_index():
    people = json.load(open(os.path.join(VA, "openstates_va_people.json")))
    fg, fam = {}, collections.defaultdict(list)
    for nm, rec in people.items():
        t = _toks(nm)
        if len(t) >= 2:
            fg[(t[-1], t[0])] = rec; fam[t[-1]].append((t[0], rec))
    return fg, fam

def member_meta(code):
    """LIS member id -> {party, district}. Resolved by name against the Open States roster; ambiguous
    matches resolve to None rather than to a guess."""
    fg, fam = people_index()
    out = {}
    for m in csv.DictReader(io.StringIO(read_cached(code, "Members.csv"))):
        t = re.match(r"^([^,]+),\s*(.+)$", m["MBR_NAME"].strip())
        if not t: continue
        f = _toks(t.group(1))[-1] if _toks(t.group(1)) else ""
        g = (_toks(t.group(2)) or [""])[0]
        rec = fg.get((f, g))
        if rec is None:
            c = fam.get(f, [])
            if len(c) == 1: rec = c[0][1]
            else:
                hits = [r for gg, r in c if gg[:1] == g[:1]]
                rec = hits[0] if len(hits) == 1 else None
        if rec: out[m["MBR_MBRNO"].strip()] = rec
    return out

def vote_profiles(code):
    """member -> {rollcall: +1/-1} over CONTESTED votes only. Unanimous votes carry no information about
    who agrees with whom, so including them would wash every agreement score toward 1.0."""
    prof = collections.defaultdict(dict)
    winners = {}
    for r in csv.reader(io.StringIO(read_cached(code, "Vote.csv"))):
        if not r: continue
        vid = r[0].strip()
        pairs = [(r[i].strip(), r[i + 1].strip()) for i in range(1, len(r) - 1, 2)]
        ys = sum(1 for _, v in pairs if v == "Y"); ns = sum(1 for _, v in pairs if v == "N")
        winners[vid] = 1 if ys > ns else -1
        if ys < 3 or ns < 3: continue
        for mid, v in pairs:
            if v in ("Y", "N"): prof[mid][vid] = 1 if v == "Y" else -1
    return prof, winners

def agreement(prof, a, group, minshared=10):
    vals = []
    for b in group:
        if b == a: continue
        common = set(prof.get(a, {})) & set(prof.get(b, {}))
        if len(common) >= minshared:
            vals.append(sum(1 for v in common if prof[a][v] == prof[b][v]) / len(common))
    return sum(vals) / len(vals) if vals else None

def build2(code, prior=None):
    B = {norm(r["Bill_id"]): r for r in csv.DictReader(io.StringIO(read_cached(code, "Bills.csv")))
         if (r.get("Bill_id") or "").strip()}
    spon = collections.defaultdict(list)
    for r in csv.DictReader(io.StringIO(read_cached(code, "Sponsors.csv"))):
        if (r.get("BILL_NUMBER") or "").strip(): spon[norm(r["BILL_NUMBER"])].append(r)
    subj = collections.defaultdict(list)
    try:
        for r in csv.DictReader(io.StringIO(read_cached(code, "CiBillSubjects.csv"))):
            if (r.get("Bill_Number") or "").strip():
                subj[norm(r["Bill_Number"])].append((r.get("Subject_Name") or "").strip())
    except FileNotFoundError: pass
    cmem = collections.defaultdict(set)
    for r in csv.DictReader(io.StringIO(read_cached(code, "CommitteeMembers.csv"))):
        cmem[(r.get("CMB_COMNO") or "").strip()].add((r.get("CMB_MBRNO") or "").strip())
    meta = member_meta(code)
    prof, winners = vote_profiles(code)
    party = {m: r["party"] for m, r in meta.items()}
    chamber_major = {}
    for ch in ("H", "S"):
        c = collections.Counter(p for m, p in party.items() if m.startswith(ch))
        if c: chamber_major[ch] = c.most_common(1)[0][0]

    def survived(b):
        h = b["Bill_id"].strip().upper().startswith("H")
        return 0 if (b.get("Last_house_actid" if h else "Last_senate_actid") or "").strip().endswith("94") else 1
    def passed(b):
        h = b["Bill_id"].strip().upper().startswith("H")
        return 1 if (b.get("Passed_house" if h else "Passed_senate") or "").strip().upper() == "Y" else 0

    chief_of, cops_of, com_of = {}, {}, {}
    for bid, b in B.items():
        sp = spon.get(bid, [])
        chief_of[bid] = next((r["MEMBER_ID"].strip() for r in sp if (r.get("PATRON_TYPE") or "").startswith("1001")), "")
        cops_of[bid] = [r for r in sp if not (r.get("PATRON_TYPE") or "").startswith("1001")]
        h = bid[0] == "H"
        com_of[bid] = (b.get("Last_house_committee_id" if h else "Last_senate_committee_id") or "").strip()

    # patron behavioural aggregates (from THIS session's votes and sponsorships — all pre-decision)
    generosity = collections.Counter()
    network = collections.defaultdict(set)
    for bid in B:
        for r in cops_of[bid]:
            m = r["MEMBER_ID"].strip()
            generosity[m] += 1
            if chief_of[bid]: network[m].add(chief_of[bid])
    cmte_load = collections.Counter(com_of[b] for b in B if com_of[b])
    # which committee usually handles a subject
    subj_home = {}
    tally = collections.defaultdict(collections.Counter)
    for bid in B:
        for s in subj.get(bid, []): tally[s][com_of[bid]] += 1
    for s, c in tally.items():
        if sum(c.values()) >= 5: subj_home[s] = c.most_common(1)[0][0]
    # patron rank within their own filings (by bill number)
    seq = collections.defaultdict(list)
    for bid in B:
        if chief_of[bid]: seq[chief_of[bid]].append(bid)
    rank = {}
    for m, bs in seq.items():
        for i, bid in enumerate(sorted(bs, key=lambda x: int(re.sub(r"\D", "", x) or 0))): rank[bid] = i + 1

    rows = []
    for bid, b in B.items():
        ch, com = bid[0], com_of[bid]
        chief = chief_of[bid]; cops = cops_of[bid]
        cop_ids = [r["MEMBER_ID"].strip() for r in cops]
        cp = party.get(chief, "")
        cop_parties = [party.get(m, "") for m in cop_ids if party.get(m)]
        maj = chamber_major.get(ch, "")
        chief_cop = next((r["MEMBER_ID"].strip() for r in cops
                          if (r.get("PATRON_TYPE") or "").startswith(("1041", "2041"))), "")
        cmte = cmem.get(com, set())
        same_party = [m for m in party if party[m] == cp and m.startswith(ch)]
        subs = subj.get(bid, [])
        loyal = agreement(prof, chief, same_party) if chief else None
        with_cmte = agreement(prof, chief, list(cmte)) if chief and cmte else None
        mine = prof.get(chief, {})
        won = [v for v in mine if winners.get(v) == mine[v]]
        dis = (meta.get(chief) or {}).get("district", "")
        cop_dis = {(meta.get(m) or {}).get("district", "") for m in cop_ids} - {""}
        f = {
            # --- owner-named ---
            "bipartisan_chief_pair": ("no chief co-patron" if not chief_cop else
                                      "cross-party" if party.get(chief_cop) and cp and party[chief_cop] != cp else "same-party"),
            "patron_district_band": ("unknown" if not dis or not dis.isdigit() else
                                     "1-25" if int(dis) <= 25 else "26-50" if int(dis) <= 50 else
                                     "51-75" if int(dis) <= 75 else "76+"),
            "copatron_district_spread": ("none" if not cop_dis else "1-2" if len(cop_dis) <= 2 else
                                         "3-9" if len(cop_dis) <= 9 else "10+"),
            # --- relational ---
            "majority_copatron_share": ("none" if not cop_parties else
                                        "all-majority" if all(p == maj for p in cop_parties) else
                                        "mixed" if any(p == maj for p in cop_parties) else "none-majority"),
            "cmte_member_copatrons": "Y" if cmte and any(m in cmte for m in cop_ids) else "N",
            "patron_generosity": ("0" if generosity[chief] == 0 else "1-20" if generosity[chief] <= 20
                                  else "21-60" if generosity[chief] <= 60 else "61+"),
            "patron_network_breadth": ("0-5" if len(network[chief]) <= 5 else "6-20" if len(network[chief]) <= 20
                                       else "21+"),
            # --- behavioural, from votes ---
            "patron_party_loyalty": ("unknown" if loyal is None else "<80%" if loyal < .8
                                     else "80-92%" if loyal < .92 else "92%+"),
            "patron_agrees_with_cmte": ("unknown" if with_cmte is None else "<50%" if with_cmte < .5
                                        else "50-65%" if with_cmte < .65 else "65%+"),
            "patron_floor_win_rate": ("unknown" if not mine else
                                      "<60%" if len(won) / len(mine) < .6 else
                                      "60-80%" if len(won) / len(mine) < .8 else "80%+"),
            # --- process / structure ---
            "subject_cmte_match": ("unknown" if not subs or subs[0] not in subj_home else
                                   "usual" if subj_home[subs[0]] == com else "unusual"),
            "cmte_load": ("light" if cmte_load[com] <= 60 else "medium" if cmte_load[com] <= 140 else "heavy"),
            "patron_bill_rank": ("1-3" if rank.get(bid, 99) <= 3 else "4-10" if rank.get(bid, 99) <= 10
                                 else "11-25" if rank.get(bid, 99) <= 25 else "26+"),
            "text_versions": str(min(4, sum(1 for i in range(1, 7) if (b.get(f"Full_text_doc{i}") or "").strip()))),
            "member_id_band": (chief[1:3] if len(chief) >= 3 else "?"),
        }
        if prior:
            ps, = prior
            r = ps.get((chief, subs[0])) if subs else None
            f["patron_prior_on_this_subject"] = ("unknown" if r is None else "poor" if r < .5 else "good")
        rows.append((f, {"survived": survived(b), "passed": passed(b)}, bid, chief, com, subs))
    return rows

def priors2(code, outcome="survived"):
    rows = build2(code)
    ps = collections.defaultdict(lambda: [0, 0])
    for f, y, bid, chief, com, subs in rows:
        if chief and subs: ps[(chief, subs[0])][0] += y[outcome]; ps[(chief, subs[0])][1] += 1
    return ({k: a / n for k, (a, n) in ps.items() if n >= 2},)
