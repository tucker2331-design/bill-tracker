---
tags: [knowledge, census, districts, facilities, drafting-room, multi-state]
updated: 2026-11-18
status: active
---

# District profiles — who lives in a district, what is in it, who represents it

Built 2026-11-18 for the pre-introduction drafting room ([[ideas/drafting_war_room]]). Code:
`tools/districts/build_profiles.py` (any state: FIPS + postal code; PA and VA built). Output, cached under
`tools/historical_cache/census/` with a `MANIFEST.json` (URL + sha256 for every file):
`district_profiles.json` (every seat, both chambers), `district_shapes.json` (simplified outlines for maps),
`zip_to_district.json` (ZIP area → districts with land share).

## Owner rule: count AND share, always
*"'14 nursing homes in your district' and '18% over 65' — both do if they are about their district; they mean
different things, so always have both"* (2026-11-18). Every people measure carries `count`, `share`, its denominator
(`of`) and the census margin of error (`moe`, plus `unreliable` when the CV exceeds 30%). Places are counts.

## Sources (all bulk, free, public domain or CC0; zero per-request load)
| layer | source | note |
|---|---|---|
| people, 16 measures | ACS 2020–24 5-year **table-based summary files** (www2.census.gov), 2024 state legislative districts (sumlev 610/620) + tracts | the Census **Data API now needs a key** (302 → missing_key, found 2026-11-18, [[knowledge/district_lookup]]); the bulk files do not |
| shapes | Census 2024 cartographic boundaries, 1:500k | maps + point-in-polygon |
| municipalities, school districts, counties, ZIP areas, tracts | Census 2020 relationship files, 2024 districts (`rel2020/cd-sld`) | land-area parts; "whole" when the part equals the unit |
| schools | NCES EDGE public school locations 2024–25 | lat/long |
| nursing homes + certified beds | CMS provider file (dataset 4pq5-n9py, Oct 2026) | has lat/long |
| hospitals | CMS hospital general information (xubh-q36u, Oct 2026) | no coordinates → Census batch geocoder (public facility addresses) |
| who holds the seat | Open States people CSV (current), CC0 | PA 253/253 matched; VA 139/140 |

Measures: children under 18, under 5, people 65+, veterans (of adults), poverty, child poverty, uninsured,
disability, renter households, rent-burdened renters (30%+ of income), households without a car, limited English
(speak English less than very well), foreign-born, SNAP households, households with no internet, farm/forestry/
fishing workers; median household income.

## Validation (measured, not assumed)
- **Placement check:** our point-in-polygon district for 2,949 PA and 2,159 VA public schools agrees with NCES's own
  coding for **5,107 of 5,108** (the NCES file carries SLDL/SLDU columns — note their order is lower, then upper).
- Every district has an ACS row (the build FAILS on a missing one — vintage mismatch is a DATA_ANOMALY, never a
  silent zero).
- Statewide check, PA: 2,535,503 residents 65+ of 13,018,639 (19.5%); 656 nursing homes, 82,992 certified beds.
- Shared residents (House ↔ Senate) are estimated from tracts split by land area; for HD 168 the three Senate shares
  sum to 64,117 vs 64,320 residents.

## Gaps (counted, shown on screen)
- Hospitals: 33 PA / 19 VA addresses did not match the geocoder; those whose ZIP lies wholly in one district are
  placed by ZIP (PA House 9), the rest are **not placed** (PA House 24) and the screen says so.
- No child-care centres, enrolment, libraries, funding amounts — separate sources, not fetched.

## Standards
#1/#5: nothing hardcoded per district; vintage read from the files. #4: unplaced facilities counted per reason.
#6: state is an argument. Text: none — every join is a code (GEOID, FIPS, district number).
