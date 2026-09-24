#!/usr/bin/env python3
"""Controversy measured from CONTENT, per bill and per legislator -- the multi-signal version.

OWNER, 2026-09-24: "one of the biggest confounds is simply text at all… if there was a way to know just how
controversial something is historically and relative to individual politicans it would be the golden ticket…
its based on more then one stat."

PRE-REGISTERED BEFORE ANY RESULT WAS SEEN (so the result cannot bend the test):
  Unit      one legislator's vote on one floor PASSAGE roll call of an HB/SB that has an introduced summary.
  Predict   yes / no, using ONLY information that exists before that roll call.
  Baseline  what we already know: same party as the patron, patron standing, the legislator's historical
            rate of breaking with their own party (prior years only), chamber.
  Content   + how controversial this CONTENT has been (no-share on the k most similar earlier summaries)
            + how the legislator's PARTY voted on that content
            + how the LEGISLATOR voted on it themself, shrunk toward their party on the same bills.
  History   strictly earlier YEARS; carryover twins excluded (same number, consecutive year).
  Fit       target years 2021, 2022, 2024.   Score  2025, 2026 -- never seen by the fit.
  Verdict   judged where it matters: votes where the legislator's party is NOT the patron's party, on bills
            that turned out contested -- the only place a lobbyist has anything to win.
Source: Open States floor votes + summaries (CC0, cached). Committee votes are not in Open States.
"""
from __future__ import annotations
import sys, os, re, io, csv, glob, zipfile, collections, pickle, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load, _party_lookup
import summary_memory as SM

ZIPS = os.path.join(HERE, "..", "historical_cache", "openstates_va")
CACHE = os.path.join(HERE, "content_votes_cache.pkl")
YEARS = ("2020", "2021", "2022", "2024", "2025", "2026")   # 2023 has no summaries in the source
PARTIES = ("Democratic", "Republican")


# Open States' own vote labels are unusable: EVERY 2024 roll call is classified "['passage']" (including
# "Subcommittee recommends reporting") and every 2025 one is "[]". So venue and DIRECTION are read from the
# motion text. Direction is the contested.py trick: a YES on "laying on the table" is a vote to KILL.
ANTI = re.compile(r"laying on the table|\btabled?\b|passing by indefinitely|passed by indefinitely|strik|"
                  r"continu|failed|defeated|reject", re.I)
PRO = re.compile(r"report|passed|passage|agreed to|adopt", re.I)
PROCEDURAL = re.compile(r"constitutional reading|reading of|rules suspended|reconsider|engross|"
                        r"passed by for the day|motion to|take up|recommit|conference|governor", re.I)


def venue(t):
    tl = t.lower()
    if "subcommittee" in tl:
        return "sub"
    if "reported from" in tl or "committee" in tl:
        return "com"
    return "floor"


def _party_resolver():
    """corpus's resolver, plus one LOCAL fallback: try every given-name token, so "Ware, R. Lee" finds
    Lee Ware (R) not Onzlee Ware (D), and "Fowler, Hyland F. 'Buddy'" finds Buddy Fowler. Local on purpose:
    changing corpus's resolver would silently move every earlier finding."""
    import json
    from corpus import _tk, PEOPLE
    party, person = _party_lookup()
    people = json.load(open(PEOPLE))
    fam = collections.defaultdict(list)
    for nm, rec in people.items():
        t = _tk(nm)
        if len(t) >= 2 and isinstance(rec, dict):
            fam[t[-1]].append((set(t[:-1]), rec.get("party"), nm))
    # SECOND SOURCE: LIS's own member-number party files for 2023/2024 (verified 135/135 and 137/137 against
    # the people file), joined to LIS Members.csv names. Covers members the people file lacks entirely
    # (Hashmi, Guzman) -- the first run dropped 44,178 of their votes.
    sys.path.insert(0, os.path.join(HERE, "..", "historical_cache"))
    from fetch import read_cached
    for code in ("231", "241"):
        pm = json.load(open(os.path.join(HERE, "..", "historical_cache", "va", f"party_{code}.json")))
        for r in csv.DictReader(io.StringIO(read_cached(code, "Members.csv"))):
            nm, pp = r["MBR_NAME"].strip(), pm.get(r["MBR_MBRNO"].strip())
            t = _tk(nm)
            if len(t) >= 2 and pp in PARTIES:
                fam[t[-1]].append((set(t[:-1]), pp, nm))
    def resolve(raw):
        p = party(raw)
        if p in PARTIES:
            return p, person(raw) or raw
        t = _tk(raw)
        if len(t) < 2:
            return None, raw
        hits = [(pp, nm) for giv, pp, nm in fam.get(t[-1], []) if giv & set(t[:-1]) and pp in PARTIES]
        if len({pp for pp, _ in hits}) == 1:
            return hits[0][0], hits[0][1]
        return None, raw
    return resolve


