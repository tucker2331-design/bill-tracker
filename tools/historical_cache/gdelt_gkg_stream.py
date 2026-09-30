#!/usr/bin/env python3
"""Stream GDELT's bulk Global Knowledge Graph (GKG 2.1) for a session window, keeping only Virginia-legislature rows.

Owner, 2026-09-29: "go ahead with the bulk." GDELT's search API rate-limited us and asked heavy users to use the
bulk files instead; these 15-minute files (6-7.5 MB zipped each, ~40 GB per session) are published for exactly this.
Nothing is stored except the filtered rows: each file is downloaded, filtered in memory, and discarded.

GKG rows describe one article: URL, source, date, themes, locations, persons, organizations, tone -- NOT the article
text, so bill numbers are not recoverable. What IS measurable: how often each LEGISLATOR appears in Virginia news, and
issue-theme volume. Kept when the article's locations include Virginia (ADM1 USVA) AND (a legislation theme OR an
organization naming the General Assembly / House of Delegates / Virginia Senate).

Output: va_gdelt/gkg_{YYYYMMDD}.jsonl.gz, one line per kept article. Resumable: finished days are skipped.
Run: python3 tools/historical_cache/gdelt_gkg_stream.py 2025-01-01 2025-03-15
"""
from __future__ import annotations
import csv, datetime as dt, gzip, io, json, os, re, sys, time, zipfile
import requests

csv.field_size_limit(10**8)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va_gdelt")
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
ORGS = ("general assembly", "house of delegates", "virginia senate", "senate of virginia")


def keep(row):
    locs = row[10] if len(row) > 10 else ""
    # "Virginia, United States" is a SUBSTRING of "West Virginia, United States": the first pilot kept 1,503 West
    # Virginia articles that way (audit #141). Match the ADM1 code, or the name only when not preceded by "West ".
    if "USVA" not in locs and not re.search(r"(?<!West )Virginia, United States", locs):
        return False
    themes = (row[7] if len(row) > 7 else "") + (row[8] if len(row) > 8 else "")
    orgs = (row[13] if len(row) > 13 else "").lower()
    return "LEGISLATION" in themes or "GOV_LEG" in themes or any(o in orgs for o in ORGS)


def slim(row):
    persons = sorted({p.split(",")[0] for p in (row[12] if len(row) > 12 else "").split(";") if p})
    themes = sorted({t.split(",")[0] for t in (row[8] if len(row) > 8 else "").split(";") if t})[:60]
    return {"date": row[1], "src": row[3], "url": row[4], "persons": persons, "themes": themes,
            "tone": (row[15].split(",")[0] if len(row) > 15 and row[15] else "")}


def main(start, end):
    os.makedirs(OUT, exist_ok=True)
    s = requests.Session()
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    day = d0
    while day <= d1:
        path = os.path.join(OUT, f"gkg_{day:%Y%m%d}.jsonl.gz")
        if os.path.exists(path):
            day += dt.timedelta(days=1); continue
        kept, files, missing = [], 0, 0
        for q in range(96):
            ts = dt.datetime.combine(day, dt.time()) + dt.timedelta(minutes=15 * q)
            url = f"http://data.gdeltproject.org/gdeltv2/{ts:%Y%m%d%H%M%S}.gkg.csv.zip"
            for attempt in range(3):
                try:
                    r = s.get(url, headers=UA, timeout=120)
                    break
                except requests.RequestException:
                    time.sleep(10)
            else:
                missing += 1; continue
            if r.status_code != 200:
                missing += 1; continue
            files += 1
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                with z.open(z.namelist()[0]) as fh:
                    for row in csv.reader(io.TextIOWrapper(fh, "utf-8", errors="replace"), delimiter="\t"):
                        if keep(row):
                            kept.append(slim(row))
        tmp = path + ".tmp"
        with gzip.open(tmp, "wt") as out:
            for k in kept:
                out.write(json.dumps(k) + "\n")
        os.replace(tmp, path)
        print(f"{day}: {files} files ({missing} missing), kept {len(kept)} Virginia-legislature articles", flush=True)
        day += dt.timedelta(days=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
