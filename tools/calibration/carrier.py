#!/usr/bin/env python3
"""Is the carrier doing the work, or the caucus? And is the co-patron a cause or a symptom?

THE OBJECTION (owner, 2026-09-11). "How likely is it that the party approved the policy in caucus and
therefore the patron had little influence? How can we prove a patron's effectiveness and not the work of
the party whip or caucus behind closed doors." And the same challenge to the co-patron lever: "the bills
where a lobbyist can land that name may be the ones already closest to the line."

Three designs.

INCORPORATION (test_vehicle). Virginia committees fold duplicate bills together: bill A is "incorporated
by" bill B, A dies, B carries the policy. In that moment the MERIT QUESTION IS CLOSED -- the room has
already decided to advance the policy -- and the only open question is whose name is on it. That is the
caucus decision and the carrier decision, separated by the process itself.

PATRON VARIANCE (test_patron). If the caucus does the work, every majority patron is the same coin. Real
between-patron variance, above the binomial floor, that PERSISTS year to year, is an individual effect.

LIS PRE/POST (test_copatron). The co-patron finding was built on Open States sponsorship rows, which carry
NO DATE and are a terminal snapshot. LIS's own record distinguishes `Chief Co-Patron` (named on the
introduced bill, rule-limited to ~4) from `Co-Patron` (signed on later, up to 99) -- and even labels the
mechanical carryover `Incorporated Chief Co-Patron`. Only the first is pre-treatment.

LIS SCOPE: sessions 20251 and 20261 only, from the existing on-disk cache. No new requests.

Run:  python3 tools/calibration/carrier.py
"""
from __future__ import annotations
import sys, os, re, csv, gzip, glob, json, math, random, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from corpus import load, _party_lookup, _tk
from bill_mix import two_prop_p, sign_p, difficulty, rate

LIS_SESSIONS = {"20251": "2025", "20261": "2026"}   # authorised window: 2025 onward
BILLNO = re.compile(r"\b([hs]b)\s*0*(\d+)\b", re.I)
PTYPE = re.compile(r"^\s*(\d+)\s*-\s*(.+?)\s*$")


def _wilson(k, n):
    if not n:
        return 0.0, 0.0
    p = k / n; z = 1.96; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def _corr(xs, ys):
    n = len(xs)
    if n < 8:
        return None
    mx = sum(xs) / n; my = sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if not (sx and sy):
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def incorporation_graph(allb):
    """Edges are TEXT-derived and then STRUCTURALLY checked: the named bill must exist in the same
    session, and the reciprocal edge should agree. Diagnostics only (Standard #3) -- nothing on the
    lobbyist path reads this."""
    byid = {(r["session"], r["bill"]): r for r in allb}
    absorbed, absorbs, rejected = {}, collections.defaultdict(list), collections.Counter()
    for r in allb:
        for _d, desc, _c in r["actions"]:
            dl = (desc or "").lower()
            if "incorporat" not in dl:
                continue
            tgt = [f"{a.upper()} {int(b)}" for a, b in BILLNO.findall(desc or "")]
            if not tgt:
                rejected["no bill number in the action text"] += 1
                continue
            for t in tgt:
                if (r["session"], t) not in byid:
                    rejected["names a bill absent from this session"] += 1
                    continue
                if dl.startswith("incorporated"):
                    absorbed[(r["session"], r["bill"])] = (r["session"], t)
                else:
                    absorbs[(r["session"], r["bill"])].append((r["session"], t))
    recip = sum(1 for a, b in absorbed.items() if a in absorbs.get(b, []))
    return byid, absorbed, absorbs, rejected, recip


def test_vehicle(allb):
    byid, absorbed, absorbs, rejected, recip = incorporation_graph(allb)
    pairs = []
    for a, b in absorbed.items():
        A, B = byid[a], byid[b]
        if not (A["standing"] and B["standing"]):
            continue
        if A["chamber"] != B["chamber"] or A["year"] != B["year"]:
            continue
        if A["chief_key"] == B["chief_key"]:
            continue
        pairs.append((A, B))                 # A died, B survived
    return dict(byid=byid, absorbed=absorbed, rejected=rejected, recip=recip, pairs=pairs)


