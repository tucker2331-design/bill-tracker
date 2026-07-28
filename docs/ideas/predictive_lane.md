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

## REFRAME 2026-07-27 — this is an ENTITY-STATISTICS LAYER, not a prediction widget

> Owner: *"you are thinking too small… we are talking about using the data we aggregate to then collect stats
> that can apply across the board. Maybe individual reps have their stats and committees have their stats and
> subject areas have theirs — there is so much data to derive and dig into."*

**He is right, and it reframes the whole lane.** I had been designing a per-bill prediction display. The real
thing is: **every OBJECT in our model accumulates a measured profile from the archive**, and a per-bill
prediction is just one derived VIEW over those profiles — not the product.

**Why this is the right frame, three ways:**
1. **It is Tier 1, not Tier 3.** Entity stats are COUNTING with denominators — measurement, our strongest and
   lowest-risk ground. It needs no calibration harness and carries no "the model said so" risk. The dangerous
   tier stays optional on top.
2. **It completes the OOUX finding.** [[design/object_page_patterns]] §1b established that every core object
   gets card / list / **detail** representations, and that we had never built the DETAIL for anything. This is
   what fills them: a Member page, a Committee page, a Subject page — each one an object's profile.
3. **It unifies ideas the vault already had scattered** — C1 legislator dossier, C3 committee math, C5 patron
   scouting, D2 committee mortality tables, D4 "bills like this" — which were five features. They are one
   layer applied to five objects.

**The objects and the stats each would carry (sketch, not a spec):**

| Object | Measured profile (all from the archive, all with denominators) |
|---|---|
| **Member** | vote record by subject code · party-line rate · how often they break with their chair · committee attendance · patron win-rate |
| **Committee** | report vs kill rate (overall and by subject) · how long bills sit before action · docket size and drop timing · amend-vs-pass-clean rate |
| **Subject** | pass rate by topic · which committees receive them · which patrons carry them successfully |
| **Patron** | win-rate overall, **by committee**, by subject · co-patron network · majority/minority effect |
| **Bill** | survival by stage · the composite (Tier 3, gated) |

**OWNER CORRECTION 2026-07-27 — I overclaimed the moat again.** Owner: *"you said someone can't do this
without archive but we don't have any data that's not public already since we are starting fresh."* **Right.**
Everything we hold today is public and re-derivable by anyone with the same API keys. The archive becomes
defensible *over time* (that is the "can't clone the log" argument) — **it is not defensible today**, and I
stated a future state in the present tense. Entity stats built purely on public data are **replicable**, and
the honest edge there is being *first, correct, and calibrated*, not exclusive.

**But the owner's own additions ARE the exclusive layer**, and that is the important find:
- **Contact history** — who from the org reached which member or staffer, when, and what came back.
- **Constituent mapping** — which of the org's own people/supporters live in which district.
Neither is public. Neither is scrapeable. Both exist the moment the org starts recording them, with **no
multi-year wait**. **This — not the public archive — is the proprietary data layer**, and it is why those two
belong on the Member profile as first-class fields rather than as an afterthought. It also raises the
trust-partition stakes: a member profile now mixes LIS fact, our derived stats, and org-private intel on one
page, so the three-class partition ([[design/information_display]] P20a) governs it exactly as it does the
War Room.

### ORG-RELATIVE STATS — the third proprietary layer (owner 2026-07-27)
Two more owner additions, and together with contact history + constituent mapping they are the **only**
non-public data we will hold:
- **Interaction log with a TREND, not just a count** — *"a log of the interactions so we can see most of them
  are negative or most are positive."* A relationship trajectory per member. This is knowledge a lobbyist
  normally carries in their head and the org LOSES when that person leaves.
- **ALIGNMENT: how often a member voted with US** — with the bills we support and against the ones we oppose.
  Owner's framing, and it is the strongest member stat proposed so far: more useful to the team than any
  party-line rate, because it is measured against *their* agenda. **Nobody else can compute it**, because
  nobody else knows the org's positions.

