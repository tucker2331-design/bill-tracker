// The committee roster, read ONLY through the signed-in Worker (/api/sheet) from the `Committee_Roster` tab (PA).
// Same caching rule as the War Room calls: an "unavailable" answer is never cached (the #240 lesson), so a missing
// tab or a transient error does not stick for the session; the page then says the roster is unavailable.
import { sheetUrl } from "../config";
import { apiFetch } from "../state/auth";
import { parseCsv } from "./gviz";
import { parseRosterGrid, type RosterLoad } from "./roster_rules";

export * from "./roster_rules";

const TAB = "Committee_Roster";
let cached: Promise<RosterLoad> | null = null;

export function loadRoster(): Promise<RosterLoad> {
  if (cached) return cached;
  const p: Promise<RosterLoad> = apiFetch(sheetUrl(TAB), { cache: "no-store" })
    .then(async (res) => (res.ok ? parseRosterGrid(parseCsv(await res.text())) : { status: "unavailable", reason: "no_tab" } as RosterLoad))
    .catch((e) => {
      console.warn("Committee roster: read failed", e);
      return { status: "unavailable", reason: "no_tab" } as RosterLoad;
    })
    .then((r) => { if (r.status !== "ok") cached = null; return r; });
  cached = p;
  return p;
}
