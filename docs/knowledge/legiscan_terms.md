---
tags: [knowledge, api, compliance, legiscan, corpus, rule]
updated: 2026-07-26
status: stub
open_loop: BLOCKED on the owner registering a LegiScan API key — until then the terms wording below is UNVERIFIED (recorded from public docs, not from the account's own terms page) and no LegiScan request may be made. Fill in the verified quotes + the dataset-vs-doc_id answer at key time.
---

# LegiScan — authorization & terms (the corpus source for cross-state text)

Sibling of [[knowledge/lis_api_authorization]]. That page governs Virginia's own API; this one governs the
**aggregator** we use TEMPORARILY for other states' bill text ([[architecture/text_similarity]]).

> **⚠️ STUB — nothing may be fetched yet.** Written before the key exists so that the compliance step happens
> *before* the first request, not after. The brain's standing rule (from
> [[knowledge/lis_api_authorization]] §"onboarding state #2"): **capture a source's authorization window and
> terms BEFORE pulling any of its data, and never assume that an API returning data implies authorization to
> use it.** The same discipline that kept the VA integration clean applies to a third party.

## Why LegiScan at all, and why TEMPORARILY
Owner decision, 2026-07-25: *"relying on LegiScan long-term is probably not the best idea… but at our limited,
organization-specific scale it doesn't hurt to temporarily use it until we can establish an independent
replacement… quietly outsourcing a small part of our backend so we can focus on the features that make our
site stand out."* Recorded in full at [[architecture/text_similarity]] §"OWNER DECISIONS".

**The discipline that makes a temporary dependency safe:**
1. **Seam** — every LegiScan touch sits behind a `corpus_source` contract (fetcher + field map), exactly like
   the VA source seam, so replacing it is mechanical rather than a rewrite (Standard #6).
2. **Exit criteria, either one fires → that slice is replaced:**
   - **monetization** — the free tier is non-commercial; re-read the terms *the day we charge anyone*;
   - **native onboarding** — each state we ingest natively retires its LegiScan slice, one state at a time
     (VA's own native scanner is W2; NY's is queued at [[ny/state/current_status]] #6).
3. **Never on the accuracy path** — the lobbyist-facing VA data must never depend on a third party. LegiScan
   feeds a *comparison* feature; if it vanishes, cross-state context degrades and nothing else does.

## To fill in AT KEY TIME (each is a hard prerequisite, not a nicety)
- [ ] **Quote the actual terms** from the account's own terms page (not a blog or these notes): commercial-use
      wording, attribution requirement, redistribution/caching limits, rate limits, and whether derived data
      (our similarity labels) is restricted. Paste the quotes here with the date read.
- [ ] **Answer the volume question the design hangs on:** do the bulk **dataset archives** (`getDatasetList` /
      `getDataset`) embed **full bill texts**, or only `doc_id` references that each need a `getBillText` call?
      This decides whether "all 50 states" is a few hundred requests a month or a few hundred thousand
      ([[architecture/text_similarity]] §"corpus at 50-state scale"). **Do not guess — measure one state.**
- [ ] **Record the rate limit + the free-tier query allowance**, then set our own ceiling *below* it, mirroring
      LIS-safety guardrail #4 (a hard per-cycle cap independent of the cadence logic, so a bug can't spike us).
- [ ] **Conditional fetch**: check whether the API exposes ETag/`Last-Modified` or a `dataset_hash`; if so, use
      it (guardrail #1 — never re-download unchanged data). LegiScan publishes a per-dataset hash, so a
      change-detection path likely exists; confirm the field name.
- [ ] **Attribution**: if required, decide where it renders on the product surface *before* shipping the
      feature, not as a retrofit.

## Standing rules once live
- **Authorized scope is per-state-per-session, enforced in code** the way `lis_authorization.py` does it — one
  module, one allowlist, a runtime assert on every call path. Do not scatter the scope check.
- **Cache fetched text permanently** in our own corpus store (append-only, not Sheets) and re-fetch only on a
  changed hash: this both respects the source and makes our archive independent of it over time — the slow
  path to not needing them at all.
- **A LegiScan outage must be a visible degraded state**, never a silent gap in cross-state results
  ([[design/information_display]] P25a: fail-closed, say what we cannot currently verify).

See also [[architecture/text_similarity]], [[knowledge/lis_api_authorization]], [[knowledge/lis_api_safety]],
[[ideas/moat_and_competition]] (why the dependency is acceptable *now* and must not become permanent).
