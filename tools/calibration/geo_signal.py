#!/usr/bin/env python3
"""Geography: regional allies and rural districts (owner 2026-10-24: "the externals ... district make up").

Census Gazetteer files (public domain, static files on www2.census.gov, no key; robots.txt has no rule for general
agents) give every Virginia House / Senate district's land area and interior point. 2021 files = the previous maps
(sessions 2020-2023), 2023 files = the 2022 maps (sessions 2024+). Members are placed in districts by the general
election that seated them (historical_cache/va_elections/margins.json: House 2019 -> 2020-21, 2021 -> 2022-23,
2023 -> 2024-25, 2025 -> 2026; Senate 2019 -> 2020-23, 2023 -> 2024+).
Inputs x voter side:
  near      the voter's district is within 40 km of the patron's (regional caucus / neighbouring localities)
  dist      log km between the two districts' interior points
  rural     log land area of the voter's district (big = rural), centred on the chamber
Run: python3 rerun_no2021.py geo_signal:-      (download once: python3 geo_signal.py fetch)
"""
from __future__ import annotations
import sys, os, json, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from corpus import load, _party_lookup

GZ = os.path.join(HERE, "..", "historical_cache", "va_districts")
# national files (only form published for legislative districts); the Virginia rows (USPS = VA) are kept
FILES = {("2021", "H"): "2021_Gazetteer/2021_Gaz_sldl_national.zip", ("2021", "S"): "2021_Gazetteer/2021_Gaz_sldu_national.zip",
         ("2023", "H"): "2023_Gazetteer/2023_Gaz_sldl_national.zip", ("2023", "S"): "2023_Gazetteer/2023_Gaz_sldu_national.zip"}


def fetch():
    import requests
    for (y, ch), f in FILES.items():
        p = os.path.join(GZ, f"gaz_{y}_{ch}.txt")
        if os.path.exists(p):
            continue
        time.sleep(3)
        r = requests.get("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/" + f,
                         headers={"User-Agent": "bill-tracker research (tucker2331@gmail.com)"}, timeout=60)
        r.raise_for_status()
        import zipfile, io
        z = zipfile.ZipFile(io.BytesIO(r.content)); txt = z.read(z.namelist()[0]).decode("latin-1").splitlines()
        keep = [txt[0]] + [l for l in txt[1:] if l.startswith("VA\t") or l.split("\t")[0].strip() == "VA"]
        open(p, "w").write("\n".join(keep)); print(y, ch, len(keep) - 1, "Virginia districts")


def _gaz():
    G = {}
    for (y, ch) in FILES:
        lines = open(os.path.join(GZ, f"gaz_{y}_{ch}.txt")).read().strip().splitlines()
        h = [x.strip() for x in lines[0].split("\t")]
        for line in lines[1:]:
            d = dict(zip(h, [x.strip() for x in line.split("\t")]))
            num = d["GEOID"][2:].lstrip("0")
            if num.isdigit():
                G[(y, ch, int(num))] = (float(d["INTPTLAT"]), float(d["INTPTLONG"]), float(d["ALAND_SQMI"]))
    return G


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "fetch":
    fetch(); sys.exit()

G = _gaz()
corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}
_party, person = _party_lookup()
M = json.load(open(os.path.join(HERE, "..", "historical_cache", "va_elections", "margins.json")))
SEAT = {}                                         # (election year, chamber, person) -> district
for y, chs in M.items():
    for ch, w in chs.items():
        for name, v in w.items():
            SEAT[(int(y), ch, person(name) or name)] = v["district"]
ELECTION = {("H", 2020): 2019, ("H", 2021): 2019, ("H", 2022): 2021, ("H", 2023): 2021, ("H", 2024): 2023, ("H", 2025): 2023,
            ("H", 2026): 2025, ("S", 2020): 2019, ("S", 2021): 2019, ("S", 2022): 2019, ("S", 2023): 2019, ("S", 2024): 2023,
            ("S", 2025): 2023, ("S", 2026): 2023}
MEAN_AREA = {k: sum(math.log(v[2]) for kk, v in G.items() if kk[:2] == k) / max(1, sum(1 for kk in G if kk[:2] == k))
             for k in {kk[:2] for kk in G}}


def place(yr, ch, who):
    e = ELECTION.get((ch, yr)); vint = "2021" if yr <= 2023 else "2023"
    d = SEAT.get((e, ch, person(who) or who)) if e else None
    return (G.get((vint, ch, d)), vint) if d else (None, vint)


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def sig(r):
    ch = "S" if r["chamber_S"] else "H"; s = float(r["same"])
    z = {"near": 0.0, "dist": 0.0, "rural": 0.0}
    v, vint = place(r["yr"], ch, r["who"])
    if v:
        z["rural"] = math.log(v[2]) - MEAN_AREA[(vint, ch)]
        b = corpus[r["bill"]]; pch = r["bill"][1][0]
        p, _ = place(r["yr"], pch, b["chief"]) if b["chief"] else (None, vint)
        if p and person(b["chief"]) != person(r["who"]):
            k = km(v, p); z["near"] = float(k < 40); z["dist"] = math.log1p(k) - 4.5
    return {f"{k}_{side}": x * (s if side == "same" else 1 - s) for k, x in z.items() for side in ("same", "other")}
