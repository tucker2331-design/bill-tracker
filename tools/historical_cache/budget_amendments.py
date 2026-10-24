#!/usr/bin/env python3
"""Members' budget amendment requests, 2025 + 2026 regular sessions (owner OK 2026-10-23: "you have the ok to exhaust all
of the non ai tests assuming youve fully checked we arent violating internal or external policy (incluiding TOS etc)").

Why: a patron who puts the same idea into the budget often strikes or continues the bill (owner, 2026-10-23).
Source + policy check: [[knowledge/budget_portal]] -- DLAS site, no robots.txt, LIS rules applied (2025/2026 only,
personal research use per the 2026-09-24 owner decision on the LIS ToS). The web service returns empty lists, so the
public HTML pages are read: /amendments/<year>/1/<budget bill>/Introduced/MR/ (Member Request).
Guardrails (lis_api_safety): #1 each page fetched ONCE and cached (re-runs read the cache); #2 jittered 4-9 s gaps;
#3 retry with backoff on 429/5xx, STOP after 2 consecutive failures; #4 hard cap MAX_REQUESTS for the whole run;
#5 one-off, run off-session (October). Session check: lis_authorization.assert_lis_authorized before every request.
Run: python3 budget_amendments.py fetch | show
"""
from __future__ import annotations
import os, sys, time, random, re, html
import requests
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, ROOT)
from lis_authorization import assert_lis_authorized

OUT = os.path.join(HERE, "va_budget")
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
PAGES = {("20261", "HB30"): "https://budget.lis.virginia.gov/amendments/2026/1/HB30/Introduced/MR/",
         ("20261", "SB30"): "https://budget.lis.virginia.gov/amendments/2026/1/SB30/Introduced/MR/",
         ("20251", "HB1600"): "https://budget.lis.virginia.gov/amendments/2025/1/HB1600/Introduced/MR/",
         ("20251", "SB800"): "https://budget.lis.virginia.gov/amendments/2025/1/SB800/Introduced/MR/"}
MAX_REQUESTS = 12


def fetch():
    os.makedirs(OUT, exist_ok=True); n = 0; fails = 0; s = requests.Session()
    for (code, bb), url in PAGES.items():
        assert_lis_authorized(code)
        path = os.path.join(OUT, f"mr_{code}_{bb}.html")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            print(f"{code} {bb}: cached ({os.path.getsize(path):,} bytes)"); continue
        for attempt in range(3):
            if n >= MAX_REQUESTS:
                raise SystemExit(f"request cap {MAX_REQUESTS} reached -- stopping (guardrail #4)")
            time.sleep(random.uniform(4, 9)); n += 1
            r = s.get(url, headers=UA, timeout=90)
            if r.status_code == 200:
                open(path, "wb").write(r.content); fails = 0
                print(f"{code} {bb}: {len(r.content):,} bytes"); break
            print(f"{code} {bb}: HTTP {r.status_code} (attempt {attempt + 1})")
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(30 * (attempt + 1)); continue
            break
        else:
            fails += 1
        if fails >= 2:
            raise SystemExit("two consecutive failures -- stopping (guardrail #3)")
    print(f"requests made: {n}")


def text(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))


def show():
    for (code, bb) in PAGES:
        p = os.path.join(OUT, f"mr_{code}_{bb}.html")
        if os.path.exists(p):
            x = text(p); print(f"== {code} {bb}: {len(x):,} chars"); print(x[x.find("Member Request"):][:1500])


# date each chamber's member requests became public (LIS HISTORY.CSV "Budget amendments available", first entry)
PUBLIC = {("20251", "HB1600"): "2025-01-17", ("20251", "SB800"): "2025-01-15",
          ("20261", "HB30"): "2026-01-22", ("20261", "SB30"): "2026-01-21"}
MEMBER = re.compile(r"([A-Z][A-Za-z.' -]{1,40}?) First Year - FY\d{4} Second Year - FY\d{4}")
REF = re.compile(r"\b(HB|SB)\s?(\d{1,4})\b")


def parse():
    """-> list of dicts: session, budget bill, public date, member surname, item title, cited bills, dollars."""
    out = []
    for (code, bb), date in PUBLIC.items():
        x = text(os.path.join(OUT, f"mr_{code}_{bb}.html"))
        x = x[x.find("Spreadsheet"):]
        parts = MEMBER.split(x)                       # [pre, name1, body1, name2, body2, ...]
        for name, body in zip(parts[1::2], parts[2::2]):
            for m in re.finditer(r"#\d+[hs] (.*?)(?=(?:\s\S+ #\d+[hs] )|$)", body):
                title = m.group(1).strip()
                refs = sorted({f"{a} {int(b)}" for a, b in REF.findall(title) if f"{a}{b}" != bb})
                dollars = sum(int(v.replace(",", "")) for v in re.findall(r"\$([\d,]+)", title))
                out.append({"session": code[:4], "budget": bb, "public": date, "member": name.strip().split()[-1],
                            "title": title[:200], "refs": refs, "dollars": dollars})
    return out


def summary():
    A = parse()
    import collections
    print("amendments parsed:", collections.Counter((a["session"], a["budget"]) for a in A))
    print("citing a bill:", collections.Counter((a["session"], a["budget"]) for a in A if a["refs"]))
    for a in [a for a in A if a["refs"]][:6]:
        print("  ", a["session"], a["member"], a["refs"], a["dollars"], a["title"][:90])


if __name__ == "__main__":
    {"fetch": fetch, "show": show, "summary": summary}[sys.argv[1]]()
