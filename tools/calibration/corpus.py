#!/usr/bin/env python3
"""One loader for the 20-session Open States corpus, so cuts are queries and not new scripts.

Round 1's bugs came from twenty one-off scripts each written once and never checked. This builds a single
per-bill record ONCE, caches it, and every question becomes a filter over it.

Fuzzy companion pairing: VA titles read "Subject; what it does." The subject half is stable and the action
half gets edited, so exact-title matching misses ~10-18% of pairs ("Grand larceny; threshold" vs "Grand
larceny; increases threshold amount"). Measured recall against abstract-derived truth: exact 81-89%,
exact+fuzzy 92-95%.
"""
from __future__ import annotations
import csv, io, json, os, re, zipfile, collections, pickle

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "historical_cache", "openstates_va")
PEOPLE = os.path.join(HERE, "..", "historical_cache", "va", "openstates_va_people.json")
CACHE = os.path.join(HERE, "corpus_cache.pkl")
SUF = {"jr", "sr", "ii", "iii", "iv", "md", "dr"}

def _surname_first(s):
    """Rewrite "Adams, D.M." -> "D.M. Adams", leaving "Norment, Jr." alone.

    THE SESSIONS DO NOT AGREE ON NAME FORMAT. 2023 writes patrons surname-first ("Adams, D.M."); every
    other session writes them given-name-first ("A.C. Cordoza"). Overlap between 2023 and 2024 chief
    patrons was **ZERO of 141**, and because `_tk` just splits on non-letters, "Adams, D.M." tokenised to
    ["adams","d","m"] and the party lookup keyed on "m" as the surname. Result: **2023 resolved a party
    for 3% of its bills against 95-99% everywhere else**, so ~2,000 bills silently vanished from every
    majority/minority finding — the split was computed, reported, and believed on 17 sessions while
    looking like 18.

    A comma is NOT sufficient to detect the format: "Thomas K. Norment, Jr." is given-name-first with a
    suffix. Only swap when the text after the comma is not a suffix."""
    if "," not in (s or ""):
        return s
    head, _, tail = s.partition(",")
    tail_tokens = [t for t in re.sub(r"[^A-Za-z]", " ", tail).lower().split() if t]
    if tail_tokens and all(t in SUF for t in tail_tokens):
        return s                      # "Norment, Jr." — a suffix, already given-name-first
    return f"{tail.strip()} {head.strip()}".strip()


def _tk(s):
    s = _surname_first(s)
    return [t for t in re.sub(r"[^A-Za-z]", " ", s or "").lower().split() if t and t not in SUF]
def norm(t): return re.sub(r"\s+", " ", (t or "").strip().lower().rstrip("."))
def subj(t): return norm((t or "").split(";")[0])
def toks(t): return set(re.findall(r"[a-z]{3,}", (t or "").lower()))

def _party_lookup():
    """Returns (party, person) resolvers. `person` maps any spelling of a patron to ONE canonical roster
    name, which is what makes a patron comparable ACROSS sessions.

    Storing the raw string does not: 2023 writes "McPike", 2024 writes "Jeremy S. McPike", and chief-patron
    overlap between the two sessions was ZERO of 141. Anything keyed on patron identity across sessions —
    seniority, a patron's track record, subject affinity — silently sees every legislator as a new person
    each year."""
    people = json.load(open(PEOPLE))
    fg, fam = {}, collections.defaultdict(list)
    canon_fg, canon_fam = {}, collections.defaultdict(list)
    for nm, rec in people.items():
        t = _tk(nm)
        if len(t) >= 2:
            p = rec["party"] if isinstance(rec, dict) else rec
            fg[(t[-1], t[0])] = p
            fam[t[-1]].append((t[0], p))
            canon_fg[(t[-1], t[0])] = nm
            canon_fam[t[-1]].append((t[0], nm))
    def party(nm):
        t = _tk(nm)
        if not t:
            return None
        # SURNAME ONLY. 2023 writes many chief patrons as a bare surname ("McPike", "Deeds", "Bell"),
        # where every other session writes a full name. The old `len(t) < 2` guard rejected all of them
        # outright, which is why 2023 resolved a party for 3% of its bills against 95-99% elsewhere and
        # ~2,000 bills sat outside every majority/minority finding without appearing to.
        # Resolved ONLY when the surname is unique in the roster — an ambiguous surname returns None
        # rather than picking one, because a wrong party silently flips a bill's `standing`.
        if len(t) == 1:
            c = fam.get(t[0], [])
            parties = {p for _g, p in c}
            return parties.pop() if len(parties) == 1 else None
        if (t[-1], t[0]) in fg: return fg[(t[-1], t[0])]
        c = fam.get(t[-1], [])
        if len(c) == 1: return c[0][1]
        h = {p for g, p in c if g[:1] == t[0][:1]}
        return h.pop() if len(h) == 1 else None

    def person(nm):
        """Canonical roster name, or None when the spelling is genuinely ambiguous (fail closed — a wrong
        identity merges two legislators' records, which is worse than leaving one unresolved)."""
        t = _tk(nm)
        if not t:
            return None
        if len(t) == 1:
            c = canon_fam.get(t[0], [])
            names = {n for _g, n in c}
            return names.pop() if len(names) == 1 else None
        if (t[-1], t[0]) in canon_fg:
            return canon_fg[(t[-1], t[0])]
        c = canon_fam.get(t[-1], [])
        if len(c) == 1:
            return c[0][1]
        h = {n for g, n in c if g[:1] == t[0][:1]}
        return h.pop() if len(h) == 1 else None

    return party, person

