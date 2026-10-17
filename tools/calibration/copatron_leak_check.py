#!/usr/bin/env python3
"""Leak check (statistician, 2026-09-29): the co-patron lists come from Open States sponsorships with NO dates. If
co-patrons are added after a bill's first vote, only survivors can gain them, inflating the co-patron finding.
Compare, for 2025 bills, the co-patrons printed on the INTRODUCED text (as of filing) with the undated list."""
import sys, os, re, glob, collections, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import first_vote as FV
from corpus import load
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
D = FV.assemble()
def filed_patrons(path):
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", open(path, encoding="utf-8", errors="replace").read()))
    m = re.search(r"Patrons?\s*[—–-]+\s*(.+?)\s*[—–]{3,}", t)
    if not m: return None
    s = re.sub(r"(Senators?|Delegates?)\s*:", ",", m.group(1))
    names = [x.strip() for x in re.split(r",|;|\band\b", s) if x.strip() and len(x.strip()) > 1]
    return names
rows = []
for f in glob.glob(os.path.join(HERE, "..", "..", ".va_text_corpus", "blob", "2025", "*.html")):
    bno = re.sub(r"(HB|SB)(\d+)\.html", r"\1 \2", os.path.basename(f)); key = ("2025", bno)
    b = corpus.get(key); fp = filed_patrons(f)
    if not b or fp is None or key not in D["rc"]: continue
    ballots = D["rc"][key][0][4]
    rows.append((max(0, len(fp) - 1), len(b["cops"]), all(not s for *_x, s in ballots), D["rc"][key][0][3]))
R = np.array([(a, b, int(k), int(v == "sub")) for a, b, k, v in rows])
print(f"2025 bills with introduced text + first vote: {len(R)}")
print(f"  co-patrons at filing: mean {R[:,0].mean():.2f} | in the undated list: mean {R[:,1].mean():.2f}")
grew = R[:, 1] > R[:, 0]
print(f"  bills whose undated list has MORE co-patrons than at filing: {grew.mean():.1%}")
for lab, m in (("died unanimously at first vote", R[:, 2] == 1), ("did not", R[:, 2] == 0)):
    print(f"  {lab:32s} n={m.sum():4d}  list grew after filing {grew[m].mean():.1%}  mean extra {np.mean(R[m,1]-R[m,0]):.2f}")
sub = R[:, 3] == 1
for lab, col in (("AT FILING", 0), ("undated list", 1)):
    none, some = sub & (R[:, col] == 0), sub & (R[:, col] > 0)
    print(f"  subcommittee kill rate by co-patrons {lab:13s}: none {R[none,2].mean():.1%} (n={none.sum()})  some {R[some,2].mean():.1%} (n={some.sum()})")
