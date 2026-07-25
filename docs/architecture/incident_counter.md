---
tags: [architecture, trust, incident, health, parity, plan, owner-decision]
updated: 2026-07-17
status: active
open_loop: UNBLOCKED + fully scoped 2026-07-17 — definition = the owner's sentence, display = Health-first, guards = the three named, verification = FIRE DRILLS on the real ledger (owner killed the scratch-workbook idea: "don't build fake sandboxes"). Scoping pass 2 found 8 more issues (flood/dedup via open-incident semantics, guard credentials — all three guard workflows are creds-free today, denominator display, drill exclusion). WIRING IS THE NEXT ENGINEERING PR, build order inside. Public promotion of the number stays a later owner call.
---

# Incident counter + LIS-parity — architecture & the owner decisions that gate it

The trust claim expands from "never wrong" to **"never less than LIS"** ([[ideas/lobbyist_jtbd_ideation]]
§8b). The visible artifact is a **"N days since a data incident"** counter. Build-wave TASK 2, phases P1–P3.

## What is BUILT vs GATED

- ✅ **BUILT + proven now:** `tools/incident_log/log.py` — the append-only `Incident_Log` mechanism +
  `record_incident()` (FAIL-OPEN, closed class vocabulary) + genesis-aware `days_since` math. 9 offline
  goldens (`test_incident_log.py`). The counter mechanism is unambiguous regardless of the exact definition.
