---
tags: [testing, edge-cases, future-proofing, registry]
updated: 2026-06-07
status: active
---

# Edge-Case Registry (living)

Owner's concern (2026-06-07): *"we had a lot of bugs in that history — who's to say that's all of them and not just the ones from that specific session?"* This registry enumerates the edge-case **space** per pipeline stage (not just bugs that happened), so coverage is visible and proactive. Populated by the Phase-C multi-session replay (`tools/edge_case_replay/`). Status: ✅ handled · ⚠️ partial · ❌ open.

## How this was built (proactive, not reactive)
The 2026 bugs surfaced because we looked at 2026 data. To catch *unknown* classes, the replay runs the PURE functions (time parse, `classify_action`, `route_event`, modal derivation) against **all data LIS still serves** (Schedule API rolling window 2022–2026; per-session HISTORY.CSV for 2024, 2024-special, 2025). **Architectural finding:** LIS blob storage + the Schedule API are a **rolling recent window** — pre-~2022 sessions 404, so true historical replay is bounded to ~2022–2025 (relevant to any 50-state historical-backfill plan).

## Time / schedule parsing
| Edge | Status | Note |
|---|---|---|
| `00:00` / `04:00` / `05:00` doc-batch artifacts | ✅ | `[7,23]` window (#74) excludes all; unified router+recovery. |
| Relative "X min after [chamber] adjourns" | ✅ | #79 anchor + offset; derivation reuses it. |
| **`"8am"` (no colon), `"8:30AM"` (no space before AM/PM), lowercase** | ✅ **FIXED (PR-C7.1y)** | `parse_24h_time` `strptime('%I:%M %p')` fails → **`23:59` sort fallback** → meeting mis-sorted to end-of-day. Real current entries: Senate General Laws 1/23 (`8am`), Senate Education & Health 2/6 (`8:30AM`). **Same blind spot as #79** (has a time, so Section 9 never flagged it; the SORT is wrong). Fix: normalize (insert space before AM/PM, add `:00` when colon-less) before strptime. **→ post-#100 batch.** |
| `"Invalid date"` literal junk | ⚠️ | → `23:59`; rare LIS junk (Crime Commission 2025). Acceptable fallback but should be counted (Standard #4 visibility). |
| midnight-wrap (late adjournment + offset → 00:29) | ✅ | derivation bounds to `[7,23]` (#76). |

## Action classification (`classify_action` text fallback — Standard #3 residual)
The STRUCTURAL primary (`route_event` on ReferenceType/VoteTally/Status) is robust; text is the blank-route fallback. Multi-session replay (2024/2025) found **200+ unclassified TEXT templates** the fallback doesn't know — but `route_event` DOES classify them:
| Class | text fallback | structural `route_event` | Status |
|---|---|---|---|
| **Veto: "sustained Governor's veto" (×254)** | ❌ unclassified | ✅ `meeting (status_in_session)` | ⚠️ benign IF structurally routed; **verify the 2026 reconvened/veto-session production `unclassified` count is ~0** (Phase B). |
| Veto explanation / "items vetoed by the Governor" | ❌ | ✅ `admin (executive)` | ⚠️ as above |
| **Committee rename: "moved from X to Y due to a change of the committee name" (×75)** | ❌ unclassified | (admin milestone) | ⚠️ confirms the rename edge case; verify structural handling + the modal/normalize maps survive a rename across sessions. |
| `"enacted, chapter #"`, `"title replaced"`, `"readings waived"`, `"referred from X"` | ❌ unclassified | varies | ⚠️ ministerial law (#67) should absorb the milestone ones (≥20 untimed/unvoted); verify. |
**Net:** the structural core handles the new classes; the text FALLBACK is incomplete (the documented #3 caveat, now quantified). Real residual = rows that are BOTH blank-route AND text-unclassified — quantify in production (Phase B), don't paper over with a dictionary.

## derived_standing (the flagged last-resort)
| Edge | Status |
|---|---|
| weak plurality (no dominant modal) | ✅ majority rule (#76) |
| out-of-hours / midnight-wrap derived time | ✅ `[7,23]` bound (#76) |
| wrong anchor: "of X subcommittee/committee", "Commerce and Labor", hyphen/comma separators, formal names | ✅ allowlist of chamber forms via `[^()]+` capture (#76 + Gemini #100 r1/r2/r3) |
| "after recess" (non-adjournment relative) | ✅ declines |
| 50-state: "Senate"/"House", "adjourned" grammar, exclusion words | ❌ VA/English-specific (audit gap **G3**) |

## Cross-session / lifecycle
| Edge | Status |
|---|---|
| session rollover (cache overflow) | ✅ session-prune (#73) + schema-backfill (#75) |
| 2027 cold-start (empty cache, new committees/EventCodes) | ⚠️ dry-run pending (Phase C) |
| committee rename between sessions (modal/normalize keyed on old name) | ⚠️ see classification table; verify |
| special sessions (codes 2026**2**, etc.) | ⚠️ `_normalize_session_code_5d` handles 5-digit; verify blob_code + window for a special session |
| Schedule API / HISTORY.CSV rolling window (no pre-2022) | ✅ documented; bounds historical backfill |

## Open items → batched
- **B1 (bug):** ✅ FIXED (PR-C7.1y) — `parse_24h_time` normalizes no-colon/no-space/lowercase formats before strptime.
- **G1–G4:** the Standard gaps from `scalability_audit.md` (drift counter, derived volume guard, 50-state isolation, denominator).
- **V1 (verify, Phase B):** production `unclassified` count in the reconvened/veto session ~0 (structural route covers veto); committee-rename handling.
- **DR1:** 2027 cold-start dry-run.
