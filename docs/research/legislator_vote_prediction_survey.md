---
tags: [research, literature, prediction]
updated: 2026-10-25
status: active
---

# Legislator vote prediction: literature survey and ideas for the "hard third"

**Scope.** About 70 web searches and page reads (2026-10-25) on what drives individual legislative votes, how votes are predicted (classic, ML, graph, LLM), defection prediction, state committee practice (Virginia in particular), and calibration/abstention. Public pages only.

**Reading caveats.** Several sources returned only abstracts (paywall, 403, or PDFs the fetcher could not read). I extracted full text from these papers: Gerrish & Blei 2011, Kraft et al. 2016, Kornilova et al. 2018, Eidelman et al. 2018, Gerrish & Blei 2012, the PAA paper, the EP persona paper, Wu et al. 2023 (partially) and the Dobson 2025 working paper (abstract and intro only). Everything else is from abstracts or secondary summaries. Items marked **[unverified]** were not confirmed against a primary source. Idea payoffs in section E are judgment, not measurement.

**Bottom line up front.**
1. No published work I found reports 80%+ on a "hard third" defined this way. Most published numbers are on federal data, where one party-line axis explains most votes. State committee/subcommittee data, with kills at the patron's request, is essentially unstudied.
2. The strongest evidence for gains is structural, not linguistic: sponsor/committee/procedural context beat bill text in state data (Eidelman 2018), and text-model gains fade out of session (Kornilova 2018).
3. The most promising direction is to predict the *meeting-level outcome type* (unanimous kill/continue vs party-line vs bipartisan split) before the individual vote. Most of your hard-third categories are collective phenomena, not individual ones.
4. LLM results so far are mixed, and your year-to-year instability matches the literature. Use LLMs as structured feature extractors, not as final voters.

---

## A. What the evidence says drives individual votes

**Party and ideology dominate, with large noise on the rest.**
- Party-pressure literature (Snyder & Groseclose 2000; Cox & Poole 2002; McCarty, Poole & Rosenthal 2001) debates how much of party-line voting is leadership pressure versus shared preferences. All agree the party effect is large and strongest on procedural and agenda-defining votes. Snyder & Groseclose note substantial randomness on lopsided votes. Moderates then vote with the extremes, so lopsided votes carry little ideological information.
- Frances Lee's *Beyond Ideology* (2009) argues that parties fight even over low-stakes or consensual measures for power reasons (blurb-level evidence only).
- Heckman & Snyder (1997) find the attribute space of House votes has more dimensions than the Poole-Rosenthal one or two. Issue-specific attributes matter (abstract-level).
- Gerrish & Blei (2012) give an anatomy of errors. A one-dimensional ideal point fit to the 2009-10 House classifies 98% of training votes but only 83.3% for Baron Hill (D-IN, Blue Dog) and 80.0% for Ron Paul. Their issue-adjusted model adds a sparse per-issue shift per member. Held-out accuracy was 96% in the House and 93% in the Senate, and Paul's training accuracy rose 83.8% to 87.9% after the adjustment (as printed in the paper).

**Cue-taking and information.**
- Kingdon (1973) and Matthews & Stimson (1975) report that members cue off trusted colleagues on a large share of votes. Self-reports range from about 40% to 75%, and observational estimates are lower (about 10%, per a secondary summary).
- Zelizer (2019, APSR, a state legislature) used two field experiments (more than 2,000 observations). Cue-taking affects a large share of positions, occurs late in the process, and complements other information. Details of effect sizes are behind a paywall.
- Committee informational theory (Krehbiel): state committees are rarely preference outliers. A 12-lower-house study and a 42-senate study found outlying committees rare. Hall & Grofman (1990) argue floor roll calls may hide committee bias, so deference can be invisible in roll-call data.

**Constituency and electoral vulnerability.**
- A study of 46 state lower chambers plus the U.S. House (snippet only; I did not retrieve its title or authors) finds that cross-pressured legislators are more likely to back a bill early (cosponsorship) but later change positions. The effect is strongest in the majority party.
- A Congress vote-switching paper (committee to floor, UMD hosted) argues electorally vulnerable members switch less **[secondary summary]**.
- Crossover-district members have electoral incentives to cross party lines, though the evidence I found is federal.

