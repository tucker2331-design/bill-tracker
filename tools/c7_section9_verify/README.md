# c7_section9_verify

Production-faithful check of the X-Ray **Section 9** bug count (meeting actions
without times), run against the **live Sheet1** the worker writes.

```bash
python tools/c7_section9_verify/verify_section9.py          # human report
python tools/c7_section9_verify/verify_section9.py --json   # machine-readable
```

**Why it exists:** [[failures/assumptions_audit#62]] — PR #57/#58 were certified
by a sidecar tool (`full_validate.py`) that fetched LegislationEvents *fresh*,
so it never saw the worker's truncated cache and reported a collapse that
didn't happen in production. This script verifies against the **real
production artifact** instead:

- Reads live Sheet1 via the public gviz CSV — **no LIS API, no auth, read-only,
  zero LIS-ban exposure.** Safe to run anytime.
- Scores with the **exact** `classify_action` + pattern lists from the deployed
  X-Ray (`pages/ray2.py`), extracted via `ast` (Streamlit never runs; the
  classifier can't drift from production).
- Reports text-only vs route-aware Section 9, the route distribution on the
  flagged subset, and **LegEvent cache coverage** (the leading indicator).

**Use it AFTER re-hydrating the cache** (PR #61 + a ⏩ Backfill Burst or several
worker cycles). The `VERDICT` line refuses to call a drop while coverage < 95%
— it will say "cache still hydrating … do not declare the drop yet" rather than
repeat the premature-victory mistake of #62.
