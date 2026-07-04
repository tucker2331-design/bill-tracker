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
| [[audits/fable_2026-07/multistate_ingestion_pa]] | PA (and the non-API-state class): researched sources, the lambda architecture, decade-grade text-layer doctrine |
| [[audits/fable_2026-07/sweep_findings]] | Everything else Fable noticed (security, CI blind spots, doc drift) |

## Priority queue for Opus (do in this order)

1. **C-1 Session-rollover runbook + horizon canary** (codebase audit) — dated risk: the system HALTS in
   Jan 2027 without a 5-minute human action nobody will remember. Highest value per hour.
2. **B-1 current_status.md restructure** (brain audit) — one hour of work; improves EVERY future session.
3. **B-3 Machine-executable pre-push audit** (brain audit) — converts prose rules into checks that fire;
   would have caught the #189 logic-version miss automatically.
4. **C-2 Cell-ceiling gauge + witness offload plan** (codebase audit) — the quiet whale; measure first,
   then execute the offload design.
5. **S-1 LIS WebAPIKey hygiene** (sweep) — small, do alongside any tools/ touch.
6. **C-8 NY canaries + verification oracle** (codebase audit) — port the proven VA patterns to NY.
7. **P-* PA ingestion** (multistate page) — build when the owner green-lights the PA state; the page is a
   full implementation spec, sequenced in phases with validation gates.
8. Everything else as convenient (each finding carries its own effort estimate).

## How to read the findings

Each finding has: **ID** · What · Evidence (verified, with the command/URL used) · Risk horizon · The fix,
in detail · Validation gate (how Opus proves the fix) · Effort. Do not skip validation gates — the gate IS
the definition of done (Standard #7: no denominator, no ship).

See also [[state/current_status]], [[workflow/three_phase_protocol]], [[failures/assumptions_audit]].
