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
     becomes ours; commercial-use terms need review). **Adopted as the independent VERIFICATION oracle**
     — the PA analog of VA's MinutesBook reconciliation: weekly diff of our derived state vs LegiScan's,
     divergence rate with denominator. Two independent pipelines disagreeing is the strongest
     drift-detector money can't buy.
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

## Part 3 — 100%-accuracy, decades-grade handling of the controlled-vocabulary layer

This is the "fragile task" done un-fragilely. The recipe is the one that took VA to Section 9 = 0,
written as a checklist for any state:

1. **Enumerate the closed set BEFORE shipping.** PA's XML reaches back to **1969** — run the entire
   57-year corpus through the classifier-in-development and enumerate every distinct action phrase
   (normalized: tallies/dates/names blanked). The registry IS the spec. Ship only when the classifier
   covers ≥99.9% of historical phrases and every uncovered phrase is explicitly quarantine-classed.
   (VA equivalent: the multi-session schedule replay that found the 8am/"8:30AM" formats.)
2. **Classify by phrase registry, never by regex-guess.** Each registry entry maps
   `normalized_phrase → {event_type, chamber_scope, committee_ref_style, terminality}` — data, not code.
   New states add registry files, not parser branches (Standard #6).
3. **Unknown ⇒ quarantine, never guess.** An unmatched phrase gets `event_type=UNKNOWN`, is EXCLUDED from
   lobbyist-facing derivations (shows as the honest "unclassified" bucket with its denominator), and
   fires the drift canary. The system stays *correct* under drift by refusing to be *complete* — the
   trust rule ("allowed not to know, never pretend") applied to ingestion.
4. **Self-calibrating reconciliation** wherever the source offers redundancy: PA roll-call RSS vs history
   "final passage (198-0)" tallies; bill-updated dates vs derived last-action; LegiScan weekly as the
   outside oracle. Every check is a rate with a denominator and an alert threshold calibrated on the
   historical corpus.
5. **Vocabulary canaries in production**: every cycle, count phrases not in the registry; 0 is green;
   any N is a WARN listing the novel phrases verbatim (they become registry PRs — a 10-minute human loop
   a few times per year, which is Standard-#8-acceptable because a legislature changing its clerk
   vocabulary IS a genuine anomaly worth eyes).
6. **Freeze nothing implicitly**: registry files carry `source_corpus: 1969–2026, coverage: 99.97%` in
   frontmatter; the weekly sustainability audit re-runs coverage against the rolling corpus.

**Why this holds for decades:** every failure mode has a *visible* landing zone (quarantine bucket,
canary alert, reconcile rate) instead of a silent misclassification; the moving parts (phrases) live in
data files reviewable in a diff; and the two-pipeline oracle means even a subtle systemic error surfaces
as cross-source divergence. This is the same posture that has VA running unattended — nothing here is
novel machinery, which is precisely the point.

## Part 4 — Execution plan for Opus (when the owner green-lights PA)

Phase 0 (1 day): LDPC contact for schema docs; download 3 sessions of Bill History XML; write the schema
map page (docs/knowledge/pa_bill_history_xml.md) — every element, with samples.
Phase 1 (2–3 days): corpus enumeration tool (`tools/pa_corpus/enumerate_phrases.py`) over 1969–2026;
produce the registry draft + coverage report. **Gate: ≥99.9% coverage, every residual phrase dispositioned.**
Phase 2 (3–5 days): `pa_bill_tracker.py` batch pipeline (mirror `ny_bill_tracker.py`'s shape: fail-safe,
completeness object, alerts) writing to its own workbook (C-2 lesson: never co-locate). **Gate: full-corpus
replay classifies 100% (incl. quarantine class); LegiScan reconcile divergence < 0.5% on the live session.**
Phase 3 (2–3 days): speed layer — RSS pollers (committee schedules + calendars first; roll calls second)
with provisional stamping + the reconciler. **Gate: one week of speed_wrong_rate < 1% and zero
never-confirmed quarantines.**
Phase 4: front-end state switcher (out of scope here; UI is Opus+owner territory per the owner).

Sources: [PA General Assembly Data Downloads](https://www.palegis.us/data) · [LDPC Resources](https://www.paldpc.us/Resources) · [LegiScan PA datasets](https://legiscan.com/PA/datasets)
See also [[knowledge/lis_api_safety]] (the guardrail charter applies to every state), [[architecture/calendar_pipeline]], [[audits/fable_2026-07/codebase_longevity_audit]] C-8 (NY gets the same oracle pattern first).
