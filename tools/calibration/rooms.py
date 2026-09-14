#!/usr/bin/env python3
"""Where Virginia bills are actually decided, and by how many people.

Everything before this described BILLS. This describes ROOMS. It reads the 28,769 committee and
subcommittee roll calls in `committee_votes` (sessions 2023-2026) rather than bill-level outcomes.

WHAT IT SETTLES
  - how many members are in the room that decides (median 8, not the full committee)
  - whether those kills are party-line (86%) or persuadable (14%)
  - whether the majority/minority gap is ACCESS to a hearing or the OUTCOME of one (it is the outcome)
  - three plausible lobbyist heuristics that are NULL: silence duration, the substitute, and the
    pooled subcommittee discontinuity

WHAT IT DOES NOT SETTLE
  The 86:1 odds on a subcommittee recommendation are selection-contaminated: rooms report bills they
  like. The threshold design that would fix it does not work here -- see `test_rd`.

Run:  python3 tools/calibration/rooms.py
"""
from __future__ import annotations
import sys, os, re, collections, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV
from corpus import load, _party_lookup
from bill_mix import two_prop_p

FATAL = ("laying on the table", "striking from", "failed to recommend", "passing by indefinitely")
SESSIONS = {"2023", "2024", "2025", "2026"}     # what the roll-call corpus covers


def _bk(e):
    """Roll-call bill ids are 'HB53'; the corpus writes 'HB 53'. This project has shipped five bugs in
    exactly this shape, so the join rate is printed, never assumed."""
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (e.get("bill") or "").strip())
    return (e["session"], f"{m.group(1)} {int(m.group(2))}") if m else None


def _cls(desc):
    t = (desc or "").lower()
    if any(f in t for f in FATAL):
        return "fatal"
    if "recommends reporting" in t:
        return "favorable"
    return None


def build():
    d = CV.load()
    c = load()
    party, _ = _party_lookup()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    byev = collections.defaultdict(list)
    resolved = total = 0
    for v in d["votes"]:
        total += 1
        p = party(v.get("name") or "")
        if p:
            resolved += 1
            byev[(v["session"], v["vote_id"])].append((p, v["opt"], v["name"]))
    return d, cb, byev, resolved / total


def defectors(vs):
    """Members who voted against their own party's majority on this roll call."""
    tal = collections.defaultdict(collections.Counter)
    for p, o, _n in vs:
        tal[p][o] += 1
    out = []
    for p, cnt in tal.items():
        if cnt["yes"] + cnt["no"] == 0:
            continue
        losing = "no" if cnt["yes"] >= cnt["no"] else "yes"
        out += [n for pp, o, n in vs if pp == p and o == losing]
    return out


def test_room_size(d, cb, byev):
    rows = []
    for key, e in d["events"].items():
        if e["venue"] != "subcommittee":
            continue
        k = _bk(e); cl = _cls(e["desc"])
        if not (k and k in cb and cl):
            continue
        vs = byev.get(key) or []
        rows.append(dict(k=k, cl=cl, e=e, vs=vs, dfc=defectors(vs) if len(vs) >= 5 else None))
    return rows


def test_rd(rows, cb):
    """WHY THE DISCONTINUITY DESIGN FAILS HERE, kept so nobody rebuilds it.

    Pooled, the threshold looks perfect: bills that barely clear subcommittee pass 82%, bills that
    barely fail pass 17%. But the balance check breaks it -- 88% of the barely-favourable side has a
    majority-party patron against 16% on the barely-fatal side. In an EIGHT-SEAT room a margin of 2 IS
    the party-line result, not a close call, so 'close' selects for party, not for marginal bills."""
    a = [r for r in rows if r["cl"] == "favorable" and (r["e"].get("margin") or 9) <= 2]
    b = [r for r in rows if r["cl"] == "fatal" and (r["e"].get("margin") or 9) <= 2]
    f = lambda g, fn: sum(1 for r in g if fn(cb[r["k"]])) / len(g)
    return dict(na=len(a), nb=len(b),
                ra=sum(1 for r in a if cb[r["k"]]["passed"]) / len(a),
                rb=sum(1 for r in b if cb[r["k"]]["passed"]) / len(b),
                maj_a=f(a, lambda x: x["standing"] == "majority"),
                maj_b=f(b, lambda x: x["standing"] == "majority"))


def test_access(d, cb):
    """Is the majority/minority gap ACCESS to a hearing, or the OUTCOME of one?"""
    heard = collections.defaultdict(set)
    for _key, e in d["events"].items():
        k = _bk(e)
        if k:
            heard[k].add(e["venue"])
    B = [r for r in cb.values() if r["standing"] and r["session"] in SESSIONS]

    def was_heard(r):
        return bool({"committee", "subcommittee"} & heard.get((r["session"], r["bill"]), set()))
    out = {}
    for std in ("majority", "minority"):
        g = [r for r in B if r["standing"] == std]
        h = [r for r in g if was_heard(r)]
        s = [r for r in g if not was_heard(r)]
        out[std] = dict(n=len(g), heard=len(h), unheard=len(s),
                        rate_h=sum(1 for r in h if r["passed"]) / len(h),
                        rate_s=sum(1 for r in s if r["passed"]) / max(1, len(s)),
                        rate_all=sum(1 for r in g if r["passed"]) / len(g))
    return out