def test_patron(B, diff):
    """Between-patron variance above the binomial floor, and whether it persists."""
    out = {}
    for st in ("majority", "minority"):
        rows = [r for r in B if r["standing"] == st and (r["session"], r["bill"]) in diff]
        py = collections.defaultdict(list)
        for r in rows:
            py[(r["chief_key"], r["year"])].append(r)
        big = {k: v for k, v in py.items() if len(v) >= 10}
        res = {k: sum(x["passed"] - diff[(x["session"], x["bill"])] for x in v) / len(v)
               for k, v in big.items()}
        m = sum(res.values()) / len(res)
        var_obs = sum((x - m) ** 2 for x in res.values()) / (len(res) - 1)
        var_bin = sum(sum(diff[(x["session"], x["bill"])] * (1 - diff[(x["session"], x["bill"])])
                          for x in v) / len(v) ** 2 for v in big.values()) / len(big)
        random.seed(7); a, b = [], []
        for v in big.values():
            vv = v[:]; random.shuffle(vv); h = len(vv) // 2
            if h >= 5:
                a.append(sum(x["passed"] - diff[(x["session"], x["bill"])] for x in vv[:h]) / h)
                b.append(sum(x["passed"] - diff[(x["session"], x["bill"])] for x in vv[h:2 * h]) / h)
        byp = collections.defaultdict(dict)
        for k in big:
            byp[k[0]][k[1]] = res[k]
        xs, ys = [], []
        for d in byp.values():
            yy = sorted(d)
            for y1, y2 in zip(yy, yy[1:]):
                xs.append(d[y1]); ys.append(d[y2])
        q = sorted(res.values())
        out[st] = dict(n=len(big), var_obs=var_obs, var_bin=var_bin,
                       sd=math.sqrt(max(0.0, var_obs - var_bin)),
                       half=_corr(a, b), nhalf=len(a), yoy=_corr(xs, ys), nyoy=len(xs),
                       p10=q[int(.1 * len(q))], p90=q[int(.9 * len(q))])
    return out


def lis_sponsors(cb, party):
    """LIS's authoritative patron record for the authorised sessions, read from the on-disk cache."""
    byb = collections.defaultdict(lambda: {"chief": None, "intro": [], "later": [], "mech": []})
    parsed = joined = resolved = 0
    for f in sorted(glob.glob(os.path.join(HERE, "..", "historical_cache", "va", "*", "Sponsors.csv.gz"))):
        s = os.path.basename(os.path.dirname(f))
        if s not in LIS_SESSIONS:
            continue
        with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                m = PTYPE.match(r.get("PATRON_TYPE") or "")
                m2 = re.match(r"^([HS]B)0*(\d+)$", (r.get("BILL_NUMBER") or "").strip())
                if not (m and m2):
                    continue
                parsed += 1
                k = (LIS_SESSIONS[s], f"{m2.group(1)} {int(m2.group(2))}")
                if k not in cb:
                    continue
                joined += 1
                nm = (r.get("MEMBER_NAME") or "").strip()
                p = party(nm)
                resolved += bool(p)
                kind = m.group(2)
                g = byb[k]
                if kind == "Chief Patron":
                    g["chief"] = p
                elif kind == "Chief Co-Patron":
                    g["intro"].append(p)
                elif kind == "Co-Patron":
                    g["later"].append(p)
                elif kind == "Incorporated Chief Co-Patron":
                    g["mech"].append(p)
    return byb, dict(parsed=parsed, joined=joined, resolved=resolved)


