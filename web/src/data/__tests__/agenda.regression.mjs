/** Floor-session collapse — one session card per chamber per day, not one per parliamentary event.
 *
 * Baseline is MEASURED on the live calendar (2026-07-31), not plausible:
 *   BEFORE: 50 days carried floor cards · MEDIAN 4 per day · MAX 9
 *           worst day 2026-03-14 = 9 cards, ALL NINE carrying zero bills
 *   AFTER:  median 2 (one per chamber) · max 2 · 2026-03-14 = 2 cards, 6 and 3 markers folded inside
 *           total meeting count 1503 -> 1358; the 145 difference is markers absorbed, none dropped
 *
 * Run (from web/):
 *   node tools/ts2mjs.mjs src/data/agenda.ts /tmp/agenda.mjs && node src/data/__tests__/agenda.regression.mjs
 */
import { collapseFloorSessions, classifyMeetingKind } from "/tmp/agenda.mjs";
let pass = 0, fail = 0;
const is = (n, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n} -> ${JSON.stringify(got)}${ok ? "" : ` (want ${JSON.stringify(want)})`}`);
  ok ? pass++ : fail++;
};
const M = (o) => ({
  dateKey: "2026-03-14", committee: "House Convenes", chamber: "House", kind: "floor",
  time: "10:00 AM", tba: false, minutes: 600, unresolved: false, bills: [],
  agendaUrl: "", meetingUrl: "", markers: [], ...o,
});
const bill = (b) => ({ bill: b, action: "" });

// --- the real 2026-03-14: nine cards, two chambers, zero bills -----------------------------------
const day0314 = [
  M({ committee: "House Convenes", chamber: "House", time: "10:00 AM", minutes: 600 }),
  M({ committee: "Senate Convenes", chamber: "Senate", time: "12:00 PM", minutes: 720 }),
  M({ committee: "House recessed until 12:00 p.m.", chamber: "House", time: "12:03 PM", minutes: 723 }),
  M({ committee: "House recessed until 2:45 p.m.", chamber: "House", time: "1:38 PM", minutes: 818 }),
  M({ committee: "Senate recessed until 3:00 p.m.", chamber: "Senate", time: "2:40 PM", minutes: 880 }),
  M({ committee: "House recessed until 5:00 p.m.", chamber: "House", time: "3:49 PM", minutes: 949 }),
  M({ committee: "House recessed until 5:40 p.m.", chamber: "House", time: "5:27 PM", minutes: 1047 }),
  M({ committee: "House adjourned Sine Die", chamber: "House", time: "7:08 PM", minutes: 1268 }),
  M({ committee: "Senate adjourned Sine Die", chamber: "Senate", time: "7:26 PM", minutes: 1286 }),
];
const c = collapseFloorSessions(day0314);
is("2026-03-14: 9 cards -> 2", c.length, 2);
is("one per chamber", c.map((m) => m.chamber).sort(), ["House", "Senate"]);
is("House keeps its 6 markers", c.find((m) => m.chamber === "House").markers.length, 6);
is("Senate keeps its 3 markers", c.find((m) => m.chamber === "Senate").markers.length, 3);
is("nothing lost", c.reduce((n, m) => n + m.markers.length, 0), 9);
// The card takes the CONVENING's time and name — the earliest marker, structurally, not by matching text.
is("card time is the convening", c.find((m) => m.chamber === "House").time, "10:00 AM");
is("card name is the convening", c.find((m) => m.chamber === "House").committee, "House Convenes");

// --- committee meetings must be untouched ---------------------------------------------------------
const mixed = [
  M({ committee: "House Convenes", chamber: "House", minutes: 600 }),
  M({ committee: "House adjourned", chamber: "House", minutes: 1200 }),
  M({ committee: "Senate Education and Health", chamber: "Senate", kind: "committee", minutes: 540 }),
];
const cm = collapseFloorSessions(mixed);
is("committee card survives alone", cm.filter((m) => m.kind === "committee").length, 1);
is("committee card keeps no markers", cm.find((m) => m.kind === "committee").markers.length, 0);
is("mixed day: 3 -> 2", cm.length, 2);

// --- bills roll up, deduped ------------------------------------------------------------------------
const withBills = [
  M({ committee: "House Convenes", minutes: 600, bills: [bill("HB2"), bill("HB1")] }),
  M({ committee: "House recessed", minutes: 700, bills: [bill("HB1"), bill("HB3")] }),
];
const wb = collapseFloorSessions(withBills)[0];
is("bills union, deduped, sorted", wb.bills.map((b) => b.bill), ["HB1", "HB2", "HB3"]);

// --- honesty flags are UNIONS, never averages ------------------------------------------------------
is("one unplaceable marker makes the sitting unplaceable",
  collapseFloorSessions([M({ minutes: 600 }), M({ minutes: 700, unresolved: true })])[0].unresolved, true);
is("a sitting is TBA only when NO marker had a clock",
  collapseFloorSessions([M({ minutes: 600, tba: true }), M({ minutes: 700, tba: false })])[0].tba, false);
is("all-TBA sitting stays TBA",
  collapseFloorSessions([M({ minutes: 600, tba: true }), M({ minutes: 700, tba: true })])[0].tba, true);
// A livestream posted against any part of the sitting covers the whole sitting.
is("links adopted from whichever marker carries them",
  collapseFloorSessions([M({ minutes: 600 }), M({ minutes: 700, meetingUrl: "u" })])[0].meetingUrl, "u");

// --- never guess ------------------------------------------------------------------------------------
// A floor marker with NO chamber cannot be attributed, so it stays its own card rather than being
// folded into a chamber we picked.
const noChamber = [M({ chamber: null, committee: "Joint Assembly convened", minutes: 600 }),
                   M({ chamber: null, committee: "Joint Assembly adjourned", minutes: 700 })];
is("chamberless markers are not merged", collapseFloorSessions(noChamber).length, 2);
is("single floor card is passed through untouched",
  collapseFloorSessions([M({ minutes: 600 })])[0].markers.length, 0);
is("empty day", collapseFloorSessions([]), []);

// --- the kind that decides whether we collapse at all -----------------------------------------------
is("House Convenes is floor", classifyMeetingKind("House Convenes"), "floor");
is("Senate adjourned is floor", classifyMeetingKind("Senate adjourned"), "floor");
is("a real committee is not floor", classifyMeetingKind("Senate General Laws and Technology"), "committee");
is("a caucus is not floor", classifyMeetingKind("Rural Caucus"), "committee");

console.log(`\n${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
