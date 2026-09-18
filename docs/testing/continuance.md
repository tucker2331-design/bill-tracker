---
tags: [testing, calibration, carryover, committee, war-room, lever]
updated: 2026-09-18
status: active
open_loop: The `Left in <committee>` date is observed for ONE cycle (18-19 Nov 2024). Re-read 20261/HISTORY.CSV in Nov 2026 for a second observation before the War Room ever prints it as a published deadline.
---

# A continuance is a soft kill with a twelve-day clock

**429 bills are sitting "continued to next session" right now.** Everyone tracking one of them believes
they are tracking a live bill. Nothing in the product said otherwise, because nobody had counted it.

`python3 tools/calibration/continuance.py`

## The number

| | |
|---|---|
| bills continued by a committee, 2018–2026 | **1,346** |
| of those, ever moved again | **25 — 1.9%** |
| longest gap between the continuance and that next action | **12 days** |
| of the 25, came back the same day | **12** |
| bills continued out of 2024 with any action in the 2025 session (LIS) | **0 of 333** |

The mechanism is written in the descriptions: every one of the 25 was **`Reconsidered by <committee>`**
while the committee was still sitting. A committee that means to revive a bill does it inside a fortnight.
**Nothing in the record comes back after the session ends.** LIS then writes the epitaph itself —
`Left in <committee>` on all 333 of the 2024 carryovers, dated **18–19 November 2024**, seven weeks before
the 2025 session convened.

## The artefact that almost shipped as the finding

The obvious question is *"of bills continued to the next session, how many passed in that next session?"*
and the obvious answer from Open States is **0 of 901**. That is a **measurement artefact**, not a result.
Open States never updates a carried-over record — the next session's copy is the previous session's
history plus one `Continued from last session` stub — so the numerator is structurally unreachable while
the denominator looks authoritative.

| | carried into the next session's file | carrying ANY action dated that year |
|---|---|---|
| 2020→2021 | 359 | **0** |
| 2022→2023 | 156 | **0** |
| 2024→2025 | 367 | **0** |

**What rescues the question is a capability check on a second source.** LIS's `20251/HISTORY.CSV` keeps the
whole biennium, so ask it the same thing *and then ask whether it could have answered*:

```
bills continued out of 2024, with any 2025 action ...........   0 of 333
NOT continued but active in 2024, with a 2025 action ........ 132 of 169   <- the file can see it
```

The second row is the whole argument. Without it, a zero from a file that stops updating and a zero from a
legislature that stops acting are indistinguishable. This is the same class as the `assert_lis_authorized`
false-200 trap and the outcome leak in [[testing/enacting_clause]]: **a clean-looking number from a source
that was never able to produce a dirty one.**

## Audit point #1 bit here too

The 2026 session writes `Continued to next session in Rules`. 2018 through 2024 write
`Continued to 2019 in Finance`, `Continued to 2025 in ...`. A pattern matching only the 2026 wording finds
429 bills and reports **0 for every earlier session** — which reads as a clean result rather than a broken
pattern. Both forms are matched.

Two near-misses that are **not** this event and are excluded:
- `Subcommittee recommends continuing to …` — a recommendation; the full committee's action supersedes it.
- `Continued to 2022 Sp. Sess. 1 pursuant to HJR455` — a move to a special session convening days later,
  not a carryover. (No ` in <committee>` tail, which is what the pattern keys on.)

## What it is worth on the War Room

This is **sourced plus derived**, cleanly split under [[design/object_page_patterns]] §5b: `Continued to
next session in Rules` and `Left in Rules` are LIS actions and render plain; *25 of 1,346* is our count and
renders amber.

It is the first thing found here that changes what a volunteer does **today** rather than describing what
already happened. A continued bill is not a bill to keep working — it is a bill whose number is spent and
whose idea has to be refiled. Coverage is 429 bills, 18% of the 2026 session.

**Still open:** the "Left in" date is observed for **one** cycle (Nov 2024). Whether that is a fixed rule
or a clerk's scheduling is not established, so the page says *"on last cycle's timing"* and never prints a
deadline as though it were published. Second observation arrives Nov 2026 — check `20261/HISTORY.CSV` then.

Related: [[testing/venue_shopping]] (the room is worth +18 with the year held fixed), [[testing/rooms]],
[[testing/panel_audit]].
