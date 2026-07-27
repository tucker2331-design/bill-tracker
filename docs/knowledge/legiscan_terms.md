---
tags: [knowledge, api, compliance, legiscan, corpus, rule, decision]
updated: 2026-07-27
status: active
---

# Cross-state text corpus — why LegiScan is OFF the plan, and what replaced it

Sibling of [[knowledge/lis_api_authorization]]. That page governs Virginia's own API; this one governs the
**aggregator** for other states' bill text ([[architecture/text_similarity]]).

## DECISION 2026-07-27 — REVERSES the 2026-07-25 "temporary LegiScan" plan. Corpus = Open States (Plural Open).

**Owner, on reaching LegiScan's API survey:** *"LegiScan seems a bit too much honestly. It's not that I can't
and won't do this, it's that it's asking for an excessive amount of information and compliance with a number
of rules and laws that I'm not comfortable engaging with via an AI."*

**The concern is correct, and it is sharper than "too much paperwork."** The free "public service" key is not a
config value — it is gated behind a **binding attestation made by the owner personally**, on a form that
states the response **cannot be edited after submission**. The two required declarations:

| Survey question | Answer the free tier requires | Why that is a problem HERE |
|---|---|---|
| Commercial or **non-commercial** use? | Non-Commercial | A cost to SEQUENCE, not a permanent bar — see the owner correction below. We would have had to fully transition off before charging anyone. |
| Derivative works internal-only or **externally published**? | Internal Use Only | **The binding one.** Cross-state comparison is *displayed to users* in the War Room's "Elsewhere" zone — externally published by construction, and that conflicts from day one, free or paid. |

### OWNER CORRECTION 2026-07-27 — I overclaimed; here is the accurate version
Owner: *"idk if this LegiScan form would've totally prevented us from using our site for compensation — I
think we would've had to just make the full transition off the LegiScan API before we could monetize."*
**He is right, and my "compliance conflict" framing was too absolute on that axis.** A non-commercial
attestation governs the *use*: use it non-commercially now, stop using it before charging anyone, and there is
no violation. That is literally the exit criterion I wrote on 07-25 ("monetization → replace that slice"). I
should have said "a cost to sequence" rather than implying a permanent bar. Correction recorded.

**What survives the correction, and it is the sharper half:**
1. **"Internal Use Only" bites IMMEDIATELY, not at monetization.** Cross-state comparison renders in the War
   Room's Elsewhere zone — shown to users outside our org. That is externally published *while still free*, so
   this conflict is day one, not deferred. The commercial question was never the binding one.
2. **The exit cost is UNKNOWN, and that is on me** — LegiScan's terms page returned 403 to me, so I never read
   the redistribution/derived-data clauses. "Transition off" might mean swapping a fetcher, or it might mean
   purging cached text and any similarity labels derived from it. I do not know which, and I should not
   pretend a cost I never measured is either small or prohibitive.
3. **It is moot anyway:** Open States is better on every axis we care about (public domain, no attestation,
   full text, bulk-friendly), so declining LegiScan gives up nothing. The decision stands on the alternative's
   merits, not on the severity of the LegiScan terms.

### The structural lesson (still stands, restated precisely): a licence attestation is not a swappable dependency
The 2026-07-25 decision banked LegiScan as *"temporary, behind a `corpus_source` seam, swap it out later."*
That reasoning is sound for a **technical** dependency — an API shape can be adapted away. It does **not** hold
for a **legal** one: you remain bound by what you attested, and the exit is not a refactor, it is a terms
violation already committed. **Prefer a licence that requires no attestation over a seam that lets you swap
the code.** The owner's instinct here protected the monetization path the seam could not have.

The process point stands on its own too: **an AI must not draft or mediate the owner's legal declarations.**

## The replacement: Open States / Plural Open (verified 2026-07-27)
- **Bulk per-session JSON downloads include FULL BILL TEXT.** (The CSV variant is metadata-only — take JSON.)
- **Public-domain dedication:** *"data is provided under a public domain dedication but attribution is greatly
  appreciated and very helpful."* No commercial restriction to attest to → no conflict with monetizing later.
- **No registration, no survey, no attestation** for the bulk downloads.
- Coverage: all 50 states + DC + PR. An API v3 exists (simple key) but **bulk is the right path anyway** — it
  matches guardrail #1 (fetch less, cache more) far better than per-bill calls.
