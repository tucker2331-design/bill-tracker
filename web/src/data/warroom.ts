// The served War Room member calls, read ONLY through the signed-in Worker (/api/sheet) from the private
// `War_Room_Calls` tab. Rules (parsing, groups, order) live in warroom_rules.ts so they are golden-tested.
// An "unavailable" answer is never cached (a missing tab or a transient error must not stick for the session,
// the #240 lesson); every bill then reads "can't call", which is the honest state, never a guess.
import { sheetUrl } from "../config";
import { apiFetch } from "../state/auth";
import { parseCsv } from "./gviz";
import { parseCallsGrid, type CallsLoad } from "./warroom_rules";

export * from "./warroom_rules";

const TAB = "War_Room_Calls";
let cached: Promise<CallsLoad> | null = null;

export function loadCalls(): Promise<CallsLoad> {
  if (cached) return cached;
  const p: Promise<CallsLoad> = apiFetch(sheetUrl(TAB), { cache: "no-store" })
    .then(async (res) => (res.ok ? parseCallsGrid(parseCsv(await res.text())) : { status: "unavailable", reason: "no_tab" } as CallsLoad))
    .catch((e) => {
      console.warn("War Room calls: read failed", e);
      return { status: "unavailable", reason: "no_tab" } as CallsLoad;
    })
    .then((r) => { if (r.status !== "ok") cached = null; return r; });
  cached = p;
  return p;
}