**This is why POSITION must exist, and it revisits D5.** The owner previously locked *"the star simply
signifies if it's one we're tracking… the level of involvement is a different question."* That still holds —
but alignment **cannot be computed without knowing which side we are on**, so position is now a DATA
REQUIREMENT surfacing, not UI creep.

**Owner's design (adopted as the direction):** clicking the star opens a popup — the same pattern as the
two-step untrack already shipped — carrying (a) **position** and (b) **tracking level** (watching / high
alert / involved; names TBD). The card shows ONE symbol reflecting position, never two. Nothing new is added
to the card, which answers the owner's own crowding concern.

**The design catch that must not be missed: a NEUTRAL position is mandatory.** If the popup forces
favor-or-oppose on every tracked bill, users will pick arbitrarily on bills they are merely watching, and
those fake positions **poison the alignment stat** — the exact number the feature exists to produce. So:
favor / oppose / watching-no-position, and only the first two count toward alignment. (Same family as the
absent-vs-unverified rule: a forced value is worse than an honest blank.)

**Constituent mapping deserves its own note:** "three of your members live in Newman's district" is the single
most actionable line a lobbyist can be handed — legislators answer to constituents, not to advocates. It is
also PII-adjacent, so it needs a deliberate handling decision (what is stored, who sees it, retention) before
it is built. Flagged, not designed.

### BACKTESTING — which stats actually matter (owner: "I don't want that to be a feature, I'm curious")
Owner: *"with historical data you can see the actual outcome so you can see what we would have predicted and
what actually happened… maybe we can do something once we know which stats matter more if any."*

**This is not a feature — it is how we decide which stats deserve to EXIST.** Every stat listed above is
currently a guess about what matters. A backtest converts that guess into a measurement: committee kill rate
may separate outcomes cleanly while party-line rate turns out to be noise. Two disciplines make it honest,
both borrowed from the similarity calibration:
1. **Point-in-time only.** Compute each stat using ONLY what was known on that date — no peeking at later
   data. A leak makes every stat look predictive.
2. **Accept the answer**, including "most of these predict nothing." That result is a WIN: it tells us what
   not to build and what not to show.

**Source (owner: "either Open States or legacy, doesn't matter to me"):** use BOTH, for different jobs —
**Open States** for the cross-state backtest, because uniform data is what makes states comparable; **VA's
legacy channel** for Virginia depth, since it is the authoritative record. Neither blocks the other. Note the
hard constraint: our LIS API authorization is 2025/2026 only, so multi-session history CANNOT come from it.

### PER-STATE TUNING — with the guardrail that keeps it maintainable
Owner: *"this might be something we have to tune per state and then… when we have a bulk amount of states do
a master test and see what stats stand out."* Agreed, with one rule: **stat DEFINITIONS stay identical across
states; only CALIBRATION is per-state.** Fifty states with fifty different definitions is fifty things to
maintain — precisely what Standard #8 forbids. Same recipe everywhere, locally measured numbers.

**The master test is the real payoff:** run across states it reveals which stats are UNIVERSAL versus which
are Virginia quirks. That distinction is only visible in aggregate, and it is exactly the kind of knowledge a
single-state competitor can never derive.

**Open, and the reason this is a discussion not a build:** which objects get a detail page FIRST, what belongs
on each, and how a profile stays honest at small n (a member with 3 relevant votes must not display a 33% rate
as if it meant something — the Wilson interval + thin-data guard from §Tier 1 apply to every cell here).

## What statistics each tier actually uses (owner asked: "what stats?")

