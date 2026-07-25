---
tags: [architecture, text-intelligence, similarity, cross-state, rush, scoping]
updated: 2026-07-17
status: active
open_loop: RUSHED to front of line behind the counter. Owner decisions 2026-07-25 banked — LegiScan TEMPORARY (seam + exit criteria), ALL states (two-stage corpus design), historical depth YES (VA pre-2025 never via the API; legacylis CSV/text location UNLOCATED — probe flagged; LegiScan VA-historical is the no-conflict channel), companion tracker PROMOTED to a feature (progress + chamber-to-chamber drift; resolves the companion-sourcing unknown via sasts + our detector). Remaining owner blocker: the LegiScan key + terms check (dual-use with the NY oracle). Verify-at-key-time: whether dataset archives embed full texts or only doc_id references.
---

# Bill-text similarity — rush scoping (front of line after the counter)

> **Why rushed:** owner 2026-07-17 — *"a lobbyist informed me the bill text similarity identifier could be very
> helpful in the coming weeks — rush it in a restaurant way, not a sacrificing-quality way."* Front of the
> queue behind the counter. This page is the sufficient-scoping pass so the build is mechanical.

## OWNER DECISIONS 2026-07-25 (supersede the open items below where they overlap)

1. **LegiScan = TEMPORARY, by explicit owner proposal.** *"Relying on LegiScan long-term is probably not the
   best idea — but at our limited, organization-specific scale it doesn't hurt to temporarily use it until we
   can establish an independent replacement… quietly outsourcing a small part of our backend so we can focus on
   the features that make our site stand out."* Banked as the decision, with the discipline that makes it safe:
   - **Seam requirement (Standard #6):** every LegiScan touch goes behind a `corpus_source` contract (fetcher +
     field map), exactly like the VA source seam — so the swap-out later is mechanical, never a rewrite.
   - **Exit criteria (either fires → replace that slice):** (a) **monetization** (the free tier is
     non-commercial — re-check terms the day we charge); (b) **native onboarding** — each state we ingest
     natively (the NY pattern) replaces its LegiScan slice one state at a time. No big-bang replacement needed.
   - **Dependency honesty:** it's an outage/limit/terms-change exposure on a NON-accuracy-path feature. The
     lobbyist-facing VA data never depends on it.
2. **States: ALL of them** — *"assuming it's free and sustainable, the more data the better."* Feasible within
   the free tier only with a two-stage design (see "corpus at 50-state scale" below); sustainability math inside.
3. **Historical depth: YES** — compare against other states' *past* sessions too, and Virginia's own history
   "to an extent" (the extent is exactly the LIS authorization rule — see the historical section below).
4. **Companion tracker promoted to a FEATURE** (not just calibration data): the companion bill's **progress +
   text-drift, chamber to chamber** (owner: *"think about how important that info is"*). Design below.

## The owner's question, answered first: is cross-state comparison impossible without full per-state datasets?

**Not impossible — but yes, you can only compare against text you HAVE.** The similarity math needs the other
state's bill text on our side. The good news is that does **NOT** mean building 50 state ingests:

| Corpus source | What it gives | Cost / terms | Verdict |
|---|---|---|---|
| **LegiScan API** | 50-state bills incl. **full texts** (base64 via `getBillText`), one contract | free tier ~30k queries/mo; **key = 5-min registration; terms check required** (free tier is non-commercial — fine pre-revenue, re-check at monetization) | **RECOMMENDED.** And it's **dual-use**: a LegiScan key is ALREADY the named blocker for C-8 Part 2 (the NY independent oracle, [[state/current_status]] NEXT #2). One owner action unblocks two workstreams. |
| **Open States (Plural)** | bulk downloads + API v3, permissive terms | free; text is often *links* rather than inline | the fallback / supplement — better terms at monetization, weaker inline-text coverage |
| Per-state native APIs | deepest quality (our VA/NY pattern) | one integration per state | the LONG-term multi-state path — NOT a rush prerequisite |

