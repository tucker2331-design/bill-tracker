#!/usr/bin/env python3
"""District profiles for the drafting room — every state legislative district, both chambers, any state.

Owner (2026-11-18): "who will this be especially important for ... who represents a lot of these people", and
"14 nursing homes in your district and 18% over 65 — both, always, they mean different things".
So every measure carries BOTH the count and the share, plus its denominator and the census margin of error.

Sources (all federal, public domain, bulk files — no key, no per-request load; cached under
tools/historical_cache/census/, see MANIFEST.json there):
  * ACS 2020-2024 5-year table-based summary files (www2.census.gov), 2024 state legislative districts
    (summary levels 610 upper / 620 lower) and census tracts.
  * Census 2024 cartographic boundaries (sldl/sldu/tract, 1:500k) — map shapes + point-in-polygon.
  * Census 2020 relationship files, 2024 districts x county subdivision (municipality) / school district /
    county / ZCTA (ZIP area) / tract — land-area parts.
  * NCES EDGE public school locations 2024-25; CMS nursing home provider file (Oct 2026, has lat/long);
    CMS hospital general information (Oct 2026) geocoded by the Census batch geocoder.
  * Who holds each seat: Open States people CSV (current), CC0.

Standard #6: nothing here is state-specific — the state is a FIPS code + postal code argument.
Standard #4: every row that cannot be placed is COUNTED in `unplaced` (no silent drop).
"""
from __future__ import annotations

import collections
import csv
import io
import json
import math
import os
import sys
import zipfile

import shapefile                      # pyshp
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
C = os.path.join(ROOT, "tools", "historical_cache", "census")
STATES = {"42": "PA", "51": "VA"}
CH = {"sldl": "lower", "sldu": "upper"}
SUMLEV = {"620": "sldl", "610": "sldu"}


def L(table, *nums):
    return [f"{table}_{n:03d}" for n in nums]


# measure key -> (label for a volunteer, numerator lines, denominator line(s) [minus lines], unit noun)
MEASURES = {
    "children": ("children under 18", L("B01001", *range(3, 7), *range(27, 31)), (["B01001_001"], []), "residents"),
    "under5": ("children under 5", L("B01001", 3, 27), (["B01001_001"], []), "residents"),
    "seniors": ("people 65 and over", L("B01001", *range(20, 26), *range(44, 50)), (["B01001_001"], []), "residents"),
    "veterans": ("veterans", ["B21001_002"], (["B21001_001"], []), "adults"),
    "poverty": ("people below the poverty line", ["B17001_002"], (["B17001_001"], []), "people with poverty status"),
    "child_poverty": ("children below the poverty line", L("B17001", *range(4, 10), *range(18, 24)),
                      (L("B17001", *range(4, 10), *range(18, 24), *range(33, 39), *range(47, 53)), []), "children"),
    "uninsured": ("people without health insurance", L("B27010", 17, 33, 50, 66), (["B27010_001"], []), "residents"),
    "disability": ("people with a disability", None, (["B18101_001"], []), "residents"),
    "renters": ("renter households", ["B25003_003"], (["B25003_001"], []), "households"),
    "rent_burdened": ("renters paying 30%+ of income on rent", L("B25070", 7, 8, 9, 10), (["B25070_001"], ["B25070_011"]), "renter households"),
    "no_vehicle": ("households without a car", ["B08201_002"], (["B08201_001"], []), "households"),
    "limited_english": ("people who speak English less than very well", None, (["B16005_001"], []), "residents 5+"),
    "foreign_born": ("people born outside the US", ["B05002_013"], (["B05002_001"], []), "residents"),
    "snap": ("households on SNAP (food stamps)", ["B22010_002"], (["B22010_001"], []), "households"),
    "no_internet": ("households with no internet", ["B28002_013"], (["B28002_001"], []), "households"),
    "farm_jobs": ("workers in farming, forestry, fishing", ["C24030_004", "C24030_031"], (["C24030_001"], []), "workers"),
}


def shells():
    by = collections.defaultdict(list)
    with open(os.path.join(C, "shells.psv"), encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="|"):
            by[r["Table ID"]].append(r)
    return by


