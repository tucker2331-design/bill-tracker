---
tags: [ideas, architecture, multi-state, strategy, data, trust]
updated: 2026-06-24
status: vision
---

# Multi-State Data Strategy — bulk-as-truth + provisional speed layer

Owner vision (2026-06-24), captured for the future. As we scale past Virginia, **not every state hands us
clean structural APIs.** VA does (the LIS Schedule/History/Docket/Vote blobs + committee/session APIs). Other
states give us less — and we'll have to **rebuild structural reinforcement ourselves**, and in some cases
**parse/scan their websites** (the thing we otherwise avoid — Standard #3). This page is the architecture
for doing that **without losing trust**, plus my challenges + recommendations (owner asked me to question it).

## 1. The owner's proposal (faithful restatement)
- **Pennsylvania** (likely next, or soon) publishes **bulk data hourly**. Use that **stable hourly bulk** as
  the backbone of the **master database + the site that tracks macro trends** (the slow, trustable layer).
- **Lobbyists may need fresher info** than hourly → when we must, **text-parse/scrape** the state site, but
  into a **SEPARATE database** (the fast layer).
- **Cross-verification:** the bulk file wins. If an item already exists in the bulk file, the bulk version is
  authoritative; the text layer only adds **new** items the bulk hasn't published yet.
- **Goal:** the two layers continuously verify each other; the site is fed **stable, trustable data** for
  everything that doesn't need instantaneous updates.

## 2. Why this is the right shape (endorse)
This is a **Lambda-style architecture** (a *batch/serving layer* = bulk + a *speed layer* = scrape), and it
fits the project's spine perfectly:
- **Bulk = the system of record** (structural, complete, stable) — the same role LIS's blobs play for VA.
- **Text/scrape = a PROVISIONAL speed layer**, explicitly subordinate — which honors **Standard #3** ("text
  parsing for internal/provisional only, validated against structural data") and the **trust layer** ("never
  pretend": provisional data is *flagged* provisional, never presented as confirmed).
- **Bulk-wins reconciliation** is the correct precedence and keeps text-parser errors out of the trusted store.

## 3. Challenges + questions (owner asked me to push)
1. **Do lobbyists actually need sub-hourly?** Legislative actions are not high-frequency — committee meetings
   are scheduled, floor sessions are dated, votes cluster in session hours. **Hourly bulk is already fresh.**
   The speed layer is the brittlest, highest-maintenance part (the very text-parsing we fought to remove on
   VA). **Recommendation: gate the speed layer hard** — only during *active session hours*, only for the
   *time-critical signals* (a live vote, a same-day meeting/agenda change), never a full duplicate of the
   bulk. Quantify the real freshness gap before building it; if hourly covers ~95%+, the speed layer is a
   thin, session-scoped supplement, not a second pipeline.
2. **Conflict resolution must be at the ACTION grain, not the BILL grain.** "Favor bulk if the item exists"
   is right, but a bill *exists* in the bulk while a *new action on it* may not yet. So: **the bulk is
   authoritative for every action it contains; the speed layer only surfaces actions NOT YET in the bulk,
   each flagged provisional; when the next hourly bulk includes that action, it SUPERSEDES the provisional
   one** (and if the bulk's version differs, the bulk wins **and we log the discrepancy**).
3. **"Two databases" — split by PURPOSE, not just freshness.** Cleaner than "bulk DB vs text DB":
   - **(a) Macro/historical store = immutable hourly bulk snapshots.** Append-only; never touched by the
     speed layer. Perfect for trend analysis (per-committee survival rates, cross-session trends) — the
     [[ideas/product_vision]] §9 historical tracker. Stable by construction.
   - **(b) Current-state store = bulk baseline + a provisional speed overlay.** The lobbyist live view. The
     overlay is TTL'd and superseded by the next bulk.
   This split (immutable-history vs mutable-current) is sturdier than splitting by data source.
4. **The cross-verification IS a feature, not just plumbing.** Every hour the bulk **grades the speed layer**:
   provisional items the bulk confirms = correct; ones it contradicts = a text-parser miss. That's a
   **continuous accuracy metric** — the same discipline as VA's MinutesBook reconciliation tripwire and the
   Health tab's drift gauge. Surface it on the (access-gated) Health tab per state: "text-parser agreement
   with bulk: 99.x%". If it drops, we *know* the scraper drifted (a state changed its site) — Standard #8
   (humans pinged only on real anomalies), not silent rot.

## 4. Recommendations
- **A. Per-state SOURCE MANIFEST (structural config — Standard #5/#6).** Each state declares its sources
  (`api` / `bulk` / `scrape`), each source's cadence, completeness, and **trust precedence**. The
  reconciliation engine is generic; only the manifest is per-state. VA = api(blobs); PA = bulk(hourly) +
  scrape(session-only); scrape-only states = scrape + heavier structural reinforcement. This is the real
  50-state isolation — no per-state code, just per-state declarations.
- **B. Probe PA's bulk feed BEFORE designing** (like the NY calendar probe / the VA blob discovery). Confirm:
  what the hourly bulk actually contains, whether it's *complete* (all bills/actions) or partial, its
  structural identifiers, and the true cadence. Don't assume "hourly bulk" = complete + structural.
- **C. Provisional-flag everything in the speed layer** end-to-end (data model → UI badge), reusing the
  existing trust primitives (the pin, `derived_standing`, the confidence/freshness badges). A speed-layer
  fact reads "provisional — not yet in the hourly bulk"; it clears or is corrected when the bulk arrives.
- **D. Reuse the structural reinforcement we built for VA** (refid-namespace logic, the structural router's
  meeting/admin classification, the convene-time graph) as the *reusable engine*; the per-state inputs are
  swappable. Where a state lacks structural IDs, we synthesize them and validate against the bulk.
- **E. Plan retention up front.** Immutable hourly snapshots grow fast (cf. the VA session-archive capacity
  work). Decide snapshot granularity (hourly raw vs daily rolled-up) + retention before it bites.

## 5. Owner decisions + new directions (2026-06-25)
Owner reviewed §3/§4 and answered. Decisions + the ideas this surfaced:

- **§3.1 freshness SLA → 15 min for now** (current-state lobbyist view), *revisit later.* The speed layer
  is sized to "fresher than the hourly bulk, within ban/load limits." **NEW IDEA (owner, park for later):**
  instead of a always-on scrape, consider an **on-demand "get me the latest" button** in the UI that fires a
  *single, specific* live API/scrape call for one bill/committee on request — gives a lobbyist instant fresh
  data exactly when they need it, while keeping baseline load near zero (the cleanest way to honor the
  ban/load charter — pull only when a human actually asks). Weigh per-call rate-limits + caching the result.
- **§3.2 action-grain reconciliation → confirmed.**
- **§3.4 cross-verification → "do it." → SELF-HEALING ARCHITECTURE (owner, big idea to carry system-wide).**
  The bulk grading the scraper every hour isn't just a metric — it's the seed of a **self-healing system**:
  every derived/provisional layer is continuously checked against a more-authoritative source, and a
  disagreement *diagnoses its own failure* ("the PA scraper drifted because PA changed its site") and can
  eventually **auto-correct or auto-quarantine** the bad path rather than silently rot. This is the ultimate
  expression of Standard #8 (zero routine maintenance; humans pinged only for true anomalies). **Owner: keep
  in the back of our minds and consider how to implement across the whole system** — we already have early
  instances (the calendar's MinutesBook reconciliation tripwire, the Health drift gauge, the breaker's
  rolling baselines). A future pass should unify these into one "every layer is graded by a better layer"
  discipline. **→ tracked as a system-wide design principle to mature.**
- **§4 (split stores by PURPOSE) → owner asked me to justify further. Justification:**
  1. **Different jobs, different shapes.** Macro/trends queries are *analytical* time-series ("per-committee
     survival rates across 5 sessions") wanting an **append-only, never-mutated** dataset — each hourly
     snapshot is a frozen fact ("at hour T the world looked like X"). The current-state store is
     *transactional* ("latest on HB123 right now") — mutable, overwritten each cycle. One store can't be
     both append-only and overwrite-in-place well.
  2. **Reproducibility.** A trend chart must not change retroactively. If trends read the same mutable store
     the speed layer overwrites, "bills passed per week" could differ tomorrow — the data moved under you.
     **Immutable snapshots make history reproducible.**
  3. **Purity / no corruption.** If the speed layer (provisional text) wrote to the trend store, one
     mis-parse could permanently skew a multi-session trend. Feeding the macro store **only from the
     authoritative bulk** keeps the historical record as clean as the bulk.
  4. **Isolation.** Heavy analytical scans (months of snapshots) shouldn't compete with the live view's
     reads/writes — separate performance domains.
  5. **It's the PROVEN VA pattern, generalized.** We already split current-state (live `Sheet1`) from frozen
     per-session snapshots (the "Mastermind Archive" workbook the §9 historical tracker reads —
     [[architecture/session_archive]]). "Split by purpose" is not new; it's what works for VA.
- **§5 macro per-state or cross-state → "all of it; build in both."** So **normalize the schema across states
  from day one** (a state column + a shared record shape) so the same store serves a per-state view AND
  cross-state comparison without a later migration. (Codex already did this instinct for NY: it flattens NY
  OpenLeg into the *same product columns* as VA's `Bill_Tracker`.)
- **Speed layer writing to the macro store → "if the macro store is genuinely always correct, no need —
  but don't write it off."** Agreed invariant: **provisional/unverified data NEVER enters the macro store.**
  The open part is *what counts as the authoritative feed per state*: for a state with no bulk (scrape-only),
  the "bulk" role is filled by the **validated** scrape (provisional data still excluded until verified). So
  the rule is "macro is fed only by the per-state authoritative, verified source," not "macro is fed only by
  a literal bulk file." Keep the door open for states that force a different authoritative feed.

## 6. Open questions still on the table
- Per-call rate-limit + caching design for the on-demand "latest" button (§5) — does one live call per
  user-click stay within each state's ban/load budget?
- For scrape-only states: what's the verification bar that promotes a scraped action from provisional →
  macro-eligible (a second independent source? a structural cross-check?)?

See also [[ideas/product_vision]] (§9 historical tracker, §7 trust layer), [[ideas/lis_data_inventory]],
[[knowledge/lis_api_safety]] (the load discipline ports to PA), [[architecture/calendar_pipeline]],
[[workflow/zero_routine_maintenance]] (Standard #8), the New York state-brain in `docs/ny/`.
