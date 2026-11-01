/**
 * What's new — one line per bill with where the action happened (owner 2026-11-01).
 * Rows are copied from the real PA sample (SB509) and the real VA 2026 HISTORY text shapes.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/data/action_where_rules.ts /tmp/action_where_rules.mjs \
 *         && node web/src/data/__tests__/action_where.regression.mjs
 */
import { parseWhereGrid, feedLines, sentenceCase, ACTION_WHERE_HEADER } from "/tmp/action_where_rules.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

// PA SB509: ...passed Senate, then "In the House" and "Referred to TRANSPORTATION, Oct. 29, 2026" the same day
const pa = parseWhereGrid([ACTION_WHERE_HEADER,
  ["SB509", "SSHH", JSON.stringify(["Introduced", "Third consideration and final passage (49-1)", "In the House", "Referred to Transportation"])]]);
is("reads the tab", pa.status, "ok");
const day = [
  { bill: "SB509", idx: 2, action: "In the House", n: 4 },
  { bill: "SB509", idx: 3, action: "Referred to TRANSPORTATION,  Oct. 29, 2026", n: 4 },
];
is("PA: one line per bill, the latest action, where it happened, the state's own short line",
   feedLines(day, pa.byBill, null).map((l) => `${l.bill} (${l.where}) ${l.text}`), ["SB509 (In the House) Referred to Transportation"]);

// VA: LIS's chamber code column is removed for display only; where comes from the tab, never from that code
const va = parseWhereGrid([ACTION_WHERE_HEADER, ["SB100", "SSSH", ""]]);
const vaDay = [{ bill: "SB100", idx: 3, action: "H Referred to Committee on Transportation", n: 4 }];
is("VA: code column stripped, where from the tab",
   feedLines(vaDay, va.byBill, /^[HS] /).map((l) => `${l.bill} (${l.where}) ${l.text}`), ["SB100 (In the House) Referred to Committee on Transportation"]);
is("VA: the action's raw text is kept for the meeting-time join", feedLines(vaDay, va.byBill, /^[HS] /)[0].action, vaDay[0].action);
is("no tab -> no bracket, never a guessed one", feedLines(vaDay, null, /^[HS] /)[0].where, "");
is("unknown code (-) -> no bracket", feedLines([{ bill: "X1", idx: 0, action: "a", n: 1 }], new Map([["X1", { where: "-", short: null }]]), null)[0].where, "");
is("Governor", feedLines([{ bill: "HB17", idx: 0, action: "Approved by the Governor", n: 1 }], new Map([["HB17", { where: "G", short: null }]]), null)[0].where, "With the Governor");
is("a where-string from another snapshot (length differs) is not used (Codex #260)",
   feedLines([{ bill: "SB509", idx: 3, action: "Referred to TRANSPORTATION", n: 5 }], pa.byBill, null).map((l) => [l.where, l.text]),
   [["", "Referred to TRANSPORTATION"]]);
is("sentence case: all-caps lowered after the first letter", sentenceCase("INTRODUCED AS NONCONTROVERSIAL"), "Introduced as noncontroversial");
is("sentence case: mixed case keeps proper nouns", sentenceCase("signed in Senate"), "Signed in Senate");
is("a short list that does not line up is counted and not used",
   parseWhereGrid([ACTION_WHERE_HEADER, ["HB1", "HH", JSON.stringify(["only one"])]]).unreadable, 1);
is("bad JSON is counted", parseWhereGrid([ACTION_WHERE_HEADER, ["HB1", "HH", "{"]]).unreadable, 1);
is("wrong header -> unavailable", parseWhereGrid([["Bill", "X"]]).status, "unavailable");

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
