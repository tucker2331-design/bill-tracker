/**
 * REGRESSION TESTS — the 2026-07-28 wrong-sheet defect.
 *
 * Run:  npx esbuild web/src/data/incidents.ts --format=esm --outfile=/tmp/incidents.mjs \
 *         && node web/src/data/__tests__/incidents.regression.mjs
 *
 * The first five cases replay the EXACT payload production received: gviz answered a request for the
 * missing `Incident_Log` tab with the calendar's CSV, and `SortTime` values were read as incident classes.
 * If these ever pass trivially again, the header guard has been removed.
 */
import { counterFromRows } from "/tmp/incidents.mjs";
let pass=0,fail=0;
const is=(n,g,w)=>{const ok=JSON.stringify(g)===JSON.stringify(w);
  console.log(`  ${ok?"ok  ":"FAIL"} ${n}${ok?"":`  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`);ok?pass++:fail++;};

// THE REGRESSION — the exact shape production received on 2026-07-28.
const wrongHeader=["Date","Time","SortTime","Status","Committee"];
const wrongRow=["2025-11-03","2:00 PM","14:00","","Virginia Land Conservation Foundation"];
const bad=counterFromRows([wrongHeader,wrongRow,wrongRow,wrongRow]);
is("wrong sheet -> flagged",        bad.wrongSheet, true);
is("wrong sheet -> NO open incidents", bad.openNow.length, 0);
is("wrong sheet -> not available",  bad.available, false);
is("wrong sheet -> daysClean null", bad.daysClean, null);
is("wrong sheet -> no fake incidents", bad.incidentsEver, 0);

const H=["StartUTC","EndUTC","Class","Summary","DetectedBy"];
const NOW=new Date("2026-07-28T00:00:00Z");
const good=counterFromRows([H,
  ["2026-06-01T00:00:00Z","","_genesis","monitoring begins","owner"],
  ["2026-07-01T00:00:00Z","2026-07-02T00:00:00Z","API_FAILURE","outage","sentinel"]],NOW);
is("real tab -> not wrongSheet",  good.wrongSheet, false);
is("real tab -> available",       good.available, true);
is("real tab -> 1 incident ever", good.incidentsEver, 1);
is("real tab -> 26 days clean",   good.daysClean, 26);
is("real tab -> monitoring 57d",  good.monitoringDays, 57);

const open=counterFromRows([H,
  ["2026-06-01T00:00:00Z","","_genesis","begin","owner"],
  ["2026-07-20T00:00:00Z","","DATA_ANOMALY","still open","sentinel"]],NOW);
is("open incident surfaced",      open.openNow, ["DATA_ANOMALY"]);
is("clock reads from its start",  open.daysClean, 8);

// genesis/drill still excluded from the clock
const drill=counterFromRows([H,
  ["2026-06-01T00:00:00Z","","_genesis","begin","owner"],
  ["2026-07-25T00:00:00Z","2026-07-25T01:00:00Z","_drill","fire drill","owner"]],NOW);
is("drill is not an incident",    drill.incidentsEver, 0);
is("drill does not reset clock",  drill.daysClean, 57);
is("drill age reported",          drill.lastDrillDays, 2);

// empty / blank-padded sheet is 'not seeded', NOT wrongSheet
is("empty sheet -> not wrongSheet", counterFromRows([]).wrongSheet, false);
console.log(`\n${pass} of ${pass+fail} passed`);
process.exit(fail?1:0);
