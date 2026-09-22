---
tags: [failures, data-quality, openstates, corpus, scope]
updated: 2026-09-22
status: active
---

# The corpus has no committee-stage actions before 2020, and it fails silently

Found 2026-09-22 while chasing why "never heard" bills appeared to pass 37% of the time. They did not —
791 bills in the 2018 session are recorded as going straight from `Referred to Committee` to
`Read second time and engrossed`, with **the committee's report action missing entirely**.

## Measured coverage

| session | bills | `Reported from` | `Subcommittee recommends` | `Passed by indefinitely` | `Failed to report` | `Continued to` |
|---|---|---|---|---|---|---|
| 2017 | 1,899 | **0%** | 23% | **0%** | **0%** | **0%** |
| 2018 | 2,606 | **0%** | 7% | **0%** | **0%** | 1% |
| 2019 | 2,181 | **0%** | 4% | **0%** | **0%** | 1% |
| 2020 | 2,830 | 58% | 59% | 4% | 2% | 13% |
| 2022 | 2,141 | 56% | 58% | 8% | 2% | 9% |
| 2024 | 2,284 | 60% | 67% | 4% | 1% | 16% |
| 2026 | 2,366 | 65% | 67% | 4% | 1% | 18% |

## Why it is dangerous rather than merely annoying

**Nothing about it looks broken.** The bills are all there. `Referred to Committee` is 81-83% in the early
years, right in line with later ones. **The passage flag is intact** — 2017 reads 49%, 2018 37%, 2019 39%,
against 51-58% later — so every outcome-based finding keyed on `passed` is unaffected.

**And one committee action survives at full strength: `Left in committee`** (28%, 40%, 29% — normal). So the
early years contribute **kills without reports**: a one-sided sample that arrives wearing a full denominator.
This is the same shape as the [[testing/continuance]] artefact (an unreachable numerator under an
authoritative-looking denominator) and the [[testing/enacting_clause]] outcome leak.

## What it cost

[[testing/bill_states]] was computed over 2017-2026. Recomputed on 2020-2026:

| state | published | corrected | move |
|---|---|---|---|
| **Re-referred** | 1,467 of 2,363 = **62.1%** | 1,305 of 1,669 = **78.2%** | **+16.1 pts** |
| Reported to the floor | 89.9% | 89.9% | — |
| Tabled | 1.0% | 1.0% | — |
| Continued | 0.9% | 0.9% | — |
| Failed to report / Stricken / Incorporated / Left in | unchanged | unchanged | — |

**Seven of eight rows were robust; one was wrong by sixteen points.** Re-referred is exactly the row the gap
would hit hardest: a re-referred bill's *next* step is `Reported from`, so in years where that action does
not exist, every re-referred bill looks abandoned.

## The guard

`bill_states.FIRST_GOOD_YEAR = 2020` and `assert_years()` **raises** rather than filtering, so a future
caller who widens the window gets a failure instead of a plausible number. A silent filter would have
reproduced the original bug the moment someone passed it a wider corpus.

**Not affected:** every roll-call finding, because `committee_votes` only covers 2023-2026 in the first
place and reads `VOTE.CSV`, not action text ([[testing/rooms]], [[testing/member_signals]],
[[testing/contested_vs_routine]], [[testing/coverage]]). **Marginally affected:** [[testing/continuance]] —
2018 contributes 19 of its 1,346 bills and was already reported as 0 recoveries, so the finding stands on
2020/2022/2024/2026; the page now says so.

**The lesson, in one line:** *a source that is missing a column does not tell you — it tells you zero.*
Before trusting any per-session rate, plot the coverage of the input action itself across sessions.