**Interest groups and money.** Contributions affect roughly a third of roll calls in one meta-analysis (Roscoe & Jenkins 2005) while Ansolabehere et al. (2003) found no consistent causal effect. Stratmann (2005) finds an effect. A UMD study of 4,000 legislators in 22 states found business contributions affect votes on business-supported bills in non-professional legislatures. Causality is contested, but as a *predictor* the signal likely exists.

**Bipartisanship and reciprocity.**
- Dobson (2025, 401,720 bills, 43 states, 2009-2018): bipartisan cosponsorship predicts lawmaking success in the states as in Congress, with large variation across legislatures by rules, competition and majority security. The Congress analog (Harbridge-Yong, Volden & Wiseman) finds reciprocity: members who cosponsor across the aisle draw cross-party support later.
- Eidelman et al. (2018, 50 states): "bipartisan sponsorship" ranked in the top 5 features in Virginia, Missouri, Maine and Mississippi, and below 200 in SD, MN, WI, PA and others. Sponsor in minority/majority matters in some states (10% in Kentucky, 7% in Wisconsin).

**Sequential voting.** An alphabetical-order study of the U.S. Senate (1971-2013) found early voters less likely to vote with their party majority (free riding). A replication found nothing in recent Congresses, the U.S. House or three state legislatures. Treat order effects as unproven.

**Virginia-specific institutional facts (relevant to the hard third).**
- House subcommittee kills were historically unrecorded. In 2017, 390 of 571 failed House bills died on unrecorded voice votes (WHSV, from LIS data). Transparency Virginia's 2015 study counted 825 of 1,892 House bills dying in subcommittee/committee, with only 104 on a recorded vote. Senate committees record votes. The House began requiring recorded subcommittee votes in 2018 (secondary reports).
- Committee motion vocabulary includes "pass by indefinitely" and "lay on the table" (2011 HR56 text). A 2026 bill (HB 378) was reported "laid on the table" in subcommittee 10-0 (a secondary fact-check page, so a **[unverified]** claim).
- "Continued to 2027": nearly 450 bills in the 2026 session. Continuation is allowed only in even-year sessions. Per Virginia Mercury (snippet) a political scientist said continuation is sometimes used to kill a bill without offending the patron, and sometimes for fiscal reasons or compromise. This matches your "killed unanimously at the patron's request" bucket.
- VPAP (Feb 2026): for the first time since 2018, a majority of closely contested votes (opposition at least one-third) were exactly party-line. "Straight" party-line means all R against all D. Reported unity on closely contested votes (via The Center Square): House D about 81%, House R about 70%; Senate D about 92%, R about 62%. Democrats hold a 2026 trifecta, and the Senate is 21-19.
- Hypothesis to test: 2026 being more party-line would explain why a "D/R support" LLM rating helped one year and not the next. In straight party-line years the party feature already contains the rating's information. I did not find evidence for or against this.

---

## B. Prediction methods and reported accuracies

Important: accuracy is only meaningful against a baseline. Federal numbers sit on 61-85% "everyone votes yea" baselines. Most papers report all votes, not a "hard third."

