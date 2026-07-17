---
tags: [ideas, product, prediction, trust, war-room, scoping]
updated: 2026-07-17
status: active
open_loop: DISCUSSION opened, no decision. The go/no-go on INDIVIDUAL behavioral prediction (tier 3) is the owner's call; tiers 1–2 (measured history + deterministic math) are recommended to build first regardless. The calibration harness (the gate any shipped probability must pass) is specced here but not built.
---

# The predictive lane — how to do it without becoming the slop we sell against

> Owner, 2026-07-17: *"let's talk about some of the predictive stuff because I think we can do it but it's going
> to open up a new lane to build carefully and considerately."* This page is the "talk" — a discussion doc, not
> a decision. It exists because prediction sits in direct tension with our founding identity, and that tension
> must be resolved *before* code, not discovered after.

## The tension, stated plainly
Our whole identity is **trust as the moat** ([[ideas/product_identity]]): structural determinism, *"never a
probabilistic guess, never a hidden row"* on the lobbyist path (Standard #3). We sell **against** FiscalNote /
Quorum precisely on *"their LLM summaries hallucinate; ours don't guess"* ([[ideas/lobbyist_jtbd_ideation]] §G2).

A prediction is, by definition, a probabilistic guess. So the naive version of this lane **is the exact thing we
mock competitors for.** The question is not "can we compute a prediction" (yes — the vote matrix is right there,
[[architecture/roster_and_votes_ingestion]]). It's **"how does a guess live inside a product whose promise is
'we don't guess' — without breaking the promise?"**

## The resolution: not all "prediction" is the same risk. Three tiers.
The word "predictive" hides a spectrum from *honest arithmetic about the past* to *guessing an individual's
future*. They have wildly different risk, and we should treat them as different features, earned in order.

### Tier 1 — MEASURED HISTORY (not prediction at all; it's our archive's payoff)
Descriptive statistics over what already happened, always with a denominator. *"Bills referred to Senate Courts
died in committee 68% of the time (n=340, 2020–2026)."* *"This patron's bills on this subject passed 2 of 11
times."* (Ideation D2 committee mortality, D4 "bills like this", C5 patron scouting.)
- **Risk: low.** This is **measurement, not a guess** — Standard #7 ("a metric must have a denominator") *is* the
  feature. It's the commercial reason our session archive exists.
- **Honesty rule:** it's a base rate about a *reference class*, never a claim about *this* bill's fate. Say "bills
  like this," never "this bill will."
- **This is where the lane should START.** High value, defensible, and it's just counting — which we're the best
  in the market at doing correctly.

### Tier 2 — DETERMINISTIC MATH (also not prediction; it's arithmetic)
No probability at all. *"To beat crossover this bill must clear full committee + 3 floor readings in 9
legislative days"* (D3 deadline math — already on the mockup). *"Need 8 of 15; you have 5 confirmed; 6 of the 7
unknowns are Republican"* (C3 committee math — the cross-tab, already built into mockup v3, exact).
- **Risk: zero.** It's computation on known facts. No calibration needed; correctness is checkable.
- **Already largely designed.** Just needs the roster data under it.

### Tier 3 — INDIVIDUAL BEHAVIORAL PREDICTION (the real "predictive lane"; the dangerous one)
*"Our model thinks Sen. Newman will vote No (72%)."* Roll-call prediction per member (ideation C2; D1 survival
odds at the individual level). This is the one the owner means by "carefully."
- **Two distinct risks:**
  1. **It can be wrong in a way that costs the user a vote** — and a confidently-wrong number is worse than no
     number, because it *replaces* the user's own judgment.
  2. **It can make the user dumber** (flagged on the mockup): a model saying "Newman leans no" next to an empty
     "our read" invites the team to accept the guess instead of *making the call*. Our product identity says the
     tool stops at the judgment line — this is that line.
- **It is NOT off-limits — but it must be EARNED**, behind a hard gate (below).

