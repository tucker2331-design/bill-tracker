---
tags: [workflow, principle, non-negotiable]
updated: 2026-05-12
status: active
---

# Zero Routine Human Maintenance (Standard #8)

**Owner mandate, 2026-05-11:**

> Any solution that requires consistent manual updating is not valid unless under unusual circumstances in which I need to be notified.

## The principle

Architecture must absorb routine variation autonomously. Human notification is reserved for **genuine anomalies that warrant interruption** — data integrity violations, upstream API contract breaks, structurally unprecedented variation, security events, or cases where the system cannot reach a confident answer.

**"Routine"** = the variation is predictable in shape, and the architecture has a deterministic way to interpret it (new code in an existing structural range, new phrasing in a known taxonomy, etc.).
**"Anomaly"** = it doesn't.

## Why this is non-negotiable

The arithmetic of routine human work at 50-state scale:

| Cadence per state | × 50 states = annual ops burden |
|---|---|
| 1 update per day | 18,250/year — full-time hire |
| 1 update per week | 2,600/year — full-time hire |
| 1 update per month | 600/year — half-time hire |
| 1 update per quarter | 200/year — still on-call attention |
| 0 routine; alerts only for true anomalies | 0/year — the only viable model |

A bootstrapped SaaS cannot hire to absorb routine variation. The architecture must.

## What this principle does NOT prescribe

This page intentionally **does not** name a specific architectural mechanism (triangulation, structural derivation, upstream consumption, ML, etc.). Multiple architectures can satisfy the principle. Which one fits a given problem is an architecture decision, not a workflow rule.

What the principle DOES require, regardless of mechanism:

- Whatever produces the answer must produce it **without routine human attention** for events that fall inside its design envelope.
- The architecture must have a clear definition of "anomaly" — events that fall outside that envelope. Anomalies are what humans get pinged for.
- The maintenance cadence under steady state must be zero, not "small."

## Decision test

When evaluating a proposed architecture, ask: *in normal operations, how often does a human have to do something other than respond to a true anomaly?*

- "Zero" → satisfies the principle.
- "Once a month per state" → fails; multiplied across 50 states = personnel cost.
- "Only when something breaks that the system can't resolve" → satisfies, if the "can't resolve" criterion is well-defined and rare.

## Related

- [[../../CLAUDE.md|CLAUDE.md]] Standard #6 (Scalability to 50 States) — Standard #8 is the operational expression
- [[../failures/assumptions_audit#54]] — the failure mode this principle prevents
