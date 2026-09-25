#!/usr/bin/env python3
"""Structural features from each bill's INTRODUCED text (2025/2026, fetched by text_corpus/blob_text.py).

The introduced text is what exists before the first vote. Features are read from the legal instrument's
fixed grammar where possible (the enacting clause, the § section list, standard clauses such as
"That the provisions of this act shall not become effective unless an appropriation..."). INTERNAL ONLY
(Standard #3) until sourced structurally; used here to measure whether text carries signal at all.

Both enacting verb forms are matched ("A BILL to" and "An Act to") -- matching only "A BILL" selects bills
that FAILED ([[testing/enacting_clause]] outcome leak).
"""
from __future__ import annotations
import os, re, html, glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, ".va_text_corpus", "blob")
FLAGS = {
    "penalty":     r"civil penalty|penalty of not more than",
    "crime":       r"class \d misdemeanor|class \d felony|is guilty of",
    "approp":      r"appropriation|general fund|nongeneral fund",
    "unfunded":    r"shall not become effective unless an appropriation",
    "study":       r"work group|study|shall report (its findings|to)",
    "moratorium":  r"moratorium",
    "sunset":      r"shall expire on|sunset",
    "emergency":   r"an emergency exists",
    "delayed":     r"shall become effective (on|in) (january|july) 1, 20",
    "prohibit":    r"\bshall not\b|\bprohibit",
    "local":       r"\blocality|locality's|county, city, or town",
    "fee":         r"\bfee\b|\bfees\b",
    "tax":         r"\btax(es|ation)?\b",
}


def _text(path):
    raw = open(path, "rb").read().decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def features(session, bill):
    p = os.path.join(CORPUS, session, bill.replace(" ", "") + ".html")
    if not os.path.exists(p):
        return None
    t = _text(p)
    tl = t.lower()
    m = re.search(r"(a bill|an act) to (.{0,600}?)(?:\bbe it enacted|$)", tl)
    clause = m.group(2) if m else ""
    amend = bool(re.search(r"\bamend and reenact\b", clause))
    add = bool(re.search(r"\bby adding\b", clause))
    repeal = bool(re.search(r"\brepeal", clause))
    out = {"tx_has": 1, "tx_amend": int(amend and not add), "tx_add": int(add and not amend),
           "tx_both": int(amend and add), "tx_repeal": int(repeal),
           "tx_sections": min(len(re.findall(r"§", clause)), 20) / 20,
           "tx_len": min(len(t.split()), 20000) / 20000}
    for k, pat in FLAGS.items():
        out["tx_" + k] = int(bool(re.search(pat, tl)))
    return out


TX_COLS = ["tx_has", "tx_amend", "tx_add", "tx_both", "tx_repeal", "tx_sections", "tx_len"] + ["tx_" + k for k in FLAGS]
EMPTY = {c: 0 for c in TX_COLS}


if __name__ == "__main__":
    import collections
    files = glob.glob(os.path.join(CORPUS, "*", "*.html"))
    print(f"{len(files)} texts cached")
    c = collections.Counter()
    for f in files[:400]:
        s = os.path.basename(os.path.dirname(f)); b = os.path.basename(f)[:-5]
        b = re.sub(r"^([HS]B)(\d+)$", r"\1 \2", b)
        ft = features(s, b)
        for k, v in ft.items():
            if k != "tx_len" and k != "tx_sections":
                c[k] += v
    print({k: v for k, v in c.most_common()})
