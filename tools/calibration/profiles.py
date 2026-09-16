#!/usr/bin/env python3
"""What to put on the two War Room surfaces: the ROOM panel and the MEMBER panel.

THE ASK (owner, 2026-09-16): "we have info on the committee and info on the committee members. but not
much on either. find more for both of those. you know what doesnt work so find what does."

WHAT DOES NOT WORK is settled: ten member-level "who can be moved" hypotheses are null or collapse
([[testing/member_signals]], [[testing/money_and_vulnerability]]). 86% of subcommittee kills have nobody
crossing, so there is little persuasion to detect. Everything here is therefore DESCRIPTIVE — properties
of a room or a person that a lobbyist reads, not a prediction that anyone can be moved.

A VERB-FORM BUG WAS FOUND WRITING THIS, and it is the pre-push audit's own point #1. The fatal-action
matcher said "passing by indefinitely"; Virginia writes "passed by indefinitely" — 639 Senate actions. The
consequence was that EVERY Senate room reported 0% of its kills happening on a recorded vote, which looked
like a fact about the Senate and was a fact about my tuple. Corrected, House and Senate medians converge
(75% / 70%). Senate also uses "continued to" (488) and "failed to report" (98), neither previously matched.

Run:  python3 tools/calibration/profiles.py
"""
from __future__ import annotations
import sys, os, re, json, math, collections, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV
from corpus import load, _party_lookup
from bill_mix import difficulty

# EVERY conjugation Virginia actually writes, both chambers. Audit point #1.
FATAL = ("laying on the table", "lay on the table", "tabled in", "striking from", "strike from",
         "passed by indefinitely", "passing by indefinitely", "continued to",
         "failed to report", "failed to recommend", "stricken at request of patron")
FAVOURABLE = ("recommends reporting", "reported from")
MIN_ROOM = 120
MIN_BILLS = 40


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def _subjects():
    lab = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1)
        lab[(s, b)] = tuple(v)
    return lab


def _corr(xs, ys):
    n = len(xs)
    if n < 8:
        return None
    mx = sum(xs) / n; my = sum(ys) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in xs)); sy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (sx * sy) if sx and sy else None


def rooms(cb):
    cv = CV.load()
    first = collections.defaultdict(lambda: (None, "~"))
    acts = collections.defaultdict(list)
    for key, e in cv["events"].items():
        if e["venue"] not in ("committee", "subcommittee"):
            continue
        k = _bk(e["session"], e.get("bill"))
        if not k or k not in cb:
            continue
        com = CV.room_code(key[1]); d = e.get("date") or "~"
        if d < first[k][1]:
            first[k] = (com, d)
        acts[k].append((com, e["desc"], e.get("margin"), e.get("n")))
    prof = collections.defaultdict(lambda: dict(n=0, passed=0, maj=[0, 0], minr=[0, 0],
                                                fav=0, rew=0, onrecord=0, dead=0, unan=0, votes=0))
    for k, (com, _d) in first.items():
        if not com or k not in cb:
            continue
        B = cb[k]; P = prof[com]
        P["n"] += 1; P["passed"] += B["passed"]
        g = P["maj"] if B["standing"] == "majority" else (P["minr"] if B["standing"] == "minority" else None)
        if g is not None:
            g[0] += B["passed"]; g[1] += 1
        had = False
        for _c, desc, mg, n in [a for a in acts[k] if a[0] == com]:
            t = desc.lower()
            if any(f in t for f in FAVOURABLE):
                P["fav"] += 1
                P["rew"] += ("substitute" in t or "amend" in t)
            if any(f in t for f in FATAL):
                had = True
            if mg is not None and n:
                P["votes"] += 1; P["unan"] += (mg == n)
        if not B["passed"]:
            P["dead"] += 1; P["onrecord"] += had
    out = []
    for com, P in prof.items():
        if P["n"] < MIN_ROOM:
            continue
        mg = P["maj"][0] / P["maj"][1] if P["maj"][1] >= 20 else None
        mn = P["minr"][0] / P["minr"][1] if P["minr"][1] >= 20 else None
        out.append(dict(com=com, n=P["n"], rate=P["passed"] / P["n"], maj=mg, minr=mn,
                        gap=((mg - mn) if (mg and mn) else None),
                        onrecord=(P["onrecord"] / P["dead"] if P["dead"] else 0),
                        rewrite=(P["rew"] / P["fav"] if P["fav"] else 0),
                        unan=(P["unan"] / P["votes"] if P["votes"] else 0)))
    return out