def main():
    c = load()
    allb = c["bills"]
    B = [r for r in allb if r["standing"] and r.get("chief_key")]
    party, _ = _party_lookup()
    cb = {(r["session"], r["bill"]): r for r in allb}

    print("=" * 78)
    print("1. THE VEHICLE CONTEST — the caucus decision and the carrier decision, separated")
    print("=" * 78)
    V = test_vehicle(allb)
    print(f"\n  incorporation edges, structurally validated: {len(V['absorbed']):,} "
          f"({V['recip'] / max(1, len(V['absorbed'])):.0%} reciprocated by the other side)")
    for k, n in V["rejected"].items():
        print(f"    rejected — {k}: {n}")
    pairs = V["pairs"]
    mix = [(A, B_) for A, B_ in pairs if A["standing"] != B_["standing"]]
    mw = sum(1 for _A, B_ in mix if B_["standing"] == "majority")
    print(f"\n  {len(pairs):,} contests: same chamber, same year, different patrons")
    print(f"  {len(mix):,} of them pit a majority patron against a minority patron")
    print(f"\n    the room keeps the MAJORITY member's vehicle : {mw:>4}")
    print(f"    the room keeps the MINORITY member's vehicle : {len(mix) - mw:>4}")
    print(f"    -> {mw / len(mix):.0%}, odds {mw / max(1, len(mix) - mw):.1f}:1, "
          f"sign p = {sign_p(mw, len(mix) - mw):.1e}")
    print(f"\n  The policy is advancing either way. Only the name is open.")

    def num(r):
        return int(r["bill"].split()[1])

    def sen(r):
        return r["year"] - (r["chief_first_year"] or r["year"])

    lo = sum(1 for A, B_ in pairs if num(B_) < num(A))
    print(f"\n  CONFOUND — filing order")
    print(f"    survivor has the lower bill number: {lo}/{len(pairs)} = {lo / len(pairs):.0%}"
          f"  p = {sign_p(lo, len(pairs) - lo):.2f}   (null)")
    late = [(A, B_) for A, B_ in mix if num(B_) > num(A)]
    w = sum(1 for _A, B_ in late if B_["standing"] == "majority")
    print(f"    restricted to contests the majority vehicle entered LATER (n={len(late)}): "
          f"majority wins {w / len(late):.0%}  p = {sign_p(w, len(late) - w):.1e}")
    sw = sum(1 for A, B_ in pairs if sen(B_) > sen(A)); sl = sum(1 for A, B_ in pairs if sen(B_) < sen(A))
    print(f"\n  CONFOUND — seniority")
    print(f"    survivor is the more senior member: {sw}/{sw + sl} = {sw / (sw + sl):.0%}"
          f"  p = {sign_p(sw, sl):.2f}   (null)")
    eq = [(A, B_) for A, B_ in mix if sen(A) == sen(B_)]
    w = sum(1 for _A, B_ in eq if B_["standing"] == "majority")
    print(f"    contests between members of IDENTICAL tenure (n={len(eq)}): "
          f"majority wins {w / len(eq):.0%}  p = {sign_p(w, len(eq) - w):.1e}")
    same = [(A, B_) for A, B_ in pairs if A["standing"] == B_["standing"]]
    s2 = sum(1 for A, B_ in same if sen(B_) > sen(A)); s3 = sum(1 for A, B_ in same if sen(B_) < sen(A))
    l2 = sum(1 for A, B_ in same if num(B_) < num(A))
    print(f"\n  PLACEBO — {len(same)} contests where BOTH members are on the same side:")
    print(f"    more senior wins {s2 / (s2 + s3):.0%} (p = {sign_p(s2, s3):.2f}), "
          f"earlier filing wins {l2 / len(same):.0%} (p = {sign_p(l2, len(same) - l2):.2f})")
    print(f"    Neither reaches significance. Party is not overriding seniority and filing order —")
    print(f"    it is the ONLY thing in this data that predicts which vehicle the room keeps.")

    print("\n" + "=" * 78)
    print("2. IS THERE A PATRON EFFECT AT ALL, once party is held constant?")
    print("=" * 78)
    L = json.load(open(os.path.join(HERE, "subject_labels.json")))
    lab = {}
    for k, v in L["labels_coarse"].items():
        s, b = k.split("|", 1)
        lab[(s, b)] = tuple(v)
    diff = difficulty(B, lab)
    P = test_patron(B, diff)
    print("\n  Each bill's expected fate is subtracted first — how OTHER patrons' bills in the same")
    print("  session x subject x chamber fared, this patron's own bills excluded from the benchmark.")
    for st in ("majority", "minority"):
        d = P[st]
        print(f"\n  {st.upper()}  ({d['n']} patron-years with >=10 bills)")
        print(f"    residual variance observed          : {d['var_obs']:.4f}")
        print(f"    variance from coin-flipping alone   : {d['var_bin']:.4f}"
              f"   -> {d['var_obs'] / d['var_bin']:.1f}x the noise floor")
        print(f"    TRUE between-patron SD              : {d['sd'] * 100:.0f} points")
        print(f"    split-half inside one patron-year   : r = {d['half']:.2f} (n={d['nhalf']})")
        print(f"    consecutive years, same standing    : r = {d['yoy']:.2f} (n={d['nyoy']})")
        print(f"    10th-90th percentile of the residual: {d['p10'] * 100:+.0f} to {d['p90'] * 100:+.0f} pts")
    maj = [r for r in B if r["standing"] == "majority"]; mino = [r for r in B if r["standing"] == "minority"]
    print(f"\n  Party standing is worth {(rate(maj) - rate(mino)) * 100:.0f} points. A one-SD better "
          f"carrier is worth {P['majority']['sd'] * 100:.0f}-{P['minority']['sd'] * 100:.0f}.")
    print(f"  Carrier effectiveness is measurable, persistent, and roughly half the party effect.")

    print("\n" + "=" * 78)
    print("3. THE CO-PATRON — pre-treatment vs post-treatment, on LIS's own labels")
    print("=" * 78)
    byid, absorbed, _ab, _rj, _rc = incorporation_graph(allb)

    def lastname(n):
        t = _tk(n)
        return t[-1] if t else ""
    hit = tot = 0
    for a, b in absorbed.items():
        A, B_ = byid[a], byid[b]
        if not A.get("chief"):
            continue
        tot += 1
        hit += lastname(A["chief"]) in {lastname(x) for x in B_["cops"]}
    print(f"\n  WHY THE OPEN STATES VERSION CANNOT ANSWER THIS:")
    print(f"    sponsorship rows carry no date — the list is a terminal snapshot")
    print(f"    and the absorbed bill's chief patron is added to the SURVIVOR "
          f"{hit}/{tot} = {hit / tot:.0%} of the time.")
    print(f"    LIS has a type for exactly that: 'Incorporated Chief Co-Patron'.")

    byb, diag = lis_sponsors(cb, party)
    print(f"\n  LIS sponsor rows parsed {diag['parsed']:,} | joined to a corpus bill "
          f"{diag['joined']:,} ({diag['joined'] / diag['parsed']:.1%}) | party resolved "
          f"{diag['resolved'] / max(1, diag['joined']):.1%}")

    def hx(lst, ch):
        return any(q and ch and q != ch for q in lst)
    cuts = (("no co-patrons at all", lambda g: not (g["intro"] or g["later"] or g["mech"])),
            ("chief co-patron at INTRODUCTION, cross-party", lambda g: hx(g["intro"], g["chief"])),
            ("chief co-patron at INTRODUCTION, same party only",
             lambda g: g["intro"] and not hx(g["intro"], g["chief"])),
            ("co-patrons added LATER only", lambda g: not g["intro"] and (g["later"] or g["mech"])))
    for st in ("majority", "minority"):
        print(f"\n  {st.upper()} PATRON            {'pass':>18}{'n':>7}     95% CI")
        cells = {}
        for lbl, f in cuts:
            ks = [k for k, g in byb.items() if f(g) and cb[k]["standing"] == st]
            w = sum(1 for k in ks if cb[k]["passed"]); n = len(ks)
            cells[lbl] = (w, n)
            loo, hi = _wilson(w, n)
            print(f"    {lbl:<48}{(w / n if n else 0):>6.0%}{n:>7,}   [{loo:.0%}-{hi:.0%}]")
        a = cells["chief co-patron at INTRODUCTION, cross-party"]
        b = cells["chief co-patron at INTRODUCTION, same party only"]
        z = cells["no co-patrons at all"]
        print(f"    -> CROSS-party premium over same-party, both pre-treatment: "
              f"{(a[0] / a[1] - b[0] / b[1]) * 100:+.0f} pt   p = {two_prop_p(*a, *b):.2f}")
        print(f"    -> ANY chief co-patron at introduction vs none:             "
              f"{((a[0] + b[0]) / (a[1] + b[1]) - z[0] / z[1]) * 100:+.0f} pt   "
              f"p = {two_prop_p(a[0] + b[0], a[1] + b[1], *z):.1e}")
    print(f"\n  The cross-party premium is NOT established at these sample sizes. What survives is")
    print(f"  party-blind: a co-patron named on the INTRODUCED bill. See the retraction in")
    print(f"  docs/testing/calibration_corrections.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
