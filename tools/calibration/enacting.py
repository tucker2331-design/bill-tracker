#!/usr/bin/env python3
"""The enacting clause — the structural version of "what kind of ask is this bill?"

WHY THIS EXISTS. [[testing/blind_sweep]] found, blind, that a bill whose TITLE says "amend" outperforms one
that says "establish" — and biggest for a minority patron. That was a regex over a title, which Standard #3
forbids on any lobbyist surface. This is the structural replacement.

THE SOURCE. Open States ships each bill's ENACTING CLAUSE as the abstract noted `title`:

    "A BILL to amend and reenact § 58.1-402 of the Code of Virginia, relating to corporate income tax."
    "A BILL to amend the Code of Virginia by adding in Chapter 14 of Title 10.1 an article numbered 3.8."

That is the bill's own formal legal statement of what it does, in a fixed grammar, naming exact Code
sections. Parsing it is reading structural identifiers out of a legal instrument, not keyword-matching
prose — but it is still parsing, so it stays an INTERNAL measure until sourced from LIS directly.

⚠ THE OUTCOME LEAK THAT NEARLY SHIPPED. A bill that PASSES has its title rewritten from "A BILL to…" to
"An Act to…". Matching only "A BILL" therefore SELECTS BILLS THAT DID NOT PASS: the matched subset showed a
18% pass rate against 100% for the unmatched, and every downstream number was fiction. **Both verb forms
must be matched.** With both, the subset's pass rate is 53% against a corpus 53% — the check that caught it.

COVERAGE. Open States carries the clause from the 2025 session forward: 0% for 2017-2024, 61% for 2025,
51% for 2026, 100% for 2027. This can therefore be measured only on 2025-2026, which makes it a genuinely
held-out test of a hypothesis discovered on 2017-2022 titles.

Run:  python3 tools/calibration/enacting.py
"""
from __future__ import annotations
import sys, os, re, io, csv, zipfile, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import committee_votes as CV
from corpus import load
from bill_mix import two_prop_p

ARCHIVES = ("VA_2025.zip", "VA_2026.zip")
D = os.path.join(HERE, "..", "historical_cache", "openstates_va")
CLAUSE = re.compile(r"^\s*(?:A\s+BILL|An\s+Act)\s+to\b", re.I)   # BOTH forms — see the leak note above
SECTION = re.compile(r"\b(\d[\dA-Za-z.]*)-[\dA-Za-z.:]+")
MIN_CELL = 25


def act_type(t):
    """What the bill formally does. Order matters: a clause doing both is its own category."""
    tl = t.lower()
    amend = bool(re.search(r"\bamend and reenact\b", tl))
    add = bool(re.search(r"\bby adding\b", tl))
    if amend and add:
        return "AMEND+ADD"
    if amend:
        return "AMEND"
    if add:
        return "ADD"
    if re.search(r"\brepeal\b", tl):
        return "REPEAL"
    if re.search(r"^\s*(?:a bill|an act) to (?:direct|require|establish|create)\b", tl):
        return "DIRECTIVE"
    return "OTHER"


def _bk(s, b):
    m = re.match(r"^([HS]B)\s*0*(\d+)$", (b or "").strip())
    return (s, f"{m.group(1)} {int(m.group(2))}") if m else None


def build():
    c = load()
    cb = {(r["session"], r["bill"]): r for r in c["bills"]}
    first = collections.defaultdict(lambda: (None, "~"))
    for key, e in CV.load()["events"].items():
        if e["venue"] not in ("committee", "subcommittee"):
            continue
        k = _bk(e["session"], e.get("bill"))
        if not k:
            continue
        d = e.get("date") or "~"
        if d < first[k][1]:
            first[k] = (key[1][:3], d)
    rows = []
    for zf in ARCHIVES:
        path = os.path.join(D, zf)
        if not os.path.exists(path):
            continue
        z = zipfile.ZipFile(path); sess = zf[3:-4]
        bills = list(csv.DictReader(io.StringIO(
            z.read([x for x in z.namelist() if x.endswith("_bills.csv")][0]).decode("utf-8", "replace"))))
        abst = list(csv.DictReader(io.StringIO(
            z.read([x for x in z.namelist() if "bill_abstracts" in x][0]).decode("utf-8", "replace"))))
        idmap = {b["id"]: b["identifier"] for b in bills}
        best = {}
        for a in abst:
            bid = idmap.get(a["bill_id"]); t = (a["abstract"] or "").strip()
            if not bid or not re.match(r"^[HS]B ", bid) or not CLAUSE.match(t):
                continue
            if a["note"] == "title" or bid not in best:
                best[bid] = t
        for bid, t in best.items():
            k = (sess, bid)
            if k not in cb:
                continue
            B = cb[k]
            if not (B["standing"] and B.get("chief_key")):
                continue
            secs = SECTION.findall(t)
            rows.append(dict(k=k, act=act_type(t), nsec=len({s for s in secs}),
                             code_title=(collections.Counter(secs).most_common(1)[0][0] if secs else None),
                             com=first.get(k, (None,))[0], chamber=B["chamber"],
                             passed=B["passed"], standing=B["standing"]))
    return cb, rows


def rate(g):
    return (sum(1 for r in g if r["passed"]) / len(g), len(g)) if g else (0.0, 0)


