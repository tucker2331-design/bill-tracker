#!/usr/bin/env python3
"""House of Delegates written testimony (HODSpeak) -- per-bill COUNTS only.

Owner, 2026-09-29: cleared the House written-testimony probe ("clear for everything you mentioned"). HODSpeak
(hodspeak.house.virginia.gov, the House Clerk's public-participation site) publishes, per committee meeting, the
written comments submitted for each bill: last name, locality, optional organization, free text. robots.txt is empty
(checked 2026-09-29). This is not the LIS API and needs no key.

PRIVACY: nothing personal is stored. Per bill we keep only counts -- comments, comments naming an organization,
comments whose wording reads as support / opposition (a keyword rule, internal research only, Standard #3) -- and
the organization names that look like organizations (a keyword filter; free-typed personal statements are counted,
not kept). Names, localities and comment text are never written to disk.

LOAD: one request per meeting, 3 s apart, identified user agent; only meetings dated Jan-Mar (the session), so
interim commissions are skipped. Resumable: meetings already parsed are not fetched again.

Output: va_hodspeak/{year}.json  {"meetings": {id: {"date", "committee", "bills": {bill: counts}}}}
Run:    python3 tools/historical_cache/hodspeak_comments.py 2024 2025
"""
from __future__ import annotations
import collections, json, os, re, sys, time, html
import requests

BASE = "https://hodspeak.house.virginia.gov"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va_hodspeak")
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
SUP = re.compile(r"\b(i support|we support|support (this|hb|sb|the bill)|supportive|in (strong )?favor|vote yes|"
                 r"vote for|please pass|urge (you|the committee)? ?to (pass|support|vote yes|report)|endorse)", re.I)
OPP = re.compile(r"\b(oppos\w*|against|vote no|vote against|reject|do not (support|pass)|please vote no|"
                 r"say no|urge (you|the committee)? ?to (vote no|oppose|reject|table|kill))", re.I)
ORGWORD = re.compile(r"association|league|council|coalition|\binc\b|naacp|union|society|foundation|alliance|"
                     r"chamber|federation|center|network|action|club|committee|church|diocese|institute|party|"
                     r"corporation|\bllc\b|project|partnership|advocates|organization|board|commission|"
                     r"department|office|county|city of|town of|virginians for|aclu|sierra|trust|fund", re.I)
# a self-description ("Individual capacity - chair of X", "myself as a volunteer") can identify a person: counted, never kept
PERSONAL = re.compile(r"individual|myself|my self|personal|\bself\b|citizen|resident|volunteer|retired|concerned|"
                      r"parent|mother|father|grandm|voter|taxpayer|\bme\b|\bi am\b|chair of|member of", re.I)
CARD = re.compile(r'<div class="card mt-4 commentCard.*?(?=<div class="card mt-4 commentCard|<footer)', re.S)
BILL = re.compile(r'<span class="heavyLabel">\s*((?:HB|SB|HJ|SJ|HR|SR)\d+)\s*-')
COMMENT = re.compile(r'<div class="card-header cardHighlight">(.*?)<p class="card-text[^"]*">(.*?)</p>', re.S)
ROW = re.compile(r"<tr.*?</tr>", re.S)
MEET = re.compile(r"/meetings/(\d+)/public_comments")
DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def get(s, path):
    for attempt in range(3):
        try:
            r = s.get(BASE + path, headers=UA, timeout=60)
            if r.status_code == 200:
                return r.text
            print(f"  HTTP {r.status_code} on {path} (attempt {attempt + 1})", flush=True)
        except requests.RequestException as e:
            print(f"  request error on {path}: {type(e).__name__} (attempt {attempt + 1})", flush=True)
        time.sleep(15)
    return None


def parse_meeting(page):
    bills = {}
    for card in CARD.findall(page):
        m = BILL.search(card)
        if not m:
            continue
        c = collections.Counter(); orgs = collections.Counter()
        for head, text in COMMENT.findall(card):
            c["comments"] += 1
            t = html.unescape(re.sub(r"<[^>]+>", " ", text))
            s_, o_ = bool(SUP.search(t)), bool(OPP.search(t))
            c["support" if s_ and not o_ else "oppose" if o_ and not s_ else "unclear"] += 1
            org = re.search(r'Organization:</span>\s*<span class="infoText">\s*([^<]*?)\s*</span>', head)
            if org and org.group(1).strip():
                c["with_org"] += 1
                name = html.unescape(org.group(1).strip())
                if ORGWORD.search(name) and not PERSONAL.search(name) and len(name) <= 120:
                    orgs[name] += 1
        # a card can carry only an attachment (0 typed comments) -- every key is written, zeros included
        bills[m.group(1)] = {**{k: c[k] for k in ("comments", "with_org", "support", "oppose", "unclear")},
                             "attachments": card.count("active_storage/blobs"), "orgs": dict(orgs)}
    return bills


def main(years):
    os.makedirs(OUT, exist_ok=True)
    s = requests.Session()
    for y in years:
        path = os.path.join(OUT, f"{y}.json")
        doc = json.load(open(path)) if os.path.exists(path) else {"meetings": {}, "failed": {}}
        idx = get(s, f"/past_meetings?year={y}"); time.sleep(3)
        if idx is None:
            raise SystemExit(f"could not read the {y} meeting list -- stopping (nothing guessed)")
        todo = []
        for row in ROW.findall(idx):
            m, d = MEET.search(row), DATE.search(row)
            if not (m and d):
                continue
            mm, dd, yy = d.groups()
            if int(mm) > 3:
                continue
            name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).replace("View Comments", "").strip()
            name = DATE.sub("", name).strip()
            if m.group(1) not in doc["meetings"]:
                todo.append((m.group(1), f"{yy}-{mm}-{dd}", name))
        print(f"{y}: {len(todo)} session meetings to fetch ({len(doc['meetings'])} already done)", flush=True)
        for i, (mid, date, name) in enumerate(todo):
            page = get(s, f"/meetings/{mid}/public_comments"); time.sleep(3)
            if page is None:
                doc["failed"][mid] = date; continue
            doc["meetings"][mid] = {"date": date, "committee": name, "bills": parse_meeting(page)}
            if i % 20 == 0:
                json.dump(doc, open(path, "w")); print(f"  {i}/{len(todo)}", flush=True)
        json.dump(doc, open(path, "w"))
        nb = sum(len(m["bills"]) for m in doc["meetings"].values())
        print(f"{y}: {len(doc['meetings'])} meetings, {nb} bill-cards, {len(doc['failed'])} failed", flush=True)


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]])