**Solution shape:** one aggregator contract (LegiScan) gives the corpus for *any* target state now; native
ingests replace it state-by-state as we onboard them for real. Per the brain's standing rule
([[knowledge/lis_api_authorization]] §"onboarding state #2"): capture the aggregator's authorization terms as a
sibling knowledge page **before** the first pull.

## What is already confirmed on our side (probed live, 2026-07-17)
- **VA full text is structurally available, inline.** `LegislationVersion/GetLegislationVersionbyBillNumberAsync`
  (a route the worker ALREADY consumes) lists every version with `LegislationTextID`; then
  `LegislationText/GetLegislationTextByIDAsync` returns the **entire bill text** in `DraftText` (HTML; ~19 KB for
  a sample bill). Both public keys authenticate.
- **Bonus discovered in the payload:** the text embeds structural hyperlinks to every affected
  `law.lis.virginia.gov/vacode/§` section — the future "watch a CODE SECTION" feature (ideation B2) gets its
  substrate for free from the same ingest.
- **Ground truth for calibration exists in our own data:** VA House/Senate **companion pairs** (e.g. the
  HB463↔SB402 pattern) are known near-identical pairs — a labeled validation set for tuning and TESTING the
  similarity thresholds. Measure-first applies to the algorithm itself: thresholds are fit to labeled pairs,
  not chosen by feel.

## The corpus at 50-state scale (free AND sustainable — the design that makes "all of them" true)
Naively pulling every US bill text via per-text API calls (~130–180k bills/yr) blows the ~30k/month free tier in
week one. The sustainable shape, same philosophy as [[knowledge/lis_api_safety]] guardrail #1 (fetch less, cache
more):
1. **Bulk datasets first:** LegiScan publishes per-state, per-session **dataset archives** (`getDatasetList` →
   `getDataset`), refreshed weekly — one query returns a whole session's bill metadata. 50 states on a weekly
   check ≈ hundreds of queries/month, trivial. **⚠️ verify at key-time:** whether the archives embed full texts
   or only `doc_id` references (determines stage-2 volume; the docs are ambiguous and I will not assume).