- ⛔ **GATED on owner decisions (below):** wiring the counter's WRITERS into the verification guards, the
  exact incident DEFINITION, and whether the number is shown PUBLICLY (trust header) or Health-tab-only.
  **Why not wired now:** (1) the definition wording is the owner's call (like the war room); (2) I cannot
  VERIFY a `record_incident` write-path fires without manufacturing a real incident — and shipping an
  unverifiable write into the accuracy sentinel (a critical guard) violates "verify the row"
  ([[failures/assumptions_audit#74]]) and risks destabilizing the guard.

## The owner decisions — RESOLVED 2026-07-17, definition AMENDED 2026-07-25

1. **The incident DEFINITION — the owner's sentence, now covering the whole trust EXPERIENCE:** *"how long data
   holds clean before intervention"* — where "clean" is judged **from the client's chair, not the pipeline's.**
   Owner correction 2026-07-25 (after the false red Accuracy ring): *"that incident absolutely has to affect
   the clean ledger, because it sent off a red accuracy alarm… imagine you're the lobbyist I sold this to."*
   **A false alarm on the trust surface IS an incident** — the client cannot (and must not need to) distinguish
   "the data is wrong" from "the alarm is wrong"; either way the product broke its promise that morning. Classes:
   - `accuracy` — wrong data was visible on the product (sentinel FAIL / breaker bypass), **or a human had to
     manually correct product data**.
   - `parity_gap` — content on LIS not visible here for > 1 worker cycle (P2/P3 parity checks).
   - `degraded` — a user-visible degraded state (stale banner / missing panel) lasting > 60 min.
   - **`false_alarm` (NEW, 2026-07-25)** — the trust surface showed red without a verified underlying data
     failure. The alarm system is part of the product and is held to the same standard as the data.
   - **`unverified` (NEW, 2026-07-25, owner: "an UNKNOWN is still a violation")** — a signal fired whose impact
     on published output could not be determined. **Opens immediately and breaks the streak**; the auto-resolver
     (§3) closes it without human involvement in the normal case. The ledger therefore measures **days we could
     VERIFY clean** — we never bank a day we couldn't check.
   **The 2026-07-25 outcome-drift event is the ledger's FIRST incident** — recorded as `false_alarm` at
   seeding, with its honest (approximate, and marked approximate) start date. The counter's story begins by
   telling the truth about itself.
2. **Display: Health-tab first — and the Health tab is CLIENT-FACING (owner 2026-07-25):** executives at client
   orgs get it ("other executives deserve to know the health of the data and the details"); their staff
   generally don't. This sets the tab's register: an alarm must be **self-diagnosing to a non-engineer
   executive** — structured facts, never internal jargon, never AI prose (owner: "don't translate data issues
   to English, but I don't want an AI to have to diagnose it every time").
3. **Guards that WRITE: the named three** for data incidents (fail-open one-liners in FAIL paths) + the manual
   CLI for interventions and `false_alarm` entries. **Structural rule added (the real fix): the display bands
   and the incident ledger must derive from the SAME verified verdicts** — the Health page may never carry an
   independent judgment that can go red while every guard passes, which is precisely what happened on
   2026-07-25. One truth pipeline: checks → verdicts → (display AND ledger). A band that can diverge from the
   guards is a second, unaudited alarm system, and it will eventually cry wolf.

## What RED means on the client-facing trust surface (the alarm law, owner criticism 2026-07-25)
The owner's two-part criticism, turned into design law:
1. **"If it was truly a false alarm it shouldn't have sent accuracy red."** → **Red accuracy = the product's
   published output is wrong, verified.** An internal consistency check that disagrees WITHOUT impeaching the
   published value (2026-07-25: our published `carried_over` matched LIS's own flags — the check was between
   LIS's two internal fields) is a **different, quieter class** — visible, never red-accuracy.
2. **"I couldn't tell whether everything was wrong or a minor disagreement matching what LIS itself shows."**
   → every alarm row must carry, as **structured fields, not prose**: (a) **what disagrees with what** (our
   published value vs which check); (b) **scope with denominator** (443 of 3,633); (c) **the verdict a client
   actually needs: "published output matches LIS: YES/NO."** If that last field is YES, the alarm is by
   definition not red-accuracy (see 1).
The owner's own summary is the standard: *"the solution is probably it not fucking up in the first place"* —
the alarm system gets the same engineering bar as the data: calibrated thresholds, partitioned classes, no
independent display judgment, and a false red counts against us on our own ledger.

## Owner follow-ups 2026-07-25 — both my answers were WRONG; corrected here

### 1. "Matches LIS" — my claim was unsubstantiated, and the brain already said so
I wrote that the website "renders from the same source" we check, inferring it from the SPA's public key. Owner
pushed back: *"you say it feeds the site but I just feel like this claim might be unsubstantiated… I don't know
if CSV + API is as reliable as the front-end actual site — we haven't proved that, nor that it directly feeds
it like you claim."* **He is right, and [[knowledge/lis_dom_scraping]] contains the refutation in our own
words:** *"LIS website is the **authoritative source** for calendar accuracy. **Schedule API has gaps.** …When
accuracy questions cross what the APIs can answer, **the website is the tiebreaker**."* We have known since
April 2026 that the API is **not** equivalent to the site — the entire crossover audit exists because of it.
- What the public key actually proves: the SPA calls *some* LIS gateway endpoints. It does **not** prove that
  every displayed field comes from the endpoints we consume, nor equal timeliness, nor equal completeness.
- **Therefore the claim is downgraded to what we measure and nothing more:** *"matches LIS's API + CSV data
  service."* **We do not claim website parity**, and the "same source the website renders from" phrasing is
  struck. If we cannot measure it, we do not say it — including in a parenthetical.

### 1b. W8 (DOM parity) — RE-SCOPED, because the wall is real and our own rule forbids the naive version
Owner: *"we have had problems with there being a wall where a non-human user can't see the LIS site."* Correct
and documented ([[knowledge/lis_dom_scraping]]): lis.virginia.gov is a React SPA — a plain fetch returns a ~3 KB
shell with **no data**; only a real browser (headless Chrome, `--headless=new --dump-dom`, ~15–25 s/page, 1–5 %
hydration failures) sees content. **And that same page states the rule I violated when I proposed W8: *"Don't
scrape real-time… DOM scraping is for one-time audits against frozen historical windows."*** So:
- W8 is **not** a monitor and cannot underwrite a continuous promise. It is a **periodic, small-sample,
  point-in-time AUDIT** (owner-approved cadence, tiny N, jittered, obeying the probe protocol).
- The strongest honest artifact it can produce is a **dated, sampled parity receipt** — *"last website audit:
  N bills, DATE, X discrepancies"* — never a standing "we match the website" claim.
- **Owner sign-off + a terms review are prerequisites**, not details. Until then the claim stays as in §1.

### 2. Pre-writing text per anticipated signal — a REPEAT anti-pattern; the design is inverted
Owner: *"this 'what happened' thing is assigning texts to signals, which I think is a bad habit, because the
signal we will get is the one we don't expect, not the one we've already scoped for."* **Correct, and this is
the SECOND time he has made this exact criticism** (first: the change-ledger register — *"a lot of data-to-text
going on, which requires us to know every possible data point and have corresponding text; sounds like a
massive sustainability problem"*). It went unrecorded, so I rebuilt it. The per-class prose table is **struck**.
**The inversion — ONE universal alarm record; text is RENDERED from fields, never looked up per signal:**
| Field | Meaning | When the signal is unanticipated |
|---|---|---|
| `check` | which check emitted it (identifier, not prose) | always present — whatever fired knows its own name |
| `observed` / `expected` / `threshold` | the raw values that tripped it | always present — a check that can't say this is unshippable |
| `scope_n` / `scope_of` | the count **and its denominator** (Standard #7) | present, or explicitly `unknown` |
| `surface` | which LIS surface was compared (§1) | present — never the bare word "LIS" |
| **`published_output_impeached`** | **TRUE / FALSE / UNKNOWN — the tri-state that drives colour** | **UNKNOWN** |
- **Colour is computed, not authored** — see §3 for the tri-state rule (my first version said "UNKNOWN routes
  to human review"; the owner correctly killed that — it violated Standard #8 and mis-stated the ledger).
- **This alone would have prevented 2026-07-25:** our published value matched LIS's own flags, so
  `published_output_impeached` = FALSE → structurally incapable of turning the ring red.
- **No enumeration treadmill:** a new check ships by filling fields it already has. Nobody writes a sentence.
- Free-text prose on the client surface remains forbidden — but the replacement is a *rendered record*, not a
  bigger dictionary of pre-written cases.

---

## 3. UNKNOWN: it breaks the streak, and the SYSTEM resolves it — not a human
*(Written under [[workflow/design_proposal_protocol]] — competing options, self-audited, before presenting.)*

**Two owner corrections that set the constraints:**
1. *"An UNKNOWN is still a violation and will reset the counter if we don't know if it's causing a serious data
   issue or if it's minor."* → **we may never bank a clean day we cannot verify.**
2. *"Don't just send a bunch of alerts to a human to fix — I'm the only human and I'm busy auditing you."* →
   **"escalate to a person" is not a resolution strategy** (it was also a naked Standard #8 violation).

### The candidates, audited against our own rules
| # | Design | Audit verdict |
|---|---|---|
| A | **Route UNKNOWN to human review** (my rejected first answer) | ❌ **Standard #8** (zero routine human maintenance) — and the owner is a single bottleneck, so it doesn't scale past one unknown/week. Dead. |
| B | **Quarantine: hide affected rows until verified** | ❌ **Standard #3** — the lobbyist surface must be complete, *"never a hidden row."* Hiding trades a visible unknown for an invisible one. Dead as stated; its useful half (**mark, don't hide**) survives into E. |
| C | **Fail-closed: treat every UNKNOWN as impeached → RED** | ❌ **P24** (red = verifiably wrong) and it re-creates the 2026-07-25 cry-wolf failure; the counter could never accumulate, killing the moat ([[ideas/moat_and_competition]] #4). Dead as a *display* rule — but its conservatism is correct for the **ledger**, which is where E puts it. |
| D | **Two counters** ("days verified clean" + "days since a confirmed error") | ⚠️ Honest but **fails the client test**: an exec reading two trust numbers must arbitrate between them. One number, one meaning. Rejected as over-engineering; the detail belongs in the incident row, not a second headline. |
| **E** | **AUTO-RESOLVER + tri-state display + UNKNOWN breaks the streak** | ✅ **Winner** — detailed below. |

### E — the design
**1. UNKNOWN breaks the streak, immediately.** The ledger's meaning sharpens to **"days we could VERIFY
clean."** An unresolved unknown is logged as an OPEN incident of class `unverified` the moment it appears. This
is strictly more honest than the old rule and satisfies correction (1): we never bank an unverifiable day.

**2. The system resolves it — the targeted re-verification loop (satisfies correction (2) + Standard #8).**
Any check that fires must name its **affected rows** (already required: `scope_n`/`scope_of`). The resolver then
does automatically what a human would do, and it needs **no understanding of the signal's semantics** — which
is what makes it work for the unanticipated signal (P25):
   - re-fetch those specific records from the authoritative source(s);
   - diff them against **our published values**;
   - **match → `impeached = FALSE`** → incident auto-closes as benign, with its evidence attached;
   - **mismatch → `impeached = TRUE`** → RED, real `accuracy` incident, breaker/quarantine path;
   - **the source contradicts ITSELF** (exactly 2026-07-25: LIS's flags vs LIS's strings) → resolve against the
     **structural oracle** per Standard #3 → we matched it → FALSE, auto-closed, evidence: *"we match LIS's
     structural flags; LIS's own display string disagrees with them."* **Friday's incident would have
     self-diagnosed in one cycle, with no human and no red ring.**
   - Cost is bounded by the affected set, not the corpus; it reuses the reconciliation machinery we already own.

**3. A check that cannot name its affected rows cannot ship.** If scope is unknowable, the honest scope is
*everything* → the whole surface is unverified → the streak breaks. That's deliberately expensive, so checks
get built to localize. (This is the metric driving the right engineering, Standard #7.)

**4. Tri-state display — the third state is the missing piece.** Binary green/red forced the false choice that
started all this:
   - **Verified clean** — checks passed, published output confirmed.
   - **UNVERIFIED** *(new)* — "we cannot currently confirm this; resolving." Distinct from red, **not** a claim
     of correctness, and per §1 it is honestly time-stamped ("unverified since HH:MM"). Affected rows are
     **marked in place, never hidden** (B's surviving half; Standard #3).
   - **RED** — published output verifiably wrong (`impeached == TRUE`), unchanged from P24.

**5. Escalation is by DURATION, not by default.** The resolver retries on the worker's cadence. Only if an
unknown survives **N cycles** does it reach the owner — as a fully-documented dossier (what fired, affected
rows, what the resolver tried, why it failed), never as a raw "please look at this." **The system does the
investigation; the human only ever makes a judgment call.**

**What would make E wrong / residual risk (protocol step 4):** if the authoritative source is *itself*
unreachable, the resolver cannot conclude — that correctly stays UNVERIFIED (breaking the streak during an LIS
outage, which is honest but will make the counter look worse than "our" reliability). Accepted deliberately:
the client's question is *"can I trust what I see right now?"*, and during an upstream outage the honest answer
is "we can't currently verify it." **The runner-up (D, two counters) handles that case more flatteringly — and
we reject it because flattering our own metric is exactly what the counter exists not to do.**

## Verification design — FIRE DRILLS, not sandboxes (owner correction 2026-07-17)

> Owner: *"don't build fake sandboxes to avoid resetting the timer — figure out a workaround that still allows
> us to use the real data to test scenarios."*

The scratch-workbook idea is **dead**. Replacement — the **drill row**: a new closed-vocabulary class `_drill`
written to the **real** `Incident_Log` through the **entire production write path** (real `record_incident`,
real append, real workbook, real read-back), and **structurally excluded from the clock** by `latest_incident_end`
/ `days_since` / the "incidents ever" count — exactly the mechanism `_genesis` already uses. Like a fire drill:
the real alarm rings, everyone really walks out, and nobody logs a fire. This is *stronger* verification than a
sandbox (it proves the production workbook, tab, permissions, and quota — a sandbox only proves a copy) and the
drill rows remain in the ledger as a visible, honest record that the alarm is tested. A scheduled monthly drill
(cron) turns "the write path works" from a one-time claim into a standing guarantee — if a drill fails to
appear, THAT alerts (the alarm's alarm).

## Scoping pass 2 (2026-07-17) — the other issues found, beyond verification

1. **Incident flood / dedup (the biggest one).** A 3-day outage makes the sentinel FAIL ~100 consecutive
   cycles. Naively wired, that's ~100 rows = 100 "incidents" for ONE event — the counter would lie in the
   *pessimistic* direction. Design: **open-incident semantics.** Before appending, a guard reads the tab; if an
   incident with the same `Class` + `DetectedBy` is already OPEN (empty `EndUTC`), it does NOT append. On its
   next PASS, the guard **closes** its own open incident (fills `EndUTC = now`). One event → one row with a real
   duration. Append-only in spirit is preserved (rows are never deleted; closing fills a blank cell). Race
   between two runs → worst case one duplicate row; acceptable, noted.
2. **Recovery detection comes for free** from #1: the guard that detects the failure is the guard that declares
   it over. No new machinery.
3. **Multi-guard storms:** one outage may trip sentinel + tripwire + reconciliation → 3 open incidents for one
   cause. V1 accepts this honestly (they ARE three distinct symptoms); the Health display groups by overlapping
   time window. Do not over-engineer cross-guard correlation now.
4. **Credentials — a real security-posture decision (checked, not assumed):** `accuracy_sentinel.yml`,
   `completeness_tripwire.yml`, and `legevent_reconcile.yml` run **without** `GCP_CREDENTIALS` today — the
   sentinel is deliberately creds-free (reads public gviz only). Wiring writes means granting them creds.
   Recommended: **(a)** add the existing `GCP_CREDENTIALS` to the three guard workflows (the secret already
   backs ~20 workflows; these are our own repo's code; least-privilege note in each). Alternative if the owner
   wants the sentinel to stay creds-free in spirit: **(b)** a dedicated service account shared ONLY on the
   ledger workbook. (a) is simpler; decide at build time.
5. **The denominator (our own Standard #7!):** "47 days clean" is meaningless without its context. Display is
   **"N days clean · monitoring for M days"** (M = days since genesis) — a young counter must not masquerade as
   a long record. Longest-streak can come later.
6. **Clock semantics during an open incident:** `days_since` falls back to `StartUTC` when `EndUTC` is empty, so
   the counter correctly reads ~0 *during* an incident; display shows red while any incident is OPEN.
7. **Drill rows in counts:** excluded from "incidents ever recorded" and from `latest_incident_end`, included in
   a quiet "last drill: N days ago" line (proves the alarm is tested — and a stale drill date is itself a signal).
8. **Pre-genesis history:** incidents before genesis (e.g. the July 0→66 regression) are NOT backfilled — the
   genesis row's honest meaning is "monitoring began here." The counter never claims cleanliness it didn't measure.

## Wiring plan (READY — the next engineering PR, in this order)
1. `log.py`: add `_drill` class + exclusion in `latest_incident_end`/counts; **open-incident dedup + close-on-PASS**
   helpers; manual-intervention CLI subcommand (`record accuracy "…" manual`); goldens for all three behaviors.
2. **Seed the genesis row** (one CI run auto-creates tab + epoch). **Every un-seeded day is thrown-away provable
   trust — this lands the same day as the PR.**
3. Run the first **drill** end-to-end against the real ledger; schedule the monthly drill cron.
4. Wire the three guards' FAIL branches (fail-open one-liners + the creds decision from #4 above).
5. Frontend: Health-tab line via gviz — "N days clean · monitoring for M days", red only while an incident is
   OPEN, quiet last-drill note. (Trust-header promotion stays a later owner call.)
- **Why this matters beyond the feature** ([[ideas/moat_and_competition]] #4): the counter is the *receipt* that
  turns claimed trust into counted trust — accumulated, dated evidence a late entrant cannot backfill. It has
  the same can't-vibe-code-the-past property as the observation layer.

## Parity feeders (P2/P3 — separately tracked)
- **P2 endpoint audit** — SHIPPED (#220/#221, `tools/parity/endpoint_audit.py`): catches LIS API routes we
  don't consume (the unknown-unknown). Its INFO alert is the seed of `parity_gap` detection.
- **P3 sampled DOM parity** (not built) — weekly headless render of N tracked-bill LIS pages, diff
  history-row + meeting counts vs ours; a mismatch is a `parity_gap` incident. Spec in the build-wave README.
- Once P2/P3 are stable they call `record_incident("parity_gap", …)` automatically.

See also [[audits/build_wave_2026-07/README]] (TASK 2), [[ideas/lobbyist_jtbd_ideation]] §8b,
[[architecture/verification_durability]] (the guards that would write here).
