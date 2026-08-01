---
tags: [legal, open-data, policy, virginia, advocacy, research]
updated: 2026-08-01
status: active
---

# Open-data law: what exists, what does not, and Virginia's 2018 attempt

**Why this is here (owner, 2026-08-01):** *"don't be surprised if you see that bill formulate in the
future."* This is the research behind that — kept so the argument does not have to be rebuilt, and so
anyone drafting later starts from verified facts rather than impressions.

---

## 1. There is no general "public services must be open" doctrine

The intuition that a government-run service must be free and accessible **has no general legal basis**. What
actually exists is narrower:

- **FOIA** — a right to *records*, on request, within a statutory response window. Not a right to a live
  feed, a format, or a delivery mechanism.
- **No copyright in government edicts** (*Georgia v. Public.Resource.Org*, 2020) — stops an agency claiming
  ownership; does not compel convenient publication.
- **Open-data statutes** — the closest thing, and where they exist they are usually executive-branch only.

**FOIA is the workhorse. Everything else is thinner than people assume.**

## 2. Virginia tried in 2018 and it died — VERIFIED from the bill records

| bill | what it did | outcome (from LIS history) |
|---|---|---|
| **HB781** (2018) — "Virginia Open Data Initiative Act" | would have required agencies to publish datasets in **non-proprietary, machine-readable** format under a Chief Data Officer | **"Stricken from docket by Science and Technology (22-Y 0-N)"** — killed unanimously, 5 Feb 2018 |
| **SB830** (2018) | companion | **"Incorporated by General Laws and Technology (SB580-Hanger)"** |
| **SB580** (2018) | **PASSED.** Amends the Government Data Collection and Dissemination Practices Act; creates the Chief Data Officer | passed — **but it governs data SHARING BETWEEN AGENCIES**, not publication to the public |

**The decisive detail:** HB781 required a report on *"the feasibility of **expanding the open data
initiative to the legislative and judicial branches** of government."*

**That language means the legislature was never inside it.** Even the bill that died would only have
*studied* whether to cover DLAS. So there is no Virginia statute requiring the General Assembly's own data
arm to publish openly — and the one that came closest excluded it by design.

## 3. Other states are ahead

- **California** — Gov. Code § 6253.10 requires open data to be published in a form that is
  "platform independent and machine readable."
- **Hawaii, New York, Texas, Connecticut, Maryland, Utah** — generally rated ahead of the pack on
  publishing basic government data in machine-readable form
  ([Center for Data Innovation](https://datainnovation.org/2014/08/state-open-data-policies-and-portals/)).
- **New York is the sharpest contrast, and is already this project's second state:** the NY Senate runs
  *Open Legislation*, a public REST API over the Legislative Bill Drafting Commission's data
  ([docs](https://legislation.nysenate.gov/static/docs/html/index.html)). The same class of service Virginia
  gates behind non-commercial terms, New York publishes openly.
- **Open States / Plural** grades all 50 states against the Ten Principles for Opening Up Government
  Information ([report card](https://open.pluralpolicy.com/reportcard/)) — higher scores for bulk,
  machine-readable publication; lower where scraping is required.

## 4. The strategic point, recorded because it cuts against our own interest

**Our strongest present argument is exclusivity** — that meeting schedules and floor calendars exist in
*no* ungated channel ([[knowledge/lis_tos_legal_analysis]] §6b).

**If DLAS responds by publishing schedules as a CSV, that argument disappears** and what remains is only
"their version is faster and better formatted," which no law entitles anyone to.

**That is a good outcome for public access and a weaker position for us, simultaneously.** Worth going in
with eyes open: pressing exclusivity invites the cheap fix, and the cheap fix is the right thing.

## 5. If a bill were ever drafted

The gap is specific and narrow, which is what makes it draftable:

1. **Scope it to the legislative branch.** That is precisely what HB781 deferred to a study.
2. **Require publication in bulk, machine-readable form** — the CSV route already exists; the gap is
   coverage (no Schedule/Calendar/text) and retention (~3 sessions, per
   [[knowledge/legacylis_csv_route]]).
3. **Bar purpose-based conditions on access**, mirroring what FOIA already says about records
   (Va. Code § 2.2-3704.A — purpose irrelevant, commercial use permitted).
4. **Retention.** The current CSV channel drops sessions after roughly three years, which is why this
   project can reach back only to 2023.

**Precedent to cite:** California § 6253.10; New York's Open Legislation service; and Virginia's own
SB580, which already established a Chief Data Officer — the office exists, its remit simply stops at the
executive branch.
