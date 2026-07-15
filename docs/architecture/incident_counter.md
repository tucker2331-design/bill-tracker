---
tags: [architecture, trust, incident, health, parity, plan, owner-decision]
updated: 2026-07-15
status: active
open_loop: incident DEFINITION + public-vs-Health display + which guards write are owner decisions — mechanism built, wiring gated on them
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

## The owner decisions (each blocks the wiring)

1. **The incident DEFINITION (exact wording — needed before anything public).** Draft (from §8b), three classes:
   - `accuracy` — wrong data was visible on the product (an accuracy-sentinel FAIL / a breaker bypass).
   - `parity_gap` — content on LIS not visible here for > 1 worker cycle (P2/P3 parity checks).
   - `degraded` — a user-visible degraded state (stale banner / missing panel) lasting > 60 min.
   Owner: approve/adjust the wording + the thresholds (">1 cycle", ">60 min").
2. **Public vs Health-only.** Ship the counter on the **Health (operator) tab first** (recommended — it's
   honest but unpolished), and only promote it to the public **trust header** once the owner blesses the
   definition and a clean baseline exists. (Owner already said keep the 4 Health rings — this is additive.)
3. **Which guards WRITE incidents.** The unambiguous three: `accuracy_sentinel` FAIL, `completeness_tripwire`
   FAIL, `reconciliation` mismatch. Owner: confirm this set (each wiring is a fail-open one-liner:
   `record_incident("accuracy", summary, "accuracy_sentinel")` inside the tool's existing FAIL path).

## Wiring plan (mechanical, once decisions are made)
- Seed the genesis row (one CI run of `days_since_last_incident()` auto-creates the tab + epoch).
- Add the fail-open `record_incident(...)` call to each approved guard's FAIL branch (never the success path).
- Frontend: a Health-tab line reading `Incident_Log` via gviz (VA·Live, gviz-readable) →
  "N days since a data incident"; red only if an incident is currently OPEN. (Later: the same value in the
  trust header on owner approval.)

## Parity feeders (P2/P3 — separately tracked)
- **P2 endpoint audit** — SHIPPED (#220/#221, `tools/parity/endpoint_audit.py`): catches LIS API routes we
  don't consume (the unknown-unknown). Its INFO alert is the seed of `parity_gap` detection.
- **P3 sampled DOM parity** (not built) — weekly headless render of N tracked-bill LIS pages, diff
  history-row + meeting counts vs ours; a mismatch is a `parity_gap` incident. Spec in the build-wave README.
- Once P2/P3 are stable they call `record_incident("parity_gap", …)` automatically.

See also [[audits/build_wave_2026-07/README]] (TASK 2), [[ideas/lobbyist_jtbd_ideation]] §8b,
[[architecture/verification_durability]] (the guards that would write here).
