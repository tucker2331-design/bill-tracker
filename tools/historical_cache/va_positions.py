#!/usr/bin/env python3
"""Association positions on bills -- the stakeholder lineup, from what associations publish themselves.

Owner, 2026-09-29: cleared collecting association position lists ("clear for everything you mentioned").
Sources checked the same day (robots.txt, Anthropic crawlers):
    valcv.org (Virginia League of Conservation Voters)   ALLOWED (crawl-delay 10) -> scorecard PDFs 2019-2025
    familyfoundation.org                                   BLOCKS ClaudeBot / anthropic-ai -> not used
    vpap.org, nfib.com                                     403 to automated requests -> not used
    vachamber.com, vaco.org, vml.org, veanea.org, afphq    allowed; no per-bill position list found yet
The in-session list at scale is HODSpeak's organization field (hodspeak_comments.py); this file holds the
positions an association states for itself.

VALCV scorecards: each scored item is a header "House Bill N - Del. X (P-Place) / Senate Bill M - ..." followed by
"Virginia LCV Position: Support|Oppose". 2019-2021 print the position as an icon that extracts as "p" (check =
support) or "X" (cross = oppose). A scorecard is written AFTER the session, so which bills it includes is chosen
knowing the votes -- but the position itself was public during the session. Use it only conditionally (among scored
bills), never as a signal that a bill is important.

PDFs (5-48 MB each) are cached OUTSIDE git (va_positions/valcv_pdf/, gitignored) and re-downloadable; the parsed
positions (va_positions/valcv.json) are committed.
Run: python3 tools/historical_cache/va_positions.py
"""
from __future__ import annotations
import json, os, re, sys, time, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "va_positions")
PDFDIR = os.path.join(OUT, "valcv_pdf")
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
BASE = "https://valcv26.wpenginepowered.com/wp-content/uploads/2026/08/"
FILES = {2019: "2019_scorecard_final_sized.pdf", 2020: "2020-Conservation-Scorecard_FINAL_3.pdf",
         2021: "2021-Conservation-Scorecard_final_3.pdf", 2022: "2022-Conservation-Scorecard_FINAL.pdf",
         2023: "2023-Conservation-Scorecard.pdf", 2024: "2024-Conservation-Scorecard_Revised.pdf",
         2025: "2025-Conservation-Scorecard_Final.pdf"}
POS = re.compile(r"LCV Position:\s*(Support|Oppose|p|X)\b", re.I)
# headers spell the chamber out ("House Bill 528 - Del. ..."); story text uses "HB 528", so only the full form
# is read -- the short form picked up the PREVIOUS item's story and produced conflicting labels (26 across 7 years)
BILL = re.compile(r"\b(House|Senate)\s+Bill\s+(\d{1,4})\b")


def text(year):
    path = os.path.join(PDFDIR, f"{year}.pdf")
    if not os.path.exists(path):
        import requests
        os.makedirs(PDFDIR, exist_ok=True)
        r = requests.get(BASE + FILES[year], headers=UA, timeout=300)
        if r.status_code != 200:
            raise SystemExit(f"VALCV {year}: HTTP {r.status_code} -- nothing guessed")
        open(path, "wb").write(r.content)
        time.sleep(10)                                   # the site's crawl-delay
    import pypdf
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import logging; logging.getLogger("pypdf").setLevel(logging.ERROR)
        return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(path).pages)


def parse(t):
    """bill -> position. The bills in the ~400 characters BEFORE each position marker (the item header)."""
    out, conflicts = {}, 0
    prev = 0
    for m in POS.finditer(t):
        head = t[max(prev, m.start() - 400):m.start()]
        pos = {"p": "Support", "x": "Oppose"}.get(m.group(1).lower(), m.group(1).capitalize())
        for b in BILL.finditer(head):
            bill = f"{b.group(1)[0]}B {b.group(2)}"
            if out.get(bill, pos) != pos:
                conflicts += 1
            out[bill] = pos
        prev = m.end()
    return out, conflicts


def main():
    os.makedirs(OUT, exist_ok=True)
    doc = {}
    for y in sorted(FILES):
        pos, conf = parse(text(y))
        doc[str(y)] = pos
        print(f"{y}: {len(pos)} bills ({sum(v == 'Support' for v in pos.values())} support, "
              f"{sum(v == 'Oppose' for v in pos.values())} oppose), {conf} conflicting labels", flush=True)
    json.dump({"source": "VALCV Conservation Scorecards (valcv.org/scorecard-archives)", "positions": doc},
              open(os.path.join(OUT, "valcv.json"), "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
