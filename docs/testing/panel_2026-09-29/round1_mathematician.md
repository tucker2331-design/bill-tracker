# Round 1: Mathematician's position memo

Labels: **[repo]** project files · **[bounds]** my run, `panel/math/bounds.py` → `math/bounds.out` (2025 scored, 2026 never loaded into a fit) · **[research]** cited · **[derivation]** arithmetic shown.

**Bottom line.** The model is fine. Two of the numbers used to argue that it has hit a ceiling don't prove that. The twin oracle is an interval with both a floor and a ceiling. The 97.3% is a decomposition of where the error sits, not a limit on what can be predicted. The ballot also isn't the natural thing to predict: it is a derived quantity of three other objects.

## 1. What is being predicted

**The ballots are exchangeable within (bill, side).** Given the bill, same-party members of a room behave almost like copies of each other. By de Finetti's theorem, a joint distribution like that is a mixture of independent coin-flips, each with a latent rate θ<sub>b,s</sub>. Party cohesion puts θ near 0 or 1 [derivation]. The data agree:
- Members have a 2.7% error rate once party positions are known [repo].
- 84.6% of all member errors fall in (bill, side) groups where the party position was called wrong [bounds].
- There are 3,245 such groups with a mean size of 5.41 [bounds]. The bill-cluster design effect is 4.23 [bounds], so the effective sample is 17,553 / 4.23 ≈ 4,150 ballots [derivation]. That is about one unknown per group, not per ballot.

**The decision-relevant objects are therefore three, and the ballot comes from them:**
1. **S — does the bill reach a recorded vote at all.** Full-committee kills are voice votes [repo]. HB 1515 was continued on a voice vote, and 12 of 1,348 continued bills later reached a floor vote [repo, mockup].
2. **Θ — the two party positions** (about 2 bits).
3. **O — the room outcome**, which is a function of Θ plus rare defections.

The current target, P(ballot | S = 1), conditions away S and marginalises over Θ.

