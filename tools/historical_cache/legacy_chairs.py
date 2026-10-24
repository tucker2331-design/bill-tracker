#!/usr/bin/env python3
"""Committee chairs and vice-chairs by session, 2019-2025, from LIS's legacy session pages.

WHY: the modern API publishes committee ROLES only for the authorized sessions (2025-26), and the legacy CSVs carry
membership without roles -- so a chair test could only run WITHIN 2025. Owner, 2026-09-29: "find the chair roles
from previous years and run the tests with that." The legacy CGI committee page lists every member with "(Chair)" /
"(Vice Chair)" and a member link, per session (e.g. legp604.exe?191+com+H01 = 2019 House Agriculture).

SCOPE AND PACE: pre-2025 sessions come from legacylis (the documented route for them). One page per committee per
session, codes walked H01.. / S01.. until a missing page; 1.5-2.5 s jitter; stop on 429/503 or repeated errors;
cached, never refetched. 2025 (251) is fetched too, ONLY to validate this parser against the API roster chairs.

Output: va_chairs/{session}.json = {committee_code: {"name", "chair", "vice", "members": [(surname, member_id)]}}
Run: python3 tools/historical_cache/legacy_chairs.py
"""
from __future__ import annotations
import json, os, random, re, time
import requests

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va_chairs")
BASE = "https://legacylis.virginia.gov/cgi-bin/legp604.exe"
SESSIONS = {"191": 2019, "201": 2020, "211": 2021, "221": 2022, "231": 2023, "241": 2024, "251": 2025}
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
MEM = re.compile(r'<a href="/cgi-bin/legp604\.exe\?\d+\+mbr\+([HS]\d+)">([^<]+)</a>')


def parse(html):
    m = re.search(r'<h3 class="xpad">\s*(House|Senate)\s+([^<]+?)\s*</h3>', html)
    if not m or "MEMBERSHIP" not in html:
        return None
    members, chair, vice, out_co = [], None, None, []
    block = html[html.find("MEMBERSHIP"):]
    block = block[:block.find("</p>")] if "</p>" in block else block
    for mid, raw in MEM.findall(block):
        t = raw.strip().rstrip(",")
        role = "Chair" if re.search(r"\((Co-)?Chair\)", t) else "Vice" if "(Vice Chair)" in t else None
        surname = re.sub(r"\s*\((Vice |Co-)?Chair\)", "", t).strip()
        members.append((surname, mid))
        if role == "Chair": chair = chair or (surname, mid)        # co-chairs: first listed kept as chair
        if role == "Chair": out_co.append((surname, mid))
        if role == "Vice": vice = (surname, mid)
    return {"name": f"{m.group(1)} {m.group(2).strip()}", "chair": chair, "chairs": out_co, "vice": vice, "members": members}


def main():
    os.makedirs(OUT, exist_ok=True)
    s = requests.Session(); errors = 0
    for code, yr in SESSIONS.items():
        path = os.path.join(OUT, f"{code}.json")
        if os.path.exists(path):
            print(f"{code} cached"); continue
        out = {}
        for ch, top in (("H", 30), ("S", 15)):          # fixed ranges: House codes are NOT sequential (gaps)
            for n in range(1, top + 1):
                cc = f"{ch}{n:02d}"
                time.sleep(random.uniform(1.5, 2.5))
                r = s.get(f"{BASE}?{code}+com+{cc}", headers=UA, timeout=30)
                if r.status_code in (429, 503):
                    raise SystemExit(f"stopped: HTTP {r.status_code} at {code} {cc}")
                if r.status_code != 200:
                    errors += 1
                    if errors > 150: raise SystemExit("stopped: too many errors")
                    continue
                p = parse(r.text)
                if p:
                    out[cc] = p
        json.dump(out, open(path, "w"), indent=0)
        print(f"{code} ({yr}): {len(out)} committees, chairs found {sum(1 for v in out.values() if v['chair'])}", flush=True)


if __name__ == "__main__":
    main()
