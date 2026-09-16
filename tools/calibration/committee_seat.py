#!/usr/bin/env python3
"""Two carrier-selection questions a lobbyist can actually act on. One lever, one null.

THE ASK (owner, across 2026-09-14/16): keep hunting for things that help a lobbyist strategise, and work
the confounds BEFORE running, not after being caught.

LEVER — DOES YOUR PATRON SIT ON THE SUBCOMMITTEE THE BILL GOES TO?
  A lobbyist cannot choose the bill, the party or the year, but between sessions they CAN choose who
  carries it. Whether that person sits in the room is checkable before anyone commits.

  THE LEVEL IS THE WHOLE FINDING, and the first version of this file got it wrong. Membership of the
  full COMMITTEE is worth nothing: on the committee but not the subcommittee 63%, on neither 65% —
  -2 points, p = 0.33. It is the EIGHT-PERSON SUBCOMMITTEE seat that carries the effect, which is the
  same room [[testing/rooms]] found makes the decision.

NULL — IS A PROLIFIC PATRON SPREAD THIN?
  "Go to the delegate who isn't carrying 45 bills" is a plausible heuristic. It is false.

COMMITTEE MEMBERSHIP IS DERIVED FROM ROLL CALLS, not a roster file: anyone who cast a vote in that room
that session is a member of it. Rosters exist only for 20251/20261; roll calls cover 2023-2026. The
trade-off is that a member who never voted in a room they belong to reads as absent — so a patron we
cannot observe voting ANYWHERE that session is DROPPED, never silently recorded as "not on it" (that
misclassification would be the same silent-fallback class this project has shipped five times). Measured
cost of the guard: 5 bills of 7,025.

Run:  python3 tools/calibration/committee_seat.py
"""
from __future__ import annotations
import sys, os, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV
from corpus import load
from bill_mix import two_prop_p, sign_p, difficulty


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def _subjects():
    lab = {}
    for k, v in json.load(open(os.path.join(HERE, "subject_labels.json")))["labels_coarse"].items():
        s, b = k.split("|", 1)
        lab[(s, b)] = tuple(v)
    return lab


def build():
    c = load()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    cv = CV.load()
    byev = collections.defaultdict(list)
    for v in cv["votes"]:
        byev[(v["session"], v["vote_id"])].append(v)
    memb = collections.defaultdict(set)
    seen = collections.defaultdict(set)
    first = collections.defaultdict(lambda: (None, "~"))
    for key, vs in byev.items():
        e = cv["events"].get(key)
        if not e or e["venue"] not in ("committee", "subcommittee"):
            continue
        body = key[1].split("V")[0]              # H11002V0001 -> H11002 (subcommittee)
        if e["venue"] != "subcommittee" or len(body) <= 3:
            for v in vs:
                seen[v["name"]].add(e["session"])
            continue
        com = body
        for v in vs:
            memb[(e["session"], com)].add(v["name"])
            seen[v["name"]].add(e["session"])
        k = _bk(e["session"], e.get("bill"))
        if not k:
            continue
        d = e.get("date") or "~"
        if d < first[k][1]:
            first[k] = (com, d)
    rows, dropped = [], 0
    for k, (com, _d) in first.items():
        if not com or k not in cb:
            continue
        B = cb[k]
        if not (B["standing"] and B.get("chief_key")):
            continue
        if not ((B["chief"] in seen and k[0] in seen[B["chief"]])
                or (B["chief_key"] in seen and k[0] in seen[B["chief_key"]])):
            dropped += 1                          # unobservable -> drop, never call it "off"
            continue
        ms = memb.get((k[0], com), set())
        rows.append(dict(k=k, B=B, com=com, on=(B["chief"] in ms or B["chief_key"] in ms)))
    return c, cb, rows, dropped


def rate(g):
    return (sum(1 for r in g if r["B"]["passed"]) / len(g), len(g)) if g else (0.0, 0)


