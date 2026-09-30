# Round 2: Mathematician's rebuttal

Labels: **[repo]** · **[bounds]** (`math/bounds.out`) · **[memo: name]** another panelist's round-1 figure · **[research]** · **[derivation]** arithmetic shown.

## What changed my mind

1. **Censoring comes first (genius, lobbyist).** When the minority-patron copy of a twin bill dies, it dies "on the clock" 69% of the time [memo: genius, citing repo]. Of 1,346 continued bills, 25 ever moved again [memo: genius]. In round 1 I listed S (whether a bill reaches a recorded vote at all) as one object among three. It is the dominant one, so the bill-fate model now ranks above my ceiling corrections.
2. **The informant backtest (genius) is the empirical proof of my exchangeability argument.** Copying one random party-mate gives 96.4% [memo: genius]. The party-majority ceiling on the same rows is 97.4%. The gap of about 1 point is the self-inclusion I flagged in round 1. **I adopt 96.4% as the replacement for 97.3%.**
3. **2025 is validation, not test (statistician).** About 35 approaches were scored on it [repo], so my rolling-origin 2025 figure is on a reused year too. I accept the relabelling.
4. **Correction to the statistician's credit line.** My design effect of 4.23 came from a bill-cluster bootstrap, not an analytic formula [bounds]. The two estimates, 4.23 and 4.6, agree.

## Where I still disagree

**Genius: 96.4% as a target.** It is a ceiling, and a same-day one: it copies the party-mate's *realised* ballot at that roll call [memo: statistician]. A volunteer's report arrives earlier and is noisier.

Suppose a report gets the caucus position right with probability r. Then member accuracy ≈ r(1 − 2d) + d, where d is the defection rate [derivation].
- To beat the model's 86.1% outright, with d = 0.027: r > (0.861 − 0.027) / 0.946 = **0.882**.
- With the leave-one-out d = 0.036 (1 − 0.964): r > (0.861 − 0.036) / 0.928 = **0.889**.

So a *replacement* rule needs volunteers who are right about 88–89% of the time on caucus positions. There is no evidence yet that they are. A *pooling* rule is different: treat the report as a likelihood ratio on the party's latent position θ, with the model as the prior. Pooling helps whenever the report is calibrated, even if it is weak. The informant belongs inside a correlated room model, scored by log loss on the bills where a report exists. It should not be a standalone number to hit.

**Lobbyist: pivotality and triage.**
- **Triage: agreed.** "Likely" is 70% of ballots and right 94 in 100 [repo], so it is a valid way to rule members out.
- **"Pivotality is exact arithmetic": still wrong** (the statistician agrees). "3 of 5 needed" is exact. *Which* member is pivotal is a probability over correlated votes.
- **Realised margins support the lobbyist's conclusion.** Only 3.9% of rooms were within one vote [bounds]. Individual pivots are rare, and the caucus position is the lever.
- **Display fix.** Show "votes needed vs current labels" as a deterministic count (P20b). Never show "Kilgore is the pivot" as a fact.

**Marketing officer: "95% on the most-confident 67%."**
- It is one point on a risk–coverage curve ([Geifman & El-Yaniv 2017](https://arxiv.org/abs/1705.08500)) [research]. Any model has *some* subset at 95%.
- The confident subset is disproportionately same-party ballots, because the hard third is 72% other-party [repo].
- Publish the curve with its coverage, from the 2026 score, or nothing.
- **The FTC point strengthens this** ([FTC Workado order](https://www.ftc.gov/news-events/news/press-releases/2025/08/ftc-approves-final-order-against-workado-llc-which-misrepresented-accuracy-its-artificial)) [research]. The metric list must be pre-registered before 2026 is opened.

**Statistician: detection limit and retiring the hard-third target.** I agree on both, and add two things.
- **Log loss is the more sensitive acceptance metric.** The same ablation reads z ≈ 3.7 on log loss vs 2.9 on accuracy [bounds].
- **Between-year spread is larger than within-year noise.** Overall accuracy ranges 84.36–86.09 and the hardest third 64.86–68.85 across 2021–2025 [bounds; repo]. A feature's gain should therefore be pooled across rolling-origin years, not judged on one year.
- **"Hard third >80%" is the same as about 90.2% overall** (0.80/3 + 0.953 × 2/3) [derivation, round 1]. Retiring it loses nothing.

**Genius: "the mathematician will propose hierarchical IRT."** Only for coherence: room-outcome probabilities and Bayesian updating from informants. Never as an accuracy play; member×bill factors failed [repo]. The statistician reached the same position independently.

## Revised top 5, in priority order

1. **Pre-register the locked 2026 score.** Metrics: bill-clustered log loss, Brier, accuracy, calibration by label, room-outcome accuracy, and the risk–coverage curve. Freeze thresholds and slices first; 2025 is relabelled validation. (Agrees with statistician #1 and marketing #1.)
2. **Build the bill-fate model (S).** Competing risks: not heard / stricken / voice-killed / recorded / reported. Score it with bill-level log loss against patron party alone. Precede it with the majority-party roll-rate diagnostic ([Cox & McCubbins](https://books.google.com/books/about/Setting_the_Agenda.html?id=fm9qVy379AQC)) to measure how agenda-filtered the recorded sample is.
3. **Build a correlated room model** (a θ random effect per party per bill). It outputs P(room outcome) and a probability of each member being pivotal, and it takes informant and contact-log reports as likelihood updates. Validate it now with the genius's chosen-vs-random informant backtest, using the r > 0.88 replacement threshold above as the benchmark. Pre-register Brier-scored pooling for 2027.
4. **Correct the ceiling statements in `first_vote.md`:**
   - the twin result as a Cover–Hart interval: 75–86.2% on joint positions, 80–88.7% on the other party
   - the model-vs-twin comparison recomputed in the same units on the 734 pairs
   - 96.4% leave-one-out in place of 97.3%
5. **Acceptance rule:** paired log loss pooled across rolling-origin years, z ≥ 3. Retire "hard third >80%" and "break 95" as goals; keep the fixed-set hard third as a diagnostic only.