**The 97.3% is not a Bayes ceiling.** It conditions on the realised party majority (part of the outcome, and self-referential if it includes the member's own ballot; groups average 5.4). The genius's leave-one-out version (copy one random party-mate) gives 96.4% [repo-derived, genius memo]. That is the cleaner figure.

**The twin concordance is an interval, not a ceiling.** Treat the two twins as two independent draws of the same party-position label given the bill content x.
- Disagreement is then R<sub>NN</sub> = E[2η(1−η)], where η is the probability of the modal outcome given x. The Bayes error is R* = E[min(η, 1−η)].
- Cover–Hart gives R* ≤ R<sub>NN</sub> ≤ 2R*(1−R*) for two classes, R*(2 − MR*/(M−1)) for M ([Cover & Hart 1967](https://isl.stanford.edu/~cover/papers/transIT/0021cove.pdf)) [research].

| twin set | R<sub>NN</sub> | smallest R* | Bayes accuracy from content |
|---|---|---|---|
| joint positions (4 classes, bound R*(2 − 4R*/3)), all 734 pairs | 0.25 | (2 − √(8/3))/(8/3) = 0.138 | 75% to 86.2% |
| other party | 0.20 | (1 − √0.6)/2 = 0.113 | 80% to 88.7% |
| same venue and standing (75 pairs, SE ≈ 3.9 pts) | 0.13 | 0.070 | 87% to 93% |

[derivation]

So "bill content cannot say more than this" [repo] is wrong: content can support up to about 11 more points on joint positions. Caveats: the later chamber may see the earlier vote (dependence), and both twins must reach a roll call (selection).

**The model-vs-oracle comparison mixes units.** The twins' 80% is agreement on the other party's *position*. The model's 80.2% is accuracy on other-party *ballots*. A valid comparison is the model's joint-position accuracy on the same 734 pairs, placed against the interval above.

## 2. The plateau argument

- **The loss.** Accuracy only registers threshold crossings. Dropping the room aggregates changed 597 of 17,553 decisions [bounds]. Log loss detected the loss at z ≈ 3.7; accuracy at z ≈ 2.9 [bounds; statistician]. So "within ±0.6" is close to the detection limit (MDE ≈ 0.64 points, statistician). It rules out step changes, not zero gains.
- **One test year.** Rolling origin gives overall / hardest third of 85.39 / 66.16 (2021), 84.92 / 68.85 (2022), 84.36 / 64.86 (2024), 86.09 / 67.77 (2025) [bounds; repo for 2024]. The yes base rate moves from 0.728 to 0.760 [bounds]. Between-year spread (1.7 overall, 4.0 hard third) exceeds any within-year feature effect.
- **The hard-third target is fixed by calibration.** Mean confidence in the hardest third is 0.6727 and accuracy is 0.6777 [bounds]. The top two-thirds run at (0.8609 − 0.6777/3)/(2/3) = 95.3%. Lifting the bottom third to 80% with the top unchanged gives 0.80/3 + 0.953 × 2/3 = **90.2% overall** [derivation]. "Hard third >80%" and "roughly 90% overall" are the same demand.
- **Breaking 95.** With party-position accuracy P and defection rate d, member accuracy ≈ P(1−2d) + d. At d = 0.027, 95% needs P = (0.95 − 0.027)/0.946 = **97.6%**; at d = 0.036, 98.5%. Today's ballot-weighted P is 86.8% [bounds] [derivation].
- **What a rigorous bound needs.** A model only upper-bounds conditional entropy (log loss 0.317 nats [bounds] ≥ H(Y | features)). Fano turns a *lower* entropy bound into an error floor, and only replicated labels (twins, triplets, reintroductions) supply one. Method-of-moments on k-tuples, or the soft-label estimator of [Ishida et al. 2023](https://arxiv.org/abs/2202.00395), would estimate R* directly [research].

## 3. Structural ideas not yet tried

1. **Agenda selection as a hidden first stage.** Under negative agenda control, the majority blocks bills that would roll it, so recorded votes are selected on the expected outcome ([Cox & McCubbins](https://books.google.com/books/about/Setting_the_Agenda.html?id=fm9qVy379AQC); for states, [Shor & Kistner](https://priceschool.usc.edu/wp-content/uploads/2024/10/Shor-and-Kistner.pdf)) [research]. Two cheap tests:
   - Compute the majority-party *roll rate* at recorded first votes by room. A near-zero rate means the sample is agenda-filtered.
   - Model S as competing risks (agree with the statistician). A [Heckman](https://www.econometricsociety.org/publications/econometrica/1979/01/01/sample-selection-bias-specification-error) correction lacks an exclusion restriction here.
2. **Counting on small rooms.** Only 3.9% of first-vote rooms had a margin of ≤1 vote, and 26.5% had ≤3 [bounds]. Take a 4–1 room where the minority opposes. Flipping the outcome needs at least two majority defections: C(4,2) × 0.027² ≈ 0.44% [derivation, independence assumed]. That is the same order as the repo's 0.4% of rooms with a flippable target. In small rooms the outcome is Θ, and member-level toss-ups are almost never pivotal.
3. **Value of information, formalised.** Choose the one question (to whom, about which caucus) that maximises the mutual information I(O; answer). O carries at most 1 bit, so one well-chosen answer can resolve most of it. This makes the genius's informant idea a ranking rule.
4. **A hierarchical model with a θ<sub>b,s</sub> random effect**, for *coherence* rather than accuracy. It gives joint room probabilities and consistent updating when one member's position becomes known. Not an accuracy play: member×bill factors already failed [repo].

## 4. Ranked recommendations

1. **Re-pose the estimand as (S, Θ, O).** Score each with bill-clustered log loss; derive ballots from them.
2. **Correct the ceiling claims in `first_vote.md`.** Report the twin result as the Cover–Hart interval, recompute the comparison in joint-position units on the 734 pairs, and replace 97.3% with the leave-one-out figure. Cheap: data cached.
3. **Estimate the Bayes error from replicates** (twins plus same-patron reintroductions, as k-tuples). It is the only defensible "ceiling" statement.
4. **Retire the "hard third >80%" and "break 95" goals.** Replace them with a risk–coverage curve ([Geifman & El-Yaniv](https://arxiv.org/abs/1705.08500)) and a pooled rolling-origin log loss.
5. **Run the roll-rate diagnostic, then the competing-risks fate model.**
6. **Co-patrons: dating leak resolved** (2025: 0 of 1,663 bills gained co-patrons after filing; kill rate 19.8%, n = 425, vs 6.0%, n = 517 [moderator]). Still an association, not an effect.

## 5. Where the lobbyist and the marketing officer go wrong

**Lobbyist.**
- *"Pivotality is exact arithmetic."* Only the threshold is exact. P(member i is pivotal) = P(the others land exactly at the threshold), which requires the correlated joint of Θ. Realised margins leave a single member decisive in only 3.9% of rooms [bounds].
- *"Persuadable × pivotal."* A toss-up label measures *our* ignorance, not their movability. Persuadability is a causal quantity no observational vote model identifies ([Hall & Deardorff 2006](https://www.cambridge.org/core/journals/american-political-science-review/article/abs/lobbying-as-legislative-subsidy/AE4B5D8AB9C2487BB78C2A51BB53E03F) point the same way: lobbying subsidises allies) [research].
- *"Predicting the hard third would mean predicting our own work."* Only partly. Training data already include typical lobbying, so the model predicts the equilibrium. What it lacks is the counterfactual, and that needs a randomised contact pilot.

**Marketing officer.**
- *"95%+ on the most-confident ~67% is the 'break 95' a product can sell."* Any model reaches 95% on *some* subset. The claim only means something as a curve with coverage attached. The confident 67% is also concentrated where volunteers need the least help: the hard third is 72% other-party ballots [repo], so the confident set is mostly the rest. That is the owner's own "accurate when least useful" warning.
- *"Label calibration is the thing to publish."* Agreed on form, but the label counts are ballots at a design effect of about 4. "94 in 100" has an effective denominator near a quarter of its face value. Publish it with 2026 bill-clustered intervals.
