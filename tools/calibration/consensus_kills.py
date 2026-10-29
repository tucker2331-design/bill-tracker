"""Consensus kills: every member of the room votes against the bill at its FIRST recorded vote. What are they?"""
import sys, re, collections, pickle, numpy as np
sys.path.insert(0, "tools/calibration")
import first_vote as FV
from corpus import load
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
D = FV.assemble()
YEARS = {"2019", "2020", "2021", "2022", "2024", "2025"}
recs = []
for key, lst in D["rc"].items():
    if key[0] not in YEARS or key not in corpus: continue
    date, _vo, vid, ven, ballots = lst[0]
    b = corpus[key]
    if b["chief_party"] not in FV.PARTIES or not b["standing"]: continue
    ukill = all(not sup for _w, _p, sup in ballots)
    ufor = all(sup for _w, _p, sup in ballots)
    acts = b["actions"]
    after = " | ".join(t for d, t, _c in acts if d and d >= date).lower()
    before = [t.lower() for d, t, _c in acts if d and d < date]
    recs.append(dict(key=key, ukill=ukill, ufor=ufor, ven=ven, date=date, after=after, before=before, b=b,
                     n_ballots=len(ballots)))
R = recs; K = [r for r in R if r["ukill"]]
print(f"first votes {len(R)}; unanimous kills {len(K)} ({len(K)/len(R):.1%}); unanimous for {sum(r['ufor'] for r in R)/len(R):.1%}")
def rate(label, pred):
    a = [r for r in R if pred(r)]
    if not a: return
    k = sum(r["ukill"] for r in a)
    print(f"  {label:58s} bills {len(a):5d}  consensus-kill rate {k/len(a):6.1%}  share of all kills {k/len(K):6.1%}")
print("\nWHAT HAPPENED (after-text of the kill vote):")
for lab, pat in [("incorporated into another bill", r"incorporat"), ("sent with a letter (study / commission)", r"letter"),
                 ("continued to next session", r"continu"), ("stricken", r"strick|strik"), ("passed by indefinitely", r"indefinitely"),
                 ("tabled", r"tabl"), ("patron's request", r"request of patron|patron'?s request")]:
    k = sum(bool(re.search(pat, r["after"])) for r in K)
    print(f"  {lab:40s} {k:5d} of {len(K)} kills ({k/len(K):.0%})")
print("\nBEFORE THE MEETING — rate of consensus kill when the bill ...")
MONEY = re.compile(r"appropriations|finance")
rate("baseline: every first vote", lambda r: True)
rate("is heard in a money committee (Appropriations/Finance)", lambda r: bool(MONEY.search(FV.first_room(r["b"]) or "")))
rate("has an impact statement from the Sentencing Commission (VCSC)", lambda r: any("vcsc" in t or "sentencing commission" in t for t in r["before"]))
rate("has a fiscal impact statement (DPB)", lambda r: any("fiscal impact" in t or "dpb" in t for t in r["before"]))
rate("was referred to 2+ committees before the vote", lambda r: sum("referred to" in t for t in r["before"]) >= 2)
rate("patron is in the minority party", lambda r: r["b"]["standing"] == "minority")
rate("patron is in the majority party", lambda r: r["b"]["standing"] == "majority")
rate("has no co-patrons", lambda r: not r["b"]["cops"])
rate("vote is in a subcommittee", lambda r: r["ven"] == "sub")
rate("vote is in full committee (no subcommittee)", lambda r: r["ven"] == "com")
rate("was carried over from the previous session", lambda r: any("continued" in t for t in r["before"]))

print("\nCOMBINATIONS (2019-2025 first votes) — consensus-kill rate:")
sub = lambda r: r["ven"] == "sub"; nocop = lambda r: not r["b"]["cops"]; minor = lambda r: r["b"]["standing"] == "minority"
for lab, f in [("subcommittee + no co-patrons + minority patron", lambda r: sub(r) and nocop(r) and minor(r)),
               ("subcommittee + no co-patrons + majority patron", lambda r: sub(r) and nocop(r) and not minor(r)),
               ("subcommittee + has co-patrons", lambda r: sub(r) and not nocop(r)),
               ("subcommittee + 5+ co-patrons", lambda r: sub(r) and len(r["b"]["cops"]) >= 5),
               ("subcommittee + bipartisan co-patrons", lambda r: sub(r) and len(set(r["b"]["cop_parties"]) & set(FV.PARTIES)) == 2)]:
    rate(lab, f)
print("\nHOW each kind of consensus kill splits by patron party (share of that kill type):")
for lab, pat in [("stricken", r"strick|strik"), ("tabled", r"tabl"), ("continued", r"continu"), ("passed by indefinitely", r"indefinitely")]:
    ks = [r for r in K if re.search(pat, r["after"])]
    if ks: print(f"  {lab:24s} {len(ks):4d}  minority patron {sum(minor(r) for r in ks)/len(ks):.0%}  no co-patrons {sum(nocop(r) for r in ks)/len(ks):.0%}")
