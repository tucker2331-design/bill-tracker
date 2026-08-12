#!/usr/bin/env python3
"""Roll-call votes: 2.75M individual member votes across 100,441 roll calls, 18 sessions.

WHY THIS EXISTS
---------------
Every finding in this project so far describes BILLS — what passes, what dies, which chamber, which
standing. A lobbyist cannot act on any of it directly, because nobody lobbies a chamber. They lobby
PEOPLE, and the only question that changes what they do on a Tuesday morning is *which member, on this
committee, is both gettable and decisive.*

That question needs member-level voting behaviour, which has been sitting unused in every session archive
(`_votes.csv` + `_vote_people.csv`) the whole time.

THE TWO MEASURES, and why both are needed
------------------------------------------
- **DEFECTION** — how often a member votes against the majority of their own party on the same roll call.
  A member who never defects cannot be moved by argument; their vote is decided by their caucus. A member
  who defects often is where persuasion has somewhere to go. This is *gettable*.
- **PIVOTALITY** — how often the member sat on the winning side of a vote decided by a margin small enough
  that their single vote would have changed it. This is *decisive*.

Neither alone is useful. A backbencher who defects constantly on lopsided votes is gettable and irrelevant;
a chair on a safe seat is decisive and immovable. **The product is the intersection.**

IDENTITY IS NOT THE NAME STRING
--------------------------------
`voter_name` has the same session-to-session format drift that hid 2,000 bills from every patron finding
([[failures/assumptions_audit]] #115): a member appears as "Hashmi, Ghazala F." in one session and
"Ghazala F. Hashmi" in another. Every join here goes through `corpus`'s canonical person resolver, and an
unresolvable name is COUNTED, never silently dropped.

WHAT THIS DELIBERATELY DOES NOT CLAIM
--------------------------------------
A defection rate is a description of past behaviour, not a prediction that a member will flip on a given
bill. It is reported with its denominator, and the calibration of "does defection actually predict
anything" is a separate measured question — see `--validate`.
"""
from __future__ import annotations

import collections
import csv
import io
import os
import pickle
import re
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

CACHE = os.path.join(_HERE, ".votes_cache.pkl")
MIN_VOTES = 40          # below this a defection rate is noise, not a trait


def _rows(z, suffix):
    n = [x for x in z.namelist() if x.endswith(suffix)]
    if not n:
        return []
    return list(csv.DictReader(io.TextIOWrapper(z.open(n[0]), encoding="utf-8", errors="replace")))


def _identity(C):
    """Resolve a `voter_name` to a canonical person, using the CHAMBER when the name alone is ambiguous.

    Three failure modes were measured on the raw data, together losing 146,220 votes (5.4%):

    1. **Bare surnames** — "Howell", "Fowler", "Campbell". Ambiguous statewide (three Howells serve across
       the corpus) so a fail-closed lookup returns nothing. **Chamber resolves nearly all of them**: only
       one Howell sits in the Senate. The roll call knows its chamber, so the lookup is given it.
    2. **Initial-first names** — "R. Lee Ware" keys on "r" while the roster says "Lee Ware". Any name whose
       first token is a single letter is retried on its SECOND token.
    3. **Genuinely absent from the roster** — Hashmi, Brewer and Guzman are real legislators the Open States
       people file simply does not contain (350 entries). No string trick fixes a missing row; they are
       given a stable synthetic identity from surname+chamber so their VOTES still count, and their party
       is resolved separately (see `_infer_parties`).

    Returns (resolve(name, chamber) -> canonical_id_or_None, party_of_canonical).
    """
    import json
    people = json.load(open(C.PEOPLE))
    fam = collections.defaultdict(list)
    for nm in people:
        t = C._tk(nm)
        if t:
            fam[t[-1]].append((t[0], nm))
    party = {nm: (rec["party"] if isinstance(rec, dict) else rec) for nm, rec in people.items()}
    # chamber of each roster member, learned from the chambers they actually vote in (no roster field
    # carries it). Filled by the caller before resolution is used in anger.
    chamber_of = {}

    def resolve(nm, chamber):
        t = C._tk(nm)
        if not t:
            return None
        cands = fam.get(t[-1], [])
        if len(t) >= 2:
            exact = [n for g, n in cands if g == t[0]]
            if len(exact) == 1:
                return exact[0]
            if len(t) >= 3 and len(t[0]) == 1:          # "R. Lee Ware" -> try "lee"
                exact = [n for g, n in cands if g == t[1]]
                if len(exact) == 1:
                    return exact[0]
            ini = [n for g, n in cands if g[:1] == t[0][:1]]
            if len(ini) == 1:
                return ini[0]
        if len(cands) == 1:
            return cands[0][1]
        if chamber:                                      # disambiguate a bare surname by chamber
            inch = [n for _g, n in cands if chamber_of.get(n) == chamber]
            if len(inch) == 1:
                return inch[0]
        return None

    return resolve, party, chamber_of