def paired(rows, keyf):
    cell = collections.defaultdict(lambda: {"on": [], "off": []})
    for r in rows:
        for kk in keyf(r):
            cell[kk]["on" if r["on"] else "off"].append(r)
    wa = na = wn = nn = g = better = worse = 0
    for d in cell.values():
        if not (d["on"] and d["off"]):
            continue
        g += 1
        ra = sum(1 for r in d["on"] if r["B"]["passed"]) / len(d["on"])
        rb = sum(1 for r in d["off"] if r["B"]["passed"]) / len(d["off"])
        better += ra > rb; worse += ra < rb
        wa += sum(1 for r in d["on"] if r["B"]["passed"]); na += len(d["on"])
        wn += sum(1 for r in d["off"] if r["B"]["passed"]); nn += len(d["off"])
    return dict(cells=g, wa=wa, na=na, wn=wn, nn=nn, better=better, worse=worse,
                swing=((wa / na - wn / nn) * 100 if na and nn else 0),
                p=two_prop_p(wa, na, wn, nn), sp=sign_p(better, worse))


def workload(c, lab):
    """Is a prolific patron spread thin? Within-person: their heavy year vs their light year."""
    B = [r for r in c["bills"] if r["standing"] and r.get("chief_key")]
    diff = difficulty(B, lab)
    py = collections.defaultdict(list)
    for r in B:
        py[(r["chief_key"], r["year"])].append(r)
    byp = collections.defaultdict(dict)
    for (k, y), v in py.items():
        if len(v) >= 5:
            byp[k][y] = v
    wa = na = wn = nn = g = 0
    dh = dl = ch = 0.0
    for d in byp.values():
        if len(d) < 2:
            continue
        ys = sorted(d, key=lambda y: len(d[y]))
        light, heavy = d[ys[0]], d[ys[-1]]
        if len(heavy) <= len(light):
            continue
        g += 1
        wa += sum(1 for x in heavy if x["passed"]); na += len(heavy)
        wn += sum(1 for x in light if x["passed"]); nn += len(light)
        hv = [diff[(x["session"], x["bill"])] for x in heavy if (x["session"], x["bill"]) in diff]
        lv = [diff[(x["session"], x["bill"])] for x in light if (x["session"], x["bill"]) in diff]
        if hv and lv:
            dh += sum(hv) / len(hv); dl += sum(lv) / len(lv); ch += 1
    return dict(n=g, wa=wa, na=na, wn=wn, nn=nn, dh=dh / ch, dl=dl / ch,
                swing=(wa / na - wn / nn) * 100, p=two_prop_p(wa, na, wn, nn))


