---
tags: [architecture, text-intelligence, similarity, cross-state, rush, scoping]
updated: 2026-07-17
status: active
open_loop: RUSHED to front of line (owner 2026-07-17, lobbyist-informed, "restaurant rush — not sacrificing quality") — builds right after the incident counter. Blockers only the owner can clear — (1) a LegiScan API key (5-min registration; DUAL-USE, it also unblocks C-8 Part 2's NY oracle) + its terms check; (2) WHICH STATES the lobbyist wants comparisons against (scopes the corpus pull). Everything else (VA text ingest, similarity core, companion-pair calibration) has zero external dependencies and can start immediately after the counter PR.
---

# Bill-text similarity — rush scoping (front of line after the counter)

> **Why rushed:** owner 2026-07-17 — *"a lobbyist informed me the bill text similarity identifier could be very
> helpful in the coming weeks — rush it in a restaurant way, not a sacrificing-quality way."* Front of the
> queue behind the counter. This page is the sufficient-scoping pass so the build is mechanical.

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
