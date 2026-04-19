---
tags: [knowledge, lis, scraping, tooling]
updated: 2026-04-18
status: active
---

# LIS Bill-Details DOM Scraping

How to get tier-A ground truth from `lis.virginia.gov` when APIs are incomplete or the browser MCP is unavailable.

## Why this matters

Per [[../CLAUDE.md]] and [[state/current_status]], LIS website is the **authoritative source** for calendar accuracy. Schedule API has gaps. HISTORY.CSV is raw but lacks committee meeting times. When accuracy questions cross what the APIs can answer, the website is the tiebreaker.

The Claude-in-Chrome extension has been broken Anthropic-side since early April 2026. This page documents the headless-Chrome bypass that unblocks all LIS website audits until the extension is fixed.

## The SPA problem

`lis.virginia.gov` is a Webpack-built React SPA. A plain `curl` or `WebFetch` returns the shell HTML (~3K bytes) with no bill history — the history lives in JavaScript-rendered components. To get the rendered DOM we need an actual browser.

## The headless-Chrome solution

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless=new \
  --disable-gpu \
  --virtual-time-budget=15000 \
  --dump-dom \
  'https://lis.virginia.gov/bill-details/20261/HB111' \
  > /tmp/lis_audit/HB111.html
```

Key flags:
- `--headless=new` — the 2023+ headless mode, actually renders SPAs properly. Old `--headless` is broken.
- `--virtual-time-budget=15000` — give the JS 15 seconds of "virtual" time to finish fetches. 25s if initial dump is under 15K bytes (hydration failed).
- `--dump-dom` — print the post-render DOM to stdout.
- `--disable-gpu` — headless convention; harmless.

Typical bill-details page renders to **20-50 KB** of DOM. If the dump is < 15 KB, rendering didn't complete — retry with a longer `virtual-time-budget`.

## URL structure

LIS URL pattern for bill details:
```
https://lis.virginia.gov/bill-details/<URL_SESSION_ID>/<BILL_NUMBER>
```
- `URL_SESSION_ID = "20" + session_code` — for session 261 (2026), use `20261`.
- `BILL_NUMBER` — e.g. `HB111`, `SB494`.

## DOM structure for history rows

Each history row:
```html
<div class="history-event-row ">
  <div class="history-event-data">
    <span>2/13/2026</span>
    <span>House</span>
  </div>
  <div class="history-event-info">
    <div class="history-event-description">
      <span><span>
        <a href="/session-details/20261/committee-information/H18/committee-details">H-Privileges and Elections</a>
        committee substitute printed 26107373D-H1
      </span></span>
      ...
    </div>
  </div>
</div>
```

The committee anchor (`<a href=".../committee-information/<CODE>/...">`) carries the structural committee code. Subcommittees use 5-digit codes (e.g. `H18001` = P&E Elections subcommittee).

> **Parser gotcha (learned the hard way during crossover audit):** the description uses NESTED `<span>` tags. A naive regex like `<div class="history-event-description"><span>(.*?)</span></div>` fails — the inner `</span>` is followed by the outer `</span>`, then junk (`<button>`, `<div></div>`, etc.), then `</div>`. The minimal-match then spans across row boundaries. The correct approach: **split the DOM on `<div class="history-event-row">` boundaries first, then parse each row segment with narrower regexes.** The segment boundary guarantees no cross-row contamination. Pattern in `tools/crossover_audit/extract_truth.py`.

## Parallel fetching

See `tools/crossover_audit/fetch_bills.sh`. Key pattern:

```bash
xargs -P 8 -I {} bash -c 'fetch_one "$@"' _ {} < bill_list.txt
```

8 concurrent Chrome processes. Full crossover-week scan (~2,000 bills) runs in 15-25 min wall time. Retries on dumps < 15KB.

## When NOT to use this

- **Don't scrape real-time.** For live worker runs, Schedule API + HISTORY.CSV are the right sources. DOM scraping is for **one-time audits** against frozen historical windows.
- **Don't scrape bill text / full contents.** Only structured history rows (date, chamber, committee, action, refid) are needed for calendar auditing.
- **Don't auto-trigger downloads.** The LIS page has "PDF" links for bill text and fiscal impact statements — we ignore them.

## Extractor

See `tools/crossover_audit/extract_truth.py`. Parses the `history-event-row` pattern, filters to a date window, emits structured JSON. Only keeps 5 fields per action (date, chamber, committee_code, committee_name, action text). DOM stays on disk, structured JSON enters the repo.

## Known failure modes

- **Dump under 10K bytes** — hydration didn't finish. Retry with `--virtual-time-budget=25000`. Observed ~1-5% of the time.
- **Dump contains the shell but no history section** — bill number likely invalid; check URL.
- **Committee code missing from anchor** — LIS occasionally renders actions without the link (seen for "Referred to Committee" boilerplate). Worker still matches via text parsing.

## See also

- [[knowledge/lis_api_reference]] — for live-run sources (Schedule API, HISTORY.CSV, DOCKET.CSV)
- [[testing/crossover_audit]] — the full-window audit that used this technique
- [[failures/pr22_post_mortem]] — why tier-A ground truth matters