def resolve_label_lines(sh):
    """Two measures are defined by label, not line number (the label is the census's own structure)."""
    MEASURES["disability"] = MEASURES["disability"][:1] + ([r["Unique ID"] for r in sh["B18101"] if r["Label"].strip() == "With a disability"],) + MEASURES["disability"][2:]
    MEASURES["limited_english"] = MEASURES["limited_english"][:1] + ([r["Unique ID"] for r in sh["B16005"] if r["Label"].strip() in ('Speak English "well"', 'Speak English "not well"', 'Speak English "not at all"')],) + MEASURES["limited_english"][2:]
    for k, (_, num, _d, _u) in MEASURES.items():
        assert num, f"measure {k} resolved to no lines"


def load_acs():
    """GEO_ID -> {line: (estimate, moe)} across every cached table."""
    vals = collections.defaultdict(dict)
    for fn in sorted(os.listdir(C)):
        if not (fn.startswith("acs5_2024_") and fn.endswith(".psv")):
            continue
        with open(os.path.join(C, fn), encoding="utf-8") as f:
            rd = csv.reader(f, delimiter="|")
            hdr = next(rd)
            for row in rd:
                g = row[0]
                for i in range(1, len(hdr), 2):
                    line = hdr[i].replace("_E", "_")
                    try:
                        e = float(row[i]); m = float(row[i + 1])
                    except (ValueError, IndexError):
                        e, m = math.nan, math.nan
                    vals[g][line] = (e, m if m >= 0 else 0.0)   # negative MOE codes = controlled/no sampling error
    return vals


def summ(v, lines):
    e = sum(v[x][0] for x in lines)
    m = math.sqrt(sum(v[x][1] ** 2 for x in lines))
    return e, m


def measure_block(v):
    out = {"people": round(v["B01003_001"][0])}
    for k, (label, num, (dp, dm), unit) in MEASURES.items():
        n, nm = summ(v, num)
        d = summ(v, dp)[0] - (summ(v, dm)[0] if dm else 0)
        out[k] = {"count": round(n), "moe": round(nm), "of": round(d), "share": round(n / d, 4) if d else None,
                  "unreliable": bool(n and nm / 1.645 / n > 0.30)}     # census rule of thumb: CV > 30%
    mi = v["B19013_001"]
    out["median_income"] = {"value": None if math.isnan(mi[0]) or mi[0] < 0 else round(mi[0]), "moe": round(mi[1])}
    return out


def read_shapes(st, layer):
    z = zipfile.ZipFile(os.path.join(C, "shp", f"cb_2024_{st}_{layer}_500k.zip"))
    base = f"cb_2024_{st}_{layer}_500k"
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                         shx=io.BytesIO(z.read(base + ".shx")))
    flds = [f[0] for f in r.fields[1:]]
    return [(dict(zip(flds, sr.record)), shape(sr.shape.__geo_interface__)) for sr in r.iterShapeRecords()]


def district_of(rec):
    return rec.get("SLDLST") or rec.get("SLDUST")


