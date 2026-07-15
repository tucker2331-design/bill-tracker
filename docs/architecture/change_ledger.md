---
tags: [architecture, change-ledger, product, plan, worker, frontend]
updated: 2026-07-15
status: active
open_loop: live wiring + the Changes tab are 2027-in-season-gated — differ is built+proven, integration specced here
---

# The Change Ledger — architecture + activation plan

The user-facing **"Changes"** tab answers *"what's different since I last looked?"* with the exact before →
after per delta. Product rationale + owner decisions: [[ideas/lobbyist_jtbd_ideation]] §8b/§8d. Register
visual spec (LOCKED, monochrome): [[design/dashboard_and_visual_language]] "the change-register pattern" +
the v2 mockup (https://claude.ai/code/artifact/17b5817d-247c-4007-9da8-45eeb093ab56).

## What is BUILT vs GATED (read first)

- ✅ **BUILT + proven now:** `tools/change_ledger/differ.py` — the pure, source-agnostic diff (history /
  schedule / docket), keyed on structural identity, 19 golden tests (`test_change_ledger_differ.py`). This
  is the hard, error-prone core and it is done + verifiable independent of any live data.
- ⛔ **GATED to the 2027 session (deliberately NOT shipped this session):** the live job that feeds the
  differ real snapshots + writes the `Change_Ledger` tab, and the frontend Changes tab. **Why gated:** the
  ledger's behavior can only be VALIDATED with in-session change data (off-season 2026 is static; the 2026
  session is past the 90-day witness retention). Shipping a live feed we cannot validate — or a hollow empty
  tab pre-launch — would violate "measure before you ship / no unvalidated live code" and the product's
  honesty ethic. The plan below is airtight so activation is mechanical when the 2027 session opens.

## The architecture (chosen for ISOLATION from the accuracy path)

**Decision (deviates from the build-wave README's "integrate into the worker"):** the live ledger job runs as
a **separate, worker-isolated tool**, NOT in `calendar_worker.py`'s hot path. Rationale: the worker is the
crown-jewel-risk file (the 0→66 saga, [[failures/assumptions_audit#105]]); the ledger is additive telemetry,
not accuracy; and adding a snapshot-load + diff + two-tab-write into the cycle — verifiable only via slow CI
runs, no local creds — is exactly the risk profile that burned us. A separate job keeps the accuracy path
literally unable to regress. Per-cycle fidelity is preserved by triggering the job on `workflow_run` **after**
each successful worker run (it reads the state the worker just produced).

```
worker cycle completes ─▶ (workflow_run) ─▶ change_ledger/build.py
                                              1. load PRIOR snapshot (Change_Ledger_Snapshot tab, VA·Live)
                                              2. read CURRENT state (see sources below)
                                              3. differ.diff_* (the proven pure core)
                                              4. append deltas → Change_Ledger tab (VA·Live, gviz-readable)
                                              5. rewrite the snapshot; retention-prune the ledger (90d)
```

### Data sources (each delta kind → its structural source)
| Kind | Source of truth | Identity key | Notes |
|---|---|---|---|
| `history_added/edited/removed` | **HISTORY.CSV** (the job fetches it independently, like `tools/reconciliation/`) | `(bill, date, History_refid)` | refid is the ONLY place a tally EDIT is distinguishable from remove+add (Sheet1 drops the raw refid — verified 2026-07-15). |
| `schedule_time_moved/cancelled` | **`Schedule_Witness`** (already computed by the worker every cycle) | `(date, committee)` | The witness already IS this diff — the job READS its deltas, doesn't recompute. Witness lives in VA·Ops after auto-shard → the job needs the service account. |
| `docket_added/removed` | **DOCKET.CSV** snapshot diff | `(date, committee) → {bills}` | new source-snapshot; bounded. |
| `unclassified_change` | fallback | — | any detected change the differ can't type → generic-but-true row + a `DATA_ANOMALY` drift canary (mirror the agenda-label canary). |

### `Change_Ledger` tab schema (VA·Live, append-only, gviz-readable by the frontend)
`DetectedAtUTC | Kind | Bill | Committee | DateKey | OldValue | NewValue | Refid | RunID | Session`
- `DetectedAtUTC` is **our detection time** (when the job saw the delta), never presented as "when LIS acted"
  (C2 honesty; the frontend renders it MUTED grey, not accent — accent time = a real meeting clock).
- Retention 90d via a prune mirroring `tools/witness_retention/prune.py` (contiguous ISO prefix), registered
  in the sustainability audit + a new `RETENTION_DAYS` entry.
- Fail-open: any ledger error is a categorized WARN; it can never block a worker cycle (separate job anyway).

## Validation plan (how we PROVE it before trusting it — 2027)

1. **Now (done):** 19 golden tests on the differ, incl. the marquee same-refid tally-edit case + the
   no-refid honesty case.
2. **Pre-2027 dry run (no user exposure):** run `build.py` for a week of real cycles at session open with the
   frontend tab NOT yet in the nav; read the `Change_Ledger` rows and hand-verify a sample against LIS
   (verify-the-row, [[failures/assumptions_audit#74]]). Also: replay TWO real Sheet1/HISTORY snapshots from
   the **session archive** (VA·Archive keeps per-session output) a day apart and confirm the differ's output
   matches a hand diff — a real-data test without waiting for live change.
3. **Ship the tab** only after the dry run's rows are verified correct on live data.

## The frontend (L2) — spec (build at activation)
- New nav tab **Changes** → `web/src/views/Changes.tsx` + `web/src/data/ledger.ts` (gviz read of
  `Change_Ledger`, copy the fetch/parse discipline of `data/health.ts`).
- Render EXACTLY the register: the product's own What's-new feedrow anatomy (accent time · small-caps grey
  KIND column · struck-old → bold-new), `drill-grouphdr` day headers, the "seen on your last visit" hairline
  from a `localStorage` marker (C3: "on this device"), filter pills with counts (All / Tracked / Record
  edits / Schedule). ZERO colored fills. Kind→sentence templates in ONE map with a `default` generic row.
- Empty (off-season): "No changes since <marker> — the legislature is quiet." (honest, designed).
- Do NOT add the tab to the live nav until the dry run (validation step 2) passes.

See also [[audits/build_wave_2026-07/README]] (TASK 1), [[ideas/lobbyist_jtbd_ideation]] §8d,
[[design/dashboard_and_visual_language]].
