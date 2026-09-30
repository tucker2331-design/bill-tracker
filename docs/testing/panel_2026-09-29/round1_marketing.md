# Round 1 — Chief Marketing Officer: position memo

Labels: **[repo]** = from the project files; **[research]** = cited outside source; **[judgment]** = my market read.

## 1. What role the model plays: a proof point, not the headline

The buyer is a volunteer-staffed advocacy group [repo: BRIEFING]. They buy time and confidence ("which three offices do we call this week, and is this bill already dead?"), so the guess matters because it sorts "who to work on", not as a number [judgment]. The moat memo already puts revenue in the War Room as system of record, with calibrated predictions as a premium layer, and warns that "a single confidently-wrong number in public sets the trust moat back" [repo: `docs/ideas/moat_and_competition.md`].

So: **a trust-building proof point that becomes a liability the moment it is the headline** [judgment]. A skeptical director hears "86% accurate" and asks *of what, against what, and what about the other 14%?* A calibrated label with its track record one tap away (the v11 "How sure is this?" sheet) answers that first [repo: mockup v11].

Funders want something else. Knight and Democracy Fund fund through relationships, not open calls ([Knight, "How We Fund"](https://knightfoundation.org/how-we-fund/); [Inside Philanthropy on Democracy Fund](https://www.insidephilanthropy.com/find-a-grant/grants-d/democracy-fund)). Arnold Ventures' visible portfolio is policy research (criminal justice, health, public finance), not civic tools ([Arnold Ventures](https://www.arnoldventures.org/)) [research]. For these funders the pitch is **"leveling the field for under-resourced advocates"**, with prediction as evidence of rigour [judgment]. The local model is VPAP: free, nonpartisan, donor-funded, every donor listed ([VPAP supporters](https://www.vpap.org/about-us/supporters/)) [research], and a possible partner [judgment].

## 2. How competitors market prediction, and how our numbers compare

- **FiscalNote:** "about a 93 percent accuracy rate in predicting whether a bill will become law" ([GovTech, 2013](https://www.govtech.com/data/Online-Services-Predict-the-Legislative-Future.html)), later "over 94 percent" for Prophecy ([Above the Law, 2015](https://abovethelaw.com/2015/08/fiscalnote-prophecy-an-algorithm-for-washington-man/)). Its 2025 PolicyNote "Bill Forecasts" give a Pre-Floor Score and a Floor Score, and explain a 70% score as roughly 7 of 10 similar bills passing ([FiscalNote blog](https://fiscalnote.com/blog/bill-forecasts-policynote-feature); [PolicyNote help](https://fiscalnotepolicynote.zendesk.com/hc/en-us/articles/36263067701915-Bill-Forecast-Overview-Turning-Legislative-Predictions-into-Advocacy-Strategy)). (Both pages blocked direct fetch; wording is from search excerpts. No current accuracy figure found.) [research]
- **Skopos Labs / Wolters Kluwer:** "99 percent" on passing the first chamber and "98 percent" on enactment ([Above the Law, 2018](https://abovethelaw.com/2018/04/can-you-predict-what-congress-will-do/)) [research].
- **Plural:** the Momentum Indicator is a binary pulse icon with no accuracy claim. Its own help page says to use it "as an insight rather than a filter" ([Plural help](https://help.pluralpolicy.com/what-is-a-momentum-indicator)). None of Plural's price tiers mentions prediction: Essential $609/yr, Professional $5,000/yr ([Plural pricing](https://pluralpolicy.com/pricing/)). [research]
- **Quorum:** quote-only pricing ([Quorum pricing](https://www.quorum.us/pricing/)). I found no passage-prediction accuracy claim [research].

**Most industry accuracy claims are base-rate effects.** BillTrack50 says 85% of state bills fail ([BillTrack50](https://www.billtrack50.com/info/blog/how-to-tell-if-a-bill-will-pass)). Nay counts 2,513 enacted of nearly 70,000 congressional bills ([PLOS ONE, 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5425031/)), so "nothing passes" is right about 96% of the time on that data (my arithmetic from the cited counts). A 93–99% claim is mostly the base rate. [research + arithmetic]

Ours is more honest and on a harder target (each member's first vote): 86.1% against a 73.9% always-yes baseline [repo: `first_vote.md`], cutting the naive guess's errors from 26.1% to 13.9% (arithmetic on repo numbers). But "86 vs 94" loses in any sales deck, so **never market comparatively** [judgment].

What to communicate is the calibration: **"When we say Likely, we're right about 94 times in 100. When we say Toss-up, we tell you it's close to a coin flip."** The tiers are Likely 70% of calls / 94 in 100, Leans 20% / about 70 in 100, Toss-up 10% / 57 in 100 [repo]. FiscalNote now uses the same "7 in 10 similar bills" framing, which shows buyers understand it [research]. The Likely / Lean / Toss-up vocabulary is Cook Political Report's ([ratings](https://www.cookpolitical.com/ratings); [accuracy page](https://www.cookpolitical.com/accuracy)), so political buyers already read it fluently [research].

**One caveat blocks publishing any of these numbers yet.** The calibration table is on 2025, and 2025 was also the tuning year, so the repo itself says to "read these as slightly optimistic until the locked 2026 check runs" [repo: `first_vote.md`]. The FTC's Workado order is the warning. Workado advertised "98 percent" accuracy, testing found 53%, and it may no longer advertise accuracy without competent and reliable evidence ([FTC, Aug 2025](https://www.ftc.gov/news-events/news/press-releases/2025/08/ftc-approves-final-order-against-workado-llc-which-misrepresented-accuracy-its-artificial)). ([Operation AI Comply](https://www.ftc.gov/news-events/news/press-releases/2024/09/ftc-announces-crackdown-deceptive-ai-claims-schemes): "no AI exemption") [research]. **The locked 2026 score is the only clean, externally quotable number the project will have. Spend it deliberately.** [judgment]

## 3. What is marketable, and what is risky

**Marketable. These are measured history, which is our strongest ground** [repo: `predictive_lane.md` Tier 1]:
1. **Co-patrons.** In subcommittee, the same patron's bills without co-patrons died unanimously 20.4% of the time vs 6.9% with them. 112 of 143 non-tied patrons were worse off without; sign test p≈6×10⁻¹² [repo]. It is actionable and it is the one factor an org can change [repo: `why_member.py` note]. Say "observed pattern", not "adding a co-patron saves bills" [repo caveat].
2. **Quiet-death warnings.** The riskiest 10% of bills die unanimously 36% of the time, 4× the base rate [repo]. "Bills like this die quietly about 1 in 3 times" is honest and useful, and no competitor I found offers it at the committee stage [judgment].
3. **Denominated base rates** on the card, such as "12 of 1,348 continued bills later reached a floor vote" [repo: mockup v11]. They are hard to argue with.
4. **"What we tested and left off."** 14 measured-and-rejected ideas are on the mockup [repo]. For a skeptical director it is the most persuasive trust artifact in the product; keep it one tap deep [judgment].

**Risky:**
- **Showing real legislators' predicted votes by name outside the org.** "Our model says Del. X leans no" in a screenshot or grant deck invites pushback from members and their staff, and could cost a nonpartisan funder its standing [judgment]. Keep member guesses private and team-only, with labels only and no percentages, as the mockup already does [repo].
- **Quoting the 67.8% "hardest third".** It is an internal diagnostic. Outside, the honest version is the Toss-up line [judgment].
- **Calling the model "explainable" or "glass-box".** The predictive-lane memo committed to a GAM/EBM and cited Rudin against bolting explanations onto black boxes. The shipped model is a depth-6 GBM with perturbation-based reasons [repo: `predictive_lane.md` vs `first_vote.md`/`why_member.py`]. Claim "reasons measured on real ballots", not "interpretable model" [judgment].
- **HB 1515's missing summary-wording score** moves the Democrats' guesses 10–17 points, an artifact [repo]. Fix it before any demo [judgment].
- **Terms of service.** LIS §2 is "personal and non-commercial use only"; nothing goes to organisations before a DLAS arrangement, and **"personal" ends before "non-commercial" does**, so even a free grant-funded rollout crosses the line [repo: `lis_tos_commercial_use.md`]. Open States (CC0) carries the history, but its operator Plural is a competitor that can cut access at will and forbids implied endorsement [repo].

## 4. Modelling investment vs product and market work

About 35 approaches land within ±0.6 of 86%; the model matches the identical-bill oracle on the other party; mixed splits (19% of bills, AUC 0.58) are near-unpredictable from public data [repo]. **Another modelling point will not change a buying decision. A signed DLAS arrangement, one pilot org, and a funder relationship each would.** [judgment]

The marginal hour goes, in order, to: the DLAS conversation and grant narrative (nothing reaches a user without them); a pilot org's contact log, which the repo names as the only lever left, aimed exactly at mixed-split members, and which builds the switching-cost moat [repo]; and the locked 2026 score, run once, to earn the right to publish calibration [repo protocol].

## 5. Ranked recommendations

1. **Freeze headline modelling; run the locked 2026 score once;** publish only the calibration tiers, labelled out-of-sample. Never "86%" alone [judgment].
2. **Lead with measured history:** co-patrons, quiet-death risk, and denominated base rates. Present prediction as "how we sort your call list" [judgment].
3. **A 2-page funder methods brief** (baseline, calibration, tested-and-left-off, ceiling), built only on data outside LIS §2 (first confirm which channel the 2025 test ballots came from), carried through warm introductions [repo + research + judgment].
4. **Set a naming policy now:** member-level guesses stay team-only, labels only, never in public marketing [judgment].
5. **Fix the HB 1515 summary-score gap before any demo** [repo].
6. **Sequence the pilot:** DLAS answer → one pilot org using the contact log → measure whether its notes lift the Toss-up bucket. That becomes the second proof point [judgment].

**Where the mathematician and statistician will over-invest [judgment]:**
- Chasing "break 95" and "hardest third >80%" against a measured ceiling. A buyer cannot tell 86% from 88%, and the model already reaches 95%+ on its most-confident ~67% of ballots [repo] — that is the "break 95" a product can sell.
- LLM "political charge" scoring and GDELT pulls: maybe a point, plus spend, the leakage risk the repo flagged, and a new source dependency; nothing for the ToS gate [repo + judgment].
- Refining member-level percentages the UI never shows [repo].
