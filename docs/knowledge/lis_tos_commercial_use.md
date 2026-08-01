---
tags: [knowledge, compliance, legal, lis, terms, blocker, owner-decision]
updated: 2026-08-01
status: active
open_loop: LIS API ToS restricts the Services to "personal and non-commercial use only" while this project is a commercial product. Needs a DLAS answer on commercial terms before launch. Owner decision, not an engineering one.
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
