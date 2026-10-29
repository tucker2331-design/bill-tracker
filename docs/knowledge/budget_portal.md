---
tags: [knowledge, lis, budget, source]
updated: 2026-10-23
status: active
---

# LIS State Budget Portal (budget.lis.virginia.gov) — probed 2026-10-23

Owner OK'd a source check (budget amendments = a public trace of "the same idea goes in the budget, so the bill is
dropped"). 11 requests, 3 s apart, User-Agent names the project.

- **robots.txt:** none (the URL returns the site's 404 page) — no crawl rules. Pages carry `meta robots noindex`.
- **Owner:** DLAS (same as LIS) — treat under the LIS rules: 2025/2026 only, > a dozen requests needs the five
  guardrails ([[knowledge/lis_api_safety]]), and LIS ToS "personal and non-commercial use only"
  ([[knowledge/lis_tos_commercial_use]]).
- **Web service:** `https://budget.lis.virginia.gov/BudgetPortalWebService/help` (XML). Member amendment requests are
  status `MR` on the budget bill (2026: HB30 / SB30; 2025: HB1600 / SB800), e.g.
  `Budget.Amendments.2.ListOfAllItems/2026/1/30/HB/MR/`.
- **Quirk:** every ListOfAllItems call tried (2026 HB30/SB30, 2025 HB1600/SB800, status MR) returned an EMPTY list
  (286 bytes, PartNumber 0); `Budget.Amendments.1.ListOfYearSessionAmendment/` also returned empty. The data is on
  the HTML pages (`/amendments/2026/1/HB30/Introduced/MR/`, "Patron Order" / "Item Order" PDFs). Not fetched: that
  would pass a dozen requests and needs the guardrails and the owner's OK.
- Cached: `tools/historical_cache/va_budget/` (the empty XML replies, for the record).
- Open question before use: the DATE member requests become public vs. first-vote dates (if after, they are not a
  pre-vote signal).