def main():
    cb, rows = build()
    corpus = [r for r in cb.values() if r["session"] in ("2025", "2026")]
    print("=" * 80)
    print("THE ENACTING CLAUSE — the structural 'what kind of ask is this?'")
    print("=" * 80)
    print(f"\n  bills with a parsed clause: {len(rows):,}")
    print(f"  LEAK CHECK — this subset passes {rate(rows)[0]:.0%}; the 2025-26 corpus passes "
          f"{sum(1 for r in corpus if r['passed']) / len(corpus):.0%}")
    print(f"  (matching only 'A BILL to' gave 18% against 100% for the unmatched — an outcome")
    print(f"   leak, because a bill that passes is retitled 'An Act to'. Both forms are matched.)")

    print(f"\n  {'act type':<14}{'bills':>7}{'passes':>9}{'majority patron':>19}{'minority patron':>19}")
    cells = {}
    for act in ("AMEND", "AMEND+ADD", "ADD", "REPEAL", "DIRECTIVE", "OTHER"):
        g = [r for r in rows if r["act"] == act]
        if len(g) < MIN_CELL:
            continue
        a = [r for r in g if r["standing"] == "majority"]; b = [r for r in g if r["standing"] == "minority"]
        cells[act] = (a, b)
        print(f"  {act:<14}{len(g):>7,}{rate(g)[0]:>9.0%}"
              f"{(f'{rate(a)[0]:.0%} (n={len(a):,})' if len(a) >= 15 else '-'):>19}"
              f"{(f'{rate(b)[0]:.0%} (n={len(b):,})' if len(b) >= 15 else '-'):>19}")
    for st, i in (("MAJORITY", 0), ("MINORITY", 1)):
        a, b = cells["AMEND"][i], cells["ADD"][i]
        ra, rb = rate(a)[0], rate(b)[0]
        print(f"\n  {st}: AMEND {ra:.0%} (n={len(a):,}) vs ADD {rb:.0%} (n={len(b):,})"
              f"   {(ra - rb) * 100:+.0f} pts   "
              f"p = {two_prop_p(round(ra * len(a)), len(a), round(rb * len(b)), len(b)):.1e}")
    print(f"\n  AMEND+ADD sits between the two in both groups — a dose response, which is what")
    print(f"  the mechanism predicts: the more NEW law a bill makes, the worse it does.")

    print("\n" + "=" * 80)
    print("SCOPE IS A NULL — it is not how MUCH you change, it is whether it already exists")
    print("=" * 80)
    print(f"\n  {'sections named':<18}{'bills':>8}{'passes':>9}{'majority':>12}{'minority':>12}")
    for lo, hi, lbl in ((0, 0, "none"), (1, 1, "1"), (2, 2, "2"), (3, 5, "3-5"), (6, 99, "6 or more")):
        g = [r for r in rows if lo <= r["nsec"] <= hi]
        if len(g) < MIN_CELL:
            continue
        a = [r for r in g if r["standing"] == "majority"]; b = [r for r in g if r["standing"] == "minority"]
        print(f"  {lbl:<18}{len(g):>8,}{rate(g)[0]:>9.0%}"
              f"{(f'{rate(a)[0]:.0%}' if len(a) >= 15 else '-'):>12}"
              f"{(f'{rate(b)[0]:.0%}' if len(b) >= 15 else '-'):>12}")
    one = [r for r in rows if r["nsec"] == 1]; many = [r for r in rows if r["nsec"] >= 3]
    print(f"\n  1 section {rate(one)[0]:.0%} vs 3+ sections {rate(many)[0]:.0%}   "
          f"{(rate(one)[0] - rate(many)[0]) * 100:+.0f} pts   "
          f"p = {two_prop_p(round(rate(one)[0] * len(one)), len(one), round(rate(many)[0] * len(many)), len(many)):.2f}")

    print("\n" + "=" * 80)
    print("THE CODE TITLE DECIDES THE ROOM — the drafting lever, structurally")
    print("=" * 80)
    for ch in ("H", "S"):
        m = collections.defaultdict(collections.Counter)
        for r in rows:
            if r["chamber"] == ch and r["code_title"] and r["com"]:
                m[r["code_title"]][r["com"]] += 1
        big = {t: c2 for t, c2 in m.items() if sum(c2.values()) >= MIN_CELL}
        if not big:
            continue
        shares = sorted(c2.most_common(1)[0][1] / sum(c2.values()) for c2 in big.values())
        det = sum(1 for s in shares if s >= 0.80)
        print(f"\n  {ch} chamber — {len(big)} Code Titles with >={MIN_CELL} bills")
        print(f"    top-committee share: median {shares[len(shares) // 2]:.0%}"
              f" (min {shares[0]:.0%}, max {shares[-1]:.0%})")
        print(f"    Titles routing >=80% of their bills to ONE committee: {det}/{len(big)}"
              f" = {det / len(big):.0%}")
        print(f"    {'Code Title':<12}{'bills':>7}{'top committee':>16}{'share':>8}")
        for t, c2 in sorted(big.items(), key=lambda x: -sum(x[1].values()))[:5]:
            tot = sum(c2.values()); top = c2.most_common(1)[0]
            print(f"    {t:<12}{tot:>7,}{top[0]:>16}{top[1] / tot:>8.0%}")
    print(f"\n  In the House the Code Title you amend largely DECIDES the committee. That is the")
    print(f"  drafting lever from [[testing/venue_shopping]], sourced from the bill's own clause")
    print(f"  rather than inferred. The Senate routes far more loosely (median 47%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