2. **Metadata prefilter → selective text fetch:** shortlist candidates per VA bill on cheap fields (title,
   description, LegiScan's own `subjects`, and `sasts` links), THEN `getBillText` only the shortlist. Text
   fetches become proportional to *candidates*, not to the national corpus.
3. **Fetched text is cached forever ours** (append-only corpus store — the same store decision as
   [[architecture/roster_and_votes_ingestion]]'s votes: NOT Sheets). Re-fetch only on a version change.
4. If a hot use case needs *exhaustive* text coverage for specific states, those states get full pulls first —
   priority-by-need inside an all-states frame.

## Historical depth (owner: "not only recent — also historically; in Virginia's case, to an extent")
- **Other states' history: easy.** LegiScan datasets reach back ~2009–2011 for most states; the mockup's rows
  (TX 2025, CO 2024) were already historical. Same pipeline, older sessions.
- **Virginia's own history — the "extent" IS the authorization rule** ([[knowledge/lis_api_authorization]]):
  the LIS API toolset is authorized for **2025/2026 session data only**; the GA has not authorized pre-2025
  extraction *via that toolset*, and LIS's own instruction is to use **legacylis.virginia.gov CSV download**
  for older sessions. So: **2025/2026 VA text via the API (probe-confirmed, inline); pre-2025 NEVER via the
  API.** Probed legacylis (2026-07-25): the site is up, but its bulk CSV/download area is not linked from the
  homepage and the obvious paths 404 — **where its CSVs live, and whether they include full TEXT vs metadata
  only, is UNLOCATED — flagged, not assumed.** The no-conflict alternative for pre-2025 VA text: **LegiScan's
  own VA historical datasets** — using LegiScan's service under LegiScan's terms does not touch VA's API
  toolset, so it does not collide with the LIS rule (the rule governs extraction *with that toolset*, and
  legacylis remains the blessed native channel if/when its text location is found). When the GA authorizes
  older sessions on the new API ("you will be notified"), the native channel opens and supersedes.

## The companion tracker (owner-promoted feature — and it closes an open unknown)
The owner's point: a companion pair (HB463 ↔ SB402) is **two simultaneous paths to the same outcome**, and what
a lobbyist needs at a glance is (a) **where each copy is** and (b) **whether they are still the same bill** —
after crossover the versions drift, and the drift *is* the negotiation state: your carve-out surviving in one
chamber and not the other tells you whether a conference fight is coming and which chamber's version to defend.
- **Detection — TWO independent sources, and this RESOLVES the companion-sourcing unknown flagged in
  [[architecture/roster_and_votes_ingestion]]:** (1) **LegiScan's `sasts` (same-as) field** — structural
  companion linkage, free with the corpus; (2) **our own similarity core** — companions are near-identical
  same-session opposite-chamber pairs, so the detector finds them even where `sasts` is missing. Each validates
  the other (the reconciliation pattern).
- **Display (War Room bill workspace, LIS region):** the companion row grows from a bare link to: companion
  number + patron · **its current stage** (sourced) · **drift label** (derived → amber): *"in sync"* /
  *"diverged — Senate version dropped the private right of action"* (the drift summary is the version-diff
  substrate, B1). This is an OOUX related-object preview, exactly the pattern the page is built on.
- **Calibration note:** hand-label ~20 known 2026 companion pairs as ground truth FIRST (org knowledge), so the
  detector is *tested against* labels, not circularly generated from them; `sasts` provides an independent
  check set.

## The algorithm (quality path, deliberately boring)
1. **Normalize:** strip HTML/anchors, drop state-specific boilerplate (enacting clauses, numbering formats
   differ per state), lowercase, collapse whitespace. Normalization quality is 80% of similarity quality.
2. **Compare:** word n-gram **shingles → MinHash/LSH** for candidate retrieval at corpus scale, **Jaccard** on
   shingle sets for scoring; section-level alignment for the *partial* case (a bill lifting two sections from a
   model act). Standard, proven, cheap — the same family the model-legislation journalism projects used. No ML,
   no embeddings, nothing to hallucinate.
3. **Output: coarse labels ONLY** — `near-identical / substantial overlap / partial / loose` — per the P20b
   honesty rule ([[design/information_display]]); the fake-precise "94%" was already killed on the mockup.
   Labels are the **DERIVED** trust class → amber provisional chips in the Elsewhere zone (already designed).
4. **Where it runs: an offline batch tool + its own workflow** writing a similarity store — **never inside the
   calendar worker.** Zero contact with the accuracy path.

## Build order (after the counter PR; steps 1–3 have NO external dependency)
1. VA text ingest tool (version list → texts; conditional-fetch + cache per [[knowledge/lis_api_safety]]).
2. Similarity core (normalize/shingle/MinHash/Jaccard) — pure, offline, golden-tested.
3. **Calibrate + prove on companion pairs** (known-same) vs random bill pairs (known-different); publish the
   separation in the PR. If the labels can't cleanly separate known-same from known-different, we say so and stop.
4. Corpus pull for the owner's target states via LegiScan (needs the key + terms page).
5. Surface: the War Room **Elsewhere** zone as mocked (amber chips, coarse words, source named per row).

## Deliberately OUT of the rush (recorded so the line holds)
- Version-to-version **redline diffing** (B1) — same ingest, different feature; next in line, not this PR.
- Code-section watch (B2) — substrate lands free, feature later.
- Any similarity-driven *prediction* — that's [[ideas/predictive_lane]] Tier 3, gated on the calibration harness.

See also [[ideas/lobbyist_jtbd_ideation]] §B4/§B5, [[design/object_page_patterns]] §5b (derived class),
[[architecture/roster_and_votes_ingestion]] (sibling ingest scoping), [[ideas/moat_and_competition]].
