/**
 * War Room list rules — groups, the order inside them, and reading the served calls tab.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/data/warroom_rules.ts /tmp/warroom_rules.mjs \
 *         && node web/src/data/__tests__/warroom.regression.mjs
 */
import { parseCallsGrid, callsFor, groupOf, sortGroup, dateKeyOf, CALLS_HEADER } from "/tmp/warroom_rules.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

// ---- groups (today = Mon 2 Feb 2026)
const T = "2026-02-02";
is("decided wins over a calendar date", groupOf("signed", "2026-02-03", T), "decided");
is("carried over is decided", groupOf("carried_over", "", T), "decided");
is("hearing tomorrow -> next 7 days", groupOf("in_progress", "2026-02-03", T), "next7");
is("hearing in exactly 7 days -> next 7 days", groupOf("in_progress", "2026-02-09", T), "next7");
is("hearing in 8 days -> scheduled later", groupOf("in_progress", "2026-02-10", T), "later");
is("M/D/YYYY reads the same", groupOf("in_progress", "2/3/2026", T), "next7");
is("no date -> nothing scheduled", groupOf("in_progress", "", T), "none");
is("a date in the past -> nothing scheduled", groupOf("in_progress", "2026-01-30", T), "none");
is("awaiting the Governor has no next room", groupOf("awaiting_governor", "", T), "none");
is("unreadable date -> empty key", dateKeyOf("next week"), "");

// ---- order inside a group with a next room: most yes still needed, then most no, then most can't call
const c = (yesNeeded, calledYes, calledNo, cantCall) => ({ yesNeeded, calledYes, calledNo, cantCall });
const items = [
  { bill: "HB10", calls: c(3, 3, 0, 2) },   // already has enough called yes -> needs 0 -> bottom
  { bill: "HB2", calls: c(6, 1, 4, 6) },    // needs 5
  { bill: "HB3", calls: c(6, 1, 2, 8) },    // needs 5, fewer no than HB2
  { bill: "HB4", calls: c(6, 1, 2, 9) },    // needs 5, same no as HB3, more can't call
  { bill: "HB5", calls: null },             // no member data: after the ranked ones
  { bill: "HB1", calls: null },
];
is("least likely to pass first", sortGroup(items, "next7").map((x) => x.bill), ["HB2", "HB4", "HB3", "HB10", "HB1", "HB5"]);
is("nothing scheduled keeps bill-number order", sortGroup(items, "none").map((x) => x.bill),
   ["HB1", "HB2", "HB3", "HB4", "HB5", "HB10"]);

// ---- the served tab
const head = [...CALLS_HEADER, "", JSON.stringify({ mode: "replay", test_year: 2026, call_edge: 0.31, ballots: 5, called: 3,
  called_right: 2, cant_call: 2, bills: 1, generated_utc: "2026-10-29T22:00:00Z" })];
const mem = JSON.stringify([{ who: "Tran", party: "D", p: 0.95, call: "yes", actual: "yes", ev: { mpat: [61, 62] } }]);
const grid = [head, ["HB1515", "2026", "Rules", "2026-02-06", "5", "3", "3", "1", "1", "3", mem], ["", "", ""]];
const r = parseCallsGrid(grid);
is("tab parses", r.status, "ok");
is("summary read from M1", r.summary && [r.summary.called, r.summary.calledRight], [3, 2]);
is("2026 regular session maps to 20261", callsFor(r.byBill, "HB1515", "20261")?.yesNeeded, 3);
is("a special session never borrows regular calls", callsFor(r.byBill, "HB1515", "20262"), null);
is("evidence survives as k-of-n", callsFor(r.byBill, "HB1515", "20261").members[0].ev.mpat, [61, 62]);
is("wrong sheet (gviz served another tab) -> unavailable", parseCallsGrid([["Date", "Time"], ["x", "y"]]).status, "unavailable");
is("unreadable members JSON -> that bill has no calls", parseCallsGrid([head, ["HB2", "2026", "", "", "1", "1", "0", "0", "1", "0", "{oops"]]).byBill.size, 0);

console.log(`\n${fail ? `${fail} FAILED` : "ALL PASS"} (${pass} ok)`);
process.exit(fail ? 1 : 0);
