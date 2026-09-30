# Round 2 — the Genius: rebuttal

Labels: **[R]** repo · **[P]** another panelist's round-1 memo/audit · **[W]** research (linked) · **[C]** conjecture.

## Where I was wrong or too bold

1. **The 96.4% line was overstated.** The statistician is right [P]. The figure copies a party-mate's *actual* ballot from the same roll call. It is a ceiling for a perfectly honest, perfectly informed informant, not what a volunteer's phone call yields. "One true answer per party would beat all ~35 approaches" holds only for a *true* answer. The quantity that matters, and that nobody has measured, is the **stated-to-cast gap**: how often an office's pre-meeting answer matches its vote. Until 2027 data exists, A and B are hypotheses with a known upper bound, nothing more.
2. **My section-5 predictions mostly failed, and that is informative.**
   - The mathematician did not push a better model class. He re-posed the estimand as (S, Θ, O) and asked for a hierarchical model for *coherence*, explicitly not accuracy [P].
   - The statistician did not miss censoring. He cited selection in roll calls ([Hug 2010](https://www.cambridge.org/core/journals/british-journal-of-political-science/article/abs/selection-effects-in-roll-call-votes/0454CD5DB7FD5CDC5639116098B81A57)) and proposed the same competing-risks fate model [P].
   - The lobbyist moved the headline from the member to the bill [P].
   - Only the marketing officer half-matched: she still calls "95%+ on the most confident ~67%" the "break 95 a product can sell" [P].
   
   Five people converged independently on "freeze the ballot model, model the bill's fate, route human information." That is the strongest evidence this panel has produced.
3. **Idea D was aimed at the wrong target.** Butler & Miller found lobbying predicts *agenda progress, not committee votes* ([paper](https://www.davidryanmiller.com/files/LobbyingImpact.pdf)) [W]. So interest-position data should first be tested on **S** (does the bill get a recorded vote at all), not on mixed-split ballots. I cited the finding and then drew the wrong test from it.
4. **E was observational where it claimed causation.** The mathematician is right that persuadability is a causal quantity no vote model identifies [P]. The repo's persuadability score is a *defection trait* (r = 0.68) [R], not uplift. Only a randomized pilot measures uplift.
5. **I skipped the terms-of-service gate.** "Pre-register a 2027 pilot with an org" collides with LIS §2. "Personal" ends at the first org rollout, even an unpaid one, and nothing goes to an org before a DLAS arrangement [R]. The marketing officer's sequence of DLAS answer → pilot org → measurement [P] is the correct order. My 2027 pilots are conditional on it.

## What changed my mind

- **The mathematician's Cover–Hart interval** [P]. Twin concordance bounds how accurate a model working from content alone could be at 75–86% on joint positions. It does not cap it at 75%. I had leaned on "content is exhausted." It is not proven exhausted, so the ~$4 Haiku content read [R] earns a bounded test. Clean only in 2027 [R].
- **Hierarchical θ<sub>b,s</sub> model** [P]. I dismissed model-class work. But informant selection by mutual information I(O; answer), and pooling contact-log forecasts, both *need* a coherent joint model that updates everyone once one member's position is known. The statistician and mathematician proposed it for exactly that. I adopt it as the engine for A and B.
- **Co-patron dating leak resolved** (19.8% none vs 6.0% some, 2025) [moderator]. Lever C stands, stated as an association: strong bills may recruit co-patrons. Cosponsorship predicting *consideration* in Congress fits too ([Wilson & Young 1997](https://www.jstor.org/stable/440289)) [P/W].
- **The detection limit, MDE ≈ 0.64 points** [P]. "Within ±0.6" rules out step changes, not small gains. My claim that "records are exhausted" should read: *records are exhausted of step changes.*

## Where I still disagree

- **Marketing officer: "95%+ on the most confident ~67% is the break 95 a product can sell."** No. Any model hits 95% on some subset. That subset leaves out most of the hard third, which is 72% other-party ballots [R], so it is accurate where it is least useful. Sell calibration tiers with bill-clustered intervals from 2026, as she herself recommends first.
- **Lobbyist: "pivotality is exact arithmetic, no amber flag."** Only the threshold is exact. *Who* is pivotal depends on correlated, uncertain votes. A single member is decisive in only 3.9% of rooms [P, math]. Show "votes needed" plainly; anything implying a pivotal member takes the derived (amber) label.
- **Lobbyist: "predicting the hard third = predicting our own work."** Only partly. The training data already contain ordinary lobbying, so the model predicts the equilibrium [P, math]. What it lacks is the counterfactual. That is an argument for the randomized pilot, not for showing "unknown" and stopping.
- **Mathematician, mildly:** the Cover–Hart upper bound is a bound, not a target. Any gain it permits must still clear the pooled z ≥ 3 acceptance rule [P].

## Revised top 5, in priority order

1. **Pre-register and score 2026 once.**
   - Metrics: bill-clustered log loss, Brier, calibration tiers, and room-majority accuracy.
   - Relabel 2025 as validation.
   - Retire "break 95" and "hard third >80%" in favour of a risk–coverage curve and pooled rolling-origin log loss [P, stat/math].
2. **Re-pose the estimand as (S, Θ, O).** Start with the roll-rate diagnostic. Then build the competing-risks fate model plus the hierarchical θ<sub>b,s</sub> room model, scored at bill level. Ballot labels become derived from them.
3. **Restructure the War Room.**
   - Top: bill fate, then denominated base rates, then levers (co-patrons, companion, room, patron seat), each as template + k of n.
   - Members second, as triage, plus one "who to ask" slot chosen by I(O; answer) from the hierarchical model.
   - Still to do before cards ship: fix the HB 1515 wording-score gap [R].
4. **Informant backtest now, pilots after DLAS.**
   - Now: rerun the leave-one-out with an MI-chosen informant, labelled as a ceiling.
   - Once an org may legally use the tool: pre-register (a) contact-log entries as Brier-scored forecasts pooled with the model, measuring the stated-to-cast gap, and (b) a randomized contact pilot for uplift (Bergan design, org consent).
5. **New structural information aimed at S.**
   - Probe the House written-comment trace the lobbyist found (owner's OK on load and terms) [P].
   - Collect in-session association position lists.
   - Run the ~$4 content read as a bounded test.
   - Accept any of them only on fate-model log loss at pooled z ≥ 3.