def _infer_parties(votes, known):
    """Assign a party to members the roster does not carry, from who they vote WITH.

    Hashmi, Brewer and Guzman are real legislators absent from the 350-entry people file, and no string
    matching invents a missing row. But party is not actually hidden in these data: a member's agreement
    rate with each caucus separates cleanly, so it is DERIVED rather than hardcoded (Standard #1) — and
    then VALIDATED, by re-predicting members whose party IS known and measuring how often it agrees.

    NOT the same as the chamber-control derivation this project already got wrong twice: that inferred a
    52-48 body-level majority from a roster with a few percent unresolved, where a handful of errors flips
    the answer. This is a per-member question with hundreds of observations each.
    """
    agree = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    byev = collections.defaultdict(list)
    for v in votes:
        byev[v["event"]].append(v)
    for members in byev.values():
        for v in members:
            for w in members:
                if w["member"] == v["member"] or not known.get(w["member"]):
                    continue
                a = agree[v["member"]][known[w["member"]]]
                a[1] += 1
                a[0] += (v["opt"] == w["opt"])
    out, scores = {}, {}
    for mem, tallies in agree.items():
        rates = {p: h / n for p, (h, n) in tallies.items() if n >= 200}
        if len(rates) < 2:
            continue
        best = max(rates, key=lambda p: rates[p])
        second = max((p for p in rates if p != best), key=lambda p: rates[p])
        # a real separation, not a coin flip: require a clear gap between the two caucuses
        if rates[best] - rates[second] >= 0.10:
            out[mem] = best
            scores[mem] = rates[best] - rates[second]
    return out, scores


