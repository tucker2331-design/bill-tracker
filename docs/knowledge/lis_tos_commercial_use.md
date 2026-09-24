---
tags: [knowledge, compliance, legal, lis, terms, blocker, owner-decision]
updated: 2026-08-01
status: active
open_loop: LIS API ToS restricts the Services to "personal and non-commercial use only". OWNER DECISION 2026-09-24 — no organizational or commercial use of any kind until an API arrangement with DLAS exists (the real-time API is the product's edge over CSV-only trackers); grant funding being explored to open that deal. Not an engineering item.
---

# LIS API Terms of Service — the non-commercial clause (owner-supplied 2026-08-01)

**The owner supplied the full ToS text. It contains a restriction the vault had never recorded, and it is
more consequential than the session limit we HAD recorded.**

## The clause

> **§2 Compliance With Applicable Laws** — "The Services are offered for your **personal and
> non-commercial use only**, and you are prohibited from using, and are expressly not granted the right to
> use, the Services for any other purpose."

`Services` is defined in the preamble as "any of its APIs … that links or refers to the Terms."

## Why this matters more than the session limit

This project is explicitly a **commercial product** — [[ideas/product_identity]] describes a paid platform
for lobbyists, and [[ideas/moat_and_competition]] plans monetization.

**And the project has already ruled on this exact issue once, in the opposite direction.**
[[knowledge/legiscan_terms]] rejected LegiScan because *"its free key requires a binding non-commercial +
internal-use-only attestation that conflicts with monetization."* **We disqualified a vendor for the same
restriction we are operating under.** That inconsistency is the finding.

## What is and is not covered — stated as facts, not as a legal opinion

| channel | key required? | covered by these ToS? |
|---|---|---|
| `lis.virginia.gov/*/api/*` | **yes** (`WebAPIKey`) | **Yes** — this is "the Services", plainly |
| `lis.blob.core.windows.net/lisfiles/*` | no key, no registration | **Unclear.** Static file downloads, not an API. The ToS attaches to APIs "that link or refer to the Terms". |
| `legacylis.virginia.gov/SiteInformation/csv/*` | no key, no registration | **Unclear**, same reasoning. Published as a public download page. |

**This is not a distinction anyone here should rule on.** It is written down so the question asked of DLAS
is precise rather than vague.

## OWNER DECISION 2026-09-24 — the line is the API deal, not revenue and not org rollout

> *"there is no reality in my understanding where it goes online for organizational/commerical use without
> something worked out for api usage bc thats where we get our real time data from, otherwise ours would be no
> better then those that rely on csv."*

So the "personal ends at org rollout" distinction below is **moot in practice**: nothing leaves personal use
before a DLAS arrangement. Funding for that deal (grants) is being explored and is not a code concern. The
structural map below stands as the record of *why* the API is the gate.

## The four words are four DIFFERENT limits (owner asked, 2026-09-23)

| term | what it restricts | where this project meets it |
|---|---|---|
| **personal** | WHO uses it — an individual, not an organization | LIS API §2 |
| **non-commercial** | WHETHER money is involved | LIS API §2 |
| **internal use only** | WHO SEES the output | LegiScan attestation — rejected for exactly this ([[knowledge/legiscan_terms]]) |
| **enterprise / per-seat / free tier** | HOW MANY users before it costs money — a price, not a use rule | Cloudflare Access, 50 free seats — replaced by app-level sign-in ([[architecture/verification_durability]]) |

**They are independent.** A nonprofit is non-commercial but not personal. A freelancer is personal but commercial.
**§2 requires BOTH "personal" AND "non-commercial"**, so the line is crossed at whichever comes first — and
**"personal" ends before "non-commercial" does: when an organization uses the tool for its work, even for
free.** The memo ([[legal/memo_lis_terms_2026-08-01]]) frames the trigger as *first revenue*; the earlier and
more likely trigger is **first org rollout to its volunteers.** (Both words are undefined in the ToS, so this is
the plain reading, not a ruling — and registration asking for an organization cuts the other way.)

## What sits on which channel — the structural map at scale (2026-09-23)

| product piece | data channel | terms exposure |
|---|---|---|
| every historical statistic and calibration finding | Open States bulk CSV | **none** — CC0 |
| War Room room stats, roll calls 2025/26 | LIS blob CSVs (no key, no assent) | **unclear**, probably outside §2 — unconfirmed |
| **calendar — meeting schedules** | LIS `Schedule` API — **no CSV equivalent exists** | **§2**, no alternative channel |
| **Virginia bill text** ("Tried before", VA half) | LIS `LegislationText` API — **no CSV equivalent** | **§2**, no alternative channel *unless* Open States bulk JSON embeds VA text |
| other states' outcomes / metadata | Open States | none — CC0 |
| other states' bill TEXT | each state's own site (Open States links, does not host) | per-state terms, unchecked |

**Structural verdict:** the choices made so far do not trap the product — the historical layer is CC0, and
LegiScan and Access were both caught before signing. **The one real dependency is a licence, not code:**
schedules and Virginia bill text exist only behind §2, so the calendar and the VA half of "Tried before" cannot
scale commercially without a DLAS answer. §6 contemplates paid access, so a route likely exists.

**Correction to 2026-09-23 (same day):** the "Tried before" terms note in [[architecture/text_similarity]] called
the feature clean after checking only Open States. The Virginia half runs on the LIS text API and sits under §2.

## The owner's objections, recorded because they are reasonable and should be put to DLAS

1. *"When I got my API key they asked which organization I was with"* — registration contemplating an
   organizational affiliation sits oddly beside "personal use only".
2. *"It's government data, taxpayer funded."* Virginia legislative records are public records.
3. *"How else would a commercial bill tracker get access?"* Commercial trackers plainly exist and operate
   on Virginia data.

**These are arguments about what the terms SHOULD say. They are not a reading of what the terms DO say.**
The clause is unambiguous on its face, and "everyone else must be doing it" is not a defence.

**But §6 cuts the other way and is the opening:** *"We may charge for access to portions of the Services…
we will notify you in advance, and give you an opportunity to subscribe."* **The ToS explicitly
contemplates paid access.** That strongly suggests a commercial arrangement exists or can be created —
which makes this a question with a likely answer, not a wall.

## What to do

1. **Ask DLAS directly** — helpdesk@dlas.virginia.gov, (804) 786-9631. One question: *"We are building a
   commercial legislative-tracking product. §2 restricts the API to personal and non-commercial use. Is
   there a commercial license, subscription, or alternate channel?"*
2. **Do not self-certify.** Neither an engineer nor an assistant should decide the blob CSVs fall outside
   "the Services". Get it in writing.
3. **Nothing changes today.** The product is pre-launch and not sold. This is a **before-revenue** blocker,
   not a stop-work order — but it must be resolved before the first paying customer, not after.

## Also in the ToS, and relevant

- **§4** — *"User specific data (including watchlist information) is intended for use strictly within the
  designed user interface of LIS. Any attempt to extract, aggregate, or programmatically access such data
  via the Services is a violation."* **We do not touch LIS user/watchlist data** — our org's tracking lives
  in our own store. Worth confirming that stays true as the War Room write path is built.
- **§4** — no "unreasonable or disproportionately large load". This is what [[knowledge/lis_api_safety]]
  already governs (conditional fetch, jitter, caps, quiet hours, self-throttling). That guardrail is not
  merely good manners; it is a term of the contract.
- **§9** — DLAS may terminate access at any time, with or without notice. **A single-source dependency with
  an at-will termination clause is a business risk**, independent of the commercial question, and it argues
  for the bulk-CSV path being kept viable as a fallback.
- **§8** — data provided "as is", no warranty of accuracy. Our own accuracy layer is what makes the product
  defensible; LIS disclaims theirs.
