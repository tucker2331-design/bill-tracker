---
tags: [workflow, doctrine, meta, process]
updated: 2026-07-06
status: active
---

# Reasoning doctrine — how we work (read at session start)

The Fable-vs-Opus gap on this project is **process, not knowledge**. These are the moves that produce
bank-grade work here. Imperative, non-negotiable. Distilled from the assumptions_audit + this brain (B-5).

1. **MEASURE before you fix.** Instrument the CURRENT behavior first — a plan's premise can be flat wrong.
   The #189 "fix" was a no-op until instrumentation showed the resolver was date-BLIND, not "unresolved"
   (audit #95). If you can't measure it, you can't ship it — and your metric needs a DENOMINATOR
   ([[workflow/source_miss_visibility]]).

2. **Verify the ROW, not the count.** A metric delta is a projection until you READ the produced rows on a
   run whose `headSha` provably contains the commit. #72's "4→1" was never real; the first true cold-start
   read was 6 (audit #74). Same for tests: assert exact output, not just a truthy verdict.

3. **Fail toward the safe state; fail OPEN on a gate.** A gate bug must only ever SLOW the system, never
   silence it. Every default resolves to the conservative action: unknown cadence → run at baseline;
   unreadable session → halt-and-alert, never guess; empty/malformed state cell → run, don't skip. A
   sentinel value must be DISTINGUISHABLE from a legitimate one (audit #15).

4. **Confirm before you advance or destroy.** Any "snapshot X, then move the pointer past / delete X" needs
   a verify step between the two — exceptions aren't the only failure mode; a silent partial success is
   worse (audit #97). This is the ethic behind copy-verify-then-delete.

5. **No silent fallback.** Every `except` returns a categorized, visible signal (alert/counter/log) — never
   a bare `pass`/`continue`. Categorize + route (Standard #4). A WARN that fires every cycle for >24 h is a
   bug signal, not a transient.

6. **Structural, not text.** Route on LIS's own codes / primary keys / refids. Text parsing is FORBIDDEN on
   the lobbyist-facing path (Standard #3) — internal diagnostics only, validated against structural data.

7. **Notify-only is the test (Standard #8).** If an alert's remediation is a foreseeable, mechanizable edit
   (add a code, move a tab, rotate a key), the system PERFORMS it and informs — a human is interrupted only
   when the world did something unprecedented. A designed-in annual human step IS routine maintenance.

8. **Read the brain first, write it back after.** Route by task ([[index]] → [[state/current_status]] →
   task page). Every lesson learned lands in `docs/` before the session ends — nothing is lost.