def build():
    import corpus as C
    resolve, party_tbl, chamber_of = _identity(C)

    votes, events = [], {}
    unresolved = collections.Counter()
    synthetic = {}
    order = sorted(f for f in os.listdir(C.D) if f.endswith(".zip") and f not in C.SKIP)

    # PASS 1 — learn which chamber each roster member votes in, so a bare surname can be disambiguated.
    # Done first and separately because resolution DEPENDS on it: doing both in one pass would resolve the
    # early sessions with an empty chamber map and the late ones with a full one, i.e. a different rule per
    # session, which is exactly the kind of silent inconsistency this project keeps paying for.
    chamber_votes = collections.defaultdict(collections.Counter)
    parsed = []

    # ORGANIZATIONS ARE CORPUS-WIDE, NOT PER-SESSION. Open States ids are global, but each archive ships
    # only the organizations it happens to define, so a roll call routinely references an org defined in a
    # DIFFERENT session's file. Looked up per-session, 22,791 roll calls (33%) came back with a blank venue
    # and were silently unclassifiable — while their motion text plainly said "Read third time and passed
    # House". The union of every archive's organizations.csv resolves them.
    orgs = {}
    for zf in order:
        try:
            zz = zipfile.ZipFile(os.path.join(C.D, zf))
        except zipfile.BadZipFile:
            continue
        for o in _rows(zz, "_organizations.csv"):
            orgs.setdefault(o["id"], o)
    for zf in order:
        code = zf[3:-4]
        year = int(re.match(r"(\d{4})", code).group(1))
        if year not in C.CONTROL:
            continue
        z = zipfile.ZipFile(os.path.join(C.D, zf))
        ev, vp = _rows(z, "_votes.csv"), _rows(z, "_vote_people.csv")
        if not (ev and vp):
            continue                      # a session Open States never captured member votes for
        bills = {x["id"]: x["identifier"] for x in _rows(z, "_bills.csv")}

        def chamber_of_org(oid):
            seen = set()
            while oid and oid in orgs and oid not in seen:
                seen.add(oid)
                cl = orgs[oid].get("classification")
                if cl == "lower":
                    return "H"
                if cl == "upper":
                    return "S"
                oid = orgs[oid].get("parent_id")
            return None

        meta = {}
        for e in ev:
            ch = chamber_of_org(e.get("organization_id"))
            oid = e.get("organization_id") or ""
            meta[e["id"]] = {"session": code, "year": year, "bill": bills.get(e.get("bill_id") or ""),
                             "motion": e.get("motion_text", ""), "result": e.get("result", ""),
                             "date": e.get("start_date", ""), "org": oid,
                             "org_name": (orgs.get(oid) or {}).get("name", ""),
                             "org_cls": (orgs.get(oid) or {}).get("classification", ""),
                             "chamber": ch, "cls": e.get("motion_classification", "")}
        parsed.append((meta, vp))
        for r in vp:
            ch = (meta.get(r["vote_event_id"]) or {}).get("chamber")
            nm = r.get("voter_name") or ""
            who = resolve(nm, None)
            if who and ch:
                chamber_votes[who][ch] += 1
    for who, cc in chamber_votes.items():
        chamber_of[who] = cc.most_common(1)[0][0]

    # PASS 2 — resolve for real, now that chamber is known.
    dup_guard = collections.Counter()
    for meta, vp in parsed:
        byev = collections.defaultdict(list)
        for r in vp:
            opt = (r.get("option") or "").lower()
            if opt not in ("yes", "no"):
                continue                  # abstain / not voting carry no directional signal
            m = meta.get(r["vote_event_id"])
            if m is None:
                unresolved["<no matching roll call>"] += 1
                continue
            nm = (r.get("voter_name") or "").strip()
            who = resolve(nm, m["chamber"])
            if who is None:
                # Real people the roster omits. A stable synthetic id keeps their votes in the dataset
                # (pivotality needs no party); FAIL CLOSED on party rather than guessing a caucus here.
                if nm.lower().startswith("mr. speaker") or not nm:
                    unresolved[nm or "<blank>"] += 1
                    continue
                t = C._tk(nm)
                if not t:
                    unresolved[nm] += 1
                    continue
                who = f"~{t[-1]}|{m['chamber'] or '?'}"
                synthetic[who] = nm
            byev[r["vote_event_id"]].append((who, party_tbl.get(who), opt))
            dup_guard[(r["vote_event_id"], who)] += 1

        for eid, members in byev.items():
            m = meta[eid]
            yes = sum(1 for _c, _p, o in members if o == "yes")
            no = len(members) - yes
            pmaj = {}
            for pty in {p for _c, p, _o in members if p}:
                py = sum(1 for _c, p, o in members if p == pty and o == "yes")
                pn = sum(1 for _c, p, o in members if p == pty and o == "no")
                if py != pn:
                    pmaj[pty] = "yes" if py > pn else "no"
            winner = "yes" if yes > no else "no"
            events[eid] = {**m, "yes": yes, "no": no, "margin": abs(yes - no),
                           "winner": winner, "n": len(members)}
            for who, pty, opt in members:
                votes.append({"event": eid, "member": who, "party": pty, "opt": opt,
                              "session": m["session"], "year": m["year"], "bill": m["bill"],
                              "org": m["org"], "org_name": m["org_name"], "org_cls": m["org_cls"],
                              "chamber": m["chamber"],
                              "defect": bool(pty and pty in pmaj and opt != pmaj[pty]),
                              "with_winner": opt == winner,
                              "margin": abs(yes - no), "n": len(members)})

    # A MEMBER MAY VOTE ONCE PER ROLL CALL. More than one row for the same (roll call, member) means two
    # spellings resolved to one identity — which is how Convirs-Fowler's votes were being added to Fowler's.
    # Counted and surfaced rather than quietly deduped, because a rising count means identity is breaking
    # again and the metrics built on it are wrong before anyone notices.
    collisions = {k: n for k, n in dup_guard.items() if n > 1}
    seen_pair = set()
    deduped = []
    for v in votes:
        key = (v["event"], v["member"])
        if key in seen_pair:
            continue
        seen_pair.add(key)
        deduped.append(v)
    votes = deduped

    # PASS 3 — parties for members the roster omits, derived and then validated.
    known = {m: party_tbl.get(m) for m in {v["member"] for v in votes} if party_tbl.get(m)}
    inferred, gaps = _infer_parties(votes, known)
    holdout_hits = holdout_n = 0
    for mem, p in inferred.items():
        if mem in known:
            holdout_n += 1
            holdout_hits += (p == known[mem])
    newly = {m: p for m, p in inferred.items() if m not in known}
    for v in votes:
        if v["party"] is None and v["member"] in newly:
            v["party"] = newly[v["member"]]
    # defection needs recomputing for the rows that only just acquired a party
    byev = collections.defaultdict(list)
    for v in votes:
        byev[v["event"]].append(v)
    for members in byev.values():
        pmaj = {}
        for pty in {v["party"] for v in members if v["party"]}:
            py = sum(1 for v in members if v["party"] == pty and v["opt"] == "yes")
            pn = sum(1 for v in members if v["party"] == pty and v["opt"] == "no")
            if py != pn:
                pmaj[pty] = "yes" if py > pn else "no"
        for v in members:
            v["defect"] = bool(v["party"] and v["party"] in pmaj and v["opt"] != pmaj[v["party"]])

    return {"votes": votes, "events": events, "unresolved": unresolved,
            "identity_collisions": len(collisions),
            "synthetic": synthetic, "inferred_party": newly,
            "party_validation": (holdout_hits, holdout_n)}