def facilities(st, postal):
    """[(kind, name, lon, lat, extra)] for one state; every row that has no usable point is counted."""
    rows, unplaced = [], collections.Counter()
    with zipfile.ZipFile(os.path.join(C, "dl", "publicsch.zip")) as z:
        txt = [n for n in z.namelist() if n.upper().endswith(".TXT")][0]
        for line in io.TextIOWrapper(z.open(txt), encoding="latin-1"):
            p = line.rstrip("\n").split("|")
            if len(p) > 13 and p[6] == postal:
                try:
                    rows.append(("schools", p[2], float(p[13]), float(p[12]), {"edge_sldl": p[-3], "edge_sldu": p[-2]}))
                except ValueError:
                    unplaced["schools"] += 1
    with open(os.path.join(C, "dl", "nh.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["State"] != postal:
                continue
            try:
                beds = int(float(r["Number of Certified Beds"] or 0))
                rows.append(("nursing_homes", r["Provider Name"], float(r["Longitude"]), float(r["Latitude"]), {"beds": beds}))
            except ValueError:
                unplaced["nursing_homes"] += 1
    with open(os.path.join(C, "dl", "hosp_geo.csv"), encoding="utf-8") as f:
        geo = {r[0]: r for r in csv.reader(f)}
    with open(os.path.join(C, "dl", "hosp.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["State"] != postal:
                continue
            g = geo.get(r["Facility ID"])
            if g and len(g) > 5 and g[2] == "Match" and "," in g[5]:
                lon, lat = map(float, g[5].split(","))
                rows.append(("hospitals", r["Facility Name"], lon, lat, {"type": r["Hospital Type"]}))
            else:
                # no geocoder match: keep the ZIP; main() places it only if that ZIP lies wholly in one district
                rows.append(("hospitals", r["Facility Name"], None, None, {"type": r["Hospital Type"], "zip": r["ZIP Code"][:5].zfill(5)}))
                unplaced["hospitals_geocoder_no_match"] += 1
    return rows, unplaced


def rel(st, ch, kind):
    path = os.path.join(C, "rel", f"tab20_{ch}202420_{kind}_st{st}.txt")
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter="|"))


def local_govts(st, ch):
    """district -> {municipalities: [(name, whole)], school_districts: [...], counties: [...]}"""
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for kind, key, nm in (("cousub20", "municipalities", "COUSUB_20"), ("sdcombo20", "school_districts", "SDCOMBO_20"),
                          ("county20", "counties", "COUNTY_20")):
        for r in rel(st, ch, kind):
            part = float(r["AREALAND_PART"] or 0)
            whole_area = float(r[f"AREALAND_{nm}"] or 0)
            name = r[f"NAMELSAD_{nm}"]
            if part <= 0 or "not defined" in name:
                continue
            d = r[f"GEOID_{ch.upper()}2024_20"][2:]
            out[d][key].append((name, abs(part - whole_area) < 1.0))
    return out


def zip_index(st, ch):
    z = collections.defaultdict(list)
    for r in rel(st, ch, "zcta520"):
        part = float(r["AREALAND_PART"] or 0)
        tot = float(r["AREALAND_ZCTA5_20"] or 0)
        if part > 0 and tot > 0 and r["GEOID_ZCTA5_20"]:
            z[r["GEOID_ZCTA5_20"]].append((r[f"GEOID_{ch.upper()}2024_20"][2:], round(part / tot, 3)))
    return z


def overlap(st, acs):
    """House district -> [(Senate district, estimated residents in common)] from census tracts:
    a tract's residents are split across the districts it touches by land area (uniform-density assumption,
    stated on screen as 'estimated from census tracts')."""
    parts = {}
    for ch in ("sldl", "sldu"):
        p = collections.defaultdict(list)
        for r in rel(st, ch, "tract20"):
            a = float(r["AREALAND_PART"] or 0); t = float(r["AREALAND_TRACT_20"] or 0)
            if a > 0 and t > 0:
                p[r["GEOID_TRACT_20"]].append((r[f"GEOID_{ch.upper()}2024_20"][2:], a / t))
        parts[ch] = p
    pair = collections.Counter()
    missing_pop = 0
    for tract, lows in parts["sldl"].items():
        pop = acs.get(f"1400000US{tract}", {}).get("B01003_001", (math.nan,))[0]
        if math.isnan(pop):
            missing_pop += 1
            continue
        for l, fl in lows:
            for u, fu in parts["sldu"].get(tract, []):
                pair[(l, u)] += pop * fl * fu
    out = collections.defaultdict(list)
    for (l, u), n in pair.items():
        if n >= 50:
            out[l].append((u, round(n)))
    for l in out:
        out[l].sort(key=lambda x: -x[1])
    return out, missing_pop


def people(postal):
    fn = os.path.join(ROOT, "tools", "historical_cache", "pa", "openstates", f"{postal.lower()}_people_current.csv")
    m = {}
    with open(fn, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ch = {"lower": "sldl", "upper": "sldu"}.get(r["current_chamber"])
            if ch and r["current_district"]:
                m[(ch, r["current_district"].zfill(3))] = {"name": r["name"], "party": r["current_party"][:1]}
    return m


def svg_paths(shapes, tol):
    """Simplified outlines projected to a plane (equirectangular, cos(lat) scaled), normalised to 1000 wide."""
    allb = [g.bounds for _, g in shapes]
    minx = min(b[0] for b in allb); maxx = max(b[2] for b in allb)
    miny = min(b[1] for b in allb); maxy = max(b[3] for b in allb)
    k = math.cos(math.radians((miny + maxy) / 2))
    W = 1000.0
    s = W / ((maxx - minx) * k)
    H = (maxy - miny) * s

    def ring(coords):
        return "M" + "L".join(f"{(x - minx) * k * s:.1f},{(maxy - y) * s:.1f}" for x, y in coords) + "Z"
    out = {}
    for rec, g in shapes:
        g2 = g.simplify(tol, preserve_topology=True)
        polys = [g2] if g2.geom_type == "Polygon" else list(g2.geoms)
        out[district_of(rec)] = "".join(ring(p.exterior.coords) for p in polys if p.area > 0)
    return out, {"w": W, "h": round(H, 1)}


def main():
    sh = shells()
    resolve_label_lines(sh)
    acs = load_acs()
    result = {"sources": __doc__.split("Sources")[1].split("Standard #6")[0].strip(), "measures": {k: {"label": v[0], "of": v[3]} for k, v in MEASURES.items()},
              "states": {}}
    geo_out = {}
    zips = {}
    for st, postal in STATES.items():
        mem = people(postal)
        fac, unplaced = facilities(st, postal)
        S = {"unplaced_facilities": dict(unplaced), "chambers": {}}
        statewide = measure_block(acs[f"0400000US{st}"]) if f"0400000US{st}" in acs else None
        geo_out[postal] = {}
        zips[postal] = {}
        for ch in ("sldl", "sldu"):
            shapes = read_shapes(st, ch)
            tree = STRtree([g for _, g in shapes])
            fac_count = collections.defaultdict(collections.Counter)
            beds = collections.Counter()
            edge_agree = edge_total = outside = 0
            zi = zip_index(st, ch)
            by_zip = {"placed": 0, "zip_spans_districts": 0}
            for kind, name, lon, lat, extra in fac:
                if lon is None:
                    hits = zi.get(extra["zip"], [])
                    if len(hits) == 1 or (hits and max(s for _, s in hits) >= 0.99):
                        d = max(hits, key=lambda x: x[1])[0]
                        by_zip["placed"] += 1
                    else:
                        by_zip["zip_spans_districts"] += 1      # counted, shown as "not placed" on screen
                        continue
                    fac_count[d][kind] += 1
                    continue
                idx = tree.query(Point(lon, lat), predicate="intersects")
                if len(idx) == 0:
                    outside += 1
                    continue
                d = district_of(shapes[int(idx[0])][0])
                fac_count[d][kind] += 1
                if kind == "nursing_homes":
                    beds[d] += extra["beds"]
                if kind == "schools":
                    e = extra["edge_sldl" if ch == "sldl" else "edge_sldu"]
                    if e and e[2:].isdigit():
                        edge_total += 1
                        edge_agree += int(e[2:].zfill(3) == d)
            lg = local_govts(st, ch)
            ov, missing = overlap(st, acs) if ch == "sldl" else ({}, 0)
            rows = {}
            for rec, g in shapes:
                d = district_of(rec)
                lev = "620L900" if ch == "sldl" else "610U900"
                v = acs.get(f"{lev}US{st}{d}")
                if v is None:
                    raise SystemExit(f"DATA_ANOMALY: no ACS row for {postal} {ch} {d} — vintage mismatch?")
                rows[d] = {"member": mem.get((ch, d)), **measure_block(v),
                           "places": {"schools": fac_count[d]["schools"], "nursing_homes": fac_count[d]["nursing_homes"],
                                      "nursing_home_beds": beds[d], "hospitals": fac_count[d]["hospitals"]},
                           "local": {k: sorted(x) for k, x in lg[d].items()},
                           "senate_overlap": ov.get(d, [])}
            S["chambers"][CH[ch]] = {"districts": rows, "facilities_outside_every_district": outside,
                                    "hospitals_by_zip": by_zip,
                                    "schools_district_agrees_with_nces": f"{edge_agree} of {edge_total}",
                                    "members_matched": sum(1 for r in rows.values() if r["member"]),
                                    "tracts_without_population": missing}
            geo_out[postal][CH[ch]] = svg_paths(shapes, 0.004 if ch == "sldl" else 0.006)
            zips[postal][CH[ch]] = zi
        S["statewide"] = statewide
        result["states"][postal] = S
    with open(os.path.join(C, "district_profiles.json"), "w") as f:
        json.dump(result, f)
    with open(os.path.join(C, "district_shapes.json"), "w") as f:
        json.dump(geo_out, f)
    with open(os.path.join(C, "zip_to_district.json"), "w") as f:
        json.dump(zips, f)
    for postal, S in result["states"].items():
        for ch, c in S["chambers"].items():
            print(postal, ch, len(c["districts"]), "districts | members matched", c["members_matched"], "| hosp by zip", c["hospitals_by_zip"],
                  "| schools NCES agree", c["schools_district_agrees_with_nces"], "| outside", c["facilities_outside_every_district"])
        print(postal, "unplaced", S["unplaced_facilities"])


if __name__ == "__main__":
    sys.exit(main())
