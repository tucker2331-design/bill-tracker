---
tags: [workflow, process, audit, design, rule]
updated: 2026-07-27
status: active
---

# The Proposal Audit — the missing gate before anything is SHOWN

> Owner, 2026-07-27: *"I'm curious why you don't ever use the brain to run your ideas through checkpoints etc.
> Is there something I could do to permanently solve this problem? Like do I need to put it as 1. on the first
> page?"*

## The honest diagnosis: it is NOT a reading failure, and prominence will not fix it

**Moving the instruction to the top of `CLAUDE.md` would not have prevented a single error in this session.**
The brain *was* read at session start. Every rule that got broken was a rule already read:

| What I got wrong | The rule that already existed | Where it lived |
|---|---|---|
| Invented "2020–2026" data windows | 2025/2026-only authorization — **with a prior remediated violation on record** | [[knowledge/lis_api_authorization]] |
| "On SB1047" — a comparison bill I picked myself | P20c — trace every claim; "similar bills" smuggles a judgement | [[design/information_display]] |
| Search type-tabs | Flamenco goal #2 — browse+search integrated, **no mode switch** | [[design/reading_notes]] |
| "Too few to judge" label | P26.1 — "k of n" is self-describing at any n | [[design/information_display]] |
| Proposed per-case "what to do" text | P25 — no text-per-signal | [[design/information_display]] |
| Ruled Subject "an attribute" | The nested-object test, quoted in full | [[design/object_page_patterns]] |

Six failures, six rules, all present in the vault and all read. **The problem is not what I know at the start
of a session; it is that nothing forces me to check what I know at the moment I produce output.**

## The structural hole

The **17-point pre-push audit gates COMMITS.** It is enforced by `tools/prepush_audit.py` and CI.

**Nothing gates PROPOSALS.** A mockup, a stat list, an architecture argument, a recommendation in chat — none
of these touch git, so none of them hit a single check. And in a design phase, *proposals are the entire
output.* The project's whole quality apparatus was pointed at the one artifact type we were not producing.

That is why the errors clustered the way they did: not code bugs, but **claims** — invented numbers,
unsourced comparisons, forgotten research, misapplied tests.

## The rule

**Before any mockup, stat list, feature proposal, or design recommendation is shown to the owner, run this
audit and SHOW IT FILLED IN.** Not "considered" — printed, with the answer next to each line. An unshown
audit did not happen.

### The 7 checks

1. **SOURCE — every number.** For each figure: where does it come from, and are we *authorized* to have it?
   Any date range, count, or rate that cannot name its source and its authorization is **deleted, not
   estimated**. (Origin: the fabricated 2020 window.)
2. **CLAIM CLASS — sourced / derived / asserted.** For each statement: which is it, and if derived, what
   exact computation produces it? "Similar", "like this", "typical" are derived-claim tripwires — if I chose
   it by judgement, a user cannot audit it. (Origin: SB1047.)
3. **PRIOR ART — has the vault already decided this?** Grep `docs/` for the feature, the object, and the
   pattern *before* designing, not after. If a page covers it, follow it or state plainly why it is being
   overridden. (Origin: Hearst mode switch, the JTBD V-series.)
4. **TEST APPLICATION — did I apply a documented test completely?** When invoking a rule with multiple
   clauses, evaluate every clause. Cherry-picking one clause to reach a conclusion is worse than not using the
   test, because it launders a guess as method. (Origin: Subject ruled an attribute on the CTA clause alone.)
5. **NO PROSE PER CASE.** Any user-facing sentence that varies by situation is a text dictionary to maintain
   and an interpretation the user did not ask for. One invariant template with substituted values, or
   nothing. (Origin: "too few to judge", "what to do next", the composition banner's editorial tail.)
6. **ARITHMETIC — do the numbers actually add up?** Compute every total, split, and complement rather than
   writing a plausible-looking figure. Mockup numbers get checked like production numbers, because an example
   that cannot exist teaches the wrong shape. (Origin: the party-math error; `38 + 6 + 9 ≠ 38`.)
7. **PERSONA — who is this for?** The primary user is [[ideas/lobbyist_jtbd_ideation]] §8a: **an advocacy org
   lobbying for itself, staffed by volunteers and inexperienced people.** A screen that assumes expert
   vocabulary or expert inference is aimed at the wrong person, however correct it is.

## ENFORCEMENT — a hook, not this page (owner correction, same day)

**The first version of this page proposed that the owner refuse any proposal lacking a filled-in audit. He
rejected it, twice over, and was right both times:**

> *"You're going to have to justify that adding another section to the brain is going to make you pay
> attention to it any more than the last."* … *"I don't want to waste tokens refusing your answers because you
> forget a checklist."*

Two distinct errors, worth separating:
1. **I answered "you don't apply the docs" by writing another doc.** That is the intervention that had already
   failed six times in the same session. A page cannot enforce itself; proposing one as the fix was the
   diagnosis and the disease in the same paragraph.
2. **I put the cost on him.** An enforcement scheme that spends the owner's review time to compensate for my
   inattention is not enforcement, it is a tax. He is the scarce resource here.

**The actual mechanism: a Claude Code hook** — `.claude/settings.json` + `tools/hooks/proposal_gate.py`.

| Event | Fires | Injects |
|---|---|---|
| `PreToolUse` matcher `Artifact` | the instant a mockup/artifact is about to publish | the full 7 checks |
| `UserPromptSubmit` | every turn | a one-line compact form |

The harness executes this, not me. It does not depend on my remembering to consult a page, it costs the owner
nothing, and it fires **at output time** — the exact moment the six failures happened — rather than at session
start, where the knowledge was already present and already insufficient.

**This is the generalisable lesson, and it is the same one the codebase already learned:** the 17-point audit
only became reliable when `tools/prepush_audit.py` + CI enforced its mechanical half (B-3). Judgment-only
points still drift; enforced points do not. **A rule with no runtime is a wish.** The content of this page is
what the hook *says*; the hook is why it gets *said*.

*Note: `.claude/settings.json` was created mid-session, so the hook may require a Claude Code restart before
it fires.*

## Why this is not just more process

Five of the seven checks are answerable in one line each, and the audit is only run at proposal boundaries —
not per message. The cost is small and bounded. The failure it prevents is the expensive kind: **the owner
spending his review time catching invented facts**, which is the one job he cannot delegate and the one this
project's standards exist to make unnecessary.

Related: [[workflow/three_phase_protocol]] (the commit-side audit), [[workflow/reasoning_doctrine]] (the
process moves), [[failures/assumptions_audit]] (the code-side ledger this mirrors).