| Paper / source | Setting | Method | Inputs | Reported result | Link |
|---|---|---|---|---|---|
| Gerrish & Blei 2011 (ICML) | U.S. Congress 106th-111th, held-out bills | Ideal-point topic model; L2 text regression | Bill text, past votes | 89% (topic model) and 90% (L2) vs 85% "all yea"; sequential (predict next 3 months): 87.0% / 88.1% | [pdf](https://www.cs.columbia.edu/~blei/papers/GerrishBlei2011.pdf) |
| Gerrish & Blei 2012 (NeurIPS) | House 2009-10, Senate | Issue-adjusted ideal points | Votes + bill issue codes | Held-out 96% House, 93% Senate; classic IP fails on issue-deviant members (80-83%) | [arXiv 1209.6004](https://arxiv.org/abs/1209.6004) |
| Kraft, Jain & Rush 2016 (EMNLP) | U.S. Congress 106th-111th | Multidimensional legislator vectors x bill word embeddings | Bill text, votes | 90.6% on 84.5% baseline; minority-class F1 0.645 | [paper](https://aclanthology.org/D16-1221/) |
| Kornilova, Argyle & Eidelman 2018 (ACL) | U.S. Congress 2005-2016; unanimous bills (under 1% nay, about 42%) excluded | CNN / mean word embedding + sponsor ideology metadata | Text + sponsor metadata | In-session 86.2% vs 68.3% guess-yes. Out-of-session: 83.6% vs 65.9% (2013-14), 71.9% vs 61.1% (2015-16, a split-Republican session) | [arXiv 1805.08182](https://arxiv.org/abs/1805.08182) |
| Eidelman, Kornilova & Argyle 2018 (COLING) | 50 states, bill-level floor action (not member votes) | Logistic-type models on text and context | Sponsor, party, majority/minority, committee, companion status, text | Baseline 68%; text 73%; sponsor 76%; no-text context 84.6%; combined 85.9% (AUROC 0.85); with later procedural events 94% | [arXiv 1806.05284](https://arxiv.org/abs/1806.05284) |
| Nay 2017 (PLOS ONE) | Federal bill enactment | Text + context ensemble | Text, sponsor, committee | Context beats text early; text beats context with newest data; combination best. Warns accuracy misleads for rare events (AUC used) | [arXiv 1607.02109](https://arxiv.org/abs/1607.02109) |
| Cal Poly thesis 2018 | California 2015-16 | Per-legislator classifiers | Legislators' hearing statements | Up to 83% member vote; bill vote 76% (F1 0.83, balanced). Single session, peak number | [thesis](https://digitalcommons.calpoly.edu/theses/1818) |
| Mou et al. 2021 (ACL); PAR (Feng et al. 2022); UPPAM (Mou et al. 2023) | U.S. House 117-118 (via PAA table) | Relational GNNs with Twitter, social context, expert knowledge | Votes, tweets, bill text | Vote+MTL 83-90%, PAR 85-90%, UPPAM 86.5-91.7% by split (three-class) | [ACL](https://aclanthology.org/2021.acl-long.99), [PAR](https://arxiv.org/abs/2108.03881) |
| Davoodi & Goldwasser 2024 (NAACL) | State level, LLM + nationwide legislator network | Generative LLM text processing + shared network with interest group and "courage test" context | Policy text, group influence, NPAT-style scores | A search snippet reports F1 77.8 on a roll-call task **[unverified; abstract has no number]** | [ACL](https://aclanthology.org/2024.naacl-long.411/) |
| Purdue (Waltenburg & Goldwasser) 2018 | Indiana House | RNN on revealed-preference matrices | Roll calls, planned tweets/news | No accuracy reported | [release](https://www.purdue.edu/newsroom/releases/2018/Q3/forecasting-model-could-predict-which-bills-get-passed.html) |
| Li, Gong & Jiang 2025 (AAAI), PAA | U.S. House 117-118, 432 members, chronological splits | LLM agents, role-play, leader-follower influence; no training | Member profile (party, committees, education, district income/urban share), sponsorship, 20 sampled past votes | GPT-4o-mini 91.8/91.3/92.1% acc (F1 92-93); Llama-3-70B 85.7-87.7%. Beats UPPAM at the smallest training split only | [arXiv 2412.07144](https://arxiv.org/abs/2412.07144) |
| Kreutner, Lutz & Strohmaier 2025 (EACL Findings 2026) | European Parliament 2024, 47 votes, 27,770 decisions | Zero-shot persona prompting | Attribute or Wikipedia persona + group speeches | Weighted F1 0.793 (Llama-3-70B, attributes + reasoning) vs 0.666 majority and 0.762 for fine-tuned BERT on speeches | [arXiv 2506.11798](https://arxiv.org/abs/2506.11798) |
| Yang, Han & Baldwin 2025 (ICNLSP), EuroParlVote | European Parliament | LLMs given speeches + MEP metadata | Speeches, demographics | Better on centrist groups than far-left/right; weaker for female speakers; GPT-4o best | [pdf](https://preview.aclanthology.org/anlp-naacl/2025.icnlsp-1.41.pdf) |
| Chen et al. 2026 | Dutch (2,701), Norwegian (10,584), Spanish (2,480) motions | LLM predicts parliamentary votes | Motion text | LLMs lean left/centrist and show negative bias toward right-conservative parties; no accuracy in abstract | [arXiv 2601.08785](https://arxiv.org/abs/2601.08785) |
| Wu, Nagler, Tucker & Messing 2023 | U.S. Senators | LLM pairwise comparisons + Bradley-Terry | Senator names only | Ideology scores correlate 0.967 with DW-NOMINATE; gun-control and abortion scores predict group ratings and votes better than DW-NOMINATE (not a held-out accuracy table) | [arXiv 2303.12057](https://arxiv.org/abs/2303.12057) |
| Meneghetti et al. 2023 (iScience) | Italian Parliament, party switching | Classifier on roll-call agreement trajectory | Voting records | Over 70% accuracy up to two months ahead; defectors' agreement with party majority decays | [paper](https://www.iris.sssup.it/retrieve/9607fc06-7dbc-4120-8b15-209f4e733a52/Meneghetti_iScience_predicting_party_switching.pdf) |

**Reading across the table.**
- Federal text/embedding gains are 3 to 6 points over strong baselines, and they shrink out of session. Kornilova's 2015-16 session (71.9% vs 61.1%) is the closest analog to a regime change. Virginia in 2026 is a trifecta change.
- Context beats text in state data (Eidelman). Bill-level text adds 1.3 points on top of context.
- Bayes-error warning: Snyder & Groseclose's noise on lopsided votes, plus members whose voting a single axis cannot fit (Hill, Paul at 80-83%), suggest an irreducible random component. I found no study that measures it for committee votes.

---

## C. LLM-based approaches: what they feed the model

1. **Political Actor Agent (PAA).** Profile built from party, committees, caucus groups, education, birthplace, constituency (median family income, urban/rural share, population), sponsored and cosponsored bills, and **20 sampled past votes**. Agents plan from three views (trustee, delegate, follower). **Leaders** (Speaker, party leaders, the bill's committee chair, related caucus members) vote first, and followers see leader predictions. Ablations (split 244): no profile 78.6, no planning 80.1, no influence 80.7, full 91.8. Removing personal info drops to 82.9, removing sponsorship 83.6, removing voting records 83.4. Constituency removal and anonymizing names change little (90.9 and 90.8). Using the *full* training votes in the prompt hurt at the largest split (too many records confuse the model). Caveats: federal House, where party explains most votes; the authors do not clearly say whether bill text is in the prompt.
2. **EP persona prompting.** Attribute personas (name, group, national party, age, country) beat Wikipedia summaries for large models; summaries help small ones. National party was the strongest cue and the most-cited in reasoning. Chain-of-thought helped. Without a persona, models vote FOR on nearly everything (aligned with S&D and Renew). Abstention was almost never predicted. Divergent groups (ID, ECR, GUE/NGL) changed votes most under counterfactual debate, meaning models struggle to hold non-default positions.
3. **Bias.** EuroParlVote and Chen et al. 2026 find consistent left/centrist skew, with worse accuracy on far-left, far-right and right-conservative actors. Your finding that a Republican rating helped in 2025 but not 2026, and that the Democratic rating was unstable, is consistent with a model whose prior is not stable across the minority-party/contested cases that dominate your hard third.
4. **LLM as measurement device rather than voter.** Wu et al. (pairwise comparison to scale), O'Hagan & Schein (2023, LLMs output ideology scores for legislators and texts, agreeing with established methods; abstract-level), and a Swiss MP graph-RAG ideology model (2026, abstract-only) all use LLMs to estimate a latent quantity that then feeds an ordinary model. This fits your stack better than end-to-end voting.
5. **Not found.** I found no study that (a) uses LLM-based prediction on *state committee or subcommittee* votes, (b) retrieves a legislator's own prior statements via RAG to predict votes, or (c) reports calibrated confidence for LLM vote prediction. These are open ground.

---

## D. Defection and hard-case prediction

- **Where classic models fail:** members whose issue positions deviate from the main axis (Blue Dogs, libertarian Republicans). Issue-adjusted ideal points target exactly these (Gerrish & Blei 2012).
- **Cross-pressure:** early support then switching (46-chamber study); electorally vulnerable members switch less; crossover-district incentives. Operationalization needs district partisanship vs member party, which you already partly have as census make-up.
- **Reciprocity:** members who cosponsor across the aisle draw cross-party support (federal evidence, Dobson extends to states). Directly measurable from LIS patron/co-patron history.
- **Dynamics:** declining agreement with the party majority precedes party switching (Italy), so the member's *recent* defection rate may deserve more weight than long-run averages. Your within-session learning does part of this.
- **Unanimous vs party-line:** the closest empirical work is VPAP's taxonomy (straight / near / not party-line; closely contested = at least one-third opposed) and Kornilova's exclusion of unanimous votes (42% of bills). I found **no model that predicts the unanimity class itself**. Eidelman's finding that procedural events up to the floor lift accuracy from 86% to 94% points to the same lesson: what happens to the bill before the vote is informative.
- **Committee bill disposition:** news coverage describes sponsor-requested kills (e.g., a South Dakota Senate committee killed SB 166 unanimously after its sponsor asked), California "suspense" and chair-controlled kills, and Virginia continuations. No systematic study of unanimity-at-sponsor-request exists in what I found.

---

## E. Concrete, testable ideas for the hard third (ranked by expected payoff)

Method for every idea: blocked-by-session CV (the literature says in-session CV overstates), report log-loss and AUROC beside accuracy, and score each idea on the hard-third subset and on its three sub-buckets (other-party/contested; mixed splits; patron-request kills) with a denominator for each. Add features to the existing gradient-boosted model, not as replacements.

**1. Predict the meeting-level outcome type first (highest payoff for the patron-request bucket).**
Define per bill-meeting a class from the recorded tally: unanimous-kill/continue/table, party-line, bipartisan split, unanimous-pass. Train a bill-level classifier and feed its probabilities into each member-level prediction (stacking, trained on out-of-fold outputs). If most of that bucket is unanimous, each member prediction is nearly decided once the class is known. Structural features, all from LIS, no text parsing:
- The patron is in the committee/subcommittee, or is the chair.
- The "by request" flag (an official LIS flag meaning the bill came from a constituent, agency or organization; check for how often these end in strike/continue).
- A companion or duplicate bill exists and its status (a bill "incorporated" into another, or a higher-ranking companion moving). Eidelman's feature set includes companion existence and status.
- Patron's own historical rate of motions to table/continue/strike in each committee, and the committee's "referral rate."
- Docket position, number of bills on that docket, and whether it is an even-year session (continuation is only possible then).
- Fiscal-impact or Appropriations referral, and whether the bill was reported with a substitute earlier.
- Whether the patron is a freshman, a minority-party member under a majority chair, or retiring.
Data: LIS history/docket/committee APIs (already ingested), HISTORY.CSV. Cost: low. Risk: the class itself may be hard to predict; measure first with a confusion matrix against the true tally class.

**2. Dyadic voter-patron features (reciprocity), including cross-party history.**
For each voter-patron pair: past co-patronage count, voter's prior votes for this patron's bills (you have this), whether the voter has signed on to *this patron's earlier bills across party lines*, patron's out-party cosponsor share (the Harbridge-Yong measure), shared caucus/delegation/region, same-seat-neighborhood, and shared committee tenure. Also a low-rank latent (matrix factorization of voter x patron) fit out-of-fold. Evidence: bipartisan sponsorship was a top-5 feature in Virginia (Eidelman); reciprocity (Dobson, Congress analogs). Data: LIS patron and co-patron lists (have). Cost: low. Expected effect: mostly on the other-party/contested bucket.

**3. Cross-pressure and electoral-vulnerability features.**
Member party vs district presidential margin (crossover-district flag), last-election margin, whether the member faces a 2027 Senate election or was elected in Nov 2025, whether they had a primary challenge or are retiring, and interactions with "bill is contested" and "majority/minority party." Evidence: cross-pressured members hedge (46-chamber study); vulnerable members switch less; crossover incentives. Data: Virginia Department of Elections and VPAP results, plus redistricting-based district presidential results (I did not find a public per-district 2024 presidential table in this pass, so verify; Daily Kos/Redistricting Data Hub are likely sources, unverified). Cost: medium.

**4. Chair and leader cue features (a within-meeting two-pass model).**
First predict the chair, the subcommittee chair, the patron-adjacent members and the majority-party mean. Then feed those predictions to followers. PAA's leader-follower ablation (80.7 to 91.8 on a federal LLM setup) suggests influence modelling matters, though that is LLM-specific and not a tree-model result. Kingdon/Zelizer support cue-taking. Do not assume order effects (the Senate order replication failed). Use only as an exchangeable cue. Cost: low-medium (stacking). Watch for leakage from using true votes of other members; use predicted ones.

**5. LLM as structured-feature extractor with a closed rubric (not a D/R rating).**
Replace the single "D/R support" score with a schema extracted from the (blinded) summary and, if available, text, with short forced-choice fields: topic (use LIS subject codes as ground truth where they exist), whether it creates a mandate/cost/penalty, who it affects (local government, business, labor, police, schools, agriculture, tenants/landlords, health providers), cleavage type (partisan, urban-rural, business-labor, regional, none), "technical or housekeeping," "study/resolution," and "likely to have an obvious duplicate or compromise route." Run 3-5 prompt variants and use their disagreement as an uncertainty feature. Where it matters, use pairwise comparison and scale (Wu et al.), which gave issue-specific scores that predicted group ratings and votes better than a generic ideology. Evidence for caution: bias and instability across groups (EuroParlVote, Chen 2026), and out-of-session decay of text signals (Kornilova). Evaluate as incremental log-loss over the existing model per year, so instability shows up as a measured variance rather than a surprise.

**6. Member-specific retrieval ("analogical votes").**
Per voter, retrieve their k most similar past bills (by embedding of the summary plus committee) and use the voter's votes on those as features (kNN vote history), or put 10-20 retrieved votes in an LLM prompt. PAA used 20 sampled past votes, and more records hurt, so *retrieval of relevant ones* is the testable improvement. A tree model can use the kNN average directly with no LLM. Cost: medium.

**7. Better ideal points for thin-record members.**
Freshmen after the 2023 and 2025 elections have little history. Options: (a) issue-adjusted or multi-dimensional ideal points (Gerrish & Blei 2012; Kraft vectors), (b) text-based ideal points from speeches/press releases (Vafa, Naidu & Blei 2020) or LLM pairwise scaling (Wu), (c) public scorecards and the Political Courage Test (NPAT) for the Virginia candidate surveys used by Shor-McCarty for state scaling. Expected effect: moderate, concentrated in new members and the "mixed splits" bucket. Cost: medium to high.

**8. Interest-group alignment.**
Member-level scorecards (conservation, education, business, gun, abortion, etc.) as extra ideal dimensions, and VPAP contributions by industry crossed with the bill's industry tag. Evidence on money is contested, so treat as a feature candidate rather than a causal story. Virginia lobbyist filings require subject matter but few filers list bill numbers (VPAP analysis of 2020 filings), so bill-level lobbying positions are likely too sparse. Cost: high, payoff uncertain.

**9. Hearing-level text (testimony, committee video).**
The Cal Poly thesis (single session, up to 83%) and Thomas-Pang-Lee style debate classification suggest speech carries signal. House floor video/minutes are published by the Clerk (confirmed); I did not confirm committee/subcommittee video archives or transcripts. High cost (ASR, speaker attribution), and the signal arrives only at or after the hearing, so it suits a "live update" product, not a pre-meeting forecast.

**10. Calibration and abstention as a product layer (does not raise accuracy, raises usefulness).**
- You already use an uncertainty score to define the hard third. Report a **risk-coverage curve** and per-segment reliability diagrams. Use isotonic or Venn-Abers recalibration per segment (other-party/contested, mixed, patron-request), and conformal prediction sets (a set of both labels means "uncertain"). The literature offers general selective-prediction methods (e.g., calibrated selective classification, arXiv 2208.12084) but I found **no roll-call-specific calibration work**.
- Treat LLM-verbalized confidence skeptically: reported overconfidence in an unrelated LLM conflict-monitoring study (2026), and raw confidence scores that overestimate accuracy.
- A realistic target: raise the *calibrated-confidence* share of the hard third rather than force 80%. If idea 1 resolves most of the patron-request bucket, the residual (other-party on contested bills) may be near its irreducible floor; say so in the product as "contested, split expected."

**Reality check on 80%.** A mix of (1) near-unanimous patron-request kills, (2) genuine splits, and (3) other-party members on contested bills is a population where a model's earlier uncertainty is itself informative. If bucket (1) is 40% of the hard third and idea 1 lifts it to 85-90%, while (2) and (3) stay near 60-65%, the blended hard-third accuracy would be roughly 71-75% (arithmetic, not evidence). Reaching 80% likely needs real gains in (3) from ideas 2, 3 and 6. Treat 80% as a stretch target, not a literature-supported expectation.

**Suggested order of experiments:** 10 (measurement baseline, free), 1, 2, 6, 3, 4, 5, 7, then 8-9 only if gaps remain.

---

## F. Source list

**LLM and vote prediction**
- Li, Gong, Jiang. Political Actor Agent (AAAI 2025): https://arxiv.org/abs/2412.07144 (html: https://arxiv.org/html/2412.07144v1; AAAI: https://ojs.aaai.org/index.php/AAAI/article/view/32017)
- Kreutner, Lutz, Strohmaier. Persona-driven Simulation of Voting Behavior in the European Parliament: https://arxiv.org/html/2506.11798v3
- Yang, Han, Baldwin. EuroParlVote (ICNLSP 2025): https://preview.aclanthology.org/anlp-naacl/2025.icnlsp-1.41.pdf; platform paper https://arxiv.org/html/2509.16264v3
- Chen et al. Political Bias in LLMs using Parliamentary Voting Records (2026): https://arxiv.org/abs/2601.08785
- Wu, Nagler, Tucker, Messing. LLMs Can Be Used to Estimate the Latent Positions of Politicians: https://arxiv.org/abs/2303.12057
- O'Hagan, Schein. Measurement in the Age of LLMs: https://arxiv.org/abs/2312.09203
- Yuan et al. Graph-Augmented LLMs for Swiss MP Ideology Prediction (2026): https://arxiv.org/abs/2605.04643
- Lucau, Voicu. Commercial LLMs vs Romanian legislative memoranda (2026; not vote prediction): https://arxiv.org/abs/2603.30028
- Davoodi, Goldwasser. State-Level Legislative Process (NAACL 2024): https://aclanthology.org/2024.naacl-long.411/

**Classic and ML prediction**
- Gerrish, Blei. Predicting Legislative Roll Calls from Text (ICML 2011): https://www.cs.columbia.edu/~blei/papers/GerrishBlei2011.pdf
- Gerrish, Blei. The Issue-Adjusted Ideal Point Model (2012): https://arxiv.org/abs/1209.6004
- Kraft, Jain, Rush. An Embedding Model for Predicting Roll-Call Votes (EMNLP 2016): https://aclanthology.org/D16-1221/
- Kornilova, Argyle, Eidelman. Party Matters (ACL 2018): https://arxiv.org/abs/1805.08182
- Eidelman, Kornilova, Argyle. How Predictable is Your State? (COLING 2018): https://arxiv.org/abs/1806.05284
- Nay. Predicting and Understanding Law-Making with Word Vectors and an Ensemble Model: https://arxiv.org/abs/1607.02109
- Vafa, Naidu, Blei. Text-Based Ideal Points (ACL 2020): https://arxiv.org/abs/2005.04232
- Mou et al. Align Voting Behavior with Public Statements (ACL 2021): https://aclanthology.org/2021.acl-long.99
- PAR / Legislator Representation Learning: https://arxiv.org/abs/2108.03881
- Lee, Kim, Jin. Issue-specific polarization, Korean National Assembly (2026): https://arxiv.org/abs/2603.01081
- Cal Poly thesis (California 2015-16): https://digitalcommons.calpoly.edu/theses/1818
- Purdue Indiana House project: https://www.purdue.edu/newsroom/releases/2018/Q3/forecasting-model-could-predict-which-bills-get-passed.html
- Meneghetti et al. Predicting party switching: https://www.iris.sssup.it/retrieve/9607fc06-7dbc-4120-8b15-209f4e733a52/Meneghetti_iScience_predicting_party_switching.pdf

**Political science of votes**
- Zelizer. Is Position-Taking Contagious? (APSR 2019): https://www.cambridge.org/core/journals/american-political-science-review/article/abs/is-positiontaking-contagious-evidence-of-cuetaking-from-two-field-experiments-in-a-state-legislature/1D1EF9146CF63241501C5E45B0FE6EA6
- Kingdon. Congressmen's Voting Decisions: https://press.umich.edu/Books/C/Congressmen-s-Voting-Decisions
- Snyder, Groseclose and critics: https://www.cambridge.org/core/journals/american-political-science-review/article/estimating-party-influence-on-roll-call-voting-regression-coefficients-versus-classification-success/253B3C8AA8C8CA64B76CCDD7410D8AF9
- Cox, Poole. On Measuring Partisanship: https://legacy.voteview.com/pdf/CP13.pdf
- Heckman, Snyder. Linear probability models of the demand for attributes: https://nber.org/papers/w5785
- Lee. Beyond Ideology (summary): https://www.wilsoncenter.org/publication/ideology-isnt-source-all-partisanship
- Shor, McCarty. Ideological Mapping of American Legislatures: https://leitner.yale.edu/sites/default/files/files/resources/papers/shor_mccarty.pdf
- Dobson. The Bipartisan Path Revisited (2025): https://thelawmakers.org/wp-content/uploads/2025/07/Dobson_July2025_workingpaper.pdf
- Cross-pressure in 46 state lower chambers (Northwestern IPR WP 23-07, per search): https://www.ipr.northwestern.edu/documents/working-papers/2023/wp-23-07.pdf
- Vote switching committee to floor (UMD): https://ilcss.umd.edu/files/vote-switching.pdf
- Sequential voting in the Senate and replication: https://openicpsr.org/openicpsr/project/113078/version/V1/view; https://www.aeaweb.org/doi/10.1257/aer.20150993
- Committee outliers in state houses: https://pure.psu.edu/en/publications/outlying-committees-in-the-statehouse-an-examination-of-the-preva/
- Campaign contributions effects on state legislators (UMD): https://drum.lib.umd.edu/handle/1903/2382
- Operationalizing legislative bodies (abstention in ideal points): https://arxiv.org/pdf/2211.17066

**Calibration and abstention**
- Calibrated selective classification: https://arxiv.org/abs/2208.12084
- SelectLLM (NeurIPS 2025): https://neurips.cc/virtual/2025/133203
- Confidence calibration in reasoning LLMs: https://www.alphaxiv.org/overview/2604.19444

**Virginia practice and data**
- Most Virginia House bills die on unrecorded votes (WHSV, 2017): https://www.whsv.com/content/news/Most-Virginia-House-bills-die-on-unrecorded-votes--415331463.html
- Transparency Virginia 2015 (secondary): https://rvamag.com/politics/bipartisan-watchdog-group-blasts-general-assemblys-murky-practices.html
- 2018 House recorded-votes rule (secondary): https://www.suffolknewsherald.com/?p=357389 (not retrievable by me; from search summary)
- Continued bills 2026, Virginia Mercury (read only via search summary; page returned 403): https://virginiamercury.com/2026/04/15/uptick-in-continued-va-general-assembly-legislation-reflects-varied-motivations/
- Nearly 1,000 bills died in 2026: https://www.yahoo.com/news/articles/nearly-1-000-bills-died-010200234.html
- VPAP party-line voting at 2026 crossover: https://origin.vpap.org/visuals/visual/party-line-voting-at-crossover-2026 (fetch failed; search summary only)
- Virginia GA glossary ("by request"): https://capclass.virginiageneralassembly.gov/includes/PDFs/GlossaryHigh.pdf
- HR56 (2011) motion vocabulary: https://legiscan.com/VA/text/HR56/2011
- VPAP lobbying disclosure specificity: https://vpap.org/visuals/visual/bills-lobbying-client-2019-20 (403; search summary only)
- House Clerk floor minutes/video: https://house.vga.virginia.gov/minutes?ses=261
- Open States/Plural API: https://help.pluralpolicy.com/how-to-access-the-open-states-api; LegiScan API (bulk datasets): https://learn.microsoft.com/en-us/connectors/legiscan

**Not found (searched, no relevant result):** LLM vote prediction on state committee votes; conformal or calibrated roll-call prediction; a model of unanimity-at-sponsor-request; systematic academic study of Virginia subcommittee practice.
