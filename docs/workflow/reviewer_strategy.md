---
tags: [workflow, review, quality, strategy, measurement]
updated: 2026-07-27
status: active
open_loop: Semgrep + mypy SHIPPED 2026-07-27 (mypy caught a real gspread bug on its first run). PR-Agent DROPPED (needs a paid model key). Remaining: connect Gemini as the backup LLM reviewer (owner is in the console), and run the mutation-testing baseline that would give a real catch-rate number instead of a guess.
---

# Reviewer strategy — how to actually raise the catch rate (not just add more bots)

> **Owner, 2026-07-27:** *"How do they compare to each other? Is there a standard test for testing code
> reviewers' ability? What gaps do we have… can we balance out? Even Fable will only catch like 50% of the
> bugs, so this reviewer setup is important to see how far we can boost that catch rate toward 100%."*

## 1. The uncomfortable finding: there is no shared yardstick, and vendors grade themselves
There is no SWE-bench equivalent for code *review*. As one analysis puts it bluntly, every vendor benchmarks
itself and wins — they publish F1/recall figures measured on different data with different bug definitions, so
the numbers are not comparable to each other. Two genuinely independent efforts now exist:
- **[CodeReviewBench](https://www.codereviewbench.com/)** — synthetic-but-realistic regressions across 5
  languages, with exact bug locations as ground truth and auditable per-model scores.
- **[Code Review Bench (Martian)](https://codereview.withmartian.com/)** — 200k+ real PRs, scored on which
  review comments developers actually *acted on*; refreshed continuously so it can't go stale.

**Neither is decisive for us**, because both measure generic code. Our bugs are project-shaped — silent
fallbacks, threshold calibration, denominators, gates that go permanently true. **We already own a better
benchmark than either: our own 56-lesson case-law record.**

## 2. What OUR history actually shows (measured, not vibes)
From [[failures/gemini_review_patterns]] — 56 documented findings, attributed by bot:

| Reviewer | Findings recorded | Status today |
|---|---|---|
| Gemini | 14 | **dead** (consumer version sunset) |
| CodeRabbit | 8 | **alive, rate-limited** (~4 PR reviews/hr free) — the only one left |
| Qodo | 5 | **dead free** (permanent tier withdrawn → 14-day trial) |
| Codex | — | **out of quota** |

Category distribution of what the bots caught (keyword frequency across the 56):

| Class | Hits | Class | Hits |
|---|---|---|---|
| silent failure / swallowed error | 24 | dedup / key collision | 9 |
| import / scope / unbound | 18+5 | fallback logic | 8 |
| denominator / rate correctness | 15 | regex over-permissiveness | 7 |
| gate / conditional logic | 14 | None / Optional handling | 7 |
| threshold calibration | 12 | race / concurrency | **3** |

**The gaps are as informative as the strengths.** Across 56 findings: **security ≈ 0**, **performance = 1**
(the O(steps×rows) replay loop), **concurrency = 3**, **dependency/supply-chain = 0**. Our reviewers have been
strong exactly where our doctrine is strong (honesty, denominators, silent failure) and near-blind where we
have no coverage at all.

## 3. CORRECTED 2026-07-27 — the owner was right, and our own history proves it

I claimed LLM reviewers are correlated enough that stacking them has strongly diminishing returns. **The owner
pushed back — "historically different reviewers actually caught different bugs, sometimes we had 4+ running
all finding different things, check the brain and verify" — and the record backs him, not me.**

Measured in [[failures/gemini_review_patterns]]:

| PR | What happened |
|---|---|
| **#214** | **CodeRabbit found #55, Gemini found #56 — two DIFFERENT bugs on the same PR** |
| **#211** | CodeRabbit found #53 AND #54 (two distinct bugs the others didn't) |
| **#209** | Gemini found #51 (CRITICAL) and #52 (HIGH) |
| **#177** | Qodo alone found the regex-namespace bug |
| **#178** | CodeRabbit + Qodo overlapped on one — **and Qodo separately found #49/#50** |
| **#161** | Gemini + Qodo overlapped on the ET/UTC bug |

**Overlap exists (2 documented cases) but complementarity is MORE common.** So the correlation is *partial*,
not near-total: each added reviewer really did contribute unique catches. **More reviewers is genuinely
better** — my "diminishing returns" framing overstated a real effect into a wrong conclusion.

**What survives, restated honestly:** the returns diminish *somewhat* (two bots did duplicate each other
twice), and the deterministic layers below are **additive on top rather than competing** — mypy caught a
gspread signature bug that two LLM reviews had walked past, which no third LLM would likely have found either.
So the plan is BOTH: keep every free LLM reviewer we can get, AND add the deterministic floor. Not either/or.

**Practical consequence:** CodeRabbit's rate limit is a real single-point-of-failure. A backup LLM reviewer is
not redundancy for its own sake — it is coverage, and it is what keeps a rate-limited hour from shipping an
unreviewed PR (which happened on #232).

## 3b. Why the deterministic layers ALSO rank high (both, not either/or)

LLM reviewers are *partially* correlated (§3) — they duplicate each other sometimes and complement each other
more often, so keep every free one. But the deterministic layers cover ground **no** LLM reliably reaches, and
they never have an off day. The answer to *"how do we get from ~50% toward 100%?"* is **more reviewers AND
more METHODS**:

| Layer | Method | Catches what LLMs miss | Ours today |
|---|---|---|---|
| **Static analysis** | dataflow/AST, deterministic | undefined names, unreachable code, type errors | ✅ pyflakes (audit #105) — **but no type checker on Python** |
| **Golden/property tests** | executed behaviour | logic regressions, honesty defaults | ✅ strong (86+ goldens added this wave) |
| **Structural invariants** | project-specific rules | OUR bug classes — version bumps, silent-fallback literals, stranded work, cadence drift | ✅ `prepush_audit.py`, **unique to us and our best asset** |
| **Runtime verification** | live probes, real data | wrong-question bugs a test can't see (the `include=` 200) | ✅ probes, live measurements |
| **Security scanning** | rule-based taint/secrets | injection, secret leakage, unsafe deserialization | ❌ **NOTHING** |
| **LLM review** | semantic/intent | design smells, missing edge cases, "this reads wrong" | 🟡 CodeRabbit only, rate-limited |
| **Human** | judgment | is this the right thing to build | ✅ owner |

**→ The two empty rows are the highest-value NEW capability** — a security scanner and a Python type checker —
because they fail *differently* from everything we run. That is not an argument against adding LLM reviewers
(§3 settles that: add every free one), it is an argument for not stopping there.

## 3c. VERIFIED AUDIT — every candidate checked against its OWN pricing page (2026-07-27)

The owner called out a real pattern: I had been quoting comparison blogs and vendor round-ups, which are
marketing, and got three things wrong in a row (Gitar's "free", Git AutoReview being a bot, Gemini being
live). **Rule now: a reviewer is not listed until its own pricing/listing page has been read directly.**

### ✅ FREE for a PRIVATE repo — verified
| Tool | Method | Verified how | Limits |
|---|---|---|---|
| **CodeRabbit** | LLM | we use it daily | free tier covers private repos; ~4 PR reviews/hr, 200 files/hr |
| **Gemini Code Assist** | LLM | Google docs: *"no charges … during Preview"* | free in preview; needs a Cloud project + Developer Connect |
| **Semgrep** | rules/AST | free ≤10 contributors on private repos | security + our own house rules |
| **mypy** | type checker | open source, runs in our CI | scoped to new modules, widening |
| **pyflakes** | static analysis | already in the pre-push audit | undefined names (audit #105) |
| **`prepush_audit.py`** | project invariants | ours | the checks no vendor has |

**OWNER RULE 2026-07-27: trials and BYOK are NOT reviewers.** *"Limit that list to no free trials or bring
your own keys — we both know those aren't even considered."* Correct: a 14-day trial is a countdown to an
outage, and BYOK just relocates the bill. Neither is a standing reviewer, so neither belongs on a bench we
are relying on. They are listed below only so nobody re-proposes them.

### ❌ NOT free for a private repo — each verified, with the disqualifier
| Tool | Reality | How verified |
|---|---|---|
| **Codacy** | free tiers are **IDE-only or open-source-only**; private repos + AI PR review start at the paid Team plan | its own pricing page, 2026-07-27 |
| **DeepSource** | free plan is **public repositories only**; AI review is pay-as-you-go even there | its own pricing page, 2026-07-27 |
| **Gitar** | **14-day trial**, not free — despite round-ups claiming "unlimited private repos at no cost" | **owner checked** |
| **Git AutoReview** | a **VS Code extension**, not a GitHub App — BYOK, human presses publish | its marketplace listing |
| **Qodo** | permanent free tier withdrawn; trial expired on our repo | its own comment on PR #232 |
| **Codex** | usage limits exhausted | its own comment on PR #233 |
| **Sourcery** | free for open-source only | pricing page |
| **Greptile** | no free tier at all | pricing page |
| **LlamaPReview** | free private reviews end May 2026 | its own site |

**The honest headline: for a PRIVATE repo there are exactly TWO genuinely free LLM reviewers — CodeRabbit and
Gemini.** Everything else marketed as "free" is public-repo-only, a trial, or bring-your-own-key. A bench of
five is still reachable, but only by counting METHODS (LLM + rules + types + static + project invariants),
which is what §3b argued for anyway — and that bench is now assembled and running.

## 4. The free plan (private repo — most "free" tiers are open-source-only and don't apply)

**Tier 1 — free, uncorrelated, highest value:**
1. **Semgrep** (free ≤10 contributors on private repos) — fills the **security** hole outright. Rule-based,
   deterministic, zero overlap with LLM review.
2. **mypy** (open source, free) — fills the **type** hole. Our Python is untyped; pyflakes catches undefined
   names but not type misuse. Start `--ignore-missing-imports` on `tools/` only, widen gradually.
3. ~~**PR-Agent**~~ — **DROPPED 2026-07-27.** The software is open source, but it requires an LLM API key, so
   every review costs tokens. I had listed it as "free"; that was wrong. **Gemini replaces it** as the backup
   LLM reviewer: genuinely free (Google Cloud preview + a $300/90-day trial credit, and the owner confirmed
   billing must be MANUALLY enabled before anything can charge), and historically our single best performer
   at 14 recorded findings.

**Tier 2 — free, and it's the measurement the owner is really asking for:**
4. **Mutation testing** (`mutmut` / `cosmic-ray`, free) — **this is our own reviewer benchmark.** It injects
   known bugs into our code and reports what fraction our tests catch. That yields a *real percentage for our
   codebase*, not a vendor's marketing figure, and it directly answers "how far can we push toward 100%?"
   It also grades the reviewers: seed N mutants, open a PR, count what each layer flags.

**Vendor "free" claims must be VERIFIED, not read (owner 2026-07-27).** I surfaced **Gitar** from a search
result claiming *"unlimited private repositories at no cost"* — the owner checked and it is a **14-day
trial**. The claim came from vendor comparison pages, which are marketing. **Rule: no reviewer goes on the
plan until its pricing page is read directly, and "free" is recorded with its expiry.**
- **Gitar** — ❌ 14-day trial, not free (owner-verified).
- **LlamaPReview** — ❌ free private-repo reviews end May 2026.
- **Git AutoReview** — 🟡 free tier of 10 reviews/day; owner installed it 2026-07-27, connection pending.

**Rejected, with the reason:** *Sourcery* (free only for open-source), *Greptile* (no free tier), *Qodo*
(permanent free tier withdrawn). Adding a paid seat is a real option later, but the free ceiling is not yet
reached — Tier 1 is unbuilt.

## 5. Process rules (free, and they matter more than the tool list)
- **Space PRs to CodeRabbit's cadence** (~4/hour). On 2026-07-27 three rapid PRs outran the only reviewer and
  **#232 merged with zero review coverage** — a self-inflicted gap, recorded in [[state/current_status]].
- **Never merge on green CI alone when the review slot was skipped.** CI proves the tests pass; it does not
  prove the design is right.
- **Every bot finding still routes to [[failures/gemini_review_patterns]]** — that record is what turns a
  one-off catch into a permanent structural check, and it is why our own audit now catches things no bot does.
- **Prefer converting a repeated bot finding into a `prepush_audit` check.** A rule that runs every push beats
  a reviewer that might notice. This is the flywheel: bots find it once → the audit catches it forever.

## 6. Honest limits of this page
The comparison table is built from OUR 56 findings, which is a small, project-shaped sample and is biased by
which bots were installed when. It says what each caught *here*, not which product is better in general. The
catch-rate question has no answer until the mutation-testing baseline in §4.4 is actually run — everything
before that is reasoning, not measurement.

See also [[failures/gemini_review_patterns]], [[workflow/bot_review_fold_in]],
[[workflow/design_proposal_protocol]], [[workflow/three_phase_protocol]] (the pre-push audit).