def floor_votes():
    """[(session, bill, rollcall_id, date, venue, [(person, party, SUPPORT01)])] -- every substantive roll
    call on an HB/SB, committee, subcommittee and floor. SUPPORT = voted in the bill's favour."""
    resolve = _party_resolver()
    out, unresolved, skipped = [], collections.Counter(), collections.Counter()
    for s in YEARS:
        z = zipfile.ZipFile(os.path.join(ZIPS, f"VA_{s}.zip"))
        n = z.namelist()
        rd = lambda suf: csv.DictReader(io.TextIOWrapper(z.open([x for x in n if x.endswith(suf)][0]), "utf-8"))
        ident = {r["id"]: r["identifier"] for r in rd("_bills.csv")}
        votes = {}
        for r in rd("_votes.csv"):
            if ident.get(r["bill_id"], "")[:3] not in ("HB ", "SB "):
                continue
            t = r["motion_text"] or ""
            if PROCEDURAL.search(t):
                skipped["procedural"] += 1
                continue
            anti = bool(ANTI.search(t))
            if not anti and not PRO.search(t):
                skipped["unclassified"] += 1
                continue
            votes[r["id"]] = (r, anti)
        ppl = collections.defaultdict(list)
        cache = {}
        for r in rd("_vote_people.csv"):
            v = votes.get(r["vote_event_id"])
            if not v or r["option"] not in ("yes", "no"):
                continue
            nm = r["voter_name"]
            if nm not in cache:
                cache[nm] = resolve(nm)
            pp, who = cache[nm]
            if pp not in PARTIES:
                unresolved[nm] += 1
                continue
            ppl[r["vote_event_id"]].append((who, pp, (r["option"] == "yes") != v[1]))
        for vid, (v, anti) in votes.items():
            if len(ppl[vid]) >= 5:
                out.append((s, ident[v["bill_id"]], vid, v["start_date"], venue(v["motion_text"]), ppl[vid]))
    return out, unresolved, skipped


def build():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    rolls, unresolved, skipped = floor_votes()
    data = {"rolls": rolls, "unresolved": unresolved, "skipped": skipped}
    pickle.dump(data, open(CACHE, "wb"))
    return data


if __name__ == "__main__":
    d = build()
    rolls = d["rolls"]
    print(f"{len(rolls)} substantive roll calls, {sum(len(r[5]) for r in rolls):,} member votes")
    print("by year:", sorted(collections.Counter(r[0] for r in rolls).items()))
    print("by venue:", collections.Counter(r[4] for r in rolls), "| skipped:", dict(d["skipped"]))
    u = d["unresolved"]
    print(f"unresolved names: {len(u)} distinct, {sum(u.values()):,} votes dropped; top: {u.most_common(6)}")


# ------------------------------------------------------------------------------------------------------
# THE TEST
# ------------------------------------------------------------------------------------------------------
K = 10          # neighbours per bill
MIN_J = 0.05    # a neighbour must share at least this much summary content
SHRINK = 3.0    # pseudo-votes pulling a member's content record toward their party's


def neighbours(bills_by_key, summ):
    """(session, bill) -> [(earlier (session, bill), jaccard)] top-K from strictly EARLIER years, carryover
    twins excluded. Summaries have the title stripped (summary_memory.shingles)."""
    keys = [k for k in bills_by_key if k in summ]
    sh = {k: SM.shingles(summ[k], bills_by_key[k]["title"]) for k in keys}
    df = collections.Counter(g for k in keys for g in sh[k])
    inv = collections.defaultdict(list)
    for k in keys:
        for g in sh[k]:
            if df[g] <= 40:
                inv[g].append(k)
    out = {}
    for k in keys:
        S = sh[k]
        if len(S) < 8:
            continue
        yr = int(k[0][:4])
        cand = {c for g in S if df[g] <= 40 for c in inv[g]
                if int(c[0][:4]) < yr and not (c[1] == k[1] and yr - int(c[0][:4]) <= 1)}
        sc = sorted(((len(S & sh[c]) / len(S | sh[c]), c) for c in cand), reverse=True)[:K]
        out[k] = [(c, j) for j, c in sc if j >= MIN_J]
    return out


