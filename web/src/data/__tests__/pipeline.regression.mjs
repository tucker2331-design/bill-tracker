/**
 * The chamber subway's counting rules (owner 2026-11-02). Rows mirror real PA records from the 2025_0 export.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/data/pipeline_rules.ts /tmp/pipeline_rules.mjs \
 *         && node web/src/data/__tests__/pipeline.regression.mjs
 */
import { countPipeline, trackOf } from "/tmp/pipeline_rules.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

const S = { stations: ["introduced", "committee1", "floor1", "committee2", "floor2", "concurrence"],
  otherChamber: ["committee2", "floor2"], mapBills: /^[HS]B\d/, idleDays: 365, governorOutcomes: ["signed", "awaiting_governor"] };
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
is("one sub-state per bill: ended > parked > idle", [c.sub["floor1|House|ended"], c.sub["floor1|House|parked"], c.sub["committee1|House|idle"]], [1, 1, 1]);
is("totals are plain sums (no overlap)", c.totals, { ended: 1, parked: 1, idle: 1, moving: 1 });
is("law counted at the Governor fork", c.out.signed, 1);
is("a resolution is not drawn", Object.values(c.at).reduce((a, x) => a + x, 0), 4);
is("a bill with no pipeline field is counted as skipped, never placed", c.skipped, 1);
is("drill keys list the bills", c.keys.get("at|committee2|House"), ["SB509"]);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
