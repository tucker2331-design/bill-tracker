---
tags: [workflow, principle, non-negotiable]
updated: 2026-05-11
status: active
---

# Zero Routine Human Maintenance (Standard #8)

**Owner mandate, 2026-05-11:**

> Relying on continuous human intervention to patch dictionary files across 50 states fundamentally destroys the automated SaaS architecture we are building. I do not have, nor will I hire, a team of data-entry clerks to monitor DLQ alerts. We need an architecture that achieves 99%+ precision AND drives the human-triage DLQ down to near zero.

> Any solution that requires consistent manual updating is not valid unless under unusual circumstances in which I need to be notified.

## The principle

**Any architecture that requires routine human intervention as part of normal operations is invalid.** Human notification is reserved for **genuine anomalies that warrant interruption**:

- Data integrity violations (structural fields contradict each other)
- Upstream API contract breaks (LIS changes schema)
- Security events (auth tokens revoked, anomalous access)
- Cases that even multi-source automated reasoning cannot resolve with confidence

NOT routine maintenance like "new EventCode appeared, please map it." That is a routine class of event and must auto-resolve through the architecture, not through a human's attention.

## Why this is non-negotiable

This is the operational expression of [[../../CLAUDE.md|CLAUDE.md]] Standard #6 (Scalability to 50 States). Standard #6 says state-specific logic must be **isolated**; Standard #8 says state-specific logic must also be **self-extending**.

The arithmetic that forces this:

| Cadence per state | × 50 states = annual ops burden |
|---|---|
| 1 mapping line per day | 18,250 lines/year — full-time data-entry hire |
| 1 mapping line per week | 2,600/year — full-time data-entry hire |
| 1 mapping line per month | 600/year — half-time hire |
| 1 mapping line per quarter | 200/year — episodic but still requires on-call attention |
| 0 routine; alerts for true anomalies | 0/year — the only viable model for bootstrapped SaaS |

A bootstrapped SaaS cannot hire to absorb routine variation. The architecture must.

## The decision rule

**"Routine"** means: the variation is predictable in shape (e.g., LIS adds a new EventCode in an existing numeric range). The architecture knows how to interpret it deterministically.

**"Anomaly"** means: the variation is structurally unprecedented (e.g., LIS introduces an entirely new EventCode prefix; the structural fields produce contradictions; multiple independent classification sources disagree). Only THEN does a human need to look.

Test: *Can this variation be resolved by reading the existing spec (LIS API contract, OpenStates taxonomy, structural fields) alone?* If yes, the architecture handles it. If no, it's an anomaly worth interrupting a human for.

## The architectural pattern that satisfies this principle

**Multi-source triangulation with deterministic agreement = automated; disagreement = alert.**

For each classification decision, compute the category from N independent sources. Ship the result only when sources agree. Disagreement is the anomaly signal.

```
INPUT: a row to classify (HISTORY.CSV row or LegEvent event)
         │
         ├──→ Path A: structural rule on (EventCode prefix, range, Status)
         │              [deterministic; one-time per state]
         │
         ├──→ Path B: OpenStates' published classification (consumed via their API)
         │              [community-maintained; 50-state coverage; no per-state work on our side]
         │
         └──→ Path C: regex match on Description (battle-tested OpenStates rule set)
                        [text-based; covers narrative-only events]

         ▼
     Aggregator
         │
         ├── 3-of-3 agreement → SHIP with category, log triangulated provenance
         ├── 2-of-3 agreement → SHIP with category, log discrepancy (telemetry only)
         └── < 2 agreement    → ALERT (genuine anomaly; the architecture cannot resolve)
```

**Properties:**

- **Determinism on agreement.** Three independent paths converging is not probability — it's structural redundancy. Same shape as triple modular redundancy in spacecraft, multi-signature crypto wallets, distributed consensus (Paxos/Raft).
- **Auto-healing on routine variation.** If LIS adds a new EventCode `H4140` and our Path A's structural rule classifies it as `reading-1` based on the `H41xx` range — and OpenStates' Path B says the same — and the Description regex Path C says the same — the system auto-classifies it. No human involvement.
- **Alert quality is high by construction.** The only events that page a human are events that THREE independent classification systems disagreed on. That's a real anomaly worth a human's judgment.

## What this principle is NOT

- **Not perfectionism.** It does not mean every system must be 100% correct on day one. It means the *maintenance model* must not require ongoing human attention for routine cases.
- **Not anti-LLM.** It does not forbid using ML/LLMs. It forbids using them in ways that create ongoing manual burden (e.g., LLM-as-classifier with "human reviews uncertain predictions" creates a queue that scales with traffic — that violates the principle even if the LLM is doing most of the work).
- **Not anti-mapping-file.** A one-time, per-state code-extraction file (like a parser for LIS's EventCode namespace, written once based on observation) is fine. The principle forbids the file from growing over time as a steady-state operation.

## Triangulation against LLM cost concerns

The triangulation pattern above does NOT require an LLM. The three paths are:
1. Deterministic structural function on LIS API fields
2. OpenStates' published API (existing service, no subscription cost)
3. Regex pattern matching on text (no runtime dependency)

If a future architecture wants to add an LLM as a fourth path (e.g., to resolve some 2-of-3 disagreements deterministically), it can be added without breaking the principle — but it must be clearly OPTIONAL and the 3-path consensus must work without it.

## What changed today (2026-05-11)

The PR-C7.1a math audit measured a derived classifier in isolation: 17.94% PASS rate, 85.81% precision on passed. The 82% DLQ rate was the visible failure of the "rely on one classifier" model.

The strategic discussion that followed surfaced the false dichotomy: low-precision-and-lying vs high-DLQ-and-human-labor. Both are unacceptable. The triangulation pattern resolves it.

This page IS the resolution, codified. See:
- [[../failures/assumptions_audit#54]] for the bug class (minimizing manual-labor cost is the failure mode of Standard #6)
- [[../architecture/calendar_pipeline]] when the triangulated architecture lands in code (PR-C7.1b)
- [[../knowledge/lis_api_reference]] for the LIS structural fields that Path A consumes

## Process upgrade

Add to [[three_phase_protocol]]'s Phase 2 (pre-push audit) as a meta-check before any new classification logic:

> **Standard #8 check:** Does this new classification path require routine human intervention to maintain (new mappings per state per quarter, DLQ reviews, etc.)? If yes, the design is invalid unless the human intervention is reserved for genuinely anomalous events that the multi-source triangulation cannot resolve.
