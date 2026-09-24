---
tags: [knowledge, campaign-finance, elect, money, sources, join, open-loop]
updated: 2026-09-16
status: active
open_loop: Join now 120 of 148 sitting members (81%, no known wrong matches), up from 54. The 28 still missing are almost all first elected 2024-25 — only Oct 2023 and Jan 2024 filings are cached. Closing it needs 2025 Report.csv files (~6 MB each, ELECT, keyless) — a download awaiting the owner's OK.
---

> **UPDATE 2026-09-24 — the join, re-diagnosed and rebuilt (`finance.committees` + `finance.join_members`).**
> The old diagnosis was wrong: blank offices do NOT drop legislators — only 7 candidate committees ever file
> one (the ~5,000 blanks are PACs). The real traps, all measured:
> 1. **`OfficeSought` has 28 spellings** of the two chambers ("Delegate", "State Senator", "Senate",
>    "Hous of Delegates", "…– Old", "…– 2001 LD Lines"), plus bare **"SD"/"HD"** (Bagby, Carroll Foy,
>    VanValkenburg). The two canonical strings cover ~44% of reports. Audit point #1 again.
> 2. **"0.00" in `OfficeSought`** on some report types (Knight, Leftwich) — a placeholder, not a column shift
>    (39 fields, correct). Kept as chamber-unknown and matched on NAME ALONE, flagged.
> 3. **A surname-only fallback produced wrong people** — Gretchen Bulova got David Bulova's committee, Nicole
>    Cole got Joshua Cole's, Wren Williams got LeOtis Williams's. Removed: a first name must agree (exact,
>    3-letter prefix, or a short explicit nickname list). A donor record on the wrong legislator is worse
>    than a gap.
> **Result: 120 of 148 sitting members, 0 ambiguous, 0 known wrong** (12/12 random spot-checks, all 9
> first-name-differs cases verified as nicknames). Missing = members first elected 2024–25 plus chamber
> switchers (Guzman, Srinivasan, Bennett-Parker last filed for their previous chamber).

# ELECT campaign finance — what is in the files, and the join that is not solved

[[knowledge/campaign_finance_source]] settled **where** to get Virginia money data. This page is what we
learned **reading it**, 2026-09-16.

`python3 tools/historical_cache/finance.py 2023_10 2024_01`

## Which file to reach for

| file | size | what it carries |
|---|---|---|
| `Report.csv` | ~6 MB | filing metadata — `CandidateName`, `Party`, `OfficeSought`, `District`, `ElectionCycle` |
| **`ScheduleH.csv`** | **~0.8 MB** | **the summary — `TotalReceiptsThisElectionCycle`.** The whole race in one small file |
| `ScheduleA.csv` | 20–30 MB | every contribution — donor name, **employer**, **occupation**, amount |

**Reach for `ScheduleH` before `ScheduleA`.** Cycle money totals are a published field; summing 30 MB of
individual contributions to recover them wastes two orders of magnitude of bandwidth and gets a worse
answer, because one month of contributions is not a cycle.

## Three field traps, all measured

1. **`IsGeneralAssembly` is always False.** A dead column. Filtering on it returns **zero rows** in both
   months checked. `OfficeSought` text is the only route.
2. **`OfficeSought` is blank on ~1,000 reports per month.** Filtering on it silently drops real sitting
   legislators — Ebbin, Rouse, Lopez and 100 others vanish. **This is why only 34% of sitting legislators
   match.**
3. **`District` is free text** — `93`, `#59`, `086` all appear for the same kind of value. Normalise before
   joining, or repeat the padding-bug class this project has shipped five times.

## What one month actually contains

`2023_10` (the pre-election filing for the November 2023 general): **131,030 contributions, $189M.**
Organisations gave **$140M** against **$49M** from individuals.

The largest organisational donors are party caucus committees — that is internal party transfer, not
interest money. Below those, the recognisable names:

| donor | 2023_10 |
|---|---|
| Dominion Energy Inc | $2,050,000 |
| Dominion Energy PAC | $1,821,000 |
| League of Conservation Voters | $2,027,000 |
| Clean Virginia Fund | $1,902,500 |

## The open loop — the join

Matching a filing committee to a legislator is **unsolved**, and it is the only thing standing between this
data and a product. Current state: **54 of 158** sitting 2024–26 patrons matched (34%).

The vault already predicted this: *"settle the name→legislator join, which is the real engineering work —
filer names are free text and must be matched to `MemberID` structurally, never by fuzzy string alone
(Standard #3)."* Confirmed. Candidate names arrive as `Mr Michael C Karslake`, `Dr. Todd E. Pillion`,
`Emily  Brewer` (double space). The fix is to join on **committee identity** rather than office text, and
it is a piece of work, not a patch.

## Storage

The CSVs are **gitignored** (`tools/historical_cache/va_finance/`) — 10 MB for two months and growing, and
re-downloadable from a documented public directory. The fetcher is committed; the bytes are not. Same rule
as the Open States session archives.

## Related

[[knowledge/campaign_finance_source]] · [[testing/money_and_vulnerability]] · [[index]] · [[log]]