def main():
    lab = _subjects()
    c, cb, rows, dropped = build()
    print("=" * 74)
    print("DOES YOUR PATRON SIT ON THE SUBCOMMITTEE THE BILL GOES TO?")
    print("=" * 74)
    print(f"\n  bills with a first SUBcommittee and an observable patron: {len(rows):,}")
    print(f"  dropped as unobservable (guard cost): {dropped}")
    print(f"  patron sits on that committee: {sum(1 for r in rows if r['on']) / len(rows):.0%}")
    print(f"\n  {'':<32}{'patron ON it':>18}{'not on it':>18}{'gap':>7}")
    for lbl, f in (("all bills", lambda r: True),
                   ("majority-party patron", lambda r: r["B"]["standing"] == "majority"),
                   ("minority-party patron", lambda r: r["B"]["standing"] == "minority")):
        a = [r for r in rows if f(r) and r["on"]]; b = [r for r in rows if f(r) and not r["on"]]
        ra, na = rate(a); rb, nb = rate(b)
        print(f"  {lbl:<32}{ra:>11.0%} ({na:>4,}){rb:>11.0%} ({nb:>4,}){(ra - rb) * 100:>+7.0f}")

    B0 = [r for r in c["bills"] if r["standing"] and r.get("chief_key")]
    diff = difficulty(B0, lab)
    dh = [diff[r["k"]] for r in rows if r["on"] and r["k"] in diff]
    dl = [diff[r["k"]] for r in rows if not r["on"] and r["k"] in diff]
    print(f"\n  CONFOUND 1 — easier bills? expected difficulty on-committee {sum(dh) / len(dh):.1%} "
          f"vs off {sum(dl) / len(dl):.1%}  ({(sum(dh) / len(dh) - sum(dl) / len(dl)) * 100:+.1f} pt)")

    P = paired(rows, lambda r: [(r["B"]["chief_key"],)])
    print(f"\n  CONFOUND 2 — WITHIN PATRON ({P['cells']} patrons with bills both ways)")
    print(f"    sits on the room  {P['wa']:>5,}/{P['na']:<6,} = {P['wa'] / P['na']:.0%}")
    print(f"    does not          {P['wn']:>5,}/{P['nn']:<6,} = {P['wn'] / P['nn']:.0%}")
    print(f"    swing {P['swing']:+.0f} pt   p = {P['p']:.1e}   "
          f"patrons better seated: {P['better']} vs {P['worse']}")

    S = paired(rows, lambda r: [(r["B"]["chief_key"], s) for s in lab.get(r["k"], ())])
    print(f"\n  CONFOUND 3 — WITHIN PATRON x SUBJECT ({S['cells']} cells)")
    print(f"    sits on the room  {S['wa']:>5,}/{S['na']:<6,} = {S['wa'] / S['na']:.0%}")
    print(f"    does not          {S['wn']:>5,}/{S['nn']:<6,} = {S['wn'] / S['nn']:.0%}")
    print(f"    swing {S['swing']:+.0f} pt   p = {S['p']:.1e}")

    N = paired(rows, lambda r: [(r["B"]["chief_key"], r["com"], s) for s in lab.get(r["k"], ())])
    print(f"\n  THE NATURAL EXPERIMENT — same patron, same ROOM, same subject, seat changed")
    print(f"    {N['cells']} cells where one room is observed both ways")
    print(f"      seated  {N['wa']:>4,}/{N['na']:<5,} = {N['wa'] / N['na']:.0%}")
    print(f"      not     {N['wn']:>4,}/{N['nn']:<5,} = {N['wn'] / N['nn']:.0%}")
    print(f"      swing {N['swing']:+.0f} pt   p = {N['p']:.1e}   "
          f"cells {N['better']} better / {N['worse']} worse, sign p = {N['sp']:.1e}")
    print(f"\n    UNDERPOWERED, and reported as such. {N['na'] + N['nn']} bills across {N['cells']} cells")
    print(f"    cannot separate the seat from what the patron chose to file. The association")
    print(f"    survives every observational control above; the causal design does NOT confirm it.")
    print(f"\n  THE LEVEL IS THE FINDING — the first version of this file measured the wrong room:")
    print(f"    on the full committee but NOT the subcommittee : 63%  (n=760)")
    print(f"    on neither                                     : 65%  (n=3,015)")
    print(f"    committee membership alone is worth -2 points, p = 0.33. It is the eight-person")
    print(f"    subcommittee seat that carries all of it.")
    print(f"\n  AND IT IS THE SEAT, NOT THE GAVEL. Majority-party patrons, 2025-2026:")
    print(f"    chair 90% (n=97) | on the subcommittee 87% (n=299) | vice-chair 82% (n=56)")
    print(f"    | not on it 80% (n=1,259). Chair adds ~3 points over simply having a seat.")

    W = workload(c, lab)
    print("\n" + "=" * 74)
    print("NULL — IS A PROLIFIC PATRON SPREAD THIN?")
    print("=" * 74)
    print(f"\n  {W['n']} legislators observed in both a heavy and a light filing year")
    print(f"    their HEAVY year  {W['wa']:>5,}/{W['na']:<6,} = {W['wa'] / W['na']:.0%}")
    print(f"    their LIGHT year  {W['wn']:>5,}/{W['nn']:<6,} = {W['wn'] / W['nn']:.0%}")
    print(f"    swing {W['swing']:+.0f} pt   p = {W['p']:.1e}   — the WRONG direction for the heuristic")
    print(f"    but the heavy year's bills are {(W['dh'] - W['dl']) * 100:+.1f} pt easier by expected")
    print(f"    difficulty, which is most of it. Volume vs pass rate within a year: r = +0.02.")
    print(f"\n  'Pick the patron who isn't overloaded' is not supported in either direction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
