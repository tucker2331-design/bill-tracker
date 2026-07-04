---
tags: [audit, fable, handoff, plan]
updated: 2026-07-04
status: active
---

# Fable Audit — 2026-07-04 (hub)

The owner had time-limited access to Fable (claude-fable-5) and directed a four-part audit at the end of
the PR #188–#193 work block. **Ground rule: Fable documents, Opus executes.** Every finding below is
specified to be executable without this conversation — file paths, exact greps, validation gates, and
sequencing included. Nothing here was implemented unless explicitly marked SHIPPED.

## The four deliverables

| Page | Scope |
|------|-------|
| [[audits/fable_2026-07/brain_audit]] | How the docs/ brain performed; concrete changes so Opus operates closer to Fable |
| [[audits/fable_2026-07/codebase_longevity_audit]] | VA + NY running code, audited for multi-YEAR sustainability + accuracy drift |
| [[audits/fable_2026-07/multistate_ingestion_pa]] | PA (and the non-API-state class): researched sources, the lambda architecture, structural-JOIN routing doctrine |
| [[audits/fable_2026-07/multistate_ingestion_ca_fl]] | California + Florida researched the same way, against the 10–15 min freshness target; the emerging 4-tier state taxonomy |
| [[audits/fable_2026-07/autonomy_upgrades]] | A-1/A-2 zero-touch session + workbook automation (owner correction to C-1/C-2) |
| [[audits/fable_2026-07/50_state_scaling_architecture]] | The three 50-state blueprints: CDN inversion (keystone), Omni-Schema (formalizes the de-facto standard + capability flags), Fleet (premise-corrected; generator + rollup + graduation path) |
| [[audits/fable_2026-07/sweep_findings]] | Everything else Fable noticed (security, CI blind spots, doc drift) |

## Priority queue for Opus (do in this order)

> **2026-07-04 owner correction:** the original C-1/C-2 designs pinged the owner to act — that violates
> Standard #8 ("alerts are FYI; automation is the actuator"). They are SUPERSEDED by the zero-touch
> designs in [[audits/fable_2026-07/autonomy_upgrades]] (A-1/A-2). The queue below reflects that.

1. **A-1 Self-extending session authorization** ([[audits/fable_2026-07/autonomy_upgrades]]) — the system
   auto-follows LIS into 20271 (probe-verified, kill-switched, FYI-alerted). Dated: before Nov 2026.
2. **A-2 Automated workbook lifecycle** (same page) — finish the rollover hook `archive.py` already
   promises (snapshot→verify→reset, zero-touch) + the headroom-triggered ops-shard actuator.
2b. **CDN inversion** ([[audits/fable_2026-07/50_state_scaling_architecture]] Blueprint 1, with Blueprint
   2's schemas as its payload format) — owner-sequenced right after A-1/A-2; dual-publish soak, then flip.
3. **B-1 current_status.md restructure** (brain audit) — one hour of work; improves EVERY future session.
4. **B-3 Machine-executable pre-push audit** (brain audit) — converts prose rules into checks that fire;
   would have caught the #189 logic-version miss automatically.
5. **S-1 LIS WebAPIKey hygiene** (sweep) — small, do alongside any tools/ touch.
6. **C-8 NY canaries + first-party verification** (codebase audit) — port the proven VA patterns to NY.
7. **P-* PA ingestion** (multistate page, incl. Part 5's first-party freshness ladder) — build when the
   owner green-lights PA; the page is a full implementation spec with validation gates.
8. Everything else as convenient (each finding carries its own effort estimate).

## How to read the findings

Each finding has: **ID** · What · Evidence (verified, with the command/URL used) · Risk horizon · The fix,
in detail · Validation gate (how Opus proves the fix) · Effort. Do not skip validation gates — the gate IS
the definition of done (Standard #7: no denominator, no ship).

See also [[state/current_status]], [[workflow/three_phase_protocol]], [[failures/assumptions_audit]].