- Sources: [bulk data](https://open.pluralpolicy.com/data/) · [docs](https://docs.openstates.org/) ·
  [API v3](https://docs.openstates.org/api-v3/)
- **We will attribute them even though it is optional** — it costs nothing and it is the right posture toward
  a civic-data commons we benefit from.

### Terms of Use — READ AND RECORDED 2026-07-27 (https://open.pluralpolicy.com/tos/)
Operative wording, quoted:
- **Data licence:** *"We make no copyright claim over any of the data we collect & publish"* — effectively
  public domain.
- **Attribution:** *"No attribution is required for using data obtained via Open States"* — but
  *"no affiliation or endorsement may be implied on your derivative product."* **→ We attribute voluntarily,
  and the wording must credit the source WITHOUT implying they endorse us.**
- **Commercial use:** no restriction stated. Nothing to attest to, nothing to re-check at monetization.
- **Derivative works:** permitted (our similarity labels are fine), subject to the no-endorsement rule.
- **Monitoring / limits — REAL NUMBERS, owner-reported from the account page 2026-07-27:**
  **500 requests per DAY, paced at 1 request per SECOND.** The ToS additionally reserves the right to block a
  user who *"attempted to exceed or circumvent these limits."*
  **→ This settles the architecture: the API is for TARGETED lookups only; the CORPUS must come from bulk
  downloads.** 500/day is ~0.35 req/min sustained — a single state's bills would consume months of quota via
  the API, while one bulk file costs zero API calls. Our own ceilings sit deliberately BELOW theirs
  (guardrail #4: a hard cap independent of cadence logic, so a bug can never spike us into a ban):
  **400 req/day (80% of theirs) and 1.2s spacing (20% slower than required).**
- **⚠️ Warranty:** *"provides the Services 'as-is' and on an 'as-available' basis"*, with
  *"no warranty that the Services will be error free."*

**The warranty clause has a TRUST-MODEL consequence, not just a legal one.** Open States data is *sourced from
another state's official record, at one remove, from a provider who explicitly disclaims accuracy* — it is NOT
the same epistemic class as our LIS-verified Virginia data. It must be labeled with its provenance ("via Open
States") and must never inherit the verified treatment ([[design/information_display]] P24a: name the surface
you actually checked; P25c: state what your verification reaches). Cross-state rows are **sourced-at-one-remove**,
and a cross-state claim we cannot verify stays visibly unverified rather than quietly presented as fact.

## Standing rules once live (unchanged in spirit from the LegiScan draft)
- **Cache fetched text permanently** in our own corpus store (append-only, not Sheets); re-fetch only on a
  changed hash. This respects the source and makes our archive independent of it over time.
- **Conditional fetch** — use ETag/`Last-Modified`/content hash; never re-download unchanged data (guardrail #1).
- **Never on the accuracy path.** The lobbyist-facing VA data must never depend on a third party; this feeds a
  *comparison* feature, so if it vanishes cross-state context degrades and nothing else does.
- **An outage is a visible degraded state**, never a silent gap ([[design/information_display]] P25a).
- **The per-state native scanner rule still stands**: each state we ingest natively retires its aggregator
  slice (VA's is W2; NY's is queued at [[ny/state/current_status]] #6). The aggregator is scaffolding.

## What this changes in the plan
- **W2/W3/W4 are unaffected and need NO external corpus at all** — Virginia-only (our own text ingest, the
  comparer, House↔Senate companion detection). The near-term lobbyist value ships with zero outside dependency.
- **W6 re-aimed:** the `corpus_source` seam stays (it is how native scanners retire aggregator slices), but the
  adapter targets Open States bulk JSON and the "at-key-time checklist" collapses — there is no key.
- **`LEGISCAN_API_KEY` is not needed.** Verified zero references outside docs, so the reversal costs nothing.
- **NY's independent oracle (C-8 Part 2) loses its assumed source** — it was scoped around a LegiScan key.
  Re-scope against Open States' NY data: same public-domain terms, and it stays genuinely independent of
  OpenLeg. Logged in [[ny/state/current_status]].

See also [[architecture/text_similarity]], [[knowledge/lis_api_authorization]], [[knowledge/lis_api_safety]],
[[ideas/moat_and_competition]].
