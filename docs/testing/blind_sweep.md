---
tags: [testing, calibration, discovery, method, war-room]
updated: 2026-09-16
status: active
---

# Letting the data nominate the hypotheses

**Owner, 2026-09-16:** *"weve only tested hypothesis. so how do we get around that and go from the reverse?
find whats working and see why maybe."*

Correct, and it identifies the one flaw a time-split backtest **cannot** fix. Roughly thirty analyses have
been run against this data. Ten came back null, several were retracted, a few survived — but *I* chose which
hypotheses to test, which thresholds to use and which cuts to make, with the answers visible the whole
time. Splitting on time does not cure that, because the **choosing** happened with full sight.

`python3 tools/calibration/sweep.py`

## The design

Generate features **mechanically**, sweep every one of them on a **discovery half (2017–2022)**, then test
the survivors **only on a confirmation half (2023–2026)** they were never found in. Multiple comparisons are
handled by replication rather than by a correction factor: anything that does not hold on data it was not
discovered in is noise.

## The trap that ate the first version

Scoring a feature like `title~tax & minority` against the **overall** base rate makes every
minority-interacted feature inherit the −18pt minority penalty. Under that rule **38 of 49 "replicated"** —
and they were one finding wearing 38 hats.

**Every feature is now scored against its own standing's base rate**, which is the only way to see what it
*adds*. Under that rule **12 of 20 survive**, and three that looked strong collapse:

| collapsed | discovery | confirmation |
|---|---|---|
| Crimes and Offenses & minority | −19 | **−5** |
| title~increas & minority | −14 | −5 |
| seniority yr5-9 & majority | +13 | +4 |

## What replicated

| for a… | feature | 2017–22 | 2023–26 | n |
|---|---|---|---|---|
| **minority** | **title~amend** | +37 | **+31** | 78 |
| minority | subject = Elections | −15 | **−18** | 141 |
| minority | title~license | +14 | +17 | 97 |
| **majority** | **title~amend** | +29 | **+15** | 99 |
| minority | title~definition | +14 | +15 | 104 |
| majority | title~definition | +14 | +14 | 206 |
| minority | subject = Public Service Companies | −16 | −14 | 113 |
| **minority** | **title~establish** | −11 | **−13** | 239 |
| majority | subject = Professions and Occupations | +19 | +11 | 282 |
| majority | title~eligib | −17 | −9 | 100 |
| minority | title~exempt | +17 | +8 | 96 |
| minority | title~prohibit | −18 | −8 | 148 |

## The headline, which nobody hypothesised

**For a minority patron, a bill that AMENDS something already on the books runs +31 points above other
minority bills. One that ESTABLISHES or CREATES something runs −13.** A 44-point spread *inside* minority
bills, driven by what kind of legislative act the bill is.

And it is **twice as large for a minority patron (+31) as for a majority one (+15)** — which is the
mechanism in one line: **without power, only a small ask survives. A new program needs authority the
minority does not have.**

The same shape runs through the rest of the list. `definition`, `license`, `exempt` — narrow, bounded,
technical — all positive. `establish`, `prohibit`, `eligib` — new authority, new restrictions, new
entitlement — all negative.

## Standard #3 — this cannot ship as written

These are **title markers**, and a regex over a title is not a structural read of a bill. "This bill amends
rather than creates" is a genuinely structural property — it is visible in which code sections the bill
touches — but **inferring it from the title is internal diagnostic only** and must not reach a lobbyist
surface. Making this shippable means sourcing the amend/create distinction from what the bill actually
does, not what it is called.

## Limits

1. Several cells are thin — `title~amend & minority` is n = 78 in discovery. The direction replicates; the
   magnitude should not be quoted precisely.
2. Subject labels are our own coarse classifier ([[testing/subject_labels]]).
3. The sweep covers features fixed at or before referral. Co-patron counts are deliberately **excluded** as
   post-treatment ([[testing/carrier_effect]]).
4. A 60% replication rate still means four in ten discovery findings were noise. That is the point of the
   confirmation half, and it is why the discovery half's numbers are never quoted on their own.

## Related

[[testing/panel_audit]] · [[testing/profiles]] · [[testing/venue_shopping]] ·
[[testing/bill_mix_confound]] · [[index]] · [[log]]
