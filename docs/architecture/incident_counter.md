---
tags: [architecture, trust, incident, health, parity, plan, owner-decision]
updated: 2026-07-17
status: active
open_loop: UNBLOCKED + fully scoped 2026-07-17 — definition = the owner's sentence, display = Health-first, guards = the three named, verification = FIRE DRILLS on the real ledger (owner killed the scratch-workbook idea: "don't build fake sandboxes"). Scoping pass 2 found 8 more issues (flood/dedup via open-incident semantics, guard credentials — all three guard workflows are creds-free today, denominator display, drill exclusion). WIRING IS THE NEXT ENGINEERING PR, build order inside. Public promotion of the number stays a later owner call.
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

## The owner decisions — RESOLVED 2026-07-17, definition AMENDED 2026-07-25

1. **The incident DEFINITION — the owner's sentence, now covering the whole trust EXPERIENCE:** *"how long data
   holds clean before intervention"* — where "clean" is judged **from the client's chair, not the pipeline's.**
   Owner correction 2026-07-25 (after the false red Accuracy ring): *"that incident absolutely has to affect
   the clean ledger, because it sent off a red accuracy alarm… imagine you're the lobbyist I sold this to."*
   **A false alarm on the trust surface IS an incident** — the client cannot (and must not need to) distinguish
   "the data is wrong" from "the alarm is wrong"; either way the product broke its promise that morning. Classes:
   - `accuracy` — wrong data was visible on the product (sentinel FAIL / breaker bypass), **or a human had to
     manually correct product data**.
   - `parity_gap` — content on LIS not visible here for > 1 worker cycle (P2/P3 parity checks).
   - `degraded` — a user-visible degraded state (stale banner / missing panel) lasting > 60 min.
   - **`false_alarm` (NEW, 2026-07-25)** — the trust surface showed red without a verified underlying data
     failure. The alarm system is part of the product and is held to the same standard as the data.
   **The 2026-07-25 outcome-drift event is the ledger's FIRST incident** — recorded as `false_alarm` at
   seeding, with its honest (approximate, and marked approximate) start date. The counter's story begins by
   telling the truth about itself.
