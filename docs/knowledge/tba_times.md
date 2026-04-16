---
tags: [knowledge, lis, api]
updated: 2026-04-16
status: active
---

# Schedule API "Time TBA" Quirk

Migrated from global `~/.claude/.../memory/project_tba_discovery.md` on 2026-04-16.

## What

The VA LIS Schedule API returns `"Time TBA"` for many entries. `SortTime` can be concrete (e.g. `12:01`) while the user-facing `Time` field is `"Time TBA"`. Existence of an API entry ≠ existence of a concrete time.

## Why it mattered

Earlier validation tests checked "did we find a Schedule API entry for this date+committee?" (yes) rather than "does the entry have a real time?" (no). TBA entries slipped through as successful matches, then the worker's downstream `has_concrete_time()` check dropped them into Ledger. The `1,212` bug count at the time was unchanged after matching improvements because matching was not the bottleneck.

## Two root causes for the 1,212

1. Floor actions missing convene times (~979).
2. Committee entries with TBA times (~233).

## How to apply

When validating Schedule API matching, check for **concrete** times, not just entry existence. Use `has_concrete_time()` / `_is_non_concrete_time()` helpers (see [[failures/assumptions_audit]] #33 for why the helper is module-level, not nested).

The overwrite-protection logic added in PR#16 (see [[failures/assumptions_audit]] #35) keeps a concrete time from being clobbered by a later TBA duplicate in `api_schedule_map`.

## Related pages

- [[knowledge/lis_api_reference]] — full API reference
- [[architecture/calendar_pipeline]] — time resolution priority list
