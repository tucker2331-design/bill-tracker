---
tags: [ideas, product, lis, data, b2]
updated: 2026-06-18
status: active
---

# LIS Data Inventory & Gap Analysis (B2)

Phase B2 of [[ideas/product_roadmap]]. Grounds every [[ideas/product_vision]] feature in data
feasibility: **feature → required LIS data → do we have it? → if not, what to start collecting.**
Built from [[knowledge/lis_api_reference]] (the verified LIS service map), the endpoints the code
actually calls, and the B1 spec. The §7 questions are genuine product decisions for the owner —
they decide which database expansions we make and in what order.

---

## 1. What LIS exposes vs. what we ingest
LIS publishes ~30 services (full table in [[knowledge/lis_api_reference]]). Mapped to our use:

| LIS service / blob | What it gives | We ingest? | Feeds which B1 need |
|---|---|---|---|
| **Session** | session lifecycle, `SessionEvents` (start/adjourn/prefile/reconvene dates) | ✅ | timeline stages, crossover date (?, see §3) |
| **Committee** | committees + codes `H01–H24`/`S01–S13`, `ParentCommitteeID` (sub→full) | ✅ | committee board, chamber-qualified names |
| **Schedule** | all meetings (date/time/room/committee) | ✅ | calendar, next-meeting |
| **HISTORY.CSV** | every bill action (BillNumber, date, description, refid) | ✅ | history, stages, what's-new, lifecycle |
| **DOCKET.CSV** | committee-meeting bill assignments | ✅ | next-meeting↔committee link |
| **VOTE.CSV** | roll-call vote ids/tallies | ✅ | latest vote |
| **LegislationVersion** | bill# → `LegislationID` (the hop) **+ bill text versions** | ⚠️ partial (id hop only; **text not ingested**) | bill card text/versions (not yet) |
| **LegislationEvent** | per-bill events w/ **minute-precision `EventDate`** + structural type | ✅ | time recovery, history, structural routing |
| **LegislationStatus list** | controlled Status vocabulary (52) | ✅ | status grouping / drift canary |
| **LegislationEventType references** | EventCode↔description map (3,912) | ✅ | admin recovery, ministerial law |
| **MinutesBook** | authoritative "committee met on date" list | ✅ (existence signal) | reconciliation tripwire |
| **LegislationPatron** | bill sponsor(s) | ❌ | **"by patron" search + bill card** |
| **LegislationSubject** | bill subject/issue tags | ❌ | **"by subject" search/grouping** |
| **LegislationSummary** | LIS-written plain summary | ❌ | a real summary on the card (beyond catchline) |
| **LegislationText** | full bill text + amendments | ❌ | bill text / amendment view (richer feature) |
| **AdvancedLegislationSearch** | bill search by criteria (the bill *universe*) | ❌ | **bill-count completeness (trust)**, robust "full session" |
| **Legislation / LegislationByMember** | bill metadata by id / by member | ❌ | catchline source confirm, patron cross-ref |
| **Calendar** | floor order-of-business (distinct from committee Schedule) | ❌ | floor-stage detail |
| **Member / MembersByCommittee** | delegate/senator + committee rosters | ❌ | patron detail, committee membership |
| **Statistics** | session stat dashboards | ❌ | (maybe the historical tracker, later) |
| CommitteeLegislationReferral | referral attribution | ❌ | reserved (committee-accuracy, if ever tracked) |

