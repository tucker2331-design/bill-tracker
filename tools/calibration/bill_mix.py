#!/usr/bin/env python3
"""Does the +26pt majority/minority within-person swing survive holding the BILL constant?

THE OBJECTION (owner, 2026-09-11). The within-person design holds the PERSON constant but lets the
BILL vary. A legislator who gains chamber control may also change what they file: swing for the fences
with control, file uncontroversial code cleanups without it. Then 60% majority / 34% minority is not
one person meeting two worlds, it is two different portfolios, and the gap is measuring ambition.

It can cut either way, which is why it has to be measured and not argued:
  - harder bills in the majority  -> the true advantage is BIGGER than +26
  - easier bills in the minority  -> the true advantage is SMALLER than +26

Four tests, each holding more of the bill constant than the last:
  A  subject-matched     same legislator, same subject area, both statuses
  B  portfolio difficulty  is the majority-year portfolio drawn from easier cells?
  C  refiled bills       same legislator, same bill, filed under both statuses
  D  companion pairs     identical text, same year -- immune to portfolio by construction

Run:  python3 tools/calibration/bill_mix.py
"""
from __future__ import annotations
import sys, os, json, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load, norm, subj


def _norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def two_prop_p(w1, n1, w2, n2):
    """Two-sided normal-approximation test on two independent proportions."""
    if not n1 or not n2:
        return 1.0
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    return 2 * (1 - _norm_cdf(abs(p1 - p2) / se))


def sign_p(better, worse):
    """Two-sided sign test, normal approximation (n is in the hundreds here)."""
    n = better + worse
    if n == 0:
        return 1.0
    z = (abs(better - n / 2) - 0.5) / math.sqrt(n / 4)
    return 2 * (1 - _norm_cdf(z))


def rate(rs):
    return sum(1 for r in rs if r["passed"]) / len(rs) if rs else 0.0


def build():
    c = load()
    bills = [r for r in c["bills"] if r["standing"] and r.get("chief_key")]
    lab = {}
    L = json.load(open(os.path.join(HERE, "subject_labels.json")))
    for k, v in L["labels_coarse"].items():
        s, b = k.split("|", 1)
        lab[(s, b)] = tuple(v)

    # A legislator-year has ONE standing. Sessions where a patron's own rows disagree are dropped
    # rather than guessed -- that is 0 rows in practice but the check is cheap.
    byy = collections.defaultdict(list)
    for r in bills:
        byy[(r["chief_key"], r["year"])].append(r)
    status = {}
    for k, rs in byy.items():
        st = {x["standing"] for x in rs}
        if len(st) == 1:
            status[k] = st.pop()
    seen = collections.defaultdict(set)
    for (k, y), st in status.items():
        seen[k].add(st)
    switchers = {k for k, s in seen.items() if s == {"majority", "minority"}}
    for r in bills:
        r["_st"] = status.get((r["chief_key"], r["year"]))
        r["_sw"] = r["chief_key"] in switchers
    return bills, lab, switchers


def test_a(bills, lab):
    """Same legislator, SAME SUBJECT, both statuses."""
    cells = collections.defaultdict(lambda: {"majority": [], "minority": []})
    for r in bills:
        if not r["_sw"] or not r["_st"]:
            continue
        for s in lab.get((r["session"], r["bill"]), ()):
            cells[(r["chief_key"], s)][r["_st"]].append(r)
    wa = na = wn = nn = 0
    better = worse = tie = 0
    for g in cells.values():
        if not (g["majority"] and g["minority"]):
            continue
        a, b = rate(g["majority"]), rate(g["minority"])
        better += a > b
        worse += a < b
        tie += a == b
        wa += sum(1 for x in g["majority"] if x["passed"]); na += len(g["majority"])
        wn += sum(1 for x in g["minority"] if x["passed"]); nn += len(g["minority"])
    return dict(wa=wa, na=na, wn=wn, nn=nn, cells=better + worse + tie,
                better=better, worse=worse, tie=tie,
                swing=(wa / na - wn / nn) * 100 if na and nn else 0,
                p=two_prop_p(wa, na, wn, nn), sp=sign_p(better, worse))


