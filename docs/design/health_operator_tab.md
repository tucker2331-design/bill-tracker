---
tags: [design, ui, health, operator, bullet-graph, access-gated, scope, web]
updated: 2026-06-24
status: built
---

> **▶️ BUILT 2026-06-24** (`claude/health-tab`, verified live): `web/src/components/BulletGraph.tsx`
> (reusable Few bullet graph w/ danger bands), `web/src/data/health.ts` (lightweight `tq WHERE`
> operator-signal loader — ~2 KB, not the 5 MB sheet), `web/src/views/Health.tsx` (9 prioritized gauges +
> breaker chip + severity-coded alert feed + router distribution + raw counters). 0 console errors;
> App.tsx unchanged (Health kept its props). **Remaining: the ACCESS-GATING infra (§4) — Cloudflare Access
> on an operator deploy.** Harmless visible now (pre-launch, no lobbyists; metrics are operational, not
> secret); must be gated before the public launch.

# Health / Operator Tab — SCOPE (Task #4)

Owner queue **Task #4**. The operator/admin trust surface (vision §3f + §7): surface the diagnostics the
system **already produces**, as **Few bullet-graph gauges with danger bands** (owner: *"like a car's RPM
red zone"* = PL-8), **access-gated** to the owner + a few (NOT lobbyist-facing). Scoped 2026-06-23, grounded
in the LIVE signals (not assumptions). Build after the Calendar PR (#166) lands.

Relates to: [[design/information_display#6 — Punch-list...|PL-8]], [[ideas/product_vision#3f Bug-health tab — the operator view]], [[ideas/product_vision#7 The trust layer]], [[design/reading_notes]] (Few read in full).

---

## 1. The data sources (all gviz-readable, no new backend)
The Health tab reads what the workers already emit — two sheets, same auth-free gviz path:

**A. `Bill_Tracker` R1 — completeness payload** (already wired in the current `Health.tsx`):
`universe_count`, `records_written`, `in_history_not_in_universe[]`, `prefiled_no_history`,
`skipped_malformed_universe`, `outcome_structural`/`outcome_keyword_fallback`,
`outcome_keyword_mismatches`/`_rate`, `patron_present`/`patron_missing`, `docket_rows_total`/
`docket_unparseable_dates`/`_rate`, `checked_at_utc`, `session_code`.

**B. `Sheet1` — the calendar subsystem's operator signals** (NOT yet wired):
- **`SYSTEM_METRICS` row** (`Origin=system_metrics`; JSON in the Outcome cell) — 50+ counters. Live values
  (2026-06-23 cycle): `total_processed=65374`, `rows_appended=60794`, **`meeting_unsourced=0`** (the
  Section-9 metric — every meeting action has a time), `invariant_violations=1`, `dropped_noise=7073`,
  `legevent_route_meeting=31668 / admin=22370 / executive=554 / blank=3709`,
  `refidclass_unknown_refid` / `refidclass_vote_unmatched=1`, `legislation_event_recovered=1005 /
  attempted=3863`, `gap_minutes` / `gap_cause`, `derived_standing=1`.
- **`SYSTEM_ALERT` rows** (`Origin=system_alert`; `Status`=severity, `Outcome`=`[SEVERITY:CATEGORY] msg`).
  Live: `[WARN:TIMING_LAG] No schedule match for HB30 … row deferred to Ledger.` → the operator alert feed.
- **State cells** (separate tiny gviz `range=` reads, documented contracts in [[architecture/calendar_pipeline]]):
  `AA1` = last-successful-cycle UTC (freshness); `W1` = breaker-trip JSON (empty when healthy);
  `Y2` = `meeting_unsourced` rolling baseline.

## 2. The metrics → bullet graphs (each with good / warning / DANGER bands + a target marker)
Few's bullet graph: a horizontal track with qualitative bands (the **rightmost = the red danger zone**,
the owner's "RPM redline"), a thin **measure bar** = current value, and a **target tick** = the goal.
Repeat as **small multiples** (one column). Calibration from steady-state + the worker's own alert floors.

| # | Metric | Source | Direction | Good | Warning | **Danger** | Target |
|---|---|---|---|---|---|---|---|
| 1 | **Section-9 accuracy** (`meeting_unsourced`) | SYSTEM_METRICS | lower=better | 0 | 1–25 | **>25** (breaker delta) | **0** |
| 2 | **Bill completeness** (`records_written/universe`) | completeness | higher=better | 100% | <100% | **anomalies>0** | **100%** |
| 3 | **Data freshness** (hrs since `AA1`/`checked_at_utc`) | AA1 / R1 | lower=better | <6h | 6–12h | **>12h** | <1h |
| 4 | **Invariant violations** | SYSTEM_METRICS | lower=better | 0 | 1–49 | **≥50** (breaker) | **0** |
| 5 | **Outcome drift** (`outcome_keyword_mismatch_rate`) | completeness | lower=better | <0.1% | 0.1–1% | **>1%** | <0.1% |
| 6 | **Unclassified share** (`route_blank/total`) | SYSTEM_METRICS | lower=better | <2% | 2–5% | **>5%** | →0 |
| 7 | **Patron coverage** (`patron_present/records_written`) | completeness | higher=better | 100% | <100% | **<98%** | 100% |
| 8 | **Recovery yield** (`legislation_event_recovered/attempted`) | SYSTEM_METRICS | context | — | — | — | (info bar) |

Bands are **data-driven** (read from the breaker thresholds / steady-state), never hardcoded magic numbers
that rot (Standard #1). A reading that lands in the red band makes the gauge's measure bar go red (popout).

## 3. Beyond the gauges
- **Breaker status** — a single status chip (GREEN armed / RED tripped) from `W1` (+ the trip JSON when red).
- **Alert feed** — the `SYSTEM_ALERT` rows, severity-coded (INFO/WARN/CRITICAL), newest first; this is the
  operator's "what needs a human" list (the only thing that should ever need attention — Standard #8).
- **Classification distribution** — `legevent_route_*` + `refidclass_*` as a small honest breakdown (where
  the rows went), so drift in the structural router is visible.
- **Raw counters** — the full `SYSTEM_METRICS` JSON in a collapsible block for deep inspection.
- Everything carries its **denominator** (PL-7) and a provenance note (which sheet/cell it came from).

## 4. Access-gating (the CONSTRAINT — operator-only, not lobbyist-facing)
**Cloudflare Access (Zero Trust)** is the clean fit for the $0 static-SPA + gviz setup:
- **Recommended:** a **separate operator deploy** — a second Cloudflare Pages project (or a subdomain like
  `operator.<domain>`) serving the Health app, protected by a **CF Access self-hosted application** with an
  **email-allowlist policy** (owner + a few) and **one-time-PIN** login (no IdP integration needed; Google/
  GitHub optional). Free tier covers ≤50 users.
- Why separate (not a path on the public SPA): a client-routed SPA serves `index.html` for every path, so
  CF Access can't cleanly gate one in-app tab — gating a distinct deploy/subdomain is enforceable and simple.
- **DATA-PUBLICITY CAVEAT (must record):** CF Access gates the operator **UI**, but the underlying
  `Bill_Tracker`/`Sheet1` gviz data is **link-readable (public)** — so the metrics themselves are not
  secret, only the operator presentation is hidden from lobbyists/public. The metrics are operational
  health (not credentials), so UI-gating is acceptable for v1. A true private data layer (a separate
  non-link-shared sheet, or an auth'd proxy / Cloudflare Worker reading via a service account) is a later
  hardening **iff** any operator signal becomes sensitive. Note in the build that we never put secrets in
  the public sheet.

## 5. Build plan (after #166)
1. **`web/src/data/health.ts`** — `loadHealth()`: read `Bill_Tracker` R1 (have it) + `Sheet1` SYSTEM_METRICS
   row + SYSTEM_ALERT rows + `AA1`/`W1` cells (gviz). Parse into a typed `HealthData` (metrics + alerts +
   breaker + raw). Lazy + cached like `loadCalendar`.
2. **`web/src/components/BulletGraph.tsx`** — a reusable Few bullet graph: props `{label, value, target,
   bands:[{upto, tone}], direction, format}`; renders the track + bands (danger = red) + measure bar +
   target tick; tabular figures; accessible (value + band in `aria-label`, never color-alone).
3. **`web/src/views/Health.tsx`** — rebuild from flat stat-cards to: a small-multiples column of bullet
   graphs (§2), the breaker chip, the alert feed, the distribution, the collapsible raw counters. Keep the
   denominator-bearing trust framing.
4. **Access-gating** — separate Cloudflare Pages operator deploy (or subdomain) + CF Access email-allowlist
   policy (one-time PIN). Document the data-publicity caveat. (Infra step; coordinate with owner's CF account.)
5. **Verify** in the preview (bands render, danger pops, alerts list, a11y, build clean); screenshot proof.
6. Its own branch + PR; CodeRabbit + Qodo; fold in; merge. Then write-back.

## 6. Master-site context (vision §9, later — not this task)
The operator Health tab is the first tenant of the eventual **master dashboard** (cross-system home for the
bug/health tab + the historical tracker). Build Health so it can lift onto that master site (self-contained
data layer + components). The historical tracker (per-committee survival rates, cross-session trends reading
the session archive) is a separate, bigger design pass — explicitly not now.

See also [[design/information_display]] (PL-7/PL-8), [[ideas/product_vision]] (§3f, §7, §9), [[state/next_session]], [[log]].