def load(refresh=False):
    if not refresh and os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    d = build()
    with open(CACHE, "wb") as fh:
        pickle.dump(d, fh, protocol=4)
    return d


def persuadability(d, years=(2024, 2025, 2026), min_votes=300):
    """Within-cohort z-score of a member's defection rate. Higher = more often votes against their caucus.

    WHY A Z-SCORE AND NOT THE RAW RATE. Defection is dominated by structural position, not temperament:
    House minority members defect 5.8% against 1.2% for the majority, Senate 2.0% against 0.7%. A raw
    ranking is therefore just a list of minority-party House members, which tells a lobbyist nothing they
    did not already know. Even excess-over-cohort in percentage POINTS still favours the high-baseline
    cohorts and never surfaces a Senator. The z-score compares a member only against others in the same
    chamber, same party-status, same year.

    VALIDATED AS A TRAIT, not a description: a member's score predicts their NEXT year's score at r = 0.68
    (n=602 member-pairs). Bottom quartile one year averages z = -0.63 the next; top quartile +0.90.
    """
    import statistics
    def cohort(v):
        if not v["chamber"] or not v["party"]:
            return None
        ctrl = _control().get(v["year"])
        if not ctrl:
            return None
        maj = ctrl[0] if v["chamber"] == "H" else ctrl[1]
        return (v["chamber"], v["year"], "maj" if v["party"] == maj else "min")

    ms = collections.defaultdict(lambda: [0, 0, None, None])
    for v in d["votes"]:
        k = cohort(v)
        if not k:
            continue
        a = ms[(v["member"], v["year"])]
        a[1] += 1
        a[0] += v["defect"]
        a[2], a[3] = k, v["party"]
    seasons = [(m, y, h / n, k, p, n) for (m, y), (h, n, k, p) in ms.items() if n >= 100]
    bycoh = collections.defaultdict(list)
    for _m, _y, r, k, _p, _n in seasons:
        bycoh[k].append(r)
    # a cohort with too few members has no meaningful spread; FAIL CLOSED rather than divide by ~0
    stats = {k: (statistics.mean(v), statistics.pstdev(v)) for k, v in bycoh.items()
             if len(v) >= 8 and statistics.pstdev(v) > 0}
    agg = collections.defaultdict(list)
    for m, y, r, k, p, n in seasons:
        if k not in stats or y not in years:
            continue
        mu, sd = stats[k]
        agg[(m, k[0], p, k[2])].append(((r - mu) / sd, r, n))
    out = []
    for (m, ch, p, pos), vals in agg.items():
        n = sum(x[2] for x in vals)
        if n < min_votes:
            continue
        out.append({"member": d["synthetic"].get(m, m), "chamber": ch, "party": p, "position": pos,
                    "score": statistics.mean(x[0] for x in vals),
                    "defect_rate": sum(x[1] * x[2] for x in vals) / n, "votes": n})
    out.sort(key=lambda r: -r["score"])
    return out


