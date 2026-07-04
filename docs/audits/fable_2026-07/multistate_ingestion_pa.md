---
tags: [audit, fable, multistate, pennsylvania, architecture, ingestion, lambda]
updated: 2026-07-04
status: active
---

# FABLE 3 — The non-API state class: Pennsylvania, the lambda architecture, and decade-grade text handling

The owner's framing: *"not every state has the extent of public data via codable input that Virginia
does… PA publishes bulk data hourly without an API… are there any solutions that aren't text parsing? If
not, how do we do the fragile task with 100% accuracy and sustainability measured in decades?"*

## Part 1 — What Pennsylvania ACTUALLY publishes (researched 2026-07-04)

Source: the PA General Assembly's official data page (palegis.us/data) and the LDPC resources page.

| Feed | Format | Contents | Cadence |
|------|--------|----------|---------|
| **Bill History Data** | XML (ZIP) | Full bill history, ALL bills & resolutions, both chambers, **back to 1969**; includes bill-updated dates, links to bill text per printer's number, co-sponsorship memos, amendments | **Hourly, Mon–Fri** |
| House / Senate **Calendars** | RSS | Upcoming legislation for floor consideration | per publication |
| House / Senate **Roll Call Votes** | RSS | Floor voting records | per publication |
| House **Voted Amendments** | RSS | Amendments voted | per publication |
| **Committee Meeting Schedules** | RSS | Scheduled meetings, both chambers | per publication |
| House / Senate **Journals**, House Daily Session Reports | RSS | Floor transcripts / summaries | per publication |
| Member data | Excel + RSS | Members by session/chamber | static / per publication |

No registration, no key. LDPC (the Legislative Data Processing Center, which produces these) publishes no
schema documentation on its resources page — but lists a phone number; **action item: contact LDPC for the
Bill History XML schema and ask whether a change-notification list exists** (a 15-minute call that buys
years of contract stability; they have run these feeds for decades).

### The direct answer to "is there a non-text-parsing solution for PA?"

**Yes at the transport layer, with one honest caveat at the semantic layer.**

1. **Transport is structured.** Hourly XML + RSS are machine formats with stable elements. There is no
   HTML scraping and no PDF parsing on the critical path. This is *better* than the owner feared: PA is
   not a "text state," it is a "bulk-XML state" — closer to VA's blob model (HISTORY.CSV ↔ Bill History
   XML) than to a scraping problem. The absence of a request/response API matters little to us: **our VA
   architecture is already bulk-first** (the 4 blobs) with APIs only as enrichment. PA fits the existing
   shape, minus the enrichment tier.
2. **The caveat:** inside the XML, a bill's history entries are LIS-status-like **controlled-vocabulary
   prose strings** ("Referred to JUDICIARY", "Third consideration and final passage (198-0)") rather than
   coded enums like VA refids. Under this project's sharpened Standard #3, consuming a source's
   *controlled vocabulary* — a finite phrase set the legislature itself publishes — is NOT forbidden text
   parsing; it is "consuming the source," the same doctrine that ships VA's outcome derivation and floor
   stages today. Free-text inference remains forbidden; closed-set phrase classification with the full
   mitigation kit (below) is the sanctioned tool.
3. **Third-party normalized alternatives evaluated (and their correct role):**
   - **LegiScan** — normalized 50-state JSON API + weekly per-state bulk datasets (PA archives confirmed
     to exist). Tempting as a primary (zero parsing!), **rejected as primary**: it inserts a third party
     between us and the legislature (their parser becomes our silent dependency; their outage/licensing
     becomes ours; commercial-use terms need review). *Owner ruling 2026-07-04: keep third parties off
     the pipeline entirely — they consume the same public feeds we do ("we are building a superior
     competitor").* So verification is **first-party cross-channel** (Part 5: roll-call RSS vs XML
     tallies, committee RSS vs calendars/journals — two LDPC channels grading each other); LegiScan
     remains at most an OPTIONAL periodic outside auditor, never load-bearing.
   - **Open States / Plural** — same analysis, second choice of oracle (scraper-based; quality varies by
     state; useful as a tiebreaker source when we and LegiScan disagree).
   - Direct LDPC relationship — see above; the highest-leverage "API alternative" is often a schema doc
     and a heads-up email list.