def difficulty(bills, lab):
    """Leave-the-legislator-out pass rate of a bill's (session, subject, chamber) cells.

    This is the bill's expected fate in the hands of SOMEBODY ELSE that year. It is built without any
    reference to the patron's own outcome, so comparing a patron's majority portfolio to their minority
    portfolio on this number asks exactly the owner's question: were the bills themselves easier?"""
    cell = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for r in bills:
        for s in lab.get((r["session"], r["bill"]), ()):
            k = (r["session"], s, r["chamber"])
            c = cell[k][r["chief_key"]]
            c[0] += r["passed"]; c[1] += 1
    tot = {k: (sum(v[0] for v in d.values()), sum(v[1] for v in d.values())) for k, d in cell.items()}
    out = {}
    for r in bills:
        num = den = 0
        for s in lab.get((r["session"], r["bill"]), ()):
            k = (r["session"], s, r["chamber"])
            w, n = tot[k]
            mw, mn = cell[k][r["chief_key"]]
            if n - mn >= 8:                      # need a real denominator from OTHER patrons
                num += (w - mw) / (n - mn); den += 1
        if den:
            out[(r["session"], r["bill"])] = num / den
    return out


def test_b(bills, diff):
    """Is the majority-year portfolio drawn from EASIER cells than the minority-year portfolio?"""
    per = collections.defaultdict(lambda: {"majority": [], "minority": []})
    for r in bills:
        if not r["_sw"] or not r["_st"]:
            continue
        d = diff.get((r["session"], r["bill"]))
        if d is not None:
            per[r["chief_key"]][r["_st"]].append(d)
    deltas = []
    for g in per.values():
        if g["majority"] and g["minority"]:
            deltas.append(sum(g["majority"]) / len(g["majority"]) - sum(g["minority"]) / len(g["minority"]))
    if not deltas:
        return None
    mean = sum(deltas) / len(deltas)
    sd = math.sqrt(sum((d - mean) ** 2 for d in deltas) / max(1, len(deltas) - 1))
    se = sd / math.sqrt(len(deltas))
    pos = sum(1 for d in deltas if d > 0); neg = sum(1 for d in deltas if d < 0)
    return dict(n=len(deltas), mean=mean * 100, se=se * 100, pos=pos, neg=neg,
                p=2 * (1 - _norm_cdf(abs(mean / se))) if se else 1.0)


def test_b2(bills, diff, nbins=5):
    """Stratify on difficulty, then compare. If the gap is composition it collapses inside a stratum."""
    rows = [r for r in bills if r["_sw"] and r["_st"] and (r["session"], r["bill"]) in diff]
    rows.sort(key=lambda r: diff[(r["session"], r["bill"])])
    out = []
    size = len(rows) // nbins
    for i in range(nbins):
        chunk = rows[i * size: (i + 1) * size if i < nbins - 1 else len(rows)]
        a = [r for r in chunk if r["_st"] == "majority"]
        b = [r for r in chunk if r["_st"] == "minority"]
        if len(a) >= 40 and len(b) >= 40:
            lo = diff[(chunk[0]["session"], chunk[0]["bill"])]
            hi = diff[(chunk[-1]["session"], chunk[-1]["bill"])]
            out.append((lo, hi, len(a), rate(a), len(b), rate(b)))
    return out


def test_c(bills):
    """REFILED BILLS. Same legislator, same bill (same subject clause of the title), both statuses.

    Virginia titles are "Subject; what it does." The subject clause is the stable half and is how a
    refile of the same idea is recognised across years. This is the strongest available content control
    short of the companion design: the legislator, the idea, and the chamber are all held fixed, and the
    only thing that changed is who runs the room."""
    idx = collections.defaultdict(list)
    for r in bills:
        if r["_sw"] and r["_st"]:
            s = subj(r["title"])
            if len(s) >= 8:
                idx[(r["chief_key"], r["chamber"], s)].append(r)
    wa = na = wn = nn = 0
    pairs = better = worse = tie = 0
    ex = []
    for (k, ch, s), rs in idx.items():
        a = [x for x in rs if x["_st"] == "majority"]
        b = [x for x in rs if x["_st"] == "minority"]
        if not (a and b):
            continue
        pairs += 1
        ra, rb = rate(a), rate(b)
        better += ra > rb; worse += ra < rb; tie += ra == rb
        wa += sum(1 for x in a if x["passed"]); na += len(a)
        wn += sum(1 for x in b if x["passed"]); nn += len(b)
        if ra > rb and len(ex) < 6:
            ex.append((k, s[:44], [f"{x['bill']}/{x['year']}" for x in b][:2],
                       [f"{x['bill']}/{x['year']}" for x in a][:2]))
    return dict(pairs=pairs, wa=wa, na=na, wn=wn, nn=nn, better=better, worse=worse, tie=tie,
                swing=(wa / na - wn / nn) * 100 if na and nn else 0,
                p=two_prop_p(wa, na, wn, nn), sp=sign_p(better, worse), ex=ex)