def members(bills, lab, diff, party, person):
    prof = collections.defaultdict(lambda: dict(n=0, passed=0, exp=0.0, expn=0,
                                                subj=collections.Counter(), xown=0, owncop=0,
                                                signed=0, xsigned=0, last=0))
    for r in bills:
        P = prof[r["chief_key"]]
        P["n"] += 1; P["passed"] += r["passed"]; P["last"] = max(P["last"], r["year"])
        k = (r["session"], r["bill"])
        if k in diff:
            P["exp"] += diff[k]; P["expn"] += 1
        for s in lab.get(k, ()):
            P["subj"][s] += 1
        if r["cops"]:
            P["owncop"] += 1
            if any(q and r["chief_party"] and q != r["chief_party"] for q in r["cop_parties"]):
                P["xown"] += 1
    for r in bills:
        for nm, q in zip(r["cops"], r["cop_parties"]):
            P = prof.get(person(nm) or nm)
            if P is None:
                continue
            P["signed"] += 1
            if q and r["chief_party"] and q != r["chief_party"]:
                P["xsigned"] += 1
    out = []
    for k, P in prof.items():
        if P["n"] < MIN_BILLS or P["expn"] < 30:
            continue
        top = P["subj"].most_common(1)
        out.append(dict(k=k, party=(party(k) or "?"), n=P["n"], act=P["passed"] / P["n"],
                        exp=P["exp"] / P["expn"], lift=P["passed"] / P["n"] - P["exp"] / P["expn"],
                        top=(top[0][0] if top else "-"),
                        conc=(top[0][1] / sum(P["subj"].values()) if P["subj"] else 0),
                        bip=(P["xown"] / P["owncop"] if P["owncop"] else 0),
                        reach=(P["xsigned"] / P["signed"] if P["signed"] else 0),
                        last=P["last"]))
    return out


def stability(bills, diff):
    """Every number on the member panel has to be a TRAIT or it is noise with a name on it."""
    def lift(rows):
        d = collections.defaultdict(lambda: [0.0, 0])
        for r in rows:
            k = (r["session"], r["bill"])
            if k not in diff:
                continue
            g = d[r["chief_key"]]; g[0] += r["passed"] - diff[k]; g[1] += 1
        return {k: (v[0] / v[1], v[1]) for k, v in d.items()}
    odd = [r for r in bills if int(r["bill"].split()[1]) % 2]
    evn = [r for r in bills if not int(r["bill"].split()[1]) % 2]
    A, Bh = lift(odd), lift(evn)
    com = [k for k in A if k in Bh and A[k][1] >= 20 and Bh[k][1] >= 20]
    E1, E2 = lift([r for r in bills if r["year"] <= 2021]), lift([r for r in bills if r["year"] >= 2022])
    ce = [k for k in E1 if k in E2 and E1[k][1] >= 20 and E2[k][1] >= 20]
    allv = {k: v for k, v in lift(bills).items() if v[1] >= MIN_BILLS}
    last = {}
    for r in bills:
        last[r["chief_key"]] = max(last.get(r["chief_key"], 0), r["year"])
    obs = st.pvariance([v[0] for v in allv.values()])
    flo = sum(0.25 / v[1] for v in allv.values()) / len(allv)
    return dict(half=_corr([A[k][0] for k in com], [Bh[k][0] for k in com]), nhalf=len(com),
                era=_corr([E1[k][0] for k in ce], [E2[k][0] for k in ce]), nera=len(ce),
                drift=_corr([last[k] for k in allv], [v[0] for v in allv.values()]),
                ratio=obs / flo)


