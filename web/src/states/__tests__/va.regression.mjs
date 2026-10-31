/**
 * Virginia, byte-identical across the multi-state split (2026-10-31). Every value below was a LITERAL in
 * web/src before the split; the config must reproduce each one exactly, and the chamber/bill-id rules must give
 * the same answer as the old inline code on every input, including the odd ones.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/states/va.ts /tmp/va_state.mjs \
 *         && node web/src/states/__tests__/va.regression.mjs
 */
import { VA } from "/tmp/va_state.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

// ---- the pre-split literals
is("APP_STATE was \"VA\"", VA.code, "VA");
is("APP_NAME / brand / <title> was \"VA Bill Tracker\"", VA.appName, "VA Bill Tracker");
is("every \"LIS\" label", VA.sourceName, "LIS");
is("War Room footer said \"Virginia LIS\"", VA.sourceLongName, "Virginia LIS");
is("loading line said \"the General Assembly\"", VA.legislatureName, "the General Assembly");
is("CROSSOVER_BY_SESSION", VA.crossoverBySession, { "20261": "2026-02-17" });
const oldUrl = (s, b) => `https://lis.virginia.gov/bill-details/${s}/${b}`;
for (const [s, b] of [["20261", "HB1515"], ["20262", "SR2001"], ["20251", "HJ5"]]) is(`lisBillUrl(${s}, ${b})`, VA.billUrl(s, b), oldUrl(s, b));

// ---- chamber of a bill: the new prefix map + each caller's own fallback == the old inline code
const origin = (bill) => VA.chambers[bill.charAt(0).toUpperCase()] ?? null;
const oldSearch = (bill) => (bill.charAt(0).toUpperCase() === "H" ? "House" : "Senate");
const oldDerive = (bill) => (bill[0]?.toUpperCase() === "S" ? "Senate" : "House");
for (const bill of ["HB1", "SB1", "hb7", "sj3", "HR2", "SR9", "", "X1", "1"]) {
  is(`Search origin ${JSON.stringify(bill)}`, origin(bill) ?? "Senate", oldSearch(bill));
  is(`derive/gviz origin ${JSON.stringify(bill)}`, origin(bill) ?? "House", oldDerive(bill));
}

// ---- the calendar's bill-id rule
const OLD_RE = /^[HS][BJR]\d+$/;
for (const id of ["HB1", "SB1515", "HJ5", "SR22", "HX1", "hb1", "HB", "Room 3", "HB1a"]) is(`bill id ${id}`, VA.billIdPattern.test(id), OLD_RE.test(id));

// ---- stages: the crossover lane (data/derive.ts Stage ids) plus the crossover marker
is("stage ids", VA.stages.map((s) => s.id), ["prefiled", "committee1", "floor1", "crossover", "committee2", "floor2", "governor"]);
is("crossover is a marker, not a place", VA.stages.filter((s) => s.marker).map((s) => s.id), ["crossover"]);
is("annual session", VA.sessionYears, 1);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
