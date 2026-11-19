---
tags: [ideas, multi-state, parity, pennsylvania, california, virginia]
updated: 2026-11-19
status: active
open_loop: PA (and CA) at Virginia's baseline — bill documents done 2026-11-19; full Health is engineering work left; summaries and vote predictions wait on owner decisions.
---

# Every state at Virginia's baseline (owner, 2026-11-19)

> *"now work on getting pa to the same baseline as va"*

Virginia is the base ([[ideas/drafting_war_room]] §0: "if it's happening to PA it gets added to VA", and the reverse
holds for the baseline). What Virginia's site has, and where PA and CA stand:

| Virginia has | PA | CA | what it takes |
|---|---|---|---|
| bills, search, timeline, chamber map, calendar, War Room positions + contact log | ✅ | ✅ | — |
| a link to the bill on the state's site | ✅ **2026-11-19:** the bill's own documents from the export: current text, the sponsor's memo (its own title, e.g. HB17 "Mandating Cursive Handwriting"), House/Senate fiscal notes, IFO actuarial notes. 5,267 / 5,269 bills | ❌ pubinfo carries no bill URL; leginfo is bot-challenged and never fetched, so no address is guessed | CA: only if Legislative Counsel publishes a URL field |
| official bill summaries | ❌ PA's bulk feeds carry none; the sponsor's memo title is the nearest plain-language line (now shown) | ❌ pubinfo has none (the analyses in `BILL_ANALYSIS_TBL` are committee staff analyses, not summaries) | **your decision:** write summaries by reading bill text (an AI read; Virginia costed ~$4–8 per 11.6k summaries, [[testing/pa_replication]]), or stay with the memo title |
| vote predictions (member calls) | ❌ model tested: 89.2% vs always-yes 87.5% (2025–26); 97.7% on the most confident two thirds; crossover AUC 0.822 | ❌ 88.2% vs 88.3% (no gain overall); crossover 0.676 ([[testing/ca_replication]]) | **your decision:** PA only gains on contested votes. Showing calls there needs a live member-vote feed (Open States CSVs, refreshed by hand today) |
| **bill-fate stats** | ✅ **level 2026-11-19:** clean (filing-day seats) 0.791 / 0.820; with co-sponsors 0.809–0.843 vs Virginia 0.676–0.809 by year ([[testing/pa_replication]] round 3) | tested, weaker: 0.705 / 0.763 (the first committee is not CA's gate) | — |
| full Health (guard jobs, incident log, days clean, breaker) | basic (intake checks) | basic (intake checks) | engineering: an independent re-check job per state + an incident log; also what the admin role unlocks ([[ideas/state_admin_role]]) |
| bill detail link "Bill and history on LIS" | memo/text links instead | — | — |

## Next, in order
1. **Full Health for PA and CA:** each state gets an independent guard job (re-reads the source on its own and
   compares with the published sheet, like Virginia's reconciliation guard) and an `Incident_Log`. Then their
   Health can switch to "full".
2. Your two decisions: summaries (AI read of bill text vs the memo title) and PA vote predictions (contested votes
   only vs none).
