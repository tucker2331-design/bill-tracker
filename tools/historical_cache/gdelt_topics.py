#!/usr/bin/env python3
"""Public attention on each ISSUE during each session: daily count of Virginia news articles per bill topic (GDELT).

Owner, 2026-09-29: "sourcing the news hypothesis from one source is a mistake and misses the substance of the
hypothesis which is about public discourse ... see if you could pull regional searches or other items that indicate
public attention on a issue or bill."

WHY GDELT, AND WHY TOPIC-LEVEL: GDELT monitors online news worldwide as open research data; its DOC 2.0 API returns
daily article counts for a full-text query back to 2017. Its rate limit is one request per 5 s and it asks heavy users
not to hammer it, so a per-BILL query (~9,300 bills, ~13 h) is ruled out; per-TOPIC per-session is ~140 requests.
Sources checked and excluded on 2026-09-29 (robots.txt blocks Anthropic crawlers): Virginia Mercury, Blue Virginia,
WRIC, WSLS, Virginia Business. No published per-bill public-comment record exists for us to use.

The subject -> keyword map below is an explicit, reviewable choice (one query per coarse LIS subject). Each query is
restricted to Virginia + the legislature, so it measures STATE issue coverage, not national noise.
Output: va_attention/gdelt_{year}.json = {subject: {"YYYYMMDD": article_count}}
"""
from __future__ import annotations
import json, os, time
import requests

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "va_attention")
API = "https://api.gdeltproject.org/api/v2/doc/doc"
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
YEARS = (2019, 2020, 2021, 2022, 2024, 2025)
TOPIC = {   # the 20 most common coarse LIS subjects (subject_labels.json) -> news keywords, ANDed with Virginia + legislature
    "Education": '(school OR schools OR teachers OR education)',
    "Taxation": '(tax OR taxes)',
    "Administration of Government": '("state agency" OR "state agencies" OR "Freedom of Information" OR FOIA)',
    "Crimes and Offenses Generally": '(crime OR penalty OR felony OR misdemeanor)',
    "Motor Vehicles": '(driver OR drivers OR "motor vehicle" OR DMV OR traffic)',
    "Elections": '(election OR elections OR voting OR voter OR voters)',
    "Health": '(health OR hospital OR Medicaid OR medical)',
    "Criminal Procedure": '(sentencing OR bail OR prosecutor OR expungement OR parole)',
    "Professions and Occupations": '(license OR licensing OR occupational)',
    "Public Service Companies": '(utility OR utilities OR Dominion OR electricity OR "data center" OR "data centers")',
    "Insurance": '(insurance OR insurer OR insurers)',
    "Conservation": '(environment OR environmental OR conservation OR Chesapeake)',
    "Educational Institutions": '(university OR universities OR college OR colleges OR tuition)',
    "Civil Remedies and Procedure": '(lawsuit OR lawsuits OR liability OR damages)',
    "Housing": '(housing OR rent OR renters OR landlord OR landlords OR eviction)',
    "Property and Conveyances": '(property OR homeowners OR "real estate")',
    "Trade and Commerce": '(business OR businesses OR consumer OR consumers)',
    "Labor and Employment": '(workers OR wage OR wages OR employment OR union OR unions)',
    "Behavioral Health and Developmental Services": '("mental health" OR "behavioral health" OR psychiatric)',
    "Prisons and Other Methods of Correction": '(prison OR prisons OR inmates OR incarceration OR jail)',
}
SCOPE = 'Virginia ("General Assembly" OR legislature OR legislators OR lawmakers)'


def main():
    os.makedirs(OUT, exist_ok=True)
    s = requests.Session()
    for yr in YEARS:
        path = os.path.join(OUT, f"gdelt_{yr}.json")
        data = json.load(open(path)) if os.path.exists(path) else {}
        for subj, kw in TOPIC.items():
            if subj in data:
                continue
            for attempt in range(6):
                time.sleep(8.0)                                     # GDELT asks for >= 5 s between requests; 8 s after a 429 run
                r = s.get(API, headers=UA, timeout=90, params={
                    "query": f"{kw} {SCOPE}", "mode": "timelinevolraw", "format": "json",
                    "startdatetime": f"{yr - 1}1215000000", "enddatetime": f"{yr}0415000000"})
                if r.status_code == 429:
                    time.sleep(75); continue
                r.raise_for_status()
                try:
                    tl = r.json()["timeline"][0]["data"]
                except (ValueError, KeyError, IndexError):
                    tl = []
                data[subj] = {d["date"][:8]: d["value"] for d in tl}
                break
            else:
                raise SystemExit(f"stopped: repeated 429 at {yr} {subj}")
            json.dump(data, open(path, "w"))
        tot = {k: sum(v.values()) for k, v in data.items()}
        print(f"{yr}: {len(data)} topics; articles: " + ", ".join(f"{k.split()[0]} {v}" for k, v in list(tot.items())[:6]) + " ...", flush=True)


if __name__ == "__main__":
    main()
