# Calendar Worker Pipeline Architecture

## Data Flow

```
LIS Session API -> get_active_session_info() -> ACTIVE_SESSION code
                                              -> test_start_date / test_end_date

LIS Committee API -> build_committee_code_map() -> COMMITTEE_CODE_MAP (runtime)
                                                -> LOCAL_LEXICON (derived)
                                                -> PARENT_MAP (ParentCommitteeID)

Google Sheets API_Cache -> api_schedule_map (historical)
                        -> convene_times (historical)

LIS Schedule API -> build_time_graph() -> resolved_parent_map
                 -> api_schedule_map (live, merged with cache)
                 -> convene_times (live)
                 -> agenda URLs -> extract_rogue_agenda() -> bill lists

Azure Blob DOCKET.CSV -> docket_memory (date -> bill -> committees)
Azure Blob HISTORY.CSV -> Sequential Turing Machine:
                          - resolve_committee_from_refid() [Phase 1: structural]
                          - LOCAL_LEXICON matching [Phase 2: text fallback]
                          - bill_locations state machine
                          - find_api_schedule_match() [time resolution]
                          -> master_events

master_events -> noise filter -> journal collapse -> dedup -> viewport slice -> Sheet1
             -> new_cache_entries -> API_Cache
```

## Committee Resolution Priority
1. **History_refid** (structural primary key) - COMMITTEE_CODE_MAP lookup
2. **LOCAL_LEXICON** (text-based fallback) - alias matching against outcome text
3. **bill_locations** memory (state machine) - where the bill was last seen

## Time Resolution Priority
1. **Exact match** in api_schedule_map (date + normalized committee name) → `Origin=api_schedule`
2. **Parent fallback** (subcommittee inherits parent time via ParentCommitteeID) → `Origin=api_schedule`
3. **Hint matching** (derive_room_hints from outcome text like "placed on X agenda") → `Origin=api_schedule`
4. **Substring matching** (partial name overlap) → `Origin=api_schedule`
5. **Convene time** (Floor actions inherit chamber convene time) → `Origin=convene_anchor`
6. **No match** → `Time="⏱️ [NO_SCHEDULE_MATCH]"`, `Origin=journal_default` (or `"⏱️ [NO_CONVENE_ANCHOR]"` / `Origin=floor_miss` for Floor actions that couldn't resolve via convene).

Every `master_events` row carries an `Origin` column (added in PR-A). This is the provenance field that survives the Journal→Ledger rename so downstream (X-Ray Section 0) can distinguish silent defaults from concrete sources. See [[workflow/source_miss_visibility]].

## Sheet1 Schema (worker output)
11 columns: `Date | Time | SortTime | Status | Committee | Bill | Outcome | AgendaOrder | Source | Origin | DiagnosticHint`.

The `Origin` column was added in PR-A. Enumerated values: `api_schedule`, `convene_anchor`, `journal_default`, `floor_miss`, `system_alert`, `system_metrics`. One `SYSTEM_METRICS` row per run carries a JSON-encoded snapshot of the source-miss counters (`total_processed`, `sourced_api`, `sourced_convene`, `unsourced_journal`, `unsourced_anchor`, `dropped_ephemeral`, `dropped_noise`, `floor_anchor_miss`). X-Ray Section 0 parses this row to render the denominator.

The `DiagnosticHint` column was added in PR-B. Populated ONLY for rows where `Origin in {journal_default, floor_miss}`; empty string otherwise. Value format: `loc='<bill_locations[bill]>'; api_<date>=[<committee>@<time>; ...]` (nearest-3 same-chamber Schedule API candidates for that date, or `<none>`). Pure measurement — no classification impact. See [[workflow/source_miss_visibility]] and [[failures/gemini_review_patterns]] #37.

## Key Design Decisions
- Calendar subsystem is separate from v2_shadow_test to allow independent perfection
- API_Cache provides resilience when LIS API is offline
- Mismatch detection catches state machine errors without stopping processing
- Noise filtering happens AFTER state machine updates (so memory stays correct)
- Ledger-Updates collapse happens BEFORE dedup (so phantom committees merge properly) and gates off the `Origin` column, not the Time string, so provenance survives the rename (PR-A)
- Viewport slice exempts `Origin in {system_alert, system_metrics}` from the `scrape_start..scrape_end` window so meta rows (stamped with the run timestamp, not investigation dates) actually reach Sheet1 (PR-B, see [[failures/gemini_review_patterns]] #36)
