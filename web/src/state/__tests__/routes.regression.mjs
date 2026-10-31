/**
 * Route table goldens — the War Room bill page lives UNDER the War Room tab (owner 2026-07-17: "your bills ->
 * drill in"), and every other path parses exactly as before.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/state/routes.ts /tmp/routes.mjs \
 *         && node web/src/state/__tests__/routes.regression.mjs
 */
import { parseRoute, routePath, tabOf, warRoomBillPath, detailPath } from "/tmp/routes.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

// ---- unchanged routes
is("root is Today", parseRoute("/"), { kind: "tab", tab: "today" });
is("war room list", parseRoute("/war-room"), { kind: "tab", tab: "warroom" });
is("trailing slash", parseRoute("/war-room/"), { kind: "tab", tab: "warroom" });
is("bill card", parseRoute("/bills/HB1515"), { kind: "detail", entity: "bills", id: "HB1515" });
is("unknown -> home", parseRoute("/nope"), { kind: "tab", tab: "today" });

// ---- the War Room bill page
is("war room bill", parseRoute("/war-room/HB1515"), { kind: "warroom_bill", id: "HB1515" });
is("war room bill decodes", parseRoute("/war-room/HB%201"), { kind: "warroom_bill", id: "HB 1" });
is("too deep -> home", parseRoute("/war-room/HB1/x"), { kind: "tab", tab: "today" });
is("malformed escape -> home, no throw", parseRoute("/war-room/%E0"), { kind: "tab", tab: "today" });
is("path round-trips", parseRoute(warRoomBillPath("SB 7")), { kind: "warroom_bill", id: "SB 7" });
is("path shape", warRoomBillPath("HB1515"), "/war-room/HB1515");
is("bill card path unchanged", detailPath("bills", "HB1515"), "/bills/HB1515");

// ---- which tab is lit
is("war room bill lights War Room", tabOf({ kind: "warroom_bill", id: "HB1" }), "warroom");
is("bill card keeps Search chrome", tabOf({ kind: "detail", entity: "bills", id: "HB1" }), "search");
is("a tab is itself", tabOf({ kind: "tab", tab: "health" }), "health");
is("routePath of a tab", routePath({ kind: "tab", tab: "warroom" }), "/war-room");

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
