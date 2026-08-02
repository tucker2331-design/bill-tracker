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

def _tk(s): return [t for t in re.sub(r"[^A-Za-z]", " ", s or "").lower().split() if t and t not in SUF]
def norm(t): return re.sub(r"\s+", " ", (t or "").strip().lower().rstrip("."))
def subj(t): return norm((t or "").split(";")[0])
def toks(t): return set(re.findall(r"[a-z]{3,}", (t or "").lower()))

def _party_lookup():
    people = json.load(open(PEOPLE))
    fg, fam = {}, collections.defaultdict(list)
    for nm, rec in people.items():
        t = _tk(nm)
        if len(t) >= 2:
            p = rec["party"] if isinstance(rec, dict) else rec
            fg[(t[-1], t[0])] = p
            fam[t[-1]].append((t[0], p))
    def party(nm):
        t = _tk(nm)
        if len(t) < 2: return None
        if (t[-1], t[0]) in fg: return fg[(t[-1], t[0])]
        c = fam.get(t[-1], [])
        if len(c) == 1: return c[0][1]
        h = {p for g, p in c if g[:1] == t[0][:1]}
        return h.pop() if len(h) == 1 else None
    return party

def _load(zf, suffix):
    z = zipfile.ZipFile(os.path.join(D, zf))
    n = [x for x in z.namelist() if x.endswith(suffix)]
    if not n: return []
    return list(csv.DictReader(io.TextIOWrapper(z.open(n[0]), encoding="utf-8", errors="replace")))

# 2023S1 is an exact duplicate of the 2023 regular session's identifier set, relabelled. Including it would
# double-count a whole session. Verified 2026-08-02.
SKIP = {"VA_2023S1.zip"}

def build():
    party = _party_lookup()
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
        maj = {}
        for ch in "HS":
            d, seen = collections.Counter(), set()
            for bid, nm in chief.items():
                if bid[0] == ch and nm not in seen:
                    seen.add(nm); p = party(nm)
                    if p: d[p] += 1
            if d: maj[ch] = d.most_common(1)[0][0]
        for nm in set(chief.values()):
            first_seen.setdefault(nm, year)
            first_seen[nm] = min(first_seen[nm], year)
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
                "majority": maj.get(bid[0]),
                "cops": cops[bid], "cop_parties": [party(c) for c in cops[bid]],
                "companion": comp.get(bid),
                "actions": acts[bid],
            })
    for r in bills:
        r["chief_first_year"] = first_seen.get(r["chief"])
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