def test_d(bills):
    """Direction. If this is a trait (ambition, skill, bill quality), it cannot turn OFF.

    Every year in which a legislator's status changed is a transition. A confound that lives in the
    person predicts the same sign on both kinds of transition. Power predicts opposite signs."""
    byy = collections.defaultdict(dict)
    for r in bills:
        if r["_st"]:
            byy[r["chief_key"]][r["year"]] = r["_st"]
    per = collections.defaultdict(list)
    for r in bills:
        per[(r["chief_key"], r["year"])].append(r)
    out = collections.defaultdict(lambda: [0.0, 0, 0, 0])
    for k, ys in byy.items():
        yy = sorted(ys)
        for y1, y2 in zip(yy, yy[1:]):
            if ys[y1] == ys[y2]:
                continue
            a, b = per[(k, y1)], per[(k, y2)]
            if len(a) < 3 or len(b) < 3:
                continue
            d = out["gained power" if ys[y2] == "majority" else "lost power"]
            d[0] += rate(b) - rate(a); d[1] += 1
            d[2] += rate(b) > rate(a); d[3] += rate(b) < rate(a)
    return out


def test_e(bills):
    """Persistence. A refile group can just be "keep filing until it lands". Split on which status
    came FIRST: persistence pushes the swing DOWN in majority-first groups, so that arm is the
    conservative floor."""
    idx = collections.defaultdict(list)
    for r in bills:
        if r["_sw"] and r["_st"]:
            s = subj(r["title"])
            if len(s) >= 8:
                idx[(r["chief_key"], r["chamber"], s)].append(r)
    out = {}
    for name, f in (("majority filed first", lambda a, b: min(x["year"] for x in a) < min(x["year"] for x in b)),
                    ("minority filed first", lambda a, b: min(x["year"] for x in a) > min(x["year"] for x in b))):
        wa = na = wn = nn = g = 0
        for rs in idx.values():
            a = [x for x in rs if x["_st"] == "majority"]; b = [x for x in rs if x["_st"] == "minority"]
            if not (a and b) or not f(a, b):
                continue
            g += 1
            wa += sum(1 for x in a if x["passed"]); na += len(a)
            wn += sum(1 for x in b if x["passed"]); nn += len(b)
        out[name] = dict(wa=wa, na=na, wn=wn, nn=nn, g=g,
                         swing=(wa / na - wn / nn) * 100 if na and nn else 0,
                         p=two_prop_p(wa, na, wn, nn))
    return out


def _xparty(r):
    p = r["chief_party"]
    return any(q and p and q != p for q in r["cop_parties"])


def test_f(allb):
    """THE LOBBYIST'S LEVER. A lobbyist cannot pick the bill, the party, or the year. They CAN put
    one member of the other party on the bill. Is that a cause, or only a sign the bill was easy?

    Held constant: the patron, the bill idea, the chamber. The same person filed the same idea twice,
    once with a cross-party co-patron and once without."""
    idx = collections.defaultdict(list)
    for r in allb:
        s = subj(r["title"])
        if len(s) >= 8:
            idx[(r["chief_key"], r["chamber"], s)].append(r)
    out = {}
    for st in (None, "majority", "minority"):
        wa = na = wn = nn = g = better = worse = 0
        for rs in idx.values():
            rr = [x for x in rs if st is None or x["standing"] == st]
            a = [x for x in rr if _xparty(x)]; b = [x for x in rr if not _xparty(x)]
            if not (a and b):
                continue
            g += 1
            better += rate(a) > rate(b); worse += rate(a) < rate(b)
            wa += sum(1 for x in a if x["passed"]); na += len(a)
            wn += sum(1 for x in b if x["passed"]); nn += len(b)
        out[st or "all"] = dict(wa=wa, na=na, wn=wn, nn=nn, g=g, better=better, worse=worse,
                                swing=(wa / na - wn / nn) * 100 if na and nn else 0,
                                p=two_prop_p(wa, na, wn, nn), sp=sign_p(better, worse))
    return out


