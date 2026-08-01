# MEMORANDUM

**To:** Director
**From:** Tucker Ward
**Date:** 1 August 2026
**Re:** Virginia LIS API terms of service — non-commercial use restriction. Decision requested on whether to involve counsel.

---

## 1. Purpose

The Virginia Legislative Information System (LIS) API, which supplies the legislative data behind our bill-tracking tool, carries a terms-of-service clause restricting use to "personal and non-commercial" purposes. **We are currently well inside that restriction.** This memo sets out the facts so you can decide whether to obtain a legal opinion before any future step that could be characterised as commercial.

**No action is urgent. Nothing is being sold, and no revenue is being generated.**

---

## 2. The clause

From the LIS API Terms of Service, §2:

> "The Services are offered for your **personal and non-commercial use only**, and you are prohibited from using, and are expressly not granted the right to use, the Services for any other purpose."

"Services" is defined in the preamble as "any of its APIs … that links or refers to the Terms."

Two further provisions are relevant:

- **§6** — "We may charge for access to portions of the Services or to the Services as a whole … we will notify you in advance, and give you an opportunity to subscribe." **The terms expressly contemplate paid access.**
- **§9** — "DLAS may terminate this agreement for any reason at any time … with or without prior notice."

---

## 3. Current status — the facts

| | |
|---|---|
| What the tool does | Tracks Virginia General Assembly bills; reads public legislative records |
| Who uses it | The author, plus two associates who have used it occasionally for testing |
| Is it sold? | **No.** No revenue, no customers, no pricing, no offer to sell |
| API credentials | Held in encrypted secrets storage; **never shared with any person** |
| Data used | Public legislative records only — bills, votes, committee actions, member rosters |
| LIS user data | **None.** §4 restricts extraction of LIS user/watchlist data; we do not access it |
| Request volume | Rate-limited, cached, throttled, with quiet hours, to comply with §4's load provision |

**One prior compliance issue, self-identified and closed.** In June 2026 an internal audit found that a one-time internal test had queried the API for sessions before 2025, which the Developers Portal does not authorise. It was read-only, was never part of the running system, and nothing was redistributed. It was corrected the same day and the tool now fails at runtime if pointed at an unauthorised session. **We were not contacted by DLAS about this, before or since.**

---

## 4. What we verified directly

Each item below was checked on **1 August 2026**.

**a) The Developers Portal restricts the API by session year — and the wording has recently changed.** It now reads:

> "API usage is authorized and validated for **session data from 2025 onward**. The General Assembly has not authorized the usage of data from sessions prior to 2025 to be extracted with this API toolset. If you require data prior to the 2025 session, please use legacylis.virginia.gov via CSV download."

Our internal records from June 2026 quoted this as "2025 and 2026 session data only." **The current language is open-ended going forward.** We comply with both readings.

**b) Virginia FOIA permits commercial use of public records.** Per the Reporters Committee for Freedom of the Press *Open Government Guide* (Virginia), citing **Va. Code Ann. § 2.2-3704.A** and *Associated Tax Service v. Fitzpatrick*:

> "The purpose or motivation behind a request is irrelevant to a citizen's entitlement to requested information."
> "A request under the Act is not invalid because it is made for a purpose other than to monitor government operations. It is permissible for a citizen to secure information under the Act for commercial purposes."
> "The Act does not restrict the use of the information obtained."

**c) Virginia holds no copyright in this material.** In *Georgia v. Public.Resource.Org*, 590 U.S. ___ (2020), the Supreme Court held that officials empowered to speak with the force of law cannot be "authors" of works produced in their official capacity, and that the doctrine reaches "whatever work legislators perform in their capacity as legislators." Separately, under *Feist Publications v. Rural Telephone* (1991), facts are not copyrightable.

**The practical consequence:** the restriction we are discussing is a **contract term attached to a convenience service**, not an assertion of ownership over the data. Virginia has no property right in the underlying records to license or withhold.

---

## 5. What we could not verify, and what is genuinely uncertain

**We could not independently retrieve the Terms of Service page.** The LIS site is a JavaScript application and the terms link does not resolve to a fetchable URL. **The clause text in §2 above is as supplied by the author from the terms presented at API registration.** Anyone relying on this memo should confirm the current text directly. Note that §1 permits DLAS to change the terms at any time.

