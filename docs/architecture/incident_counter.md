---
tags: [architecture, trust, incident, health, parity, plan, owner-decision]
updated: 2026-07-17
status: active
open_loop: UNBLOCKED 2026-07-17 (owner directive "we need to prove it — remember the counter") — definition = the owner's own sentence, display = Health-first, guards = the three named. WIRING IS NOW A READY BUILD TASK; the write-path must be made verifiable via a scratch-workbook env override (audit #74) before the guard one-liners land. Public promotion of the number stays a later owner call.
---

# Incident counter + LIS-parity — architecture & the owner decisions that gate it

The trust claim expands from "never wrong" to **"never less than LIS"** ([[ideas/lobbyist_jtbd_ideation]]
§8b). The visible artifact is a **"N days since a data incident"** counter. Build-wave TASK 2, phases P1–P3.

## What is BUILT vs GATED

- ✅ **BUILT + proven now:** `tools/incident_log/log.py` — the append-only `Incident_Log` mechanism +
  `record_incident()` (FAIL-OPEN, closed class vocabulary) + genesis-aware `days_since` math. 9 offline
  goldens (`test_incident_log.py`). The counter mechanism is unambiguous regardless of the exact definition.
- ⛔ **GATED on owner decisions (below):** wiring the counter's WRITERS into the verification guards, the
  exact incident DEFINITION, and whether the number is shown PUBLICLY (trust header) or Health-tab-only.
  **Why not wired now:** (1) the definition wording is the owner's call (like the war room); (2) I cannot
  VERIFY a `record_incident` write-path fires without manufacturing a real incident — and shipping an
  unverifiable write into the accuracy sentinel (a critical guard) violates "verify the row"
  ([[failures/assumptions_audit#74]]) and risks destabilizing the guard.

## The owner decisions — RESOLVED 2026-07-17 (owner: "we need to prove it — remember the counter we were
## gonna start, to track how long data holds clean before intervention")

1. **The incident DEFINITION — the owner's own sentence IS the definition: *"how long data holds clean before
   intervention."*** An incident = any event where the data did **not** hold clean on its own. The three classes
   implement it, with one addition the owner's word "intervention" makes explicit:
   - `accuracy` — wrong data was visible on the product (sentinel FAIL / breaker bypass), **or a human had to
     manually correct product data** — if we had to intervene, it did not hold clean; the intervention is the
     incident even if no user saw the error.
   - `parity_gap` — content on LIS not visible here for > 1 worker cycle (P2/P3 parity checks).
   - `degraded` — a user-visible degraded state (stale banner / missing panel) lasting > 60 min.
2. **Display: Health-tab first** (the recommended path, now adopted). Public/trust-header promotion remains a
   **later owner call** once a clean baseline exists — the counter must earn its way to the marketing surface.
3. **Guards that WRITE: the named three** — `accuracy_sentinel` FAIL, `completeness_tripwire` FAIL,
   `reconciliation` mismatch — each a fail-open one-liner in the existing FAIL path. Manual interventions are
   logged by hand (a CLI helper: `python3 -m tools.incident_log.log record accuracy "…" manual`).

## Wiring plan (now a READY build task — next engineering PR)
- **First, make the write-path verifiable (audit #74 gate):** add an env override for `SPREADSHEET_ID` in
  `tools/incident_log/log.py` so the full `record_incident` → row → `days_since` loop is exercised against a
  **scratch workbook** in CI — a synthetic incident must never pollute (and reset!) the real days-clean ledger.
  This was the honest reason wiring was deferred; the override closes it.
- Seed the genesis row (one CI run of `days_since_last_incident()` auto-creates the tab + epoch). **The genesis
  date is when "days clean" starts counting — every day earlier is provable trust we're not banking. Seed early.**
- Add the fail-open `record_incident(...)` call to each approved guard's FAIL branch (never the success path).
- Add the manual-intervention CLI subcommand (the owner's "intervention" class of incident needs a hand-loggable path).
- Frontend: a Health-tab line reading `Incident_Log` via gviz (VA·Live, gviz-readable) →
  "N days since a data incident"; red only if an incident is currently OPEN. (Later: the same value in the
  trust header on owner approval.)
- **Why this matters beyond the feature** ([[ideas/moat_and_competition]] #4): the counter is the *receipt* that
  turns claimed trust into counted trust — accumulated, dated evidence a late entrant cannot backfill. It has
  the same can't-vibe-code-the-past property as the observation layer. Every un-seeded day is thrown-away moat.

## Parity feeders (P2/P3 — separately tracked)
- **P2 endpoint audit** — SHIPPED (#220/#221, `tools/parity/endpoint_audit.py`): catches LIS API routes we
  don't consume (the unknown-unknown). Its INFO alert is the seed of `parity_gap` detection.
- **P3 sampled DOM parity** (not built) — weekly headless render of N tracked-bill LIS pages, diff
  history-row + meeting counts vs ours; a mismatch is a `parity_gap` incident. Spec in the build-wave README.
- Once P2/P3 are stable they call `record_incident("parity_gap", …)` automatically.

See also [[audits/build_wave_2026-07/README]] (TASK 2), [[ideas/lobbyist_jtbd_ideation]] §8b,
[[architecture/verification_durability]] (the guards that would write here).
