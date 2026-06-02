---
tags: [failures, post-mortem, architecture, legacy]
updated: 2026-06-02
status: active
---

# Why the Legacy Calendar/Tracker Versions Failed

The repo carries several earlier full-app versions of the bill tracker that pre-date the current `calendar_worker.py` + `pages/ray2.py` architecture. They still run, but they are **relative failures** — superseded for concrete, repeatable reasons. This page captures *why*, so (a) nobody resurrects their patterns, and (b) the forward-calendar / real-work build ([[ideas/future_improvements]]) doesn't repeat them.

Audited 2026-06-02 (owner ask: "look at those, see why they are bad").

## The files

| File | ~Lines | Last touched | What it was |
|------|--------|--------------|-------------|
| `app.py` | 1,606 | 2026-01-21 | First all-in-one Streamlit app (UI + scrape + classify + Slack alerts in one file) |
| `shadow_v2.py` | 990 | 2026-02-19 | "v2" rewrite of `app.py`; same patterns, trimmed |
| `pages/v2_shadow_test.py` | 680 | 2026-03-18 | v2 shadow front-end (lobbyist bill page); still referenced in CLAUDE.md as the *future* main product, but the **code** is legacy-pattern |
| `backend_worker.py` | 288 | 2026-03-22 | "Enterprise Ghost Worker" — v2's headless worker |
| `xray.py` | 275 | 2026-04-02 | First X-Ray; **DEPRECATED** — superseded by `pages/ray2.py` (+ diff-identical `calendar_xray.py`) |

> The current calendar subsystem (`calendar_worker.py`, `structural_router.py`, `pages/ray2.py`) is the line that escaped these failure modes. `pages/v2_shadow_test.py` + `backend_worker.py` are slated for a rework to absorb the calendar subsystem's advanced material before any merger (see [[state/current_status]]).

## The failure modes (shared across all of them)

### 1. Text-driven classification — the cardinal sin (CLAUDE.md Standard #3)
Every legacy version classifies bill state and calendar actions by substring-matching free-form outcome text. Concrete (`app.py`):
```python
if "agreed to by senate" in hist or "passed senate" in hist: return "✅ Passed (Resolution)"
if any(x in status for x in ["enrolled", "communicated to governor", "bill text as passed"]): ...
out_keywords = ["reported", "passed", "agreed", "engrossed", ...]
```
**Structural-identifier reference count across ALL five files = 0** — none use `History_refid` / `refid`, `EventCode`, `ReferenceType`, `COMMITTEE_CODE_MAP`, or `build_committee_maps()`. This is exactly the architecture that produced the **994 false "meeting bugs"** in the PR-C6 stress test ([[failures/assumptions_audit#55]]) — substring lists break the moment new vocabulary enters HISTORY, and `"passed senate"` matches the admin "Bill text as passed Senate" document rows. The current worker's whole reason for existing is to route on LIS's own structural fields instead ([[failures/assumptions_audit#57]], [[failures/assumptions_audit#58]]). **Lesson for forward-calendar:** consume the Schedule API's structural fields (meeting time, committee code, `IsCancelled`), never parse a meeting out of text.

### 2. Hardcoded session code — breaks every January (Standard #1 + #5)
`app.py`, `shadow_v2.py`, and `pages/v2_shadow_test.py` all hardcode the 2026 session into URLs and blob paths:
```python
LIS_BASE_URL = "https://lis.blob.core.windows.net/lisfiles/20261/"     # app.py:33, shadow_v2.py:17
lis_link = f"https://lis.virginia.gov/bill-details/20261/{bill}"        # ×7 across the files
```
`20261` is the session id. These apps **cannot survive the 2027 session without a code edit** — a direct violation of Standard #5 (session codes derived from LIS APIs at runtime) and Standard #1 (zero hardcoding of values an authoritative source provides). The current `calendar_worker.py` resolves the active session at runtime (`get_active_session_info()`), which is why it carried from the 2026 session into off-season testing untouched. **Lesson:** the forward-calendar's session id and all LIS URLs must come from the runtime session resolver, not a literal.

### 3. Silent failures everywhere (Standard #2 + #4)
Bare `except:` / `except: pass` counts: `app.py` 10, `shadow_v2.py` 11, `pages/v2_shadow_test.py` **15**. Samples:
```python
except: pass                              # v2_shadow_test.py:54,152,162,181,214
except: df_bugs = pd.DataFrame()          # v2_shadow_test.py:97  (swallows the read, hides the gap)
except: subs_df = pd.DataFrame(...)       # v2_shadow_test.py:476
```
Every one of these is a place a source-miss or API failure vanishes with no counter, no alert, no categorization. This is the precise anti-pattern the [[failures/pr22_post_mortem|PR#22 post-mortem]] and the [[workflow/source_miss_visibility|source-miss visibility]] rule exist to kill, and why the current worker has the `SYSTEM_METRICS` row, `Bug_Logs`, the `Origin` column, and `push_system_alert` categorization. **Lesson:** the forward-calendar's new row shape (`scheduled_future`) needs the same visible-miss discipline — a fetch that returns nothing must increment a counter, not silently produce an empty calendar.

### 4. Unthrottled polling — the API-ban risk, in code
`pages/v2_shadow_test.py:16`:
```python
st_autorefresh(interval=300000, limit=None, key="lobbyist_auto_sync")
```
A browser-side 5-minute auto-refresh, **per open tab, with no limit** — every viewer's browser independently hammers the data source. There's no rate-limit awareness, no backoff, no quiet hours. This is the exact LIS-WAF-ban exposure the owner flagged in 2026-06; the current architecture answers it with a single scheduled worker, the armored session + backoff, the 500/cycle hydration cap, and (PR-C7.1f) reduced cadence + overnight quiet hours. **Lesson:** never put data-fetching on a client-driven auto-refresh; one paced server-side worker writes to the sheet, and clients read from it.

### 5. Fragmented data stores + no circuit breaker
Three different Sheet IDs across versions (`18m752…` shadow_v2, `1566pCv…` backend_worker, `1PQDt…` current) — no single source of truth, state scattered. None have the mass-violation circuit breaker, the `meeting_unsourced` delta-vs-baseline guard ([[failures/assumptions_audit#53]]), or the LegEvent persistent cache. A bad scrape in these versions writes straight to the sheet with no "stop and alert on anomalous data" gate (Standard #2).

## One-line verdict per file
- **`app.py` / `shadow_v2.py`** — monolith era: text classification + hardcoded session + Slack + silent excepts. Architecturally pre-everything. Keep only as historical reference.
- **`pages/v2_shadow_test.py` / `backend_worker.py`** — the v2 front-end + worker. The *role* (lobbyist bill page) is still wanted, but the *code* must be reworked onto the calendar subsystem's structural + zero-trust foundation before merger, not extended as-is.
- **`xray.py`** — superseded by `pages/ray2.py`; deprecated, safe to ignore (do NOT edit it — edit `pages/ray2.py` and mirror to `calendar_xray.py`).

## The throughline
Every legacy failure mode maps to a CLAUDE.md Standard the current architecture was built to satisfy: **#3 structural-not-text, #5 runtime config, #2/#4 no-silent-failures + circuit breakers, #1 zero-hardcoding.** They are the "before" picture that justifies why the current worker is shaped the way it is — and the checklist the forward-calendar build must clear before it ships.
