# Accuracy Sentinel

`accuracy_sentinel.py` is the **continuous, session-agnostic guardian** of calendar
accuracy. A one-time audit can't protect next session's new data; this runs the
**same** accuracy metric the X-Ray Section 9 uses — against the **live sheet**, on a
**daily schedule** — and **fails loudly** on any regression.

It extracts the real `classify_action` / `normalize_time` / `PLACEHOLDER_TIMES`
from `pages/ray2.py` at runtime, so it can **never drift** from production
classification, then checks four invariants (worker `SYSTEM_*` diagnostic rows
excluded):

| Invariant | Default gate | Why |
|---|---|---|
| **Section 9** — meeting rows without a time | `== 0` | the accuracy goal |
| **Unclassified** — legislative rows the classifier can't place | `== 0` | the goal's second half |
| **Floor** — legislative row count | `>= 5000` | partial/empty-sheet guard (lesson #75: "Section 9 = 0 on a 277-row sheet") |
| **Derived** — flagged assumed-time rows | `<= 25` | over-derivation guard (G2) |

```
python3 tools/verification/accuracy_sentinel.py     # exit 0 = pass, non-zero = regression
```
No secrets (live sheet via public gviz CSV). Runs as the `🛡️ Accuracy Sentinel`
workflow (daily cron + manual) — and in 2027 unchanged, because it reads whatever
session the worker wrote.

See also `tools/reconciliation/` (weekly diff vs the independent official minutes)
and [[architecture/verification_durability]] for the full three-layer guard.