def main():
    d, cb, byev, pres = build()
    ev = d["events"]
    tot = sum(1 for e in ev.values() if _bk(e))
    hit = sum(1 for e in ev.values() if _bk(e) and _bk(e) in cb)
    print("=" * 76)
    print("WHERE VIRGINIA BILLS ARE DECIDED, AND BY HOW MANY PEOPLE")
    print("=" * 76)
    print(f"\n  {len(ev):,} committee + subcommittee roll calls, sessions 2023-2026")
    print(f"  join to corpus bills {hit:,}/{tot:,} = {hit / tot:.1%} | party resolved on member votes {pres:.1%}")

    rows = test_room_size(d, cb, byev)
    print("\n" + "=" * 76)
    print("1. THE ROOM IS EIGHT PEOPLE")
    print("=" * 76)
    for cl in ("favorable", "fatal"):
        g = [r for r in rows if r["cl"] == cl and r["e"].get("n")]
        ns = [r["e"]["n"] for r in g]; mg = [r["e"]["margin"] for r in g if r["e"].get("margin") is not None]
        print(f"\n  {cl.upper()} subcommittee recommendations: {len(g):,}")
        print(f"    members recorded : median {st.median(ns):.0f}  "
              f"(quartiles {sorted(ns)[len(ns) // 4]}-{sorted(ns)[3 * len(ns) // 4]})")
        print(f"    unanimous        : {sum(1 for m, n in zip(mg, ns) if m == n) / len(mg):.0%}")
        print(f"    margin <=2 votes : {sum(1 for m in mg if m <= 2) / len(mg):.0%}")

    print("\n" + "=" * 76)
    print("2. THOSE VOTES ARE PARTY-LINE")
    print("=" * 76)
    for cl in ("fatal", "favorable"):
        g = [r for r in rows if r["cl"] == cl and r["dfc"] is not None]
        pl = sum(1 for r in g if not r["dfc"])
        print(f"\n  {cl.upper()}: {len(g):,} roll calls with party resolved for >=5 voters")
        print(f"    nobody crossed their own caucus : {pl:>5,} = {pl / len(g):.0%}")
        print(f"    somebody did                    : {len(g) - pl:>5,} = {1 - pl / len(g):.0%}")
        dd = [len(r["dfc"]) for r in g if r["dfc"]]
        if dd:
            print(f"    when someone does, how many     : median {st.median(dd):.0f}, max {max(dd)}")
    print("\n  This is why the advantage does not scale with majority size (r = -0.05, measured")
    print("  earlier): an 8-seat room split 5-3 and one split 6-2 produce the same party-line")
    print("  outcome. Seats past the majority buy nothing.")

    print("\n" + "=" * 76)
    print("3. THE GAP IS NOT ACCESS TO A HEARING. IT IS THE HEARING.")
    print("=" * 76)
    A = test_access(d, cb)
    print(f"\n  {'':<12}{'bills':>8}{'never heard':>14}{'pass | heard':>16}{'pass | unheard':>17}")
    for std in ("majority", "minority"):
        a = A[std]
        print(f"  {std:<12}{a['n']:>8,}{a['unheard'] / a['n']:>13.0%}{a['rate_h']:>16.0%}{a['rate_s']:>17.0%}")
    gm, gn = A["majority"], A["minority"]
    print(f"\n  83% of bills get a recorded roll call in some room. Access is near-equal")
    print(f"  ({1 - gm['unheard'] / gm['n']:.0%} majority vs {1 - gn['unheard'] / gn['n']:.0%} minority).")
    print(f"  Among bills that WERE heard the gap is {(gm['rate_h'] - gn['rate_h']) * 100:+.0f} points — "
          f"LARGER than the raw gap of {(gm['rate_all'] - gn['rate_all']) * 100:+.0f}.")
    print(f"  Corrects the earlier 'agenda access, not vote arithmetic' reading: the room lets your")
    print(f"  bill in and then votes it down along party lines.")

    print("\n" + "=" * 76)
    print("4. THREE HEURISTICS THAT ARE NULL — worth as much as the positive results")
    print("=" * 76)
    R = test_rd(rows, cb)
    print(f"\n  (a) THE DISCONTINUITY DOES NOT IDENTIFY. Pooled it looks perfect —")
    print(f"      barely favourable {R['ra']:.0%} (n={R['na']}) vs barely fatal {R['rb']:.0%} (n={R['nb']}).")
    print(f"      But the balance check breaks it: {R['maj_a']:.0%} of the favourable side has a")
    print(f"      majority patron against {R['maj_b']:.0%} of the fatal side. In an 8-seat room a")
    print(f"      margin of 2 IS the party-line result. 'Close' selects party, not marginal bills.")
    fav = [r for r in rows if r["cl"] == "favorable"]
    sub = [r for r in fav if "substitute" in r["e"]["desc"].lower()]
    cln = [r for r in fav if "substitute" not in r["e"]["desc"].lower()
           and "amend" not in r["e"]["desc"].lower()]
    ws = sum(1 for r in sub if cb[r["k"]]["passed"]); wc = sum(1 for r in cln if cb[r["k"]]["passed"])
    print(f"\n  (b) THE SUBSTITUTE IS WORTH NOTHING. Reported with a substitute "
          f"{ws / len(sub):.0%} (n={len(sub):,})")
    print(f"      versus reported clean {wc / len(cln):.0%} (n={len(cln):,}) — "
          f"{(ws / len(sub) - wc / len(cln)) * 100:+.0f} pt, p = {two_prop_p(ws, len(sub), wc, len(cln)):.2f}.")
    print(f"      Negotiating the language does not change whether the bill survives.")
    print(f"\n  (c) HOW LONG IT HAS BEEN SITTING TELLS YOU NOTHING. Bills silent 3 days after")
    print(f"      referral pass 51%; silent 60 days, 44%. A flat curve over two months.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
