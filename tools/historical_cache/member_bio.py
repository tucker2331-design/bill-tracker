#!/usr/bin/env python3
"""Who the legislators are outside the chamber (owner 2026-10-24: "more into nitty gritty stuff ... the externals").

Occupation, military service, age and gender as public facts, from Wikipedia through its official MediaWiki API (the
same channel as election_margins.py; robots.txt has no rule against this agent; text CC BY-SA, facts only kept).
Steps: (1) the general-election pages 2015-2025 give each winner's Wikipedia page title (the [[link]] in the election
box) and district; (2) pages fetched 50 titles per request: categories + the infobox wikitext. Kept per member:
  occupation flags from categories / infobox (lawyer, physician / nurse / health, farmer, teacher / educator, business,
  law enforcement), military service (infobox branch / service, or a military personnel category), birth year,
  woman (Wikipedia category "Women state legislators in Virginia").
~8 election pages + ~10 batched page requests, 2-3 s apart. Output: va_members/bios.json
Run: python3 member_bio.py fetch
"""
from __future__ import annotations
import os, re, json, time, collections
import requests

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "va_members")
API = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
PAGES = {(2015, "S"): "2015_Virginia_Senate_election", (2017, "H"): "2017_Virginia_House_of_Delegates_election",
         (2019, "H"): "2019_Virginia_House_of_Delegates_election", (2021, "H"): "2021_Virginia_House_of_Delegates_election",
         (2023, "H"): "2023_Virginia_House_of_Delegates_election", (2025, "H"): "2025_Virginia_House_of_Delegates_election",
         (2019, "S"): "2019_Virginia_Senate_election", (2023, "S"): "2023_Virginia_Senate_election"}
BOX = re.compile(r"\{\{Election box begin[^\n]*\n\|\s*title\s*=\s*(.*?)\n(.*?)\{\{Election box end\}\}", re.S)
WIN = re.compile(r"\{\{Election box winning candidate[^\n]*\n(.*?)\n\}\}", re.S)
OCC = {"lawyer": r"lawyer|attorney|prosecutor", "health": r"physician|surgeon|nurse|pharmacist|dentist|doctor|physical therapist",
       "farmer": r"farmer|rancher|agricultur", "educator": r"teacher|educator|\bprofessor|school principal|school administrator", "business": r"businessperson|business owner|businessman|businesswoman|entrepreneur|executive",
       "police": r"police|sheriff|law enforcement"}
MIL = r"united states (army|navy|marine corps|air force|coast guard)|military personnel|veterans|army officers|navy officers|marine corps officers"


def api(params):
    for attempt in range(3):
        time.sleep(2.5)
        r = requests.get(API, params=dict(params, format="json", formatversion=2), headers=UA, timeout=60)
        if r.status_code == 200:
            return r.json()
        print(f"  HTTP {r.status_code} (attempt {attempt + 1})"); time.sleep(15 * (attempt + 1))
    raise SystemExit("Wikipedia API failing -- stopping")


def winners():
    out = {}
    for (yr, ch), page in PAGES.items():
        js = api({"action": "parse", "page": page, "prop": "wikitext"})
        t = js.get("parse", {}).get("wikitext", "")
        n = 0
        for title, body in BOX.findall(t):
            if re.search(r"primary|special|firehouse|convention", title, re.I) or "district" not in title.lower():
                continue
            m = re.search(r"(\d+)(?:st|nd|rd|th)", title); w = WIN.search(body)
            if not (m and w):
                continue
            f = dict(re.findall(r"\|\s*(\w+)\s*=\s*(.*)", w.group(1)))
            link = re.search(r"\[\[([^|\]]+)(?:\|([^\]]*))?\]\]", f.get("candidate", ""))
            if link:
                out.setdefault(link.group(1).strip(), []).append({"year": yr, "chamber": ch, "district": int(m.group(1)),
                                                                   "name": (link.group(2) or link.group(1)).strip()})
                n += 1
        print(f"{yr} {ch}: {n} winners with a Wikipedia page", flush=True)
    return out


def fetch():
    os.makedirs(OUT, exist_ok=True)
    W = winners(); titles = sorted(W); bios = {}; covered = set()
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        js = api({"action": "query", "titles": "|".join(chunk), "prop": "categories|revisions", "cllimit": "max",
                  "rvprop": "content", "rvslots": "main", "redirects": 1})
        back = collections.defaultdict(list)       # redirect target -> the election-page titles that point to it
        for rd in js.get("query", {}).get("redirects", []) + js.get("query", {}).get("normalized", []):
            back[rd["to"]].append(rd["from"])
        for pg in js.get("query", {}).get("pages", []):
            cats = " | ".join(c["title"].lower() for c in pg.get("categories", []))
            txt = (pg.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content", "")
            box = txt[:txt.find("\n'''")] if "\n'''" in txt else txt[:6000]
            fields = dict((k.strip().lower(), v.strip()) for k, v in re.findall(r"\n\|\s*([a-z_ ]+?)\s*=\s*([^\n]*)", box))
            occ_src = (fields.get("occupation", "") + " " + fields.get("profession", "") + " " + cats).lower()
            by = re.search(r"birth[_ ]date[^|]*\|\s*(\d{4})", box, re.I)
            bios[pg["title"]] = {
                **{k: bool(re.search(v, occ_src)) for k, v in OCC.items()},
                "military": bool(fields.get("branch") or fields.get("serviceyears") or re.search(MIL, cats)),
                "birth_year": int(by.group(1)) if by else None,
                "woman": "women state legislators in virginia" in cats,
                "occupation_field": (fields.get("occupation", "") + " | " + fields.get("profession", ""))[:300],
                "categories": cats[:3000],
                "seats": W.get(pg["title"], []) + [x for f in back.get(pg["title"], []) for x in W.get(f, [])]}
            for f in back.get(pg["title"], []):
                covered.add(f)
            covered.add(pg["title"])
        print(f"  pages {i + len(chunk)} of {len(titles)}", flush=True)
    # titles that redirected keep their seats under the redirect target name
    for t, seats in W.items():
        if t not in covered:
            bios.setdefault(t, {"seats": seats, "missing_page": True})
    json.dump(bios, open(os.path.join(OUT, "bios.json"), "w"), indent=1, sort_keys=True)
    have = [b for b in bios.values() if not b.get("missing_page")]
    print(f"members with a page: {len(have)}; lawyer {sum(b['lawyer'] for b in have)}, health {sum(b['health'] for b in have)}, "
          f"farmer {sum(b['farmer'] for b in have)}, educator {sum(b['educator'] for b in have)}, business {sum(b['business'] for b in have)}, "
          f"police {sum(b['police'] for b in have)}, military {sum(b['military'] for b in have)}, women {sum(b['woman'] for b in have)}, "
          f"birth year {sum(b['birth_year'] is not None for b in have)}")


if __name__ == "__main__":
    {"fetch": fetch}[__import__("sys").argv[1]]()
