// The Action_Where tab, read through the signed-in Worker. Same caching rule as the roster: an "unavailable" answer is
// never cached, and the feed then shows each line without a "(where)" — never a guessed one.
import { sheetUrl } from "../config";
import { apiFetch } from "../state/auth";
import { parseCsv } from "./gviz";
import { parseWhereGrid, type WhereLoad } from "./action_where_rules";

export * from "./action_where_rules";

const TAB = "Action_Where";
let cached: Promise<WhereLoad> | null = null;

export function loadActionWhere(): Promise<WhereLoad> {
  if (cached) return cached;
  const p: Promise<WhereLoad> = apiFetch(sheetUrl(TAB), { cache: "no-store" })
    .then(async (res) => (res.ok ? parseWhereGrid(parseCsv(await res.text())) : { status: "unavailable", reason: "no_tab" } as WhereLoad))
    .catch((e) => { console.warn("Action_Where: read failed", e); return { status: "unavailable", reason: "no_tab" } as WhereLoad; })
    .then((r) => { if (r.status !== "ok") cached = null; return r; });
  cached = p;
  return p;
}
