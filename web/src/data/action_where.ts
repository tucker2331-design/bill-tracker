// The Action_Where tab, read through the signed-in Worker. When it is unavailable the feed shows each line without a
// "(where)" — never a guessed one.
import { sheetUrl } from "../config";
import { apiFetch } from "../state/auth";
import { parseCsv } from "./gviz";
import { parseWhereGrid, type WhereLoad } from "./action_where_rules";

export * from "./action_where_rules";

const TAB = "Action_Where";

// Not cached (Codex #260): the feed asks again whenever the bill data refreshes, so the index join always pairs
// a history with the where-codes of the same run. A mismatch that still slips through is caught in feedLines
// (a code string whose length differs from the bill's history is not used).
export function loadActionWhere(): Promise<WhereLoad> {
  return apiFetch(sheetUrl(TAB), { cache: "no-store" })
    .then(async (res) => (res.ok ? parseWhereGrid(parseCsv(await res.text())) : { status: "unavailable", reason: "no_tab" } as WhereLoad))
    .catch((e) => { console.warn("Action_Where: read failed", e); return { status: "unavailable", reason: "no_tab" } as WhereLoad; });
}