---

## The non-negotiable gate for Tier 3 — the calibration harness
If we ever show a probability, **it must be calibrated, and we must prove it continuously.** When we say 70%, the
thing must happen ~70% of the time. This is not optional polish; it is the difference between us and the slop.
Our own standards already demand it:
- **Standard #7:** *if you can't measure it, you can't ship it.* A probability's "measurement" is its calibration
  curve against outcomes.
- **Standard #1:** static/heuristic values need **runtime validation that alerts on drift.** A model is a giant
  heuristic; it needs a live reliability check that fires when calibration decays.

Concretely, before any predicted number reaches a lobbyist:
1. **Backtest on the archive.** We have every roll call 2020–2026. Train on N sessions, test on held-out ones,
   plot a **reliability diagram** (predicted vs actual frequency). Publish the Brier score.
2. **A calibration SLA**, shown on the Health tab like everything else: *"vote predictions calibrated ±X% over
   the last K resolved votes."* When it drifts, it goes red and the feature **self-suppresses** — the same
   fail-toward-honesty posture as the accuracy sentinel.
3. **Ship the interval, never the false point.** "Likely No (lean, low confidence)" beats "72.4%." Coarse honesty
   over precise fiction — the same reason we killed "94% same text" ([[design/information_display]] §P20b).
4. **Predict only where the user does NOT already know** — never overwrite a confirmed org read with a guess. The
   model fills *unknowns*, it doesn't second-guess *facts*. This is what defuses the "makes you dumber" risk: the
   prediction is a starting hypothesis for an empty cell, visually amber (derived), erased the moment a human
   logs a real read.

## The visual model already supports this (no new invention)
The three-class partition ([[design/object_page_patterns]] §5b, [[design/information_display]] §P20a) already has
a home for a prediction: it is the **DERIVED** class — amber `.chip.provisional`, the same treatment as an
inferred meeting time and a cross-state text match. Sourced fact (their past votes) stays plain; the org's
confirmed read stays in the OURS column; the model's guess is unmistakably amber and never touches either. The
mockup already drew this column and I already argued for cutting it from v1 — **that argument stands: Tier 3
ships last, after the calibration harness proves out, not in the first build.**

---

## Recommended sequencing (a strawman for the owner to cut, not a decision)
1. **Ingest roster + votes** ([[architecture/roster_and_votes_ingestion]]) — everything below needs it.
2. **Tier 2 (deterministic math)** — committee math + deadline math. Zero risk, already designed.
3. **Tier 1 (measured history)** — mortality tables, base rates, patron scouting. Our archive's payoff; pure
   measurement. Big commercial differentiator, low trust risk.
4. **Build the calibration harness** against the archive — *before* any model ships. This is the gate.
5. **Tier 3 (individual prediction)** — only if step 4 clears the bar, shipped as amber/derived, interval-not-
   point, unknowns-only, with the Health-tab calibration SLA and self-suppression.

The owner's "go for the max while it's shut down" makes this the right time to build the *substrate* (1) and the
*honest tiers* (2–3) and the *harness* (4) fully — and to let the calibration numbers, not a launch deadline,
decide whether Tier 3 is good enough to exist.

## The open question for the owner
Tiers 1–2 are recommended regardless — they're measurement and arithmetic, dead-on-brand. **The real decision is
Tier 3:** do we build individual behavioral prediction at all, given it's the one feature that could dent the
trust moat if it's ever wrong in public? My recommendation is *build the harness first and let it vote* — if we
can prove calibration on the archive, a well-labeled derived prediction is defensible and valuable; if we can't,
we don't ship it, and that refusal is itself on-brand. But that's the owner's call to make, not mine to bank.

See also [[architecture/roster_and_votes_ingestion]], [[ideas/product_identity]], [[ideas/lobbyist_jtbd_ideation]]
§C/§D, [[design/information_display]] §P20a–c, [[ideas/war_room_scoping]].