## Part 2 — The lambda architecture (the owner's instinct, formalized)

The owner proposed: permanent source = the state's bulk feed; a temporary layer finds fresher data;
temporary rows are marked on the site; the verified layer corrects hourly. This is correct, and it is
also — good news — a generalization of what VA already does (bulk blobs + Schedule-API freshness +
provisional flags + witness reconciliation). Formalized:

```
STATE SOURCE CONTRACT (per state)
├── BATCH layer (authoritative, replayable)
│     PA: hourly Bill History XML   VA: HISTORY/BILLS/DOCKET/VOTE blobs   NY: OpenLeg bulk pages
│     → full re-derive each cycle (idempotent; keep-last-known-good on fetch failure)
├── SPEED layer (provisional, fresher-than-batch)
│     PA: the RSS feeds (committee schedules, calendars, roll calls — "per publication")
│     VA: Schedule API (15-min-class freshness)   NY: none yet
│     → rows stamped Origin=speed_<feed>, Provisional=true; UI shows the provisional badge
├── RECONCILER (each batch cycle)
│     batch output REPLACES speed rows by natural key (bill+date+action / meeting date+committee)
│     • speed row confirmed by batch → provisional flag cleared (silent, the happy path)
│     • speed row CONTRADICTED     → batch wins; speed_wrong counter++ (with denominator)
│     • speed row NEVER confirmed after 2× batch intervals → quarantine + WARN (witness pattern)
└── VERIFICATION oracle (weekly, independent)
      PA: LegiScan PA dataset   VA: MinutesBook + LIS calendar tripwire   NY: LegiScan NY (see C-8)
```

Design rules that make this decade-grade (each is a lesson VA already paid for):
- **The batch layer is the only writer of record.** Speed rows may only ever *pre-announce*; they can
  never survive a batch cycle unreconciled without an alert. (Prevents the two-source drift problem.)
