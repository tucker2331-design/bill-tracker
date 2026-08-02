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

## Terms — VERIFIED CLEAN 2026-08-01 (owner supplied the full text)

The Open States Terms of Service (effective 2021-09-15) contain **no commercial restriction of any kind**:

> **Attribution** — "No attribution is required for using data obtained via Open States. **We make no
> copyright claim over any of the data we collect & publish.** Of course, attribution is always appreciated
> but no affiliation or endorsement may be implied on your derivative product."

There is no non-commercial clause, no personal-use clause, and no attestation. The remaining provisions are
ordinary: right to rate-limit, termination at their discretion, warranty disclaimer, indemnity, DC law.
**Nothing here conflicts with a commercial product.** We attribute voluntarily anyway.

## Why this was not used sooner — a bookkeeping failure, not a terms problem

**The owner remembered a concerning terms clause and dropped the source. That memory is real but it
attached to the WRONG source.**

- **LegiScan was rejected** on 2026-07-27 — its free key requires *"a BINDING, uneditable attestation of
  non-commercial + internal-use-only"* ([[knowledge/legiscan_terms]]). **That is the concerning clause.**
- **Open States was ADOPTED in the same decision**, and [[architecture/text_similarity]] records it
  verified that day as *"public-domain dedication, no registration, no survey, no attestation."*

The two were evaluated side by side in one sitting, and the rejection stuck to both in memory.

**And the "login" note was narrower than it read.** The JSON bulk download needs no registration; the
**CSV** variant does. [[state/va_build_queue]] C2 recorded *"Open States bulk download needs a login"*
without that distinction, and without noting that the login is a **free account** — which the owner already
had. On 2026-08-01 he opened the CSV page and the download started immediately, no gate.

**So the source was approved on 2026-07-27 and simply never fetched.** Five days of "blocked on historical
data" sat on top of a two-minute download, because a line reading *"needs a login"* was filed as a blocker
rather than as a task.

**Lesson, same family as [[failures/assumptions_audit]] #109:** a note recording an obstacle must also
record its SIZE. "Needs a login" and "needs a negotiated licence" read identically in a queue and are
nothing alike. Write the cost, not just the existence, of a barrier.
