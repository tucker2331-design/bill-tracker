#!/usr/bin/env python3
"""District make-up, extended (owner 2026-10-24: "weve gone real deep on the internals but not the externals ... district
make up etc").

Extends districts.py in two ways:
  1. BOTH MAPS. ACS 2023 5-year sits on the 2022 maps (sessions 2024+); ACS 2021 5-year sits on the previous maps
     (sessions 2020-2023). The model could only learn district effects from 2024 on; now it can from 2020.
  2. MORE MEASURES (same codes in 2021 and 2023, checked against the API's variable labels 2026-10-24):
     industry (agriculture/forestry/fishing/mining, manufacturing, public administration), armed forces, civilian
     veterans, foreign born, unemployed, public transit commuters, renters; plus the original race / income /
     education / poverty / age set; plus land area (Census Gazetteer) for population density.
Source: Census Bureau, public domain (17 USC 105). The API now REQUIRES a key (2026-10-24: requests without one
redirect to missing_key.html) -- read from CENSUS_API_KEY in the owner's own terminal, never stored. Requests: 2 per year x
chamber (detailed + profile tables) = 8, plus 4 Gazetteer files. Fetched once, cached in va_districts/.
Run: python3 districts_ext.py fetch
"""
from __future__ import annotations
import os, sys, json, gzip, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "va_districts")
UA = {"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}
DETAIL = ["NAME", "B01003_001E", "B03002_001E", "B03002_003E", "B03002_004E", "B03002_012E", "B19013_001E",
          "B15003_001E", "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E", "B17001_001E", "B17001_002E",
          "B01002_001E"]
PROFILE = ["DP03_0033PE", "DP03_0035PE", "DP03_0045PE", "DP03_0006PE", "DP02_0070PE", "DP02_0094PE", "DP03_0005PE",
           "DP03_0021PE", "DP04_0047PE"]
GEO = {"lower": "state legislative district (lower chamber)", "upper": "state legislative district (upper chamber)"}
# land area: the Gazetteer files geo_signal.py already saved (Virginia rows of the national files; the per-state
# file names used at first do not exist for legislative districts -- 404)
GAZ = {("2023", "lower"): "gaz_2023_H.txt", ("2023", "upper"): "gaz_2023_S.txt",
       ("2021", "lower"): "gaz_2021_H.txt", ("2021", "upper"): "gaz_2021_S.txt"}


KEY = os.environ.get("CENSUS_API_KEY")   # owner's key: set ONLY in the owner's terminal, never in files / git / chat


def get(url, params=None):
    if params is not None:
        if not KEY:
            raise SystemExit("CENSUS_API_KEY is not set in this terminal -- the Census API now requires a key "
                             "(it redirects to missing_key.html). Run this in the terminal where the key is exported.")
        params = dict(params, key=KEY)
    for attempt in range(3):
        time.sleep(1.5)
        r = requests.get(url, params=params, headers=UA, timeout=60)
        if r.status_code == 200:
            return r
        print(f"  HTTP {r.status_code} on {url} (attempt {attempt + 1})"); time.sleep(10 * (attempt + 1))
    raise SystemExit(f"giving up on {url} after 3 tries")


def fetch():
    n = 0
    for year in ("2021", "2023"):
        for ch, geo in GEO.items():
            path = os.path.join(OUT, f"ext_{year}_{ch}.json.gz")
            if os.path.exists(path):
                print(f"{year} {ch}: cached"); continue
            rows = {}
            for ds, vars_ in ((f"https://api.census.gov/data/{year}/acs/acs5", DETAIL),
                              (f"https://api.census.gov/data/{year}/acs/acs5/profile", ["NAME"] + PROFILE)):
                js = get(ds, {"get": ",".join(vars_), "for": f"{geo}:*", "in": "state:51"}).json(); n += 1
                head = js[0]
                for rec in js[1:]:
                    d = dict(zip(head, rec)); key = d[geo]
                    rows.setdefault(key, {}).update(d)
            g = open(os.path.join(OUT, GAZ[(year, ch)])).read()
            lines = g.strip().splitlines(); h = [x.strip() for x in lines[0].split("\t")]
            for line in lines[1:]:
                d = dict(zip(h, [x.strip() for x in line.split("\t")]))
                key = d["GEOID"][2:]
                if key in rows:
                    rows[key]["ALAND_SQMI"] = d.get("ALAND_SQMI")
            json.dump(rows, gzip.open(path, "wt"))
            print(f"{year} {ch}: {len(rows)} districts, land area for {sum('ALAND_SQMI' in v for v in rows.values())}")
    print(f"requests made: {n}")


if __name__ == "__main__":
    {"fetch": fetch}[sys.argv[1]]()
