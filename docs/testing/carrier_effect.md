---
tags: [testing, calibration, causal, carrier, copatron, retraction]
updated: 2026-09-11
status: active
---

# The carrier vs the caucus — and the co-patron retraction

## The objection (owner, 2026-09-11)

> "how likely is it that the party approved the policy in caucus and therefore the patron had little
> influence? how can we prove a patrons effectivety and not the work of the party whip or caucus behind
> closed doors."

And the same challenge aimed at the co-patron lever:

> "'recruiting a cross-party co-patron isn't random. The bills where a lobbyist can land that name may be
> the ones already closest to the line.' same idea here."

`python3 tools/calibration/carrier.py`

---

## 1. The vehicle contest — the process itself separates the two decisions

Virginia committees fold duplicate bills together: bill A is **incorporated by** bill B, A dies, B carries
the policy forward. At that moment **the merit question is closed** — the room has already decided to
advance the policy — and the only open question is **whose name is on it**. The caucus decision and the
carrier decision are separated by the process, not by a statistical adjustment.

**The graph is text-derived and structurally checked** (Standard #3: diagnostics only, nothing on the
lobbyist path reads it). 669 "incorporated by" edges; the named bill must exist in the same session;
**89% are reciprocated** by an "incorporates X" edge on the other side. The absorbing bill is recorded as
passed 84% of the time and the absorbed bill as failed 99% of the time — which is what the edge means.

**599 contests** are same-chamber, same-year, different patrons. **208** pit a majority patron against a
minority patron:

| | |
|---|---|
| the room keeps the **majority** member's vehicle | **172** |
| the room keeps the minority member's vehicle | 36 |

**83%. Odds 4.8 : 1. Sign p < 1e-16.**

### Both confounds are null

| | | |
|---|---|---|
| survivor has the lower bill number | 315/599 = 53% | p = 0.22 — **null** |
| survivor is the more senior member | 144/260 = 55% | p = 0.09 — **null** |

And the effect is *stronger* where those confounds work against it:

- contests the majority vehicle entered **later**: majority wins **91%** (97/107), p < 1e-16
- contests between members of **identical tenure**: majority wins **77%** (95/123), p = 2.7e-09
- 39 contests where the majority patron was the **junior** member and still won

### The placebo names the mechanism

In the **391 same-side contests** — where party cannot break the tie — neither seniority (57%, p = 0.07)
nor filing order (55%, p = 0.07) reaches significance. **Party is not overriding seniority and filing
order. It is the only thing in this data that predicts which vehicle the room keeps.**

**What this does and does not prove.** It rules out the strong form of the caucus story — that the patron
is a bystander once the policy is approved. It does not distinguish "the majority member is more effective"
from "the room prefers to hand credit to its own." **For a lobbyist those are the same instruction**: to
advance this policy, get it onto a majority member's bill.

---

## 2. Carrier effectiveness is measurable, and it is not the portfolio

If the caucus does the work, every majority patron is the same coin. Each bill's expected fate is
subtracted first — how **other** patrons' bills in the same session × subject × chamber fared, this
patron's own bills excluded from the benchmark, so the residual cannot be a topic effect.

| | majority (448 patron-years) | minority (301 patron-years) |
|---|---|---|
| residual variance observed | 0.0334 | 0.0435 |
| variance from coin-flipping | 0.0151 | 0.0164 |
| ratio to the noise floor | **2.2×** | **2.7×** |
| **true between-patron SD** | **14 points** | **16 points** |
| split-half inside one patron-year | r = 0.38 | r = 0.59 |
| consecutive years, same standing | **r = 0.51** | **r = 0.46** |
| 10th–90th pct of the residual | −15 to +33 pts | −45 to +11 pts |

Residualising barely moved it (raw SD was 15 / 18). **Portfolio explains almost none of the spread.**

Party standing is worth 25 points. A one-SD better carrier is worth 14–16 — **roughly half the party
effect, and it persists year to year.** Carrier effectiveness is a real, measurable, stable trait, and a
scorecard over it is defensible in a way the co-patron claim below is not.

---

## 3. RETRACTION — the cross-party co-patron lever

**Previously claimed** (commit `530fffc`, repeated in the 2026-09-11 bill-mix work): *one cross-party
co-patron is worth +18 to +26 points, and same-party co-patrons are worth zero.* **Both halves are wrong.**

### Three defects, found in order