**Catchline caveat:** the old front end displayed an `Official Title` ([[#4 recovered model|product_vision §4]]).
B2 to confirm which feed supplies it today (likely a bill-metadata endpoint or HISTORY-adjacent) so
the card's headline name has a known, monitored source.

## 2. Feed freshness & skew — the lead/lag map (trust-layer item 3)
The pin exists because **feeds update at different rates.** The known skews (so we can flag *any*
fact a corroborating feed hasn't confirmed, not just status-vs-history):
- **Status feed ahead of HISTORY** → the pin (status names an action not yet in the log).
- **HISTORY date vs LegislationEvent date drift 1–9 days** (governor/conference/reconvene) — the
  LegEvent date is authoritative; HISTORY can lag/lead. Never exact-date-join these.
- **Schedule `ScheduleTime` empty ~16%** in session months (resolved via the time graph, but it's a
  freshness/completeness signal worth surfacing if unresolved).
- **Schedule meetings missing entirely** even when a committee met (recovered via LegEvent /
  standing-schedule; the residual is the `derived_standing` ASSUMED flag).
- **MinutesBook content blobs 404** (existence is published, content isn't) — use as existence only.
- **Blobs (HISTORY/DOCKET/VOTE) regenerate daily** (~16:00 GMT) — possibly-identical content with a
  fresh ETag (handled by guardrail #1's content check).
→ B2 action: record each feed's expected cadence so the trust layer can compute "this fact is N
hours ahead of its corroborator" and flag it.

## 3. Crossover date — NOT captured today (confirmed)
The timeline + calendar need the **crossover deadline date**, and we don't have it. Code check
(2026-06-18): crossover currently exists ONLY as a **hardcoded test window** in
`investigation_config.py` (Feb 9–13 2026, used while driving the bug count to 0) — never a derived
value. The `Session.SessionEvents` we parse are Start/Adjournment/Prefile/Reconvene only — **no
crossover event**. So it needs a real source. **PROBED LIVE (2026-06-18): crossover is NOT in the Session API.** The
2026 session returns only 5 dated `SessionEvents` (convene 1/14, prefile 11/17, adjournment ~3/14,
reconvene 4/22) — and their `EventName`s even came back blank in that response (a quirk worth noting
for whoever wires session dates). Crossover is absent. Remaining candidates (investigate when we
build the timeline, not blocking now): (a) the GA's **published session calendar** (LIS publishes a
"schedule of session" with crossover marked — possibly via the `Calendar` service or a session-rules
doc); (b) capture it once per session from that calendar with a runtime drift check (mild Standard
#5 tension, acceptable if validated). Flagged as a focused timeline-build follow-up.

## 4. Feature → data → status (the core table)
| B1 feature / field | Source | Status |
|---|---|---|
| What's-new daily feed | HISTORY/LegEvent deltas | ✅ have (incremental machinery exists) |
| Timeline stages + per-side counts | HISTORY actions (derived) | ✅ have |
| Crossover divider/deadline | Session events / rules | ⚠️ confirm source (§3) |
| Committee board (cols, sub→full, codes) | Committee API + refid + DOCKET | ✅ have |
| Referral-count badge | re-referral tracking | ✅ have |
| Calendar tab | Schedule + the calendar subsystem | ✅ have |
| Search: chamber / committee / status filters | derived | ✅ have |
| Search: **by patron** | LegislationPatron | ❌ ingest needed |
| Search: **by subject** | LegislationSubject | ❌ ingest needed |
| Bill card: number / catchline / status / lifecycle / committee | current pipeline | ✅ built (bill_tracker PR1 spine + PR2 structural position: chamber/crossed/last_committee/referral_count) |
| Bill card: latest vote + **where** | VOTE + action committee | ✅ built (bill_tracker PR2 — `latest_vote{tally,location,date}`, location structural from the vote refid) |
| Bill card: next meeting + **committee** | DOCKET/Schedule | ✅ built (bill_tracker PR2 — `upcoming[]` from DOCKET.CSV, future-only) |
| Bill card: history (action\|date, pin) | HISTORY/LegEvent | ✅ have |
| Bill card: **summary text** | LegislationSummary | ❌ optional ingest |
| Bill card: **patron** | LegislationPatron | ❌ ingest needed for "by patron" anyway |
| Bill card: **bill text / amendments** | LegislationText/Version | ❌ heavier ingest |
| Trust: data-as-of freshness | `AA1` marker | ✅ have (surface it) |
| Trust: per-bill freshness | derivable from cycle | ⚠️ build (track per bill) |
| Trust: **bill-count completeness** | a bill *universe* source | ❌ **gap — §5** |
| Trust: scope disclosure | *this document* | ✅ this is it |

## 5. The completeness gap — the scariest one (trust item 1)
Today our bill set is **derived from HISTORY** — i.e., bills that have *taken an action.* A bill
that's prefiled/introduced but hasn't acted yet, or one we dropped on a parse error, is **invisible
to its tracker, silently.** To guarantee "we have every bill LIS has," we need an authoritative
**bill universe** to diff against — `AdvancedLegislationSearch` (POST, backs the SPA's bill search)
or a full `Legislation` list. Plan: each cycle, fetch the universe count/ids, diff vs. our set,
**alert on any bill present upstream but missing from us** (and surface "we are tracking N of N").
This is the single highest-value B2 build — it closes the gap a lobbyist can't see.

## 6. Database expansion — what to start collecting (and what each unlocks)
Ordered by value / trust-criticality:
1. **Bill universe + count** (`AdvancedLegislationSearch` / `Legislation`) — *trust-critical.* Closes
   the completeness gap (§5) and makes the "full General Assembly" view authoritative, not
   action-derived. **Recommend yes regardless.**
2. **Patron** (`LegislationPatron`/`LegislationByMember`) — powers "by patron" search (a filter you
   specified) and is high-value on the card (lobbyists care intensely who carries a bill).
3. **Subject** (`LegislationSubject`) — powers "by subject" search + discovery grouping.
4. **Summary** (`LegislationSummary`) — a real one-paragraph summary on the card beyond the catchline.
5. **Bill text / versions / amendments** (`LegislationText`) — the heaviest data; needed only if we
   show text or amendment diffs (a richer, later feature).
6. **Fiscal impact statements** (`BillHistoryReferences` child docs) — surface the fiscal note for
   money bills.
7. **Floor calendar** (`Calendar`) + **Member/rosters** — floor-stage detail and committee membership;
   lower priority.

Each is additive and isolated (Standard #6) — ingest into its own tab/store, keyed by bill, behind
its own fetch with the same LIS-safety guardrails. None blocks the others.

## 7b. OWNER DECISIONS (2026-06-18) — the expansions are now decided
- **Completeness diff: ✅ BUILD** (bill-universe vs our set; "tracking N of N"; alert on missing). Top priority.
- **Patron + Subject: ✅ INGEST BOTH** (powers "by patron"/"by subject" filters + patron on the card).
- **Written summary: ✅ INGEST** (`LegislationSummary`), shown **truncated (~2 lines) + "more"** at the top of the card dropdown so it doesn't crowd; full text via the LIS link.
- **LIS bill-page link: ✅ EVERY CARD.** Recovered pattern (`shadow_v2.py:535`): `https://lis.virginia.gov/bill-details/{sessionCode}/{billNumber}` — deterministic, no API, not brittle. **Use the DYNAMIC session code** (old code hardcoded `20261`). This is also the "pressure valve" for anything that doesn't fit on the card.
- **Fiscal impact: ✅ LINK FROM HISTORY (light).** Not full ingest — capture `BillHistoryReferences[]` doc links from the LegislationEvent we already fetch, and render a "fiscal impact ↗" inline on the history row where the impact statement appears. (The LIS page link also exposes it for free as a baseline.)
- **Full bill text / amendment versions: DEFERRED** (heavy; phase 2 if ever).

## 7. Open questions for the owner (these decide the DB expansions) — RESOLVED, see §7b
1. **Completeness:** ship the bill-universe/count diff (§5) regardless? (My strong rec: yes — it's
   the scariest silent gap and it's how the "track N of N" trust signal becomes real.)
2. **Patron + Subject:** do you want **"by patron" and "by subject"** as v1 search filters? If yes,
   we ingest both (they're light). If "by committee/status/chamber" is enough for v1, we defer them.
3. **Bill detail depth:** for v1, is the card's **action history + catchline + vote/meeting** enough,
   or do you want **LIS's written summary** and/or **full bill text + amendment versions** on it?
   (Summary is light; text/amendments are heavy and can be phase 2.)
4. **Fiscal notes:** do lobbyists need the **fiscal impact statement** surfaced on money bills now,
   or later?
5. **Crossover date source (§3):** fine for me to go verify where the crossover deadline comes from
   (Session events vs. rules) and wire it as a derived value?

See also [[ideas/product_vision]], [[ideas/product_roadmap]], [[knowledge/lis_api_reference]],
[[knowledge/lis_api_authorization]], [[index]], [[log]].