2. **Display: Health-tab first — and the Health tab is CLIENT-FACING (owner 2026-07-25):** executives at client
   orgs get it ("other executives deserve to know the health of the data and the details"); their staff
   generally don't. This sets the tab's register: an alarm must be **self-diagnosing to a non-engineer
   executive** — structured facts, never internal jargon, never AI prose (owner: "don't translate data issues
   to English, but I don't want an AI to have to diagnose it every time").
3. **Guards that WRITE: the named three** for data incidents (fail-open one-liners in FAIL paths) + the manual
   CLI for interventions and `false_alarm` entries. **Structural rule added (the real fix): the display bands
   and the incident ledger must derive from the SAME verified verdicts** — the Health page may never carry an
   independent judgment that can go red while every guard passes, which is precisely what happened on
   2026-07-25. One truth pipeline: checks → verdicts → (display AND ledger). A band that can diverge from the
   guards is a second, unaudited alarm system, and it will eventually cry wolf.

## What RED means on the client-facing trust surface (the alarm law, owner criticism 2026-07-25)
The owner's two-part criticism, turned into design law:
1. **"If it was truly a false alarm it shouldn't have sent accuracy red."** → **Red accuracy = the product's
   published output is wrong, verified.** An internal consistency check that disagrees WITHOUT impeaching the
   published value (2026-07-25: our published `carried_over` matched LIS's own flags — the check was between
   LIS's two internal fields) is a **different, quieter class** — visible, never red-accuracy.
2. **"I couldn't tell whether everything was wrong or a minor disagreement matching what LIS itself shows."**
   → every alarm row must carry, as **structured fields, not prose**: (a) **what disagrees with what** (our
   published value vs which check); (b) **scope with denominator** (443 of 3,633); (c) **the verdict a client
   actually needs: "published output matches LIS: YES/NO."** If that last field is YES, the alarm is by
   definition not red-accuracy (see 1).
The owner's own summary is the standard: *"the solution is probably it not fucking up in the first place"* —
the alarm system gets the same engineering bar as the data: calibrated thresholds, partitioned classes, no
independent display judgment, and a false red counts against us on our own ledger.

## Verification design — FIRE DRILLS, not sandboxes (owner correction 2026-07-17)

> Owner: *"don't build fake sandboxes to avoid resetting the timer — figure out a workaround that still allows
> us to use the real data to test scenarios."*

The scratch-workbook idea is **dead**. Replacement — the **drill row**: a new closed-vocabulary class `_drill`
written to the **real** `Incident_Log` through the **entire production write path** (real `record_incident`,
real append, real workbook, real read-back), and **structurally excluded from the clock** by `latest_incident_end`
/ `days_since` / the "incidents ever" count — exactly the mechanism `_genesis` already uses. Like a fire drill:
the real alarm rings, everyone really walks out, and nobody logs a fire. This is *stronger* verification than a
sandbox (it proves the production workbook, tab, permissions, and quota — a sandbox only proves a copy) and the
drill rows remain in the ledger as a visible, honest record that the alarm is tested. A scheduled monthly drill
(cron) turns "the write path works" from a one-time claim into a standing guarantee — if a drill fails to
appear, THAT alerts (the alarm's alarm).

## Scoping pass 2 (2026-07-17) — the other issues found, beyond verification

1. **Incident flood / dedup (the biggest one).** A 3-day outage makes the sentinel FAIL ~100 consecutive
   cycles. Naively wired, that's ~100 rows = 100 "incidents" for ONE event — the counter would lie in the
   *pessimistic* direction. Design: **open-incident semantics.** Before appending, a guard reads the tab; if an
   incident with the same `Class` + `DetectedBy` is already OPEN (empty `EndUTC`), it does NOT append. On its
   next PASS, the guard **closes** its own open incident (fills `EndUTC = now`). One event → one row with a real
   duration. Append-only in spirit is preserved (rows are never deleted; closing fills a blank cell). Race
   between two runs → worst case one duplicate row; acceptable, noted.
2. **Recovery detection comes for free** from #1: the guard that detects the failure is the guard that declares
   it over. No new machinery.
3. **Multi-guard storms:** one outage may trip sentinel + tripwire + reconciliation → 3 open incidents for one
   cause. V1 accepts this honestly (they ARE three distinct symptoms); the Health display groups by overlapping
   time window. Do not over-engineer cross-guard correlation now.
4. **Credentials — a real security-posture decision (checked, not assumed):** `accuracy_sentinel.yml`,
   `completeness_tripwire.yml`, and `legevent_reconcile.yml` run **without** `GCP_CREDENTIALS` today — the
   sentinel is deliberately creds-free (reads public gviz only). Wiring writes means granting them creds.
   Recommended: **(a)** add the existing `GCP_CREDENTIALS` to the three guard workflows (the secret already
   backs ~20 workflows; these are our own repo's code; least-privilege note in each). Alternative if the owner
   wants the sentinel to stay creds-free in spirit: **(b)** a dedicated service account shared ONLY on the
   ledger workbook. (a) is simpler; decide at build time.
5. **The denominator (our own Standard #7!):** "47 days clean" is meaningless without its context. Display is
   **"N days clean · monitoring for M days"** (M = days since genesis) — a young counter must not masquerade as
   a long record. Longest-streak can come later.
6. **Clock semantics during an open incident:** `days_since` falls back to `StartUTC` when `EndUTC` is empty, so
   the counter correctly reads ~0 *during* an incident; display shows red while any incident is OPEN.
7. **Drill rows in counts:** excluded from "incidents ever recorded" and from `latest_incident_end`, included in
   a quiet "last drill: N days ago" line (proves the alarm is tested — and a stale drill date is itself a signal).
8. **Pre-genesis history:** incidents before genesis (e.g. the July 0→66 regression) are NOT backfilled — the
   genesis row's honest meaning is "monitoring began here." The counter never claims cleanliness it didn't measure.

## Wiring plan (READY — the next engineering PR, in this order)
1. `log.py`: add `_drill` class + exclusion in `latest_incident_end`/counts; **open-incident dedup + close-on-PASS**
   helpers; manual-intervention CLI subcommand (`record accuracy "…" manual`); goldens for all three behaviors.
2. **Seed the genesis row** (one CI run auto-creates tab + epoch). **Every un-seeded day is thrown-away provable
   trust — this lands the same day as the PR.**
3. Run the first **drill** end-to-end against the real ledger; schedule the monthly drill cron.
4. Wire the three guards' FAIL branches (fail-open one-liners + the creds decision from #4 above).
5. Frontend: Health-tab line via gviz — "N days clean · monitoring for M days", red only while an incident is
   OPEN, quiet last-drill note. (Trust-header promotion stays a later owner call.)
- **Why this matters beyond the feature** ([[ideas/moat_and_competition]] #4): the counter is the *receipt* that
  turns claimed trust into counted trust — accumulated, dated evidence a late entrant cannot backfill. It has
  the same can't-vibe-code-the-past property as the observation layer.

## Parity feeders (P2/P3 — separately tracked)
- **P2 endpoint audit** — SHIPPED (#220/#221, `tools/parity/endpoint_audit.py`): catches LIS API routes we
  don't consume (the unknown-unknown). Its INFO alert is the seed of `parity_gap` detection.
- **P3 sampled DOM parity** (not built) — weekly headless render of N tracked-bill LIS pages, diff
  history-row + meeting counts vs ours; a mismatch is a `parity_gap` incident. Spec in the build-wave README.
- Once P2/P3 are stable they call `record_incident("parity_gap", …)` automatically.

See also [[audits/build_wave_2026-07/README]] (TASK 2), [[ideas/lobbyist_jtbd_ideation]] §8b,
[[architecture/verification_durability]] (the guards that would write here).