def _control():
    import corpus as C
    return C.CONTROL


def main() -> int:
    d = load(refresh="--refresh" in sys.argv)
    V, E = d["votes"], d["events"]
    print(f"roll calls {len(E):,}   member-votes {len(V):,}")
    ur = sum(d["unresolved"].values())
    print(f"unresolved voter names: {ur:,} votes across {len(d['unresolved'])} spellings"
          f"{'  e.g. ' + str([k for k, _ in d['unresolved'].most_common(3)]) if ur else ''}")
    print(f"sessions {len(set(e['year'] for e in E.values()))}   "
          f"members {len(set(v['member'] for v in V)):,}")
    md = collections.Counter(e["margin"] for e in E.values())
    close = sum(n for m, n in md.items() if m <= 2)
    print(f"roll calls decided by <=2 votes: {close:,} ({close/len(E):.0%})")
    hits, n = d["party_validation"]
    if n:
        print(f"party inference VALIDATED on members whose party is known: {hits}/{n} = {hits/n:.1%}")
    print(f"parties derived for members absent from the roster: {len(d['inferred_party'])}")
    print(f"synthetic identities (real members the roster omits): {len(d['synthetic'])}")
    print(f"identity collisions (two spellings, one roll call, same member): {d['identity_collisions']:,}")
    noparty = sum(1 for v in V if not v["party"])
    print(f"votes still without a party (excluded from DEFECTION only): {noparty:,} ({noparty/len(V):.1%})")
    if "--swing" in sys.argv:
        rows = persuadability(d)
        print("\nPERSUADABILITY — within-cohort z of defection rate, 2024-2026, >=300 votes")
        print("  validated as a trait: predicts next year at r=0.68 (n=602 member-pairs)")
        for ch, lbl in (("S", "SENATE"), ("H", "HOUSE")):
            print(f"\n  {lbl}")
            print(f"  {'member':<26}{'party':>5}{'pos':>5}{'score':>7}{'defects':>9}{'votes':>8}")
            for r in [x for x in rows if x["chamber"] == ch][:8]:
                print(f"  {r['member'][:24]:<26}{r['party'][:3]:>5}{r['position']:>5}"
                      f"{r['score']:>+7.1f}{r['defect_rate']:>8.1%}{r['votes']:>8,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
