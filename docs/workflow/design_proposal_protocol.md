---
tags: [workflow, process, design, review, owner-rule]
updated: 2026-11-20
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

## Brainstorms of a design addition: justify its existence first (owner, 2026-11-19)
> *"justify its existence (as you should when i tell u to brainstorm anything for design addition)"*

Every brainstorm of a new screen, site or feature opens with the case for it before any feature list:
**the question it answers that nothing else answers**, **what answering it costs today** (sourced, e.g. the places
the owner has to look), **the case against** (when it would not be worth building), and **the line** where it
becomes worth it. First worked example: [[ideas/executive_site]] §1.

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

## New features go INTO the existing mockup, never a new screen (owner, 2026-09-30)

> *"this mock up is pretty new outside of the design language my understanding is you would work features into the
> existing design not just redesign everytime we have a new feature and subsequently forget some of the things we
> spent time arranging and re working"*

What happened: asked to show sure-vs-unsure member guesses, I published a fresh standalone page
(`Vote Confidence Mockup`) instead of editing the owner-approved War Room (HB 1515,
https://claude.ai/artifact/311hd8hv1eaQpSmntDQDVE). A new screen silently drops everything already arranged.
**Rule:** read the live War Room artifact first, change only the sections the feature touches, republish to the SAME
URL, and say exactly which lines changed. A separate page only when the owner asks for one.

## Mockups use the real page: site chrome, desktop width, one page per artifact (owner, 2026-11-19)

> *"biggest complaint with the drafts on leg page and the drafting room is the format is for a mobile app we dont
> have? … can you make them individually this time not 3 in one. and have them actually be the format id see them on
> the page. and dont make this mistake again bc its wasting credits and usage fixing."*

What happened: the drafting-room and legislator mockups were built as 860px single columns with tap-to-open
accordions (a phone pattern), and each was published as a Design canvas holding three boards. The owner could not
picture where anything would sit on the real site.

**Rule (every page mockup):**
1. **One page = one plain HTML artifact.** No canvases, no several boards in one link. A second page is a second
   artifact.
2. **The real chrome, copied from the site, not redrawn:** `tools/design_mocks/desktop/chrome.css` is copied from
   `web/src/index.css` (tokens, `.appheader`/`.topbar`/`.nav`, `.main` 1180px, `.wb-*` page header). Brand, trust
   line, sign-in and tabs as `App.tsx` renders them, with the right tab active.
3. **Desktop layout:** the site's `.cols` grid (main column + sidebar), every section visible. No accordions on
   desktop; it stacks to one column under 900px only because the site does.
4. **Check the render once at 1440px** before publishing, and mark placeholders (clocks, names, team-entered rows)
   in the page foot.
Generator: `tools/design_mocks/desktop/gen_desktop.py`.

## Names: simplified technical English, plain meaning in brackets (owner, 2026-11-20)

> *"the naming and identification seems to be a big problem i would try simplified technical english from here on
> for it until it seems off or wrong then bring it to my attention with a proposed alternative."*

What happened: section names like "Ideas in flight", "Where they live" and "Support" read as poetry. The owner could
not tell what was being counted, or why.

**Rule (every section, column and button):**
1. **Name = what the thing technically is**, in plain words: "Co-sponsorship memos", "Party-line rank",
   "Earlier bills on this law". Never a metaphor.
2. **Then, in brackets, what it shows**: "Recent memos (ideas they're circulating)", "Co-sponsors to ask (members
   who sign bills on this law far more often than their usual bills)".
3. **Every number says what it counts and out of what**: "12 of 47 (26%)", "75 of 128 House Democrats (1 = votes
   with the party most often)". A rank always says what it ranks.
4. **A list of people says why they are on it**: the rule that selected them, in the panel's foot. A raw count is
   not a pattern; compare with the person's usual rate ("times usual").
5. When a name still seems off, bring the owner the current name **and** a proposed alternative. Don't silently rename.

## The one-line test
> **Before presenting: "Which of our own written rules would catch this if the owner ran the checklist on it?"**
> If that question has an answer, the work isn't finished.

## Scope
Applies to any non-trivial design, architecture, metric, or UI proposal — anything the owner would have to form
an opinion about. It does **not** apply to mechanical execution of an already-approved plan (that's the pre-push
audit's job).

See also [[workflow/reasoning_doctrine]], [[workflow/three_phase_protocol]] (the code-side equivalent),
[[workflow/hardening_is_non_negotiable]], [[design/information_display]].