def run():
    import numpy as np
    import stats
    d = build()
    rolls = [r for r in d["rolls"]]
    corpus = {(r["session"], r["bill"]): r for r in load()["bills"]}
    summ = SM.summaries()
    nb = neighbours({k: v for k, v in corpus.items() if k[0] in YEARS}, summ)

    # per bill: every member ballot, and per-roll-call party majorities (for defection)
    by_bill = collections.defaultdict(list)
    for s, b, vid, date, ven, ballots in rolls:
        maj = {}
        for p in PARTIES:
            xs = [sup for _w, pp, sup in ballots if pp == p]
            if xs:
                maj[p] = sum(xs) / len(xs) >= 0.5
        opp = 1 - sum(sup for *_x, sup in ballots) / len(ballots)
        by_bill[(s, b)].append((vid, ven, ballots, maj, opp))

    # member defection history by YEAR (only votes where the member's party split at all are informative)
    defect = collections.defaultdict(lambda: collections.Counter())      # year -> Counter((who,'n'|'d'))
    for (s, b), rcs in by_bill.items():
        for vid, ven, ballots, maj, opp in rcs:
            for who, pp, sup in ballots:
                if pp in maj:
                    defect[int(s[:4])][(who, "n")] += 1
                    defect[int(s[:4])][(who, "d")] += sup != maj[pp]

    def prior_defect(who, yr):
        n = sum(defect[y][(who, "n")] for y in defect if y < yr)
        dd = sum(defect[y][(who, "d")] for y in defect if y < yr)
        return (dd + 1) / (n + 20)                                           # shrunk toward ~5%

    rows = []
    for (s, b), rcs in by_bill.items():
        bill = corpus.get((s, b))
        if not bill or bill["chief_party"] not in PARTIES or not bill["standing"]:
            continue
        yr = int(s[:4])
        nbs = nb.get((s, b), [])
        # content aggregates from neighbours' roll calls
        n_opp, n_rc = 0.0, 0
        party_sup = {p: [0.0, 0.0] for p in PARTIES}
        mem_sup = collections.defaultdict(lambda: [0.0, 0.0])
        for c, j in nbs:
            for vid, ven, ballots, maj, opp in by_bill.get(c, []):
                n_opp += opp * j
                n_rc += j
                for who, pp, sup in ballots:
                    party_sup[pp][0] += sup * j
                    party_sup[pp][1] += j
                    mem_sup[who][0] += sup * j
                    mem_sup[who][1] += j
        c_opp = n_opp / n_rc if n_rc else None
        for vid, ven, ballots, maj, opp in rcs:
            for who, pp, sup in ballots:
                same = pp == bill["chief_party"]
                ps = party_sup[pp]
                c_party = ps[0] / ps[1] if ps[1] else None
                ms = mem_sup.get(who)
                if c_party is not None and ms and ms[1] > 0:
                    c_mem = (ms[0] + SHRINK * c_party) / (ms[1] + SHRINK)
                    dev = c_mem - c_party
                    has_mem = 1.0
                else:
                    dev, has_mem = 0.0, 0.0
                rows.append({
                    "yr": yr, "y": int(sup), "same": int(same), "maj": int(bill["standing"] == "majority"),
                    "defect": prior_defect(who, yr), "ven_sub": int(ven == "sub"), "ven_com": int(ven == "com"),
                    "has_c": int(c_opp is not None and c_party is not None),
                    "c_opp": c_opp if c_opp is not None else 0.0,
                    "c_party": c_party if c_party is not None else 0.5,
                    "dev": dev, "has_mem": has_mem, "opp_actual": opp,
                })
    return rows


def evaluate(rows):
    import numpy as np
    import stats
    def X(r, content):
        base = [r["same"], r["maj"], r["same"] * r["maj"], r["defect"], r["same"] * r["defect"],
                r["ven_sub"], r["ven_com"]]
        if not content:
            return base
        return base + [r["has_c"], r["has_c"] * r["c_opp"], r["has_c"] * r["c_party"],
                       r["has_c"] * r["c_party"] * r["same"], r["has_mem"] * r["dev"], r["has_mem"]]
    nb_ = ["same", "maj", "same*maj", "defect", "same*defect", "sub", "com"]
    nc_ = nb_ + ["has_content", "content_opposition", "party_support_on_content", "party_support*same",
                 "member_dev_from_party", "has_member_record"]
    train = [r for r in rows if r["yr"] in (2021, 2022, 2024)]
    test = [r for r in rows if r["yr"] in (2025, 2026)]
    res = {}
    for name, content, names in (("baseline", False, nb_), ("content", True, nc_)):
        fit = stats.logit([X(r, content) for r in train], [r["y"] for r in train], names)
        beta = np.array([fit[k][0] for k in ["const"] + names])
        Xt = np.column_stack([np.ones(len(test)), np.array([X(r, content) for r in test], float)])
        with np.errstate(all="ignore"):
            pr = 1 / (1 + np.exp(-(Xt @ beta)))
        res[name] = (fit, pr)
    return train, test, res