def main():
    c = load(); party, person = _party_lookup()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    bills = [r for r in c["bills"] if r["standing"] and r.get("chief_key")]
    lab = _subjects(); diff = difficulty(bills, lab)

    R = sorted(rooms(cb), key=lambda x: -(x["gap"] if x["gap"] is not None else -9))
    print("=" * 88)
    print("THE ROOM PANEL — four things about a committee that are not published anywhere")
    print("=" * 88)
    print(f"\n  {'room':<6}{'bills':>7}{'passes':>8}{'maj':>7}{'min':>7}{'GAP':>6}"
          f"{'dies on a record':>18}{'rewrites':>10}{'unanimous':>11}")
    for x in R:
        g = f"{x['gap'] * 100:+.0f}" if x["gap"] is not None else "  -"
        print(f"  {x['com']:<6}{x['n']:>7,}{x['rate']:>8.0%}"
              f"{(f'{x[chr(109)+chr(97)+chr(106)]:.0%}' if x['maj'] else '-'):>7}"
              f"{(f'{x[chr(109)+chr(105)+chr(110)+chr(114)]:.0%}' if x['minr'] else '-'):>7}{g:>6}"
              f"{x['onrecord']:>17.0%}{x['rewrite']:>10.0%}{x['unan']:>11.0%}")
    gg = sorted(x["gap"] for x in R if x["gap"] is not None)
    for nm, vals in (("PARTISAN GAP", gg),
                     ("DIES ON A RECORD", sorted(x["onrecord"] for x in R)),
                     ("REWRITE RATE", sorted(x["rewrite"] for x in R)),
                     ("UNANIMITY", sorted(x["unan"] for x in R))):
        print(f"  {nm:<20}{vals[0] * 100:>5.0f} to {vals[-1] * 100:>3.0f} pts"
              f"   median {vals[len(vals) // 2] * 100:.0f}")

    M = members(bills, lab, diff, party, person)
    S = stability(bills, diff)
    print("\n" + "=" * 88)
    print("THE MEMBER PANEL — three traits, each validated as a trait before being shown")
    print("=" * 88)
    print(f"\n  CARRIER LIFT — their actual pass rate minus what their own bills should have scored")
    print(f"    split-half r = {S['half']:.2f} (n={S['nhalf']})   across eras r = {S['era']:.2f} "
          f"(n={S['nera']})   {S['ratio']:.1f}x the noise floor")
    print(f"    DRIFT CHECK — lift vs the member's last active year: r = {S['drift']:+.2f}")
    print(f"    (Correction 1 caught base-rate drift masquerading as skill once; this is the guard)")
    M.sort(key=lambda x: -x["lift"])
    print(f"\n  {'legislator':<24}{'pty':<4}{'bills':>7}{'actual':>8}{'expected':>10}{'LIFT':>7}")
    for x in M[:6]:
        print(f"  {x['k'][:23]:<24}{x['party'][:3]:<4}{x['n']:>7,}{x['act']:>8.0%}"
              f"{x['exp']:>10.0%}{x['lift'] * 100:>+7.0f}")
    print(f"  {'...':<24}")
    for x in M[-4:]:
        print(f"  {x['k'][:23]:<24}{x['party'][:3]:<4}{x['n']:>7,}{x['act']:>8.0%}"
              f"{x['exp']:>10.0%}{x['lift'] * 100:>+7.0f}")
    L = sorted(x["lift"] for x in M)
    print(f"    range {L[0] * 100:+.0f} to {L[-1] * 100:+.0f} points, median {L[len(L) // 2] * 100:+.0f}")

    print(f"\n  BIPARTISAN FILING — share of their own co-patroned bills carrying a cross-party name")
    M.sort(key=lambda x: -x["bip"])
    for x in M[:4]:
        print(f"    {x['k'][:23]:<24}{x['party'][:3]:<4}{x['bip']:>6.0%}")
    bb = sorted(x["bip"] for x in M)
    print(f"    range {bb[0]:.0%} to {bb[-1]:.0%}, median {bb[len(bb) // 2]:.0%}")

    print(f"\n  SPECIALISATION — the share of their filing that sits in one subject")
    M.sort(key=lambda x: -x["conc"])
    for x in M[:4]:
        print(f"    {x['k'][:23]:<24}{x['top'][:28]:<30}{x['conc']:>6.0%}")
    cc = sorted(x["conc"] for x in M)
    print(f"    median {cc[len(cc) // 2]:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
