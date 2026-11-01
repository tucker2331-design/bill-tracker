/**
 * Committee roster rules (PA War Room) — reading the Committee_Roster tab and finding a bill's committee.
 * The rows below are copied from the real roster built from house_committee_assignments.xml (2026-11-01).
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/data/roster_rules.ts /tmp/roster_rules.mjs \
 *         && node web/src/data/__tests__/roster.regression.mjs
 */
import { parseRosterGrid, rosterFor, partySplit, ROSTER_HEADER } from "/tmp/roster_rules.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

const grid = [ROSTER_HEADER,
  ["House", "House EDUCATION", "Education", "1105", "Bryan Cutler", "R", "100", "Chair"],
  ["House", "House EDUCATION", "Education", "1706", "Peter Schweyer", "D", "134", "Chair"],
  ["House", "House EDUCATION", "Education", "1933", "Aerion Abney", "D", "19", ""],
  ["Senate", "Senate AGING AND YOUTH", "Aging & Youth", "1921", "A Senator", "R", "1", ""],
  ["", "", "", "", "", "", "", ""],
];
const r = parseRosterGrid(grid);
is("reads the tab", r.status, "ok");
is("groups seats by committee key", [...r.byKey.keys()], ["House EDUCATION", "Senate AGING AND YOUTH"]);
is("keeps the source's order and roles", r.byKey.get("House EDUCATION").seats.map((s) => [s.member, s.role]),
   [["Bryan Cutler", "Chair"], ["Peter Schweyer", "Chair"], ["Aerion Abney", ""]]);
is("bill lookup is exact on lastCommittee", rosterFor(r.byKey, "House EDUCATION").name, "Education");
is("no fuzzy match: other case is a miss", rosterFor(r.byKey, "House Education"), null);
is("no committee -> null", rosterFor(r.byKey, ""), null);
is("party split, largest first", partySplit(r.byKey.get("House EDUCATION").seats), "2 D, 1 R");
is("a row with no key is counted, not dropped silently",
   parseRosterGrid([ROSTER_HEADER, ["House", "", "x", "1", "y", "D", "1", ""], ...grid.slice(1, 2)]).unplaced, 1);
is("wrong header -> unavailable (never a wrong column read)", parseRosterGrid([["Chamber", "Committee"], ["a", "b"]]),
   { status: "unavailable", reason: "bad_header" });
is("header only -> unavailable", parseRosterGrid([ROSTER_HEADER]), { status: "unavailable", reason: "empty" });
is("nothing -> unavailable", parseRosterGrid([]), { status: "unavailable", reason: "empty" });

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
