---
tags: [knowledge, source, historical, calibration, openstates, compliance]
updated: 2026-08-01
status: active
open_loop: Open States bulk CSV needs a free account the owner must create (assistants may not register accounts). Once downloaded, fidelity MUST be measured against our cached LIS 2023/2024 before any pre-2023 session is trusted.
---

# Open States bulk CSV — 20 Virginia sessions, CC0 (found 2026-08-01)

**This is the answer to the historical-data problem**, and it is a better one than the legacy LIS route in
two respects: far more history, and no commercial restriction.

## What is there

- **20 Virginia sessions, 2017 → 2027**, regular and special, at
  <https://open.pluralpolicy.com/data/session-csv/>
- Compare with what LIS itself still publishes: **three** sessions (2023, 2024, + a partial 2022) —
  [[knowledge/legacylis_csv_route]].
- Most states from 2017; some go much deeper (California to 1989).

## Licence — CC0, and this matters beyond convenience

Open States data is released under a **CC0 public-domain dedication**; attribution is appreciated, not
required, and **there is no restriction on commercial use**
([Open States bulk data](https://open.pluralpolicy.com/data/)).

**This is materially different from the LIS API**, whose ToS §2 limits use to "personal and non-commercial"
([[knowledge/lis_tos_commercial_use]]). Open States is a **third-party compilation of Virginia public
records**, so using it for historical analysis does not touch the LIS terms at all. It does not resolve the
live-data question — the calendar still needs the LIS `Schedule` service, which has no other source — but
it takes the entire *historical* half of the product off the disputed channel.

## The blocker, and it is the owner's to clear

**A free account is required.** *"Please log in to access download links."*

**An assistant may not create accounts.** This is a hard rule, not a preference — so this step is the
owner's regardless of how convenient it would be otherwise.

**Steps:** register at openstates.org → open the session-CSV page → download the Virginia sessions →
drop them somewhere the repo can read → the fetch tool gains a second source.

## MANDATORY before trusting any of it: measure fidelity against LIS

**Do not feed Open States data into the calibration on arrival.** It is a compilation built by scraping and
normalising, not the authoritative record, and its schema will NOT match LIS's — unlike the legacy LIS CSVs,
which matched the modern blob byte-for-byte on all 41 Bills columns.

**We are unusually well placed to check it.** We hold the authoritative LIS files for **2023 and 2024**, so
those two years can be diffed directly against Open States' version of the same sessions:

1. **Bill count** per session — do both sources agree on the universe?
2. **Outcome agreement** — for each bill, does passed/failed match?
3. **Committee attribution** — does the last-committee assignment agree?
4. **Vote records** — do roll-call tallies match?

**That measurement is the gate.** If 2023/2024 agree closely, 2017–2022 can be trusted to roughly the same
degree and the calibration base goes from 2 usable sessions to ~10. If they disagree materially, we have
learned the error rate before it silently contaminated a finding — which is the whole point of checking.

**Also unresolved until measured:** whether Open States carries committee *dockets* and meeting *schedules*
for old sessions. LIS publishes neither historically ([[knowledge/legacylis_csv_route]] — `Docket.csv` is
header-only for every legacy session), so if Open States has them it unlocks a class of analysis currently
impossible.

## Why this was not found sooner

[[state/va_build_queue]] C2 recorded it as *"Open States bulk download needs a login"* and stopped there.
**True, and it buried the lede** — the entry never recorded that behind that login sit 20 Virginia sessions
under a licence with no commercial restriction. A blocker was logged; the size of the prize behind it was
not. Same shape as [[failures/assumptions_audit]] #109: a negative result recorded without recording what
was on the other side of it.
