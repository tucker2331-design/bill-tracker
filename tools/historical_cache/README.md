# Historical CSV cache (fetch-once)

Legacy LIS sessions, gzipped. **25.2 MB raw → 1.4 MB on disk.** These files are static (a finished session
never changes), so they are fetched once and committed.

```bash
python3 tools/historical_cache/fetch.py fetch                 # idempotent
python3 tools/historical_cache/fetch.py verify                # re-hash, no network
python3 tools/historical_cache/fetch.py verify --check-remote # confirm upstream unchanged
```

Read from Python:

```python
import sys; sys.path.insert(0, "tools/historical_cache")
from fetch import read_cached
text = read_cached("241", "Bills.csv")   # decompressed CSV text
```

**Cached:** `231` (2023 regular, 3,029 bills) · `241` (2024 regular, 3,595) · `242` (2024 special, 290).
**Not cached, deliberately:** `221` is PARTIAL (363 bills vs ~2,900 in the real 2022 session) — caching it
would let a backtest treat a 12%-complete session as whole. `211` and earlier 404.

Source, compliance, and schema notes: [`docs/knowledge/legacylis_csv_route.md`](../../docs/knowledge/legacylis_csv_route.md).
