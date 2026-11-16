/**
 * The chamber subway's counting rules (owner 2026-11-02). Rows mirror real PA records from the 2025_0 export.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/data/pipeline_rules.ts /tmp/pipeline_rules.mjs \
 *         && node web/src/data/__tests__/pipeline.regression.mjs
 */
import { countPipeline, trackOf, dayOf } from "/tmp/pipeline_rules.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

const S = { stations: ["introduced", "committee1", "floor1", "committee2", "floor2", "concurrence"],
  otherChamber: ["committee2", "floor2"], mapBills: /^[HS]B\d/, idleDays: 365, governorOutcomes: ["signed", "awaiting_governor"],
  endedOutcomes: [], parkedOutcomes: [], stageSource: "pipeline", swapLabel: "to the other chamber", endedWord: "defeated", parkedWord: "parked" };
const CH = { H: "House", S: "Senate" };
const TODAY = new Date("2026-10-31T12:00:00Z");
const b = (bill, stage, extra = {}) => ({ bill, outcome: "in_progress", lastAction: "2026-10-01", floorHouse: "", floorSenate: "",
  pipeline: { stage, parked: false }, ...extra });

is("tracks: first-chamber stages on the bill's own track", [trackOf("committee1", "House", S), trackOf("floor1", "Senate", S)], ["House", "Senate"]);
is("tracks: second-chamber stages on the other track", [trackOf("committee2", "House", S), trackOf("floor2", "Senate", S)], ["Senate", "House"]);
is("tracks: concurrence back on the first chamber's track", trackOf("concurrence", "House", S), "House");

const c = countPipeline([
  b("SB509", "committee2", { lastAction: "2026-10-29" }),                                  // in a House committee
  b("HB20", "committee1", { lastAction: "2025-07-14" }),                                   // idle 1 yr+
  b("HB1099", "floor1", { floorHouse: "defeated", pipeline: { stage: "floor1", parked: true } }),   // ended beats parked
  b("HB22", "floor1", { pipeline: { stage: "floor1", parked: true }, lastAction: "2025-01-08" }),    // parked beats idle
  { bill: "HB17", outcome: "signed", lastAction: "2026-02-11", floorHouse: "passed", floorSenate: "passed", pipeline: { stage: "law", parked: false } },
  { bill: "HR1", outcome: "adopted", lastAction: "2025-01-07", floorHouse: "", floorSenate: "", pipeline: { stage: "adopted", parked: false } },
  { bill: "SB1", outcome: "in_progress", lastAction: "2025-01-07", floorHouse: "", floorSenate: "", pipeline: null },
], S, CH, TODAY);
is("SB509 sits at Committee · 2nd on the House track", c.at["committee2|House"], 1);
is("an ended bill has left the line: not in its station count", c.at["floor1|House"], 1);
is("one sub-state per bill: ended > parked > idle", [c.sub["floor1|House|ended"], c.sub["floor1|House|parked"], c.sub["committee1|House|idle"]], [1, 1, 1]);
is("totals are plain sums (no overlap)", c.totals, { ended: 1, parked: 1, idle: 1, moving: 1 });
is("law counted at the Governor fork", c.out.signed, 1);
is("still on the line: moving + idle + parked (the ended one is not)", Object.values(c.at).reduce((a, x) => a + x, 0), 3);
is("a resolution is counted as not drawn, never dropped", c.notDrawn, 1);
is("a bill with no pipeline field is counted as skipped, never placed", c.skipped, 1);
is("the totals row opens every bill in that sub-state", [c.keys.get("tot|ended"), c.keys.get("tot|parked"), c.keys.get("tot|idle")], [["HB1099"], ["HB22"], ["HB20"]]);
is("drill keys list the bills", c.keys.get("at|committee2|House"), ["SB509"]);


// ── Virginia on the same rules (owner 2026-11-16): stage derived from LIS fields, outcome-based ended/parked ──
const VA = { stations: ["prefiled", "committee1", "floor1", "committee2", "floor2"], otherChamber: ["committee2", "floor2"],
  mapBills: /^[HS]B\d/, idleDays: 31, governorOutcomes: ["signed", "awaiting_governor", "vetoed"],
  endedOutcomes: ["dead"], parkedOutcomes: ["carried_over"], stageSource: "derived", swapLabel: "Crossover", endedWord: "died", parkedWord: "carried over" };
const v = (bill, stage, outcome, lastAction, extra = {}) => ({ bill, outcome, lastAction, floorHouse: "", floorSenate: "", stage, ...extra });
const VA_TODAY = new Date("2026-02-20T12:00:00Z");
const vc = countPipeline([
  v("HB1", "committee1", "dead", "2/3/2026"),                 // tabled in committee -> died there
  v("SB2", "committee2", "carried_over", "2/18/2026"),        // carried over in the House -> parked there
  v("HB3", "floor1", "in_progress", "1/10/2026"),            // 41 days quiet -> idle
  v("HB4", "committee2", "in_progress", "2/19/2026"),        // moving
  v("HB5", "floor2", "vetoed", "4/8/2026"),
  v("HJ6", "floor1", "in_progress", "2/1/2026"),             // a joint resolution: counted, not drawn
], VA, CH, VA_TODAY, (b) => b.stage);
is("VA: a dead bill is ✕ at its stage, off the station count", [vc.sub["committee1|House|ended"], vc.at["committee1|House"] ?? 0], [1, 0]);
is("VA: carried over is parked at the station it reached (House track for an SB's 2nd committee)", [vc.sub["committee2|House|parked"], vc.at["committee2|House"]], [1, 1]);
is("VA: 41 days quiet (M/D/YYYY date) -> idle; 1 day -> moving", [vc.sub["floor1|House|idle"], vc.at["committee2|Senate"]], [1, 1]);
is("VA: vetoed on the Governor's fork", vc.out.vetoed, 1);
is("VA: joint resolution counted as not drawn", vc.notDrawn, 1);
is("VA totals", vc.totals, { ended: 1, parked: 1, idle: 1, moving: 1 });
is("dates: ISO and LIS M/D/YYYY read the same day; junk is NaN (never idle)", [dayOf("2026-02-03") === dayOf("2/3/2026"), Number.isNaN(dayOf("Feb 3"))], [true, true]);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