- **Provenance is a column, not a comment** (`Origin`, `Provisional`) — the UI and the guards read it.
- **Conditional fetch + jitter + caps on every feed** (guardrail charter applies verbatim; RSS is cheap —
  poll with `If-Modified-Since`, expect 304s, cadence tied to the legislature's session calendar).
- **The speed layer is optional per state.** A state with no trustworthy fresh feed simply runs
  batch-only at the state's cadence — honest "as of" labeling beats manufactured freshness.

## Part 3 — Structural routing, not a text dictionary (REWRITTEN 2026-07-04 after owner/Gemini rejection)

> **Retraction:** the first draft of this section proposed a "57-year historical phrase corpus" as the
> classifier. The owner rejected it, correctly: *a massive historical dictionary is still a text
> dictionary* — a clerk's novel phrase next Tuesday defeats it and pings a human (Zero Text Dependencies
> + Standard #8 violations). The corpus survives ONLY as a **one-time measurement instrument** (below),
> never as a runtime dependency. What follows replaces it, grounded in live inspection of PA's actual
> feeds (2026-07-04).

### Challenge 1 — Hidden structural codes: FOUND (verified against the live feeds)

PA's structure hides in **namespaced elements and URL grammar**, not attributes — but it is there, and
it is machine-generated by LDPC's database layer (template serialization, not clerk prose):

1. **Committee Meeting Schedule RSS — a full custom namespace.** Live items carry
   `<parss:MeetingDate>07/07/2026</>` · `<parss:MeetingTime>10:00 AM</>` (or `Call of Chair` — PA's
   honest-TBA analog) · `<parss:Committee>HOUSE FINANCE</>` · **`<parss:Bills>HB2639,HB2675,HB2521</>`**
   (the agenda as a structured field — richer than VA's Schedule API, which needs agenda-PDF parsing!)
   · `<parss:Location>` · `<parss:InCapitol>0|1</>`. **Meetings are 100% structural in PA. Zero prose.**
2. **Roll-call RSS — canonical keys in the link URL.** Every item links
   `.../roll-calls/summary?sessYr=2025&sessInd=0&rcNum=1308` — session year, session index, and roll-call
   number are DATABASE KEYS in URL grammar (VA-refid-equivalent). The `<guid>` is a deterministic
   composite (`rcNum + serialized subject + yyyymmdd`); `<description>` carries the tally in one fixed
   machine format (`115 YEAS *** 87 NAYS *** 0 LVE *** 0 N/V`); `<title>` serializes `HB 2154 PN 2787`
   — bill number + **printer's number** from database fields. Deserializing a rigid machine template is
   NOT clerk-prose classification; it is reading a wire format (same doctrine as VA's tally strings).
3. **Printer's Numbers (PN) — PA's version primary key.** Every text version of every bill has a unique
   PN; the Bill History XML links bill text *per PN* (confirmed by the data page). PN transitions are
   pure structure: amendment/engrossment events without reading a word of prose.
4. **The Bill History XML element schema** must be enumerated from one real download (it ships as ZIP —
   not fetchable through my tooling today). Phase 0 for Opus, first hour: download `2025_0`, dump the
   element/attribute tree (`xmllint --format`, then a 20-line script tabulating element names ×
   attributes × sample values). Given LDPC ships a `parss:` namespace on RSS, expect structured
   elements (dates, chamber, PN refs, possibly vote refs) around each action line. Whatever prose
   remains is handled by Challenges 2–3 below — the design does not DEPEND on the answer.

### Challenge 2 — The structural fail-safe: route by JOIN ("Prove-to-Hide"), never by text

Every lobbyist-facing event class gets its existence and classification from a **structural witness
artifact**, with history prose demoted to corroborating display text:

| Event class | Structural witness (the proof) | Text's role |
|---|---|---|
| Vote (floor or committee) | Roll-call item: `rcNum` key + tally fields; joined to the bill by the serialized `HB n PN n` + date | display only |
| Committee meeting / agenda | `parss:` schedule item (date, time, committee, **Bills**, location) | none needed |
| Text version event (amended/engrossed) | PN transition in the XML's per-PN links | display only |
| Floor consideration scheduled | Calendar RSS item for the bill | display only |
| Sponsorship event | Co-sponsorship memo RSS item (per-bill link) | display only |
| Floor session occurred | Journal / Daily Session Report RSS item (dated anchor) | display only |

The router is a **join**, exactly like VA (refid → VOTE.CSV/DOCKET): a history line for bill B dated D
routes by which artifacts exist for (B, D) — roll-call ⇒ vote event; `parss:Bills ∋ B` on D ⇒ committee
meeting event; PN change at D ⇒ version event; none ⇒ Challenge 3. The clerk can invent any phrase they
like on Tuesday: if the event was real, its artifact exists (LDPC's own systems require it — roll calls
and schedules are how the chambers operate), and we route on the artifact. **Mathematical proof of a
meeting is the owner's exact suggestion, confirmed feasible: the artifact's presence IS the
classification.**

### Challenge 3 — The unseen row: graceful degradation with zero regex, zero human

The router is a **total function over structural evidence** — there is no "unrecognized" error path,
only the lowest-evidence class:

1. A history line with NO joining artifact routes to `event_class = UNPROVEN` by construction (the
   default branch, not an exception).
2. UNPROVEN rows land in the **visible Suspense/Unconfirmed lane** (the owner's Prove-to-Hide rule from
   [[ideas/self_healing_classification]]): shown verbatim with the bill link, badged "unconfirmed
   activity," never hidden in a ledger, never guessed into a lane. Displaying clerk prose verbatim is
   always allowed — only ROUTING on it is banned.
3. Counted with a denominator (`unproven_rate`); the canary alerts on a RATE ANOMALY (statistical jump
   vs rolling baseline — pre-push audit #14 style), not per row. No phrase mapping, no regex PR, no ping.
4. **Self-healing upgrade:** artifacts often trail the line by minutes-to-one-cycle (a roll call
   publishes after the floor action). Each batch cycle re-joins the suspense lane; a row whose artifact
   arrives is upgraded and vacates automatically. Rows that never resolve stay honestly visible — which
   is the correct permanent state for genuinely artifact-less administrative lines (referrals,
   printings: Ledger-class in VA terms, no time/vote expectation anyway).
5. Optional, aligned with the parked self-healing design: recurring (normalized-line → artifact-pattern)
   co-occurrences may be LEARNED into an auto-maintained suggestion table keyed by structural pattern —
   canonical-only learning, auto-adopted only above a confidence threshold the reconciler grades.

### The corpus, demoted to what it's actually for

One offline run over the 1969→2026 archives, at build time only: measure **what fraction of historical
history-lines join to structural artifacts** per era (the honest forecast of the suspense-lane size) and
produce the validation set the router must pass (routing on 57 years of data with 0 crashes and a stable
unproven_rate). It ships nothing textual to runtime. If the measured joinable fraction for the modern era
is low (< ~80% of meeting/vote-class lines), THAT — not a dictionary — is the trigger to hunt harder for
structure (Bill History XML internals, Tier-2 site endpoints) before building.

## Part 4 — Execution plan for Opus (when the owner green-lights PA)

Phase 0 (1 day): download Bill History XML for `2025_0` + two older sessions
(`/data/file?documentType=BillHistoryData&session=2025_0`); dump + tabulate the full element/attribute
schema → `docs/knowledge/pa_bill_history_xml.md` (every element, samples, and specifically: any per-action
structured fields, PN link elements, vote refs). Snapshot each RSS feed's item schema the same way
(the `parss:` namespace is already confirmed on committee schedules — enumerate the others). LDPC contact
for schema docs + change-notification list in parallel.
Phase 1 (2 days): the **structural-join measurement** over the historical corpus (the corpus's only job):
per era, what fraction of history lines join to artifacts (roll calls, PN transitions, schedules where
archived)? Produces the suspense-lane forecast + the router's validation set. **Gate: modern-era
meeting/vote-class join rate measured and accepted by the owner; router design adjusted if < ~80%.**
Phase 2 (3–5 days): `pa_bill_tracker.py` batch pipeline (mirror `ny_bill_tracker.py`'s shape: fail-safe,
completeness object, alerts) with the JOIN router of Part 3, writing to its own workbook (C-2 lesson:
never co-locate). **Gate: full-corpus replay routes 100% of lines with 0 crashes (unproven is a valid
route, not a failure); unproven_rate stable across replay eras; first-party cross-channel reconcile
(roll-call tallies vs XML) divergence ≈ 0 on the live session.**
Phase 3 (2–3 days): speed layer — RSS pollers (committee schedules + calendars first; roll calls second)
with provisional stamping + the reconciler. **Gate: one week of speed_wrong_rate < 1% and zero
never-confirmed quarantines.**
Phase 4: front-end state switcher (out of scope here; UI is Opus+owner territory per the owner).

## Part 5 — FRESHER than hourly, first-party only (owner 2026-07-04: "we are building a superior competitor")

Owner constraint accepted: no LegiScan/aggregators anywhere on the freshness path — they consume the same
public feeds and are definitionally *slower* than us reading those feeds directly. The question is how
close we can get to the **moment PA publishes**. Answer: within minutes, first-party, ban-safe — because
the freshness floor for ANY outsider is LDPC's publication moment, and the game is won by (a) finding the
earliest first-party surface each fact appears on, and (b) ingesting it within minutes of appearing.

### The freshness ladder (all first-party)

| Tier | Channel | Latency vs publication | Trust class |
|---|---|---|---|
| 1 | **RSS feeds** (roll calls, committee schedules, calendars, voted amendments, session reports) | minutes (poll-bound) | provisional → confirmed |
| 2 | **palegis.us's own backing endpoints** (investigate: XHR/JSON the site's pages load) | seconds–minutes | provisional |
| 3 | **Hourly Bill History XML** | ≤ 1 h | AUTHORITATIVE (the reconciler) |

**Tier 1 is the workhorse, and it is enough for the product.** Map freshness-NEED before chasing
freshness: the lobbyist-critical, minutes-matter events are votes just taken (roll-call RSS), meetings
scheduled/moved/cancelled (committee-schedule RSS), floor calendars (calendar RSS), amendments voted
(voted-amendments RSS). The only class arriving *solely* via the hourly XML is administrative history
lines (referrals, printings, signings-recorded) — exactly the class VA doctrine already assigns **no
freshness expectation** (Ledger-class). So the hourly XML's cadence costs us nothing a user can feel,
PROVIDED the RSS layer is ingested aggressively:
- **Polling design:** RSS is a polling format BY DESIGN — tiny documents, built for conditional GET
  (`If-Modified-Since`/ETag → 304s). Poll every **2–5 min during session days/hours**, hourly on quiet
  days, per the activity-correlated cadence charter ([[knowledge/lis_api_safety]] guardrail 5 — the
  session calendar drives the schedule). A dozen 304s per feed per hour is a lighter footprint than one
  XML download; this is unimpeachably sustainable.
- **Push check (build-time, 10 min):** inspect the RSS HTTP responses for **WebSub** (`Link:
  rel="hub"`) headers. If LDPC offers a hub, subscribe — true push, latency ≈ 0, polling drops to a
  fallback heartbeat. If not (likely), polling stands.
- **Optional exotic tier:** PA offers email bill-alert subscriptions; an email-to-webhook bridge could
  act as a push TRIGGER for a targeted re-poll. Document-only: adopt ONLY if a measured gap demands it —
  each moving part must earn its decade of upkeep.

**Tier 2 is the VA playbook applied to PA** — the same move that got us the LIS SPA's LegislationEvent
endpoint. palegis.us is a modern site rendering live data; its bill/vote/committee pages are fed by
LDPC's internal store, fresher than the hourly export. Opus investigation protocol (1–2 h, harmless):
open a bill page + the roll-call and committee pages with DevTools; catalog every XHR/fetch returning
JSON; note auth (cookies? none?), shape, and stability markers; check robots.txt + site terms; if JSON
endpoints exist, they join Tier 2 with conditional-fetch discipline + a dedicated drift canary (an
undocumented surface gets the FULL mitigation kit: schema canary, quarantine-on-change, and Tier 3
reconciliation). If the site is server-rendered HTML only, we simply don't build Tier 2 — Tier 1 already
covers the minutes-matter classes; we never scrape HTML on the lobbyist path.

### Why accuracy does NOT degrade as freshness increases
Every Tier 1/2 row enters as `Provisional=true` with its origin stamped, surfaces with the provisional
badge (the UI vocabulary already exists), and must be CONFIRMED by the next hourly XML or it is
quarantined + alerted (Part 2's reconciler). Cross-channel redundancy gives first-party
self-verification with no third party: roll-call RSS tallies must match the XML's "(198-0)" strings;
committee-RSS meetings must appear in calendars/journals. Divergence = counted, alerted, and always
resolved in favor of Tier 3. **Freshness rides on top of accuracy; it never substitutes for it.**

### The competitive statement (the owner's actual thesis, confirmed)
Aggregators are batch consumers of these same public feeds — their floor is our ceiling. A pipeline that
ingests LDPC publications within 2–5 minutes, labels them honestly, and reconciles hourly against the
authoritative XML is *structurally* ahead of anything downstream of the same feeds, at near-zero marginal
cost and with the same unattended-for-years posture as VA. The only way to beat it is insider access —
which nobody selling a product has either.

Sources: [PA General Assembly Data Downloads](https://www.palegis.us/data) · [LDPC Resources](https://www.paldpc.us/Resources) · [LegiScan PA datasets](https://legiscan.com/PA/datasets)
See also [[knowledge/lis_api_safety]] (the guardrail charter applies to every state), [[architecture/calendar_pipeline]], [[audits/fable_2026-07/codebase_longevity_audit]] C-8 (NY gets the same oracle pattern first).