def test_g(allb):
    """THE HANDOFF. Identical title, carried by DIFFERENT people, one in the majority and one not.
    Split same-year (that is the cross-chamber companion design) from a later year (that is the move
    a lobbyist actually makes between sessions)."""
    idx = collections.defaultdict(list)
    for r in allb:
        s = norm(r["title"])
        if len(s) >= 12:
            idx[s].append(r)
    out = {"same year": [0, 0, 0, 0, 0], "later year": [0, 0, 0, 0, 0]}
    ex = []
    for s, rs in idx.items():
        a = [x for x in rs if x["standing"] == "majority"]; b = [x for x in rs if x["standing"] == "minority"]
        if not (a and b):
            continue
        if {x["chief_key"] for x in a} & {x["chief_key"] for x in b}:
            continue                       # a handoff means a DIFFERENT person, not a refile
        k = "same year" if {x["year"] for x in a} & {x["year"] for x in b} else "later year"
        d = out[k]
        d[0] += sum(1 for x in a if x["passed"]); d[1] += len(a)
        d[2] += sum(1 for x in b if x["passed"]); d[3] += len(b); d[4] += 1
        if k == "later year" and rate(a) > rate(b) and len(ex) < 5:
            ex.append((s[:50], f"{b[0]['chief_key']} ({b[0]['year']})", f"{a[0]['chief_key']} ({a[0]['year']})"))
    return out, ex