### Tier 2 — deterministic math (no statistics; exact arithmetic on known facts)
Nothing here is estimated, so nothing needs a confidence interval.
- **Committee vote math:** `need = the committee's reporting threshold` (majority of its members, per the
  committee's own rule) · `have = confirmed-yes count` · `gap = need − have` · the **party × position cross-tab**
  (already exact on mockup v3) · quorum. Inputs: the probed roster ([[architecture/roster_and_votes_ingestion]])
  + the org's reads.
- **Deadline math:** `legislative days remaining` to crossover/sine die (from our calendar) vs `procedural steps
  remaining` (from the bill's stage in our state machine: substitute → full-committee report → N floor readings →
  other chamber…). "Needs 4 steps in 9 legislative days."
- **Docket position** (`#4 of 12`) — an ordinal fact from `DOCKET.CSV`.
- Correctness is *checkable*; zero calibration burden. This ships first because it can't be wrong.

### Tier 1 — measured history (honest descriptive statistics; these become Tier 3's inputs)
- **Proportions with denominators** (Standard #7): committee kill/report rate = `reported / referred`; patron pass
  rate = `passed / patroned`; per-stage survival = `advanced / reached-stage`.
- **Confidence via the Wilson score interval** — chosen deliberately over the normal approximation because it
  stays honest at **small n and extreme proportions**, and many committee × subject cells are thin. A rate is
  shown with its interval, never bare.
- **Sample-size guard:** below a threshold n, show **"thin data,"** not a false-precise percentage
  (honest-absent beats plausible-wrong — our standing doctrine).
- **Reference-class distributions** ("bills like this": same subject × committee × patron-party) — a base rate
  about a *class*, never a claim about *this* bill.

### Tier 3 — the composite (a probability, built to be TAKEN APART)
See the next section — the owner's decomposition requirement decides the model class here.

---

## The decomposition requirement — a number you can take apart (owner 2026-07-17)

> Owner: *"we definitely shouldn't only give a number… we should see what stats make up that final number,
> because one could be particularly relevant — like the committee pass rate is high so it's counter-weighting the
> fact that every member is likely to vote no, so it ends somewhere in the middle. That's important context."*

This is exactly right, and it is not a UI preference — **it dictates which kind of model we are allowed to
build.** The owner's counter-weighting example (a positive committee-history term fighting a negative whip term,
netting to the middle) is only visible if the model is **additive**: the final score is a **sum of signed
component contributions**, each individually meaningful and displayable.

**The literature backs this exactly** (grounding, per our "digest the text" doctrine):
- **Cynthia Rudin, *"Stop Explaining Black Box Machine Learning Models for High Stakes Decisions and Use
  Interpretable Models Instead"* (Nature Machine Intelligence, 2019).** For high-stakes decisions, use models
  that are **interpretable by construction** — do NOT ship a black box and bolt a post-hoc "explanation" onto it,
  because the explanation can be *unfaithful* (it may not reflect what the model actually did). **For a
  trust-moat product, an explanation that could be wrong is worse than none** — it's the slop we sell against,
  wearing a lab coat. [paper](https://www.researchgate.net/publication/333069815)
- **The Explainable Boosting Machine (EBM / GA2M)** — Lou, Caruana, Gehrke, Hooker; Microsoft
  [InterpretML](https://github.com/interpretml/interpret). A **glass-box additive model**: *"as accurate as
  gradient boosting, as interpretable as linear regression."* Each feature's contribution `f_j` is individually
  plottable — the model IS its own honest breakdown. This is the technique that makes the owner's requirement
  native instead of bolted-on.

**So the model class is chosen by the trust requirement, not by accuracy-chasing:** a **glass-box additive model
(GAM / EBM), never a black box** (gradient boosting, neural net). We give up a hypothetical accuracy sliver we
don't need, and in exchange every prediction decomposes faithfully.

**The elegant structural fact — Tiers 1 & 2 ARE the inputs to Tier 3.** The composite survival number is a
transparent sum of the very things we already ship as standalone honest facts:

```
WINNABILITY log-odds = baseline           (the TERRAIN — does NOT include your outreach; see the reframe above)
  + f_committee( this committee's historical report rate for this bill type )   ← Tier 1 base rate
  + f_patron( pass-rate in THIS committee, majority/minority, on-committee? )    ← Tier 1 base rate
  + f_topic( how the deciding members voted on this SUBJECT CODE before )        ← SOURCED (LIS subject taxonomy)
  + f_momentum( moving through stages vs stalled; late-substitute meaning )      ← procedural, NOT raw days
  + f_companion( companion alive / advancing / dead )                           ← structural fact
  + f_stage( survival hazard at the current stage )                             ← Tier 1 base rate
  [ + f_memberlean(...) ONLY if the roll-call sub-model clears calibration ]

YOUR GRIP (separate axis) = confirmed votes / needed · contacts made · amendments landed   ← moves with YOUR work
```
**Note the whip count moved OUT of winnability** — it's the "your grip" axis, per the reframe. Winnability is the
terrain; grip is your position on it; the tool's value is the *gap* between them (winnable but unworked = act).

Reading the owner's scenario straight off it: `f_committee` is **positive** (this committee passes most of what
it hears), `f_whip` is **negative** (the confirmed count is short and the unknowns lean the wrong way), and the
net lands near 0.5 — *and the user sees both terms and their signs,* not just the 0.5. **The decomposition is
not a second feature; it is the components showing through the sum.** Which is also why we build bottom-up: the
components are independently valuable and honest, so they ship first and stand alone; the composite is added last
as their faithful sum, never as a box that replaces them.

**Display law** (also lands in [[design/information_display]]): a composite prediction is **never shown as a lone
number.** It shows its **signed component contributions**, each with the **evidence behind it** (the base rate +
its n, or the exact math), so a user can see *which* factor is driving it and *what* is fighting *what*. The
composite is the DERIVED class (amber); its components decompose back into SOURCED facts, DETERMINISTIC math, and
ORG reads — so the breakdown literally re-separates the three trust classes ([[design/information_display]] §P20a).

## Owner course-correction 2026-07-17 — I narrowed too fast; these are conceptual, still open

The owner (rightly) stopped a premature narrowing into a feature spec and surfaced four flaws + a reframe. Banked
as OPEN thinking, not decided design.

### The reframe: TERRAIN vs YOUR POSITION (the whip-count-zero flaw)
**The flaw:** folding the whip count into a single "chance of passing" number means that a bill you haven't
worked yet reads `0 confirmed votes` → looks *impossible* → the tool discourages the very work it exists to
prompt. That is the classic **absence-of-evidence vs evidence-of-absence** error (same family as the brain's
sentinel-value/`Optional` confusions, [[failures/assumptions_audit]] #53): "we haven't asked anyone" is being
scored identically to "we asked and they're against it." **Wrong, and backwards for the user's job.**

**The fix — two axes, never collapsed into one:**
- **Winnability (the terrain):** how passable is this bill *on its own merits* — committee, patron, path,
  topic history, companion. **Structural; does NOT move when you do outreach.**
- **Your grip (your position):** how locked-down is it — confirmed votes, contacts made, amendments landed.
  **Moves with your work; starts empty and that's fine.**

A bill that is **high winnability + low grip** is the **best use of your time** — the opposite of "impossible."
Collapsing the two axes into one number destroys exactly the signal a lobbyist needs: *where does my effort have
leverage?* The tool's job is to point at winnable bills you haven't locked down, not to hand out fate scores.

### Time-to-crossover is NOT a monotonic negative
Raw "days left" as a downward weight is naive (owner: a bill heard late may just need *last-minute revisions* —
which could mean "one typo from a yes" **or** "needs major surgery to survive"; opposite signs, same day count).
The clock is **Tier-2 deterministic info** ("9 days, needs 4 steps — tight"), but as a **predictive weight** it's
wrong. The real signal is **procedural momentum / stall detection** (is it moving through stages at a healthy
clip or parked?), and the *meaning of a late substitute* is partly readable from the **version diff** (a typo
fix vs a gut-and-replace — text intelligence, [[ideas/lobbyist_jtbd_ideation]] §B). Do not ship "deadline" as a
raw model feature.

### "How members voted on a topic" — SOURCED, not a similarity guess (probe 2026-07-17)
The topic question was the derived-claim trap again ("similar bills" = a judgment). **Resolved by probe:** LIS
publishes a **structural subject taxonomy** — `LegislationSubject/api/GetSubjectReferencesAsync` returns 505
subjects, each with `SubjectIndexID` + `SubjectNumber` (e.g. "Abortion" = 3005). So *"how did this member vote on
bills carrying subject X"* is a **structural filter on a code**, not a text-similarity guess — clean, sourced,
Standard #3. (Still to find: the bill→subject linkage route; the taxonomy itself is confirmed. Recorded in
[[architecture/roster_and_votes_ingestion]].)

### "Patron track record" — say exactly which signal
Vague before. Concretely, the structural, meaningful patron signals: **pass-rate in THIS committee** (does this
patron have juice with this chair?), **majority-vs-minority party**, **whether the patron sits on / chairs the
deciding committee**, **seniority/leadership**. All Tier-1 base rates with denominators + Wilson intervals; guard
against thin per-patron n. NOT "vibes about the patron."

### OWNER ENDORSEMENT 2026-07-17 — the value core, named
> Owner: *"momentum, topic voting history, patron voting history are all smart good ideas that really level us
> up. **This is where the value is** — and I don't want to say more value always comes from adding more, but in
> some cases it does; this is one of them. Be conscious of that line."*

So the signal set is owner-ratified as the product's value center — deepen HERE (see the add-vs-resist line in
[[ideas/moat_and_competition]]). One strategic annotation per signal (from the moat stress-test): which are
**commodity facts anyone can recompute** (our edge = being *first + proven/calibrated*) vs **observation-layer
signals no late entrant can backfill** (our edge = *exclusive data*):

| Signal | Substrate | Defensibility |
|---|---|---|
| Topic voting history (subject-code filter) | facts (replayable) | first + proven |
| Patron × committee record | facts (replayable) | first + proven |
| Committee base rates | facts (replayable) | first + proven |
| **Momentum / stall detection** | **partly the observation layer** (stage dates are facts; docket-drop timing, schedule volatility, late-substitute behavior are OURS alone) | **exclusive — nobody can backfill watching** |
| Notice-window stats ("this committee posts agendas ~9h ahead") | **observation layer** | **exclusive** |

The exclusive rows are why the witness/change-ledger infrastructure is strategy, not plumbing.

### Display — not "a number with 3 bars" (owner: that doesn't sound great)
Concept to develop, not a decided widget. The reframe suggests the display should be **a map of where the bill
can die and where you have leverage**, not a gauge:
- Show the bill's **path as a sequence of gates** (subcommittee → committee → floor → other chamber → governor).
  Each gate carries its own structural odds *and* flags whether it's a place your effort moves the needle. Bills
  die at **specific chokepoints**; a path-of-gates mirrors how they actually die and turns a score into *where to
  push* — and it decomposes *natively* (each gate is a component) instead of stapling bars under a number.
- Overlay the **two axes** (winnability vs your grip) so a glance says "winnable, unworked → go."
- This is a *sketch direction*; other framings are open. Draw 2–3 and react, don't commit.

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
   measurement. Big commercial differentiator, low trust risk. **These are also Tier 3's input features**, so
   building them first is not just risk-ordering — it's assembling the composite's parts as shippable facts.
4. **Build the calibration harness** against the archive — *before* any model ships. This is the gate.
5. **Tier 3 (composite, glass-box)** — only if step 4 clears the bar. A **GAM/EBM additive model** whose terms
   are the Tier-1/Tier-2 quantities from steps 2–3; shown as amber/derived, **decomposed by default** (never a
   lone number), interval-not-point, unknowns-only, with the Health-tab calibration SLA and self-suppression.

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