**(a) Open States sponsorship rows carry no date.** `VA_*_bill_sponsorships.csv` has
`id, name, entity_type, organization_id, person_id, bill_id, primary, classification` — no timestamp, no
sequence. The co-patron list is a **terminal snapshot**. Open States actions record no co-patron additions
either (252 patron-mentioning actions across 18 sessions, all "stricken at request of patron"), so the
scrape cannot date them.

**(b) Co-patrons demonstrably arrive mid-session.** In an incorporation, the absorbed bill's chief patron
is added as a co-patron of the survivor **459/669 = 69%** of the time, and their own co-patrons carry over
31% of the time. LIS has a dedicated type for this: **`Incorporated Chief Co-Patron`**. So the list is
partly post-treatment by construction.

**(c) The accumulation control fails.** If names attach to bills that are already moving, the pile-up is
**party-blind** — your own caucus is the easier name to get. Same within-patron design, three specifications:

| | cross-party | same-party only | ANY co-patron |
|---|---|---|---|
| patron × chamber × bill idea | +19 | **+16** | +17 |
| patron × year | +19 | **+12** | +16 |
| patron × year × subject | +19 | **+15** | +18 |

Same-party co-patrons are worth +12 to +16 in **every** design. The "worth zero" claim does not replicate
anywhere. And "any co-patron at all" is worth +16 to +18 — the accumulation signature exactly.

### The decisive test, on LIS's own labels

LIS distinguishes **`Chief Co-Patron`** (named on the introduced bill, rule-limited to ~4 per bill) from
**`Co-Patron`** (signed on later, up to 99 per bill). Only the first is pre-treatment. Sessions 20251 and
20261, from the existing on-disk cache — **no new requests**. Join: 16,675 sponsor rows, **100%** matched to
a corpus bill, 96.9% party-resolved.

| majority patron | pass | n | 95% CI |
|---|---|---|---|
| no co-patrons at all | 55% | 1,475 | 53–58% |
| chief co-patron at introduction, **cross-party** | 81% | 116 | 73–87% |
| chief co-patron at introduction, **same party only** | 77% | 648 | 74–81% |
| co-patrons added later only | 76% | 689 | 72–79% |

| minority patron | pass | n | 95% CI |
|---|---|---|---|
| no co-patrons at all | 28% | 1,204 | 26–31% |
| chief co-patron at introduction, **cross-party** | 48% | 63 | 36–60% |
| chief co-patron at introduction, **same party only** | 37% | 76 | 27–48% |
| co-patrons added later only | 40% | 349 | 35–46% |

**Cross-party premium over same-party, both pre-treatment: +4 pt (p = 0.39) for majority patrons, +11 pt
(p = 0.20) for minority patrons.** Not established. The confidence intervals overlap heavily at n = 63 / 76.

### What survives

**A co-patron named on the introduced bill is worth +23 pt (majority, p < 1e-16) and +14 pt (minority,
p = 7.6e-04) versus none — and it is party-blind.** This is genuinely pre-treatment, so it is not
accumulation. It is still **selection**: a bill that can attract names before it is filed is a bill that
already has support. Nothing here shows that *going and getting* a name causes anything.

**Product consequence.** "Recruit one cross-party co-patron" must come off the lever list. It was the
headline lobbyist recommendation and it is not supported. The honest replacement is weaker and narrower:
*co-patron presence at introduction is a usable early signal of a bill's standing, worth 14–23 points, and
it does not matter which party the names come from.*

---

## Limits

1. The LIS pre/post split assumes `Chief Co-Patron` means "named on the introduced bill". The evidence is
   structural — it is rule-limited to ~4 per bill where plain `Co-Patron` runs to 99, and LIS carries a
   separate `Incorporated Chief Co-Patron` type — but it is **inference from the schema, not a documented
   contract**. Confirming it against introduced bill text would need document fetches.
2. The LIS window is **two sessions**, both with Democratic majorities in both chambers. The minority-patron
   cross-party cell is n = 63.
3. The vehicle contest cannot separate carrier effectiveness from the room's preference for its own
   members. It rules out patron irrelevance, not credit allocation.
4. The patron-effect residual controls topic, session and chamber. It does not control the patron's private
   read on which bills are winnable — the same unresolved channel as everywhere else, and the reason the
   forward-validation harness matters.

## Related

[[testing/bill_mix_confound]] · [[testing/calibration_corrections]] · [[testing/calibration_conclusion]] ·
[[testing/persuadability]] · [[knowledge/lis_api_safety]] · [[index]] · [[log]]
