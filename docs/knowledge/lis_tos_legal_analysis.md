---
tags: [knowledge, compliance, legal, lis, terms, analysis]
updated: 2026-08-01
status: active
---

# The LIS terms, analysed — what the law around them actually is

**NOT LEGAL ADVICE.** No lawyer wrote this and nobody here is one. It is a map of the doctrines a real
attorney would apply, written so the question put to DLAS (or to counsel) is sharp instead of vague.
[[knowledge/lis_tos_commercial_use]] holds the clause itself and the practical status.

---

## 1. Virginia does not own this data, and cannot

Two settled doctrines say so.

**Government edicts.** *Georgia v. Public.Resource.Org* (2020) held that officials empowered to speak with
the force of law **cannot be "authors"** of works made in their official capacity, so those works get no
copyright. The Court applied it to legislative material specifically — *"the doctrine applies to whatever
work legislators perform in their capacity as legislators, including explanatory and procedural materials
they create in the discharge of their legislative duties."* Bill text, histories, votes, committee actions
sit squarely inside that. ([opinion](https://www.supremecourt.gov/opinions/19pdf/18-1150_7m58.pdf) ·
[Justia](https://supreme.justia.com/cases/federal/us/590/18-1150))

**Facts are not copyrightable.** *Feist* (1991). A bill number, a date, a vote tally, a committee
assignment are facts. A compilation earns only thin protection for original *selection or arrangement* —
and a chronological dump of every action is close to the least original arrangement possible.
([BitLaw summary](https://www.bitlaw.com/copyright/database.html))

**So there is no property right here to license.** Whatever the ToS is doing, it is not licensing
intellectual property, because there is none to license.

## 2. Then what IS the ToS doing? Restricting a pipe, not the water

It is a **contract**, and contract is a separate body of law from copyright. Courts have largely held that
copyright does **not** preempt contract claims, because a contract claim requires proof of an agreement —
an extra element beyond the copyright rights themselves. So a ToS can restrict what copyright cannot.
([Northwestern, copyright/contract preemption](https://wwws.law.northwestern.edu/research-faculty/clbe/events/roundtable/documents/rub_copyright_and_contracts_meet_and_conflict.pdf))

**The consideration you received is the convenience**, not the data: a key, a maintained REST endpoint,
uptime, structured JSON. That is a real thing to bargain for, and accepting terms for it is ordinary.

**The consequence a lawyer would flag immediately:** the restriction attaches to the **channel you accepted
terms on**, not to the underlying facts. Obtain the same facts another way and you never entered that
bargain. Which raises the question the vault has already isolated: the **bulk CSV downloads require no key,
no registration, and no assent**. Contract formation needs offer, acceptance and consideration; a file
served over plain HTTP with no gate is closer to *browsewrap*, which courts treat sceptically absent
conspicuous notice and manifested assent. **Do not self-certify this — but it is the right question to ask.**

## 3. "Non-commercial" is undefined, and that cuts our way

The ToS never defines it. In a dispute a court would reach for ordinary meaning and context, and there are
at least two live readings:

- **Narrow** — do not resell the data itself, do not build a product whose value *is* redistributing it.
- **Broad** — no use touching any revenue-generating activity at all.

**The doctrine that matters here is *contra proferentem*: ambiguity in a contract is construed against the
party that drafted it** — and this is a pure adhesion contract, offered take-it-or-leave-it with no
negotiation. **DLAS drafted the ambiguity, so DLAS generally wears it.**

A second point a lawyer would raise: the broad reading proves too much. Under it, a journalist paid a salary
could not use the API, nor could a law firm, nor a university with a commercial research arm. Readings that
absurd are disfavoured.

**None of that makes selling on it safe.** It makes the term *arguable*, which is a reason to get it
answered in writing, not a reason to proceed on a hopeful reading.

## 4. The FOIA tension — this is the strongest structural point

Virginia FOIA **explicitly permits commercial use** of public records: a request *"is not invalid because it
is made for a purpose other than to monitor government operations, and it is permissible for a citizen to
secure information under the Act for commercial purposes."* It requires **no statement of purpose** and
imposes **no restrictions on use of records**.
([Reporters Committee](https://www.rcfp.org/open-government-guide/virginia/) ·
[NFOIC](https://www.nfoic.org/virginia-foia-laws/) ·
[VA FOIA](https://law.lis.virginia.gov/vacodepopularnames/virginia-freedom-of-information-act/))

So the same Commonwealth says, through two instruments:
- **FOIA:** you may have these records and use them commercially, and we may not ask why.
- **ToS:** personal and non-commercial use only.

**They are not formally in conflict, because they govern different things** — FOIA governs a *right to
records*, the ToS governs *a convenience service*. But the practical upshot is sharp: **a term of service
cannot shrink a statutory right.** The general principle in the public-records literature is that a
government entity may not use downstream terms to deny access, and material accessible under FOI laws
should be released without contractual restrictions on redisclosure.
([Nieman Lab](https://www.niemanlab.org/2010/04/when-public-records-are-less-than-public-how-governments-try-to-use-copyright-to-limit-access-to-data/))

**Framed for the DLAS conversation:** the question is not *"may we use Virginia legislative data
commercially"* — FOIA already answers that yes. It is *"what is the right CHANNEL for a commercial user."*
That is a far easier question for a help desk to say yes to.

## 5. §9 — revocation at will

> "DLAS may terminate this agreement for any reason at any time… with or without prior notice."

**Legally unremarkable** for a free service — an at-will clause in an adhesion contract with no fee is
normal, and a court would not find it unconscionable on its own.

**Commercially, it is the single biggest dependency risk in the project**, and it is worse than a vendor
risk: there is no competitor to switch to, because Virginia is the only source of Virginia's legislative
record.

**But it is bounded by §4 above.** Revoking API access removes the *convenience*; it cannot remove a FOIA
right to the records. The fallback is slower and uglier — and it is a fallback. **This is the real argument
for keeping the bulk-CSV path alive** ([[knowledge/legacylis_csv_route]]) rather than letting the product
become API-only.

## 6. Is Virginia unusual?

**Somewhat, and not in a flattering direction.** Open States grades all 50 states on legislative-data
openness against the Ten Principles for Opening Up Government Information, scoring higher for
machine-readable bulk downloads and lower where scraping is required
([report card](https://open.pluralpolicy.com/reportcard/)).

Points of comparison worth noting:
- **New York** runs *Open Legislation*, a public REST API over its bill-drafting data
  ([docs](https://legislation.nysenate.gov/static/docs/html/index.html)) — and it is the second state in
  this project already ([[ny/README]]).
- **Open States / Plural** redistributes all 50 states' data in bulk, and its people dataset is **CC0
  public domain** — which is how this project got historical party data at all.
- That redistribution is itself the practical answer to *"how does any commercial tracker operate?"*:
  aggregators exist partly because primary channels impose terms like these.

**The honest read: gatekeeping a public record behind a non-commercial term is legally *permissible*
(contract, not copyright) and normatively awkward — and Virginia is neither the worst nor the best.**

## 6b. The exclusivity point — the strongest version of the argument (added 2026-08-01)

**Owner's question:** if the API carries fresher and better-formatted data than the CSVs, can DLAS still
call it a mere "convenience" and say the public record lives in the CSVs?

**First, the formatting half of the question: legally irrelevant, both ways.** Nice formatting is not
protected — a chronological action list has almost no original "selection or arrangement" under *Feist*,
and under *Georgia v. PRO* legislative work carries no copyright regardless. **But formatting is also not
what the restriction rests on.** The ToS is a contract about a service, not a claim of ownership, so
whether the output is tidy changes nothing. Set it aside.

**The freshness half is real but is the weaker argument.** MEASURED from LIS's own documentation: the bulk
CSVs are *"updated once an hour during Session"*, and `History.csv` *"once a day, overnight."* The API is
continuous. So the CSV channel lags. A DLAS lawyer answers this easily: **FOIA is a request-and-response
regime with a 5-working-day window (Va. Code § 2.2-3704), not an obligation to operate a real-time feed.**
Latency alone does not establish denial of a record.

**The EXCLUSIVITY point is the strong one, and it is a fact, not a theory.**

**VERIFIED 2026-08-01: several whole classes of public record are published ONLY through the gated API.**
Probed both bulk hosts for any CSV equivalent of the API's `Schedule` / `Calendar` services —
`Schedule.csv`, `Calendar.csv`, `Meetings.csv`, `MinutesBook.csv`, `Statistics.csv`, in both casings, on
`lis.blob.core.windows.net` and `legacylis.virginia.gov`. **All 404.**

Comparing the portal's 30+ API services against the 17 published CSVs, these record classes have **no bulk
equivalent at all**: `Schedule` (committee meeting times and locations), `Calendar` (floor calendars),
`MinutesBook`, `LegislationText` (full bill text — `Summaries.csv` is not the text), `LegislationVersion`,
`LegislationEvent`, `MemberVoteSearch`, `Statistics`.

**This matters to us concretely: the entire calendar product depends on `Schedule`, and there is no CSV
fallback for it.** The §9 termination hedge does not cover this data class.

**So the sharpened argument is not about speed or polish, it is about availability:**

> Virginia FOIA says purpose is irrelevant to entitlement and commercial use is permitted
> (§ 2.2-3704.A; *Associated Tax Service v. Fitzpatrick*). Meeting schedules are public records. They are
> published in exactly one place — an API whose terms exclude commercial use. A commercial user therefore
> has no route to that record class except individual FOIA requests, on a 5-working-day clock, for a
> calendar that changes daily. That is not a workable channel for that record.

**The honest counterarguments, which a DLAS lawyer would raise and which we should not pretend away:**

1. **FOIA obliges disclosure, not delivery mechanisms.** No court has held that FOIA requires an agency to
   run an API, and a slow channel is not a closed one.
2. **The ToS restricts use of the SERVICE, not of the records.** On that reading nothing stops a commercial
   user from FOIA-ing the same schedules; the terms simply do not grant the convenient route.
3. **We have not found a case holding that differential channel quality by purpose violates FOIA.** The
   argument is principled and untested, not settled.

**Which is exactly why this belongs in a question to DLAS rather than an assertion.** The productive form:

> *"Several record classes — committee schedules, floor calendars, bill text — appear to be published only
> through the API. If the API terms exclude commercial use, what is the intended channel for a commercial
> user to obtain those records?"*

That is answerable, factual, and does not require them to concede anything. **An agency asked that question
usually has an answer, because the alternative reading is one they would rather not defend.**

## 7. What a lawyer would actually tell you to do

1. **Do not rely on any of the above as a defence.** Arguable is not safe.
2. **Ask DLAS in writing**, framed as §4 suggests: not *may we*, but *what is the correct channel for a
   commercial user*. §6 already contemplates paid access, so a route probably exists.
3. **Keep the keyless bulk-CSV path working**, both as a §9 hedge and because it is the path least likely to
   carry these terms.
4. **Get a real opinion before the first invoice**, not before the next commit.
