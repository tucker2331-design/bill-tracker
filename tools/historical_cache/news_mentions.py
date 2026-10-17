#!/usr/bin/env python3
"""News coverage per bill, from Cardinal News (cardinalnews.org), for the first-vote model.

Owner, 2026-09-29: "look into news coverage next its one of the most consequential determinants statistically in the
academic community for federal level politicians."

SOURCE CHOICE (checked 2026-09-29):
  * Virginia Mercury -- EXCLUDED. Its robots.txt disallows Anthropic's crawlers (ClaudeBot, anthropic-ai,
    Claude-Web) by name and its API answered 403. Respected, not worked around.
  * Cardinal News -- robots.txt permits general access; the public WordPress API answers. Founded 2021, so it covers
    the 2022, 2024 and 2025 sessions used here (2023 fetched for completeness).
WHAT IS KEPT: per article only its date, id, link and the bill numbers it names -- never article text.
PACE: 2.0-3.0 s between requests; stop on 429/503.

Output: va_news/cardinal_{year}.json = [{"id","date","link","bills":["HB 1515", ...]}]
Run: python3 tools/historical_cache/news_mentions.py
"""
from __future__ import annotations
import json, os, random, re, time
import requests

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va_news")
API = "https://cardinalnews.org/wp-json/wp/v2/posts"
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
YEARS = (2022, 2023, 2024, 2025)
PAT = re.compile(r"\b(?:(House|Senate)\s+Bill|([HS])\.?\s?B\.?)\s*(\d{1,4})\b", re.I)


def bills_in(html):
    text = re.sub(r"<[^>]+>", " ", html)
    out = set()
    for full, short, num in PAT.findall(text):
        kind = (full or short).upper()[0]
        out.add(f"{'HB' if kind == 'H' else 'SB'} {int(num)}")
    return sorted(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    s = requests.Session()
    for yr in YEARS:
        path = os.path.join(OUT, f"cardinal_{yr}.json")
        if os.path.exists(path):
            print(f"{yr} cached"); continue
        arts, page, pages = [], 1, None
        while pages is None or page <= pages:
            time.sleep(random.uniform(2.0, 3.0))
            r = s.get(API, headers=UA, timeout=45, params={
                "after": f"{yr - 1}-12-01T00:00:00", "before": f"{yr}-04-15T00:00:00",
                "per_page": 100, "page": page, "_fields": "id,date,link,content", "orderby": "date", "order": "asc"})
            if r.status_code in (429, 503):
                raise SystemExit(f"stopped: HTTP {r.status_code} at {yr} page {page}")
            r.raise_for_status()
            pages = int(r.headers.get("X-WP-TotalPages", "1"))
            for p in r.json():
                arts.append({"id": p["id"], "date": p["date"][:10], "link": p["link"], "bills": bills_in(p["content"]["rendered"])})
            page += 1
        json.dump(arts, open(path, "w"))
        n_b = sum(1 for a in arts if a["bills"])
        print(f"{yr}: {len(arts)} articles, {n_b} name at least one bill, {len({b for a in arts for b in a['bills']})} distinct bills", flush=True)


if __name__ == "__main__":
    main()
