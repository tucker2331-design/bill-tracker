/**
 * Pennsylvania's site config (owner 2026-11-01): the screens it offers and the facts it must NOT inherit from Virginia.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/states/pa.ts /tmp/pa_state.mjs && node web/tools/ts2mjs.mjs web/src/states/va.ts /tmp/va_state.mjs \
 *         && node web/src/states/__tests__/pa.regression.mjs
 */
import { PA } from "/tmp/pa_state.mjs";
import { VA } from "/tmp/va_state.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

is("PA screens: Calendar; War Room without vote predictions, with committee rosters; no timeline; intake Health",
   PA.features, { calendar: true, timeline: false, warroom: true, predictions: false, committeeRoster: true, summaries: false, health: "intake" });
is("VA screens unchanged: everything on incl. predictions, no roster section, full Health",
   VA.features, { calendar: true, timeline: true, warroom: true, predictions: true, committeeRoster: false, summaries: true, health: "full" });
is("PA's calendar says future session days are not published; VA has no note",
   [/no future list of session days is published/.test(PA.calendarNote), VA.calendarNote], [true, ""]);
is("PA has no crossover stage or dates", [PA.stages.some((s) => s.id === "crossover"), PA.crossoverBySession], [false, {}]);
is("PA two-year session", PA.sessionYears, 2);
is("PA links no per-bill page (robots-protected, unverified)", PA.billUrl("2025_0", "HB17"), "");
is("PA product name", PA.appName, "PA Bill Tracker");
is("PA bill ids", ["HB17", "SR398", "HJ1", "XB1"].map((b) => PA.billIdPattern.test(b)), [true, true, false, false]);
is("PA intake checks are its own keys", PA.intakeChecks.map((c) => c.key),
   ["verbs_unclassified", "action_dates_unreadable", "schedule_bill_refs_unmatched", "schedule_dates_unreadable",
    "bills_committee_without_roster"]);
is("VA has no intake checks (its Health is the full one)", VA.intakeChecks, []);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
