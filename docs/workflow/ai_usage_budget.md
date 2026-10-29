---
tags: [workflow, ai, budget]
updated: 2026-10-26
status: active
---

# AI helper-agent usage budget

Owner rules (2026-10-24 / 25): AI runs use the Claude subscription (helper agents), not the API; **never more than
$5 of paid credit**; stop before the 5-hour limit.

**Incident (2026-10-26):** 7 Opus helper agents were started at once while the usage meter read 4% of the 5-hour
window. The meter was stale: the window was already near its limit. The agents ran into paid extra usage and then
all stopped at the limit before writing any output. Extra usage reached **$10.73 — over the $5 cap — for no result.**
The owner was told at once.

**Rules from now on:**
1. At most **3 helper agents at a time**; check usage before every batch.
2. Treat the meter as lagging: stop launching at **70%** of the 5-hour window (not 85-90%).
3. One agent reading ~180 short items or ~25 packets costs about **3% of a 5-hour window** (measured 2026-10-26).
4. If extra usage is enabled, assume every overrun is paid; if `spent` moves at all, stop and tell the owner.
5. Agents write their output file only at the end — a stopped agent loses everything. Prefer smaller batches.

Related: [[testing/first_vote]] (AI tests), [[research/legislator_vote_prediction_survey]].
