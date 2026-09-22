---
tags: [testing, calibration, docket, war-room, lead]
updated: 2026-09-22
status: active
open_loop: A LEAD, NOT A FINDING. Two sessions only (the action is LIS-only, so the authorization gate caps it at 2025/2026), House-only, subcommittee-only, and the pooled effect swings 2.6x between the two years. Needs (a) the 2027 session or the legacyLIS CSV route for more years, (b) a selection control for "the chair re-docketed it because he wants it". Do NOT put it on the War Room until both clear.
---

# Being put back on the agenda — a lead worth one more session

Owner, 2026-09-22, on the current War Room: *"the only portion… weve been able to upgrade to give real
unique insight to lobbyists which frankly is still pretty surface level."* Correct. This is the one live
lead found since, and it is filed as a **lead** on purpose.

## The signal

LIS writes `H Placed on <committee> Agenda` when a House committee puts a bill on a meeting's docket. Count
the distinct agenda dates a bill sat through **before that committee first acted on it**, then look at what
that first action was.

| House bills that reached a subcommittee | on 1 agenda | on 2+ agendas | gap |
|---|---|---|---|
| majority patron | 624 of 776 — 80.4% | 401 of 461 — **87.0%** | +7 |
| minority patron | 143 of 377 — 37.9% | 89 of 139 — **64.0%** | **+26** |

**Being carried to a second agenda is a good sign, not a bad one** — the opposite of what a lobbyist would
assume, and by far the largest standing-conditional gap found at the bill-state level. It is also
**prospective**: agendas are published before meetings, which is what makes it a War Room signal rather
than a post-mortem.

## Why it is not on the page

Four limits, all load-bearing:

1. **Two sessions.** `Placed on … Agenda` does not appear in the Open States corpus at all (0 of 22,659
   session-records). It is LIS-only, and [[knowledge/lis_api_authorization]] caps us at 2025/2026. Ten
   sessions of history do not exist for this signal the way they do for everything else here.
2. **The pooled effect swings 2.6×** between the only two years available — 2025 gives +20.2 points,
   2026 gives +7.7. Same failure shape as the partisan gap in [[testing/panel_audit]], which moves 11 points
   between eras and is why that page says do not sell it as prediction.
3. **House only.** The action is a House convention: the 519 "Senate" hits are SB bills placed on a *House*
   agenda after crossover, which lands after the Senate has already disposed of them. Mirror image of the
   DOCKET.CSV Senate-only limit already in CLAUDE.md.
4. **Subcommittee only, and that is a real split, not noise.** Bills that never reached a subcommittee show
   73.0% vs 73.5% — a flat null. The effect lives entirely in the subcommittee stage.

**And the confound is not controlled.** A committee re-dockets a bill because somebody wants it heard, which
is plausibly the chair — and [[failures/assumptions_audit]] #132-134 already established the room follows the
gavel. Until that is separated, "re-docketed" may just be "the chair is carrying it", which is a different
claim and not one a lobbyist can act on.

## The honest scoreboard for member-level intelligence

The goal the owner set is *"info that this persons district is very vulnerable to flip therefore lobbying
them on the data center pause will be easier."* Against that, at member level:

| tried | result |
|---|---|
| district vulnerability | r = +0.00 |
| donor alignment | +3.9 pt within-member |
| blocs / who moves together | NULL once the baseline used FOLLOW rates |
| pivotality | NULL — observed 5.2% is *below* a party-line null's 6.9% |
| unpredictability / "independent voters" | collapses into plain defection rate, r = 0.92 |
| reciprocity | −4 pt |
| chair | +3 pt over merely holding a seat |
| workload | r = +0.02 |
| subject-specific defection | **the one survivor** — 71 flags, 76% replicate vs a 41% null |

**The pattern in the failures is one fact:** committee members vote with their caucus, and what varies is the
ROOM and the BILL, not the person. Every room-level and bill-level test has produced something; almost every
person-level test has produced nothing. That is worth stating as a finding in its own right rather than
continuing to probe the same wall.

Related: [[testing/members]], [[testing/member_subject]], [[testing/bill_states]], [[testing/rooms]].