**A material fact bearing on all of this, verified 1 August 2026:** several classes of public record appear to be published **only** through the API. We probed both bulk-download hosts for any CSV equivalent of the API's `Schedule` and `Calendar` services — committee meeting times, floor calendars, chamber minutes, full bill text — and found none. Comparing the portal's 30+ API services against the 17 published CSV files, at least eight record classes have no bulk equivalent.

This weakens the characterisation of the API as a mere convenience layered over otherwise-public files, and it is the point most worth putting to DLAS. It also means our §9 continuity hedge does not cover meeting-schedule data, which the calendar feature depends on.

**Three questions we are not qualified to answer:**

1. **What "non-commercial" means here.** The term is not defined in the agreement. A narrow reading (do not resell the data) and a broad reading (no revenue-adjacent use at all) are both available on the text.
2. **Whether the restriction reaches the bulk CSV downloads.** Virginia also publishes many of the same records as static CSV files requiring no key, no registration, and no acceptance of terms. Whether those fall within "the Services" is a real question. **We are not treating them as exempt.**
3. **Whether a terms-of-service clause can narrow a statutory FOIA right.** FOIA grants a right to records; the terms govern a service. They are not formally in conflict, but the interaction is not something we should resolve internally.

---

## 6. Assessment of current exposure

**Low, in our view, for three reasons:**

1. The tool is not sold, generates no revenue, and has no customers. On any reading of "non-commercial," present use appears to fall inside it.
2. The underlying records are public and obtainable by other lawful means that carry no such restriction.
3. Virginia asserts no ownership of the data, so the exposure is contractual only — and the remedy for a breach of a free service agreement is ordinarily termination of access under §9, not damages.

**This is our assessment, not a legal opinion.**

---

## 7. The risk that is real today, independent of the commercial question

**§9 permits DLAS to terminate access at any time, without notice.** There is no alternative supplier of Virginia's legislative record. If access were withdrawn, the product would lose its live data feed.

This is a business-continuity risk rather than a legal one, and it exists whether or not we ever charge anyone. We are mitigating it by keeping a second, keyless data path (the public CSV downloads) working alongside the API.

---

## 8. Options

| | Option | Cost | When |
|---|---|---|---|
| **A** | Ask DLAS directly what channel is appropriate for a commercial user | One email | Now |
| **B** | Obtain a legal opinion on §2 and on the FOIA interaction | Counsel time | Before any revenue |
| **C** | Do both — ask DLAS first, brief counsel with their answer | Both | A now, B on their reply |
| **D** | Do nothing until we decide to charge | None | Deferred |

**On Option A:** because §6 already contemplates paid access, the productive question is not *"may we use this commercially"* — FOIA already permits commercial use of the records — but *"what is the correct channel and licence for a commercial user."*

Given the finding in §5, the enquiry is strongest phrased factually:

> "Several record classes — committee schedules, floor calendars, bill text — appear to be published only through the API. If the API terms restrict use to personal and non-commercial purposes, what is the intended channel for a commercial user to obtain those records?"

That is answerable without requiring DLAS to concede anything. Contact: helpdesk@dlas.virginia.gov, (804) 786-9631.

---

## 9. Recommendation

**Option C.** Send the DLAS enquiry now, at no cost and no commitment. If the answer is a clear commercial route, the matter closes. If the answer is unclear, adverse, or slow, brief counsel with a concrete record rather than an abstract question.

**Do not defer past the point of first revenue.** The clause is unambiguous enough on its face that proceeding to sell without resolving it would be an avoidable risk, and a favourable resolution appears reasonably likely.

---

### Appendix — sources

- LIS Developers Portal, https://lis.virginia.gov/developers (session-authorisation language, read 1 Aug 2026)
- LIS API Terms of Service §§1, 2, 4, 5, 6, 9 (text as supplied at registration; page not independently retrievable)
- Va. Code Ann. § 2.2-3704.A; *Associated Tax Service v. Fitzpatrick* — via Reporters Committee for Freedom of the Press, *Open Government Guide: Virginia*, https://www.rcfp.org/open-government-guide/virginia/
- *Georgia v. Public.Resource.Org, Inc.*, 590 U.S. ___ (2020), https://www.supremecourt.gov/opinions/19pdf/18-1150_7m58.pdf
- *Feist Publications, Inc. v. Rural Telephone Service Co.*, 499 U.S. 340 (1991)
- Virginia Freedom of Information Act, https://law.lis.virginia.gov/vacodepopularnames/virginia-freedom-of-information-act/
