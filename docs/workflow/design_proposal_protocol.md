---
tags: [workflow, process, design, review, owner-rule]
updated: 2026-07-25
status: active
---

# Design-proposal protocol — compete, self-audit, THEN present (the anti-looping rule)

> **Owner, 2026-07-25:** *"I think you are looping. Instead of shooting at the wall, research, come up with
> competing ideas, run them through our rules and checklists etc. before I see anything. There's no reason I
> should need to call you out on obvious things."*

## The failure this fixes
The 2026-07-25 alarm-law sequence was **four rounds of present → get corrected → patch**. Every correction the
owner made was derivable from rules **already written in this vault**:

| What he had to catch | The rule that already said it |
|---|---|
| "A false alarm IS an incident" | trust surface is product; honesty doctrine ([[ideas/product_identity]]) |
| "The API-feeds-the-website claim is unsubstantiated" | [[knowledge/lis_dom_scraping]]: *"Schedule API has gaps… the website is the tiebreaker"* |
| "You're assigning text to signals" | his own earlier change-register criticism (unrecorded → repeated) |
| "Don't just route to a human" | **Standard #8** — zero routine human maintenance |
| "An UNKNOWN is still a violation" | honesty doctrine — never claim clean what we cannot verify |

**Each was a rule I owned and did not apply to my own proposal.** The owner's time is the scarcest resource in
this project; spending it on checks a script or a checklist could have done is the waste this page eliminates.

## The protocol (mandatory before ANY design reaches the owner)

**1. Research before inventing.** Prior art, and the vault first — a claim contradicted by our own pages
(above) is the most embarrassing possible failure. Grep the vault for the subject before asserting anything.

**2. Generate ≥2 genuinely competing designs.** Not one design plus strawmen. Each must be one a competent
engineer could defend. If only one option exists, the problem is under-explored — go back to (1).

**3. Self-audit EVERY candidate against the written checklists** (this is the pre-push audit's logic applied
to *design*, not code):
- the **8 Non-Negotiable Standards** (CLAUDE.md) — especially **#3** structural-not-text, **#4** self-describing
  errors, **#7** measurable-with-a-denominator, **#8** zero routine human maintenance
- the **design canon** ([[design/information_display]] P1–P25) + [[design/dashboard_and_visual_language]]
- the **reasoning doctrine** ([[workflow/reasoning_doctrine]]) — measure-first, no silent fallback, verify-the-row
- relevant **case law** ([[failures/assumptions_audit]], [[failures/gemini_review_patterns]])
- **"who does the work?"** — if the answer is "a human," it fails Standard #8 unless that human is genuinely
  irreplaceable for that decision (a judgment call, a business decision), never for triage or investigation

**4. Kill your own favourite.** State explicitly what would make the winner wrong, and what the runner-up does
better. A proposal with no acknowledged weakness has not been audited.

**5. Present the VETTED result** — the winner, the rejected alternatives *with the rule that killed each*, and
the residual risk. The owner audits **reasoning**, not spelling. He should be able to disagree with a
conclusion, never to catch a missed checklist item.

## The one-line test
> **Before presenting: "Which of our own written rules would catch this if the owner ran the checklist on it?"**
> If that question has an answer, the work isn't finished.

## Scope
Applies to any non-trivial design, architecture, metric, or UI proposal — anything the owner would have to form
an opinion about. It does **not** apply to mechanical execution of an already-approved plan (that's the pre-push
audit's job).

See also [[workflow/reasoning_doctrine]], [[workflow/three_phase_protocol]] (the code-side equivalent),
[[workflow/hardening_is_non_negotiable]], [[design/information_display]].
