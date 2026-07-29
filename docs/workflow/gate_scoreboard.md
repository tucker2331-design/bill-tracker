---
tags: [workflow, process, audit, metrics]
updated: 2026-07-27
status: active
---

# Gate scoreboard — is the self-check actually working?

> Owner, 2026-07-27: *"you know how when you tell me that a reviewer caught something — I want you to keep
> your eye on our rules in the same way to see if your new method helps at all."*

**The rule for this page: I report gate outcomes the way I report a bot reviewer's findings — including the
misses.** A scoreboard I only update when it flatters the tool is worthless. Standard #7 applies to the
process itself: if I can't measure it, I can't claim it works.

## How an entry is scored

| Outcome | Means |
|---|---|
| **CAUGHT** | the gate fired and I fixed the defect *before* the owner saw it |
| **MISSED — no check** | the gate fired, but no check covered this class. A gap in the checklist. |
| **MISSED — not covered** | the gate never ran for this surface. A gap in the *wiring*, worse than above. |
| **MISSED — ran and ignored** | the check existed, fired, and I proceeded anyway. The worst kind. |

**Owner catches count against the gate.** If he found it, the gate didn't.

## Ledger

| Date | Item | Defect | Outcome | Consequence |
|---|---|---|---|---|
| 07-27 | M1 publish | "How he handles bills **like this**" — derived-claim tripwire | **CAUGHT** (check 2) | fixed pre-publish |
| 07-27 | M1 publish | "3 contacts" but only 2 log rows | **CAUGHT** (check 6) | fixed pre-publish |
| 07-27 | M1 publish | accent rail on a card (doctrine rule 5) | **MISSED — no check** | owner caught it → added check 8 (VISUAL) |
| 07-27 | M1 publish | provenance as colour chips; red tone column | **MISSED — no check** | surfaced by the same owner catch |
| 07-27 | Access recommendation | per-seat pricing vs a volunteer user base | **MISSED — no check** | owner caught it → added check 9 (DEPENDENCY) |
| 07-27 | `migrations/0001_init.sql` | no `state` column — VA-only schema (Standard #6) | **MISSED — not covered** | owner's naming question caught it → wired the CODE gate |
| 07-27 | `worker/index.js` | schema gained `state`, queries never updated | **MISSED — not covered** | I caught it, but only while fixing the above |
| 07-27 | `worker/auth.js` | `authenticatedEmail` had to go sync→async; a missed `await` returns a Promise, which is TRUTHY, authenticating everyone | **CAUGHT** (code gate, PROPAGATION) | gate fired on the Write, I grepped call sites first and awaited it |

**Standing at 2026-07-27:** 3 caught · 3 missed with the gate running · 2 never covered.

**First catch by the new CODE gate, and it was the exact class it was added for.** Making auth verification
async changed `authenticatedEmail` from sync to async. A forgotten `await` returns a Promise — which is
**truthy** — so `if (!email) return 401` would never fire and every request would authenticate. The gate's
PROPAGATION line fired on the Write, I grepped the call sites before editing, and the one site was awaited.
That is the same failure shape as the `state`-column miss, caught this time instead of shipped.

## What the ledger says, read honestly

**The two "not covered" rows are the damning ones.** The gate ran on `Artifact` and `UserPromptSubmit` only —
so while I was writing *code*, there was no gate at all. It was enforcement aimed at the surface where the
errors used to be, not where they had moved to. **Fixed 2026-07-27:** `PreToolUse` now also matches
`Write|Edit|NotebookEdit` with a code-specific gate (propagation, Standard #6, fail-closed, measure).

**The three "no check" rows share a shape, and it is the reason check 0 exists.** Each time, an authority
governed the decision — design doctrine, a vendor's pricing page — and I did not open it. Adding a specific
check per incident is reactive and always one behind. **Check 0 is the general form:** *what governs this,
and have I read it?* Checks 1–9 are just its most common answers.

**The honest limit.** The Access catch came from judgement about the owner's *business* — that per-seat
pricing is wrong for a volunteer user base — and no checklist produces that. Some catches will always be
his. The gate's job is to stop me shipping things that contradict rules **we have already written down**,
which is a smaller claim than "prevents all errors" and is the only one I can support.

## Review cadence
Append an entry at the moment of each outcome, not in a retrospective sweep — a ledger reconstructed later
is a story, not a measurement. Re-read the standing line whenever it grows by five entries and ask whether
the misses still cluster the way they do now.
