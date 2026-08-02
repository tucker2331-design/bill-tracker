---
tags: [testing, calibration, method, plan, war-room]
updated: 2026-08-02
status: active
---

# What we want to LEARN from 20 sessions

**This replaces a first draft that was methodology dressed as a plan.** The owner's correction:
*"I'm not looking to continually test hypotheses, I'm trying to find what's informative."* Right. The
questions come first; the tests are whatever answers them.

---

## The reframe that changes the analysis

Owner: *"10 years of dem control over Finance won't tell you a lot about the next year under republican
control."*

**A committee is not a stable object.** "House Finance" under one majority and the same committee under the
other are different rooms sharing a name. Every number we have pooled across sessions has been averaging
over that — which is why a committee's rate looked stable-ish year to year (r ≈ +0.44) and useless as a
predictor. **It was measuring a thing that does not persist.**

**So the unit of analysis is not the committee. It is the committee-under-a-regime.** That single change
makes several questions below answerable that were not before, and it is the thing 20 sessions buys.

---

## The questions, ranked by how much the answer would change what a lobbyist does

### 1. Where do bills actually die, and does that move?
Committee, origin floor, second chamber, conference, Governor. **The whole funnel, per session.** Everyone
"knows" bills die in committee — nobody has the number, and nobody knows whether it shifts under divided
government or in an election year.
**Why it matters:** it tells you where to spend a week. If 70% of loss is one stage, everything else is
theatre.

### 2. How much of a committee's behaviour is the COMMITTEE, and how much is who runs it?
The owner's question, made measurable. Decompose the variation in pass rates into committee identity,
control regime, and the interaction.
**Why it matters:** if control explains most of it, the useful fact is *"who runs this room"* and committee
reputation is close to noise. If committee identity survives across flips, then committees have durable
characters and *"Finance is a graveyard"* is real institutional knowledge. **These lead to opposite advice.**

### 3. What gets a minority-patron bill through?
The single most actionable question we have. Minority patrons run 30–54% depending on chamber and year —
so **thousands of minority bills DID pass.** What separates them?
**Why it matters:** every other finding tells someone their situation. This one tells them what to do about
it.

### 4. Do bills come back — and do they win the second time?
**Only possible with 20 sessions, and never considered before.** Match bills across sessions by patron and
title similarity: how often is a failed bill reintroduced, and does reintroduction improve its odds? Does a
bill that died in committee twice ever pass?
**Why it matters:** it reframes a loss. "Bills like yours pass on the second attempt X of Y times" is a
completely different conversation from "it died."

### 5. Does bipartisan support actually work, or is it theatre?
Round 1 found co-patron *count* worthless and majority-share useful. With 20 sessions this can be asked
properly: does a minority bill with majority co-patrons beat a minority bill without, **within the same
committee and regime**?
**Why it matters:** recruiting co-patrons is one of the few things an advocate can actually change.

### 6. Which committees are genuinely different from each other?
Not "what is each rate" — **which differences are large and repeated enough to act on.** Most probably are
not, and saying so is worth as much as ranking them.
**Why it matters:** stops us shipping 25 numbers that are one number plus noise.

### 7. Does subject matter independent of politics?
Do some policy areas die at high rates under every regime? That is the difference between a hostile
committee and a hostile topic.
**Why it matters:** if it is the topic, changing venue or sponsor will not save the bill.

### 8. Does timing matter?
Filing date, docket position, where in the session a bill is heard, the crossover cliff.
**Why it matters:** it is advice you can act on before the session starts.

### 9. Does divided government change the legislature's own behaviour?
Governor's party vs each chamber. Do committees kill more when a veto is likely?
**Why it matters:** it tells you whether a session is worth fighting or waiting out.

### 10. What happens to "continued to next session" bills?
LIS code `40` — 281 bills in the 2024 House alone. Is continuation a soft kill or a real second chance?
**Why it matters:** it is currently invisible in our product and it is a large population.

---

## What 20 sessions makes newly possible

| | with 2 sessions | with 20 |
|---|---|---|
| Control regimes | 1 per chamber | **several, repeated** — Q2 becomes answerable |
| Bills across sessions | impossible | **Q4 becomes possible at all** |
| Rare events (conference, veto override) | too few | enough to count |
| Committee × regime cells | ~1 bill each | real samples |
| Governor's party | constant | varies |

---

## How each answer gets used

**Not everything worth knowing goes on the panel.** Three different destinations, and being explicit stops
us building UI for insights that belong in a briefing:

- **On the bill panel** — facts about *this* bill's situation. Q1, Q3, Q5.
- **In a strategy briefing** — how the institution behaves. Q2, Q6, Q7, Q9. The owner's colleague
  conversation.
- **Nowhere, deliberately** — anything that is real but too weak to act on. Saying so is a result.

---

## The three ways this gets it wrong, and the guards

Round 1's bugs are documented in [[testing/calibration_corrections]] and
[[testing/calibration_correction_committee_outcome]]; the guards are mechanical and stay. The **conceptual**
risks for a descriptive study are different from a predictive one:

1. **Finding a pattern, then explaining it.** With 20 sessions and 40 stats there are thousands of
   comparisons; some will look striking by chance. **Guard: any finding must hold in a majority of
   independent regimes, not merely in the pooled data.** A pattern that appears in one regime is a lead,
   not a result.
2. **Averaging over a thing that changed.** The whole reason for this rewrite. **Guard: no number is
   reported pooled across a control flip without also being reported split.**
3. **Confusing "true" with "useful".** A 3-point difference can be real and worthless.
   **Guard: every finding states the effect SIZE in natural frequencies, and anything under ~10 points is
   labelled as not actionable regardless of how solid it is.**

---

## What I need from you before starting

1. **Are these the right questions?** They are my list, not yours — you know what a lobbyist actually asks.
2. **Which three matter most?** I would start with Q1 (the funnel), Q2 (committee vs control), and Q3
   (what gets minority bills through) — Q1 because everything else is framed by it, Q2 because it decides
   whether committee stats are knowledge or noise, Q3 because it is the only one that ends in an action.
3. **Anything obviously missing** that a lobbyist would want and I have not thought of.

**Nothing runs until this list is right.** Getting the questions wrong is more expensive than any bug in
answering them.
