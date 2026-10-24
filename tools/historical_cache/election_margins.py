#!/usr/bin/env python3
"""Each legislator's last general-election margin -- the public trace of electoral pressure (owner, 2026-10-16: "derive
the private decisions from public data"). A caucus often lets members in close seats vote against the party on hard
bills; the close seat is public.

Source: Wikipedia election pages, read through the official MediaWiki API (action=parse, wikitext). robots.txt has no rule
against this agent; text is CC BY-SA; numbers come from the pages' "Election box" templates, which cite the Department
of Elections results (elections.virginia.gov). The Department's own results site is a client-side app whose query
interface is undocumented, so it was not reverse-engineered.
Pages: House of Delegates 2019, 2021, 2023, 2025; Senate of Virginia 2019, 2023. 6 requests, 3 s apart.
Output: va_elections/margins.json  {year: {chamber: {winner name: {"district", "margin", "uncontested", "party"}}}}
"""
from __future__ import annotations
import json, os, re, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "va_elections")
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
PAGES = {(2019, "H"): "2019_Virginia_House_of_Delegates_election", (2021, "H"): "2021_Virginia_House_of_Delegates_election",
         (2023, "H"): "2023_Virginia_House_of_Delegates_election", (2025, "H"): "2025_Virginia_House_of_Delegates_election",
         (2019, "S"): "2019_Virginia_Senate_election", (2023, "S"): "2023_Virginia_Senate_election"}
BOX = re.compile(r"\{\{Election box begin[^\n]*\n\|\s*title\s*=\s*(.*?)\n(.*?)\{\{Election box end\}\}", re.S)
CAND = re.compile(r"\{\{Election box (winning candidate|candidate)[^\n]*\n(.*?)\n\}\}", re.S)


def clean(name):
    name = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", name)
    name = re.sub(r"\(.*?\)|<ref.*?</ref>|<ref[^>]*/>", "", name)
    return re.sub(r"\s+", " ", name).strip()


def parse(text, chamber):
    out = {}
    for title, body in BOX.findall(text):
        # 2023/2025 titles say "general election"; 2019/2021 titles carry only "district, <year>"
        if re.search(r"primary|special|firehouse|convention", title, re.I) or "district" not in title.lower():
            continue
        m = re.search(r"(\d+)(?:st|nd|rd|th)", title)
        if not m:
            continue
        cands = []
        for kind, fields in CAND.findall(body):
            f = dict(re.findall(r"\|\s*(\w+)\s*=\s*(.*)", fields))
            v = re.sub(r"[^\d]", "", f.get("votes", "")) or "0"
            cands.append((kind == "winning candidate", clean(f.get("candidate", "")), int(v), f.get("party", "")))
        cands = [c for c in cands if c[1] and "write-in" not in c[1].lower()]
        if not cands:
            continue
        tot = sum(c[2] for c in cands) or 1
        cands.sort(key=lambda c: -c[2])
        win = next((c for c in cands if c[0]), cands[0])
        second = next((c for c in cands if c is not win), None)
        margin = (win[2] - (second[2] if second else 0)) / tot
        out[win[1]] = {"district": int(m.group(1)), "margin": round(margin, 4), "uncontested": second is None,
                       "party": "Democratic" if "Democratic" in win[3] else "Republican" if "Republican" in win[3] else win[3]}
    return out


def main():
    os.makedirs(OUT, exist_ok=True); s = requests.Session(); doc = {}
    for (yr, ch), page in PAGES.items():
        r = s.get("https://en.wikipedia.org/w/api.php", params={"action": "parse", "page": page, "prop": "wikitext",
                                                              "format": "json"}, headers=UA, timeout=60)
        js = r.json()
        if "parse" not in js:
            print(f"{yr} {ch}: page not available ({js.get('error', {}).get('code')}) -- skipped, counted"); continue
        res = parse(js["parse"]["wikitext"]["*"], ch)
        doc.setdefault(str(yr), {})[ch] = res
        print(f"{yr} {ch}: {len(res)} district winners; uncontested {sum(v['uncontested'] for v in res.values())}", flush=True)
        time.sleep(3)
    json.dump(doc, open(os.path.join(OUT, "margins.json"), "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
