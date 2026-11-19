/**
 * California's site config (2026-11-18/19): the screens it offers and the facts it must NOT inherit from Virginia.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/states/ca.ts /tmp/ca_state.mjs && node web/src/states/__tests__/ca.regression.mjs
 */
import { CA } from "/tmp/ca_state.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

is("CA screens: Calendar; War Room without vote predictions, with committee members; the chamber subway; intake Health",
   CA.features, { calendar: true, timeline: true, warroom: true, predictions: false, committeeRoster: true, summaries: false, health: "intake" });
is("the lower chamber is SHOWN as the Assembly; the contract keys stay House/Senate",
   [CA.chamberLabels, Object.values(CA.chambers).sort()], [{ House: "Assembly", Senate: "Senate" }, ["House", "House", "Senate"]]);
is("committee members credit Open States (pubinfo has no membership table)", CA.rosterSourceName, "Open States");
is("the source publishes once a day: no speed can beat 24 h", CA.sourceMinIntervalHours, 24);
is("CA calendar note says upcoming floor agendas are not listed", /upcoming floor agendas are not listed/.test(CA.calendarNote), true);
is("CA bill ids", ["AB12", "SB3", "ACR44", "HR5", "SBX1 3", "HB1"].map((b) => CA.billIdPattern.test(b)), [true, true, true, true, false, false]);
is("CA links no per-bill page (the interactive site is bot-challenged, never fetched)", CA.billUrl("20252026", "AB12"), "");
is("a resolution ends adopted, never signed", CA.stages.some((s) => s.id === "adopted"), true);
is("every Health check must be 0 except subject-less resolutions (measured 281 on 2025-26)",
   CA.intakeChecks.filter((c) => c.limit !== 0).map((c) => [c.key, c.limit]), [["titles_blank", 300]]);
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