def _load(zf, suffix):
    z = zipfile.ZipFile(os.path.join(D, zf))
    n = [x for x in z.namelist() if x.endswith(suffix)]
    if not n: return []
    return list(csv.DictReader(io.TextIOWrapper(z.open(n[0]), encoding="utf-8", errors="replace")))

# 2023S1 is an exact duplicate of the 2023 regular session's identifier set, relabelled. Including it would
# double-count a whole session. Verified 2026-08-02.
SKIP = {"VA_2023S1.zip"}

# Chamber control is PINNED to the historical record, not derived. Deriving it from the sponsoring roster
# got 2 of 11 sessions wrong (2022 Senate, 2023 both chambers) because a near-tied chamber cannot survive
# the few percent of members whose party will not resolve by name. Same failure as the earlier
# voting-bloc derivation, which inverted the 2023 House 52-48. Every majority/minority label in every
# finding rides on this table, so it is data, not inference.
CONTROL = {
    2017: ("Republican", "Republican"), 2018: ("Republican", "Republican"),
    2019: ("Republican", "Republican"), 2020: ("Democratic", "Democratic"),
    2021: ("Democratic", "Democratic"), 2022: ("Republican", "Democratic"),
    2023: ("Republican", "Democratic"), 2024: ("Democratic", "Democratic"),
    2025: ("Democratic", "Democratic"), 2026: ("Democratic", "Democratic"),
    2027: ("Democratic", "Democratic"),
}

def build():
    party, person = _party_lookup()
    sessions, bills = {}, []
    first_seen = {}                       # member -> earliest session year, for seniority
    order = sorted(f for f in os.listdir(D) if f.endswith(".zip") and f not in SKIP)
    for zf in order:
        code = zf[3:-4]
        year = int(re.match(r"(\d{4})", code).group(1))
        b = _load(zf, "_bills.csv"); a = _load(zf, "_bill_actions.csv"); sp = _load(zf, "_bill_sponsorships.csv")
        if not (b and a and sp): continue
        idmap = {x["id"]: x["identifier"] for x in b}
        titles = {x["identifier"]: x["title"] for x in b}
        passed, acts = set(), collections.defaultdict(list)
        for r in a:
            bid = idmap.get(r["bill_id"])
            if not bid: continue
            acts[bid].append((r.get("date", ""), r.get("description", ""), r.get("classification", "")))
            if "'passage'" in (r.get("classification") or ""): passed.add(bid)
        chief, cops = {}, collections.defaultdict(list)
        for r in sp:
            bid = idmap.get(r["bill_id"])
            if not bid: continue
            if str(r.get("primary")).lower() in ("true", "1"): chief.setdefault(bid, r["name"])
            else: cops[bid].append(r["name"])
        if year not in CONTROL:
            continue                      # a session with no pinned control is SKIPPED, never guessed
        maj = {"H": CONTROL[year][0], "S": CONTROL[year][1]}
        # Keyed on the CANONICAL person, not the raw spelling. Keyed on the raw string, "McPike" (2023)
        # and "Jeremy S. McPike" (2024) are two different legislators, so seniority resets for most of the
        # chamber every time the source changes name format — and every session reads as full of freshmen.
        for nm in set(chief.values()):
            key = person(nm) or nm
            first_seen.setdefault(key, year)
            first_seen[key] = min(first_seen[key], year)
        real = [x for x in b if re.match(r"^[HS]B ", x["identifier"])]
        # companion pairing: exact title, else same subject-half + >=0.6 title token overlap
        bys = collections.defaultdict(list)
        for x in real: bys[subj(x["title"])].append(x["identifier"])
        comp = {}
        for sj, ids in bys.items():
            if not sj: continue
            for h in ids:
                for s in ids:
                    if h[0] == s[0] or h >= s: continue
                    ok = norm(titles[h]) == norm(titles[s])
                    if not ok:
                        A, B = toks(titles[h]), toks(titles[s])
                        ok = A and B and len(A & B) / len(A | B) >= 0.6
                    if ok: comp[h] = s; comp[s] = h
        sessions[code] = {"year": year, "majority": maj, "n_bills": len(b)}
        for x in real:
            bid = x["identifier"]; nm = chief.get(bid)
            bills.append({
                "session": code, "year": year, "bill": bid, "chamber": bid[0],
                "title": x["title"], "passed": bid in passed,
                "chief": nm, "chief_party": party(nm) if nm else None,
                "chief_key": person(nm) if nm else None,
                "majority": maj.get(bid[0]),
                "cops": cops[bid], "cop_parties": [party(c) for c in cops[bid]],
                "companion": comp.get(bid),
                "actions": acts[bid],
            })
    for r in bills:
        r["chief_first_year"] = first_seen.get(r.get("chief_key") or r["chief"])
        r["standing"] = (None if not (r["chief_party"] and r["majority"])
                         else ("majority" if r["chief_party"] == r["majority"] else "minority"))
    return {"sessions": sessions, "bills": bills, "first_seen": first_seen}

def load(rebuild=False):
    if not rebuild and os.path.exists(CACHE):
        with open(CACHE, "rb") as fh: return pickle.load(fh)
    c = build()
    with open(CACHE, "wb") as fh: pickle.dump(c, fh)
    return c

if __name__ == "__main__":
    c = load(rebuild=True)
    b = c["bills"]
    print(f"sessions: {len(c['sessions'])} | bills: {len(b):,} | with companion: {sum(1 for x in b if x['companion']):,}")
    print(f"standing resolved: {sum(1 for x in b if x['standing']):,} | distinct patrons: {len(c['first_seen']):,}")