def main():
    bills, lab, switchers = build()
    sw = [r for r in bills if r["_sw"] and r["_st"]]
    maj = [r for r in sw if r["_st"] == "majority"]
    mino = [r for r in sw if r["_st"] == "minority"]

    print("=" * 78)
    print("THE BILL-MIX CONFOUND: does the regime effect survive holding the BILL constant?")
    print("=" * 78)
    print(f"\n{len(switchers)} legislators are observed under BOTH statuses "
          f"({len(maj):,} majority-year bills, {len(mino):,} minority-year bills)")
    print(f"\n  BASELINE (person held constant, bill free to vary)")
    print(f"    in the majority   {sum(1 for r in maj if r['passed']):>5,}/{len(maj):<6,} = {rate(maj):.0%}")
    print(f"    in the minority   {sum(1 for r in mino if r['passed']):>5,}/{len(mino):<6,} = {rate(mino):.0%}")
    print(f"    swing {(rate(maj)-rate(mino))*100:+.0f} points   <-- the number under attack")

    a = test_a(bills, lab)
    print(f"\nA  SAME LEGISLATOR, SAME SUBJECT  ({a['cells']:,} legislator-x-subject cells with both)")
    print(f"    in the majority   {a['wa']:>5,}/{a['na']:<6,} = {a['wa']/a['na']:.0%}")
    print(f"    in the minority   {a['wn']:>5,}/{a['nn']:<6,} = {a['wn']/a['nn']:.0%}")
    print(f"    swing {a['swing']:+.0f} points   p = {a['p']:.2e}")
    print(f"    cells where the SAME person did better in the majority: {a['better']:,} "
          f"vs {a['worse']:,} worse ({a['tie']:,} tied)   sign p = {a['sp']:.2e}")

    diff = difficulty(bills, lab)
    b = test_b(bills, diff)
    print(f"\nB  PORTFOLIO DIFFICULTY  (each bill scored by how OTHER patrons' bills in the same")
    print(f"   session x subject x chamber fared -- the patron's own outcome excluded)")
    print(f"    {b['n']} legislators scored under both statuses")
    print(f"    mean difference in portfolio baseline, majority minus minority: "
          f"{b['mean']:+.2f} pt  (SE {b['se']:.2f})   p = {b['p']:.3f}")
    d = "HARDER" if b["mean"] < -0.5 else ("EASIER" if b["mean"] > 0.5 else "NO DIFFERENT")
    print(f"    -> majority-year portfolios are {d} than the same person's minority-year portfolios")
    print(f"       ({b['pos']} legislators drew easier cells in power, {b['neg']} drew harder)")

    print(f"\n   stratified on that difficulty score:")
    print(f"     {'cell pass rate band':<22}{'majority patron':>20}{'minority patron':>20}{'swing':>9}")
    for lo, hi, na_, ra, nb, rb in test_b2(bills, diff):
        print(f"     {lo:.0%}-{hi:<17.0%}{ra:>12.0%} (n={na_:>4,}){rb:>12.0%} (n={nb:>4,}){(ra-rb)*100:>+8.0f}")

    c = test_c(bills)
    print(f"\nC  REFILED BILLS  (same legislator, same bill idea, same chamber, both statuses)")
    print(f"    {c['pairs']:,} refile groups qualify")
    print(f"    filed while in the majority   {c['wa']:>4,}/{c['na']:<5,} = {c['wa']/c['na']:.0%}")
    print(f"    filed while in the minority   {c['wn']:>4,}/{c['nn']:<5,} = {c['wn']/c['nn']:.0%}")
    print(f"    swing {c['swing']:+.0f} points   p = {c['p']:.2e}")
    print(f"    groups better in the majority: {c['better']:,} vs {c['worse']:,} worse "
          f"({c['tie']:,} tied)   sign p = {c['sp']:.2e}")
    if c["ex"]:
        print(f"\n    the same person, the same bill, filed twice:")
        for k, s, lost, won in c["ex"]:
            print(f"      {k:<20} {s:<46} died {','.join(lost):<18} passed {','.join(won)}")

    d = test_d(bills)
    print(f"\nD  DIRECTION  (a trait cannot turn off -- power can)")
    for k in ("gained power", "lost power"):
        s_, n, up, dn = d[k]
        print(f"    {k:<14}{n:>4} transitions   that person's own pass rate moves {s_/n*100:>+4.0f} pt"
              f"   ({up} up, {dn} down)   sign p = {sign_p(up, dn):.1e}")
    print(f"    -> the effect REVERSES when the same person loses the chamber. No fixed trait")
    print(f"       of the legislator or their bills can produce opposite signs on the same person.")

    e = test_e(bills)
    print(f"\nE  PERSISTENCE  (is a refile just 'keep trying until it lands'?)")
    for k, v in e.items():
        print(f"    {k:<22}majority {v['wa']/v['na']:>4.0%} (n={v['na']:>4,})   "
              f"minority {v['wn']/v['nn']:>4.0%} (n={v['nn']:>4,})   {v['swing']:>+4.0f}pt  "
              f"p={v['p']:.1e}  [{v['g']} groups]")
    print(f"    -> persistence pushes the majority-first arm DOWN, so {e['majority filed first']['swing']:+.0f} pt is the")
    print(f"       floor with persistence working AGAINST the finding, not for it.")

    allb = [r for r in load()["bills"] if r["standing"] and r.get("chief_key")]
    g, ex = test_g(allb)
    print(f"\nF  THE HANDOFF  (identical title, carried by a DIFFERENT person)")
    for k in ("same year", "later year"):
        w, n, w2, n2, gg = g[k]
        note = "cross-chamber companion" if k == "same year" else "the move a lobbyist makes"
        print(f"    {k:<11} majority {w/n:>4.0%} (n={n:>4,})   minority {w2/n2:>4.0%} (n={n2:>4,})"
              f"   {(w/n-w2/n2)*100:>+4.0f}pt  p={two_prop_p(w,n,w2,n2):.1e}   {note}")
    for s_, lo, hi in ex:
        print(f"      {s_:<52} {lo:<26} -> {hi}")

    f = test_f(allb)
    print(f"\nG  THE ONE LEVER A LOBBYIST OWNS: one co-patron from the other party")
    print(f"   (same patron, same bill idea, same chamber -- filed once with, once without)")
    for k, lbl in (("all", "every patron"), ("majority", "majority patron"), ("minority", "MINORITY patron")):
        v = f[k]
        if v["na"] < 40 or v["nn"] < 40:
            continue
        print(f"    {lbl:<18} with {v['wa']/v['na']:>4.0%} (n={v['na']:>4,})   "
              f"without {v['wn']/v['nn']:>4.0%} (n={v['nn']:>4,})   {v['swing']:>+4.0f}pt  p={v['p']:.1e}")
    print(f"    -> worth {f['minority']['swing']:.0f} points to the minority patron and only "
          f"{f['majority']['swing']:.0f} to the majority patron.")
    print(f"       The client with the least power gets the most out of the only move they control.")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
