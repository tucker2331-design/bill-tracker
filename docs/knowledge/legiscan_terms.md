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
| Commercial or **non-commercial** use? | Non-Commercial | [[ideas/moat_and_competition]] places revenue in the workflow + insight layers. Attesting non-commercial while building toward selling is a compliance conflict, not a formality. |
| Derivative works internal-only or **externally published**? | Internal Use Only | Cross-state comparison is *displayed to users* in the War Room's "Elsewhere" zone — externally published by construction. |

### The structural lesson (generalize this): a licence attestation is NOT a swappable dependency
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

### Owner-gated before the first byte (diligence, NOT an attestation)
- [ ] Read [Terms of Use](https://open.pluralpolicy.com/tos/) and paste the relevant wording here with the date.
- [ ] Record any politeness/rate expectation for bulk downloads, then set our own ceiling *below* it
      (mirrors LIS-safety guardrail #4 — a hard cap independent of cadence logic).
- [ ] Note their preferred attribution wording, and decide where it renders **before** shipping the feature.

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
