// Route table + parse/build — the PURE half of the router (no runtime imports), split out of router.ts so the
// bare-node golden (state/__tests__/routes.regression.mjs) can import the real code via web/tools/ts2mjs.mjs.
// router.ts re-exports everything here; callers keep importing from "./router".

/** The tabs that existed before routing. Kept as-is so nothing about them changes except the URL. */
export const TAB_IDS = ["today", "calendar", "search", "warroom", "health"] as const;
export type TabId = (typeof TAB_IDS)[number];

/** Entity kinds that have their own pages. `subject` is a filter AND a profile (owner, 2026-07-27). */
export const ENTITY_KINDS = ["bills", "legislators", "committees", "subjects"] as const;
export type EntityKind = (typeof ENTITY_KINDS)[number];

export type Route =
  | { kind: "tab"; tab: TabId }
  // A tracked bill drilled into from the War Room list (owner 2026-07-17: "your bills -> drill in"). It lives
  // UNDER the War Room tab's path, so the tab stays lit and Back returns to the list.
  | { kind: "warroom_bill"; id: string }
  | { kind: "list"; entity: EntityKind }
  | { kind: "detail"; entity: EntityKind; id: string };

const TAB_PATH: Record<TabId, string> = {
  today: "/",
  calendar: "/calendar",
  search: "/search",
  warroom: "/war-room",
  health: "/health",
};

const PATH_TAB = new Map<string, TabId>(
  (Object.entries(TAB_PATH) as [TabId, string][]).map(([t, p]) => [p, t]),
);

export const HOME: Route = { kind: "tab", tab: "today" };

/**
 * Parse a pathname into a Route. Unknown paths fall back to HOME rather than throwing.
 *
 * A 404 view is deliberately NOT introduced here: the server already serves index.html for any path, so an
 * unknown path is a typo or a stale link, and dropping the user on Today is friendlier than a dead end. If
 * that ever hides a real broken link, the fix is a 404 view, not a silent redirect — noted so the choice is
 * revisitable rather than invisible.
 */
export function parseRoute(pathname: string): Route {
  const clean = pathname.replace(/\/+$/, "") || "/";
  const tab = PATH_TAB.get(clean);
  if (tab) return { kind: "tab", tab };

  const parts = clean.split("/").filter(Boolean);
  if (`/${parts[0]}` === TAB_PATH.warroom) {
    if (parts.length !== 2) return HOME;
    // A malformed escape ("%E0") makes decodeURIComponent THROW; a stale link must land on Today, not crash.
    try { return { kind: "warroom_bill", id: decodeURIComponent(parts[1]) }; } catch { return HOME; }
  }
  const entity = parts[0] as EntityKind | undefined;
  if (!entity || !(ENTITY_KINDS as readonly string[]).includes(entity)) return HOME;

  // Ids are decoded here so callers never see percent-encoding. A committee id may contain a space.
  if (parts.length === 1) return { kind: "list", entity };
  if (parts.length === 2) {
    // Same guard as the War Room path: a malformed escape must land on Today, never throw (Gemini #251).
    try { return { kind: "detail", entity, id: decodeURIComponent(parts[1]) }; } catch { return HOME; }
  }
  return HOME;
}

/** Build a path from a Route. The inverse of parseRoute — kept adjacent so they cannot drift apart. */
export function routePath(r: Route): string {
  if (r.kind === "tab") return TAB_PATH[r.tab];
  if (r.kind === "warroom_bill") return `${TAB_PATH.warroom}/${encodeURIComponent(r.id)}`;
  if (r.kind === "list") return `/${r.entity}`;
  return `/${r.entity}/${encodeURIComponent(r.id)}`;
}

export const tabPath = (t: TabId) => TAB_PATH[t];
export const detailPath = (entity: EntityKind, id: string) =>
  routePath({ kind: "detail", entity, id });
export const warRoomBillPath = (id: string) => routePath({ kind: "warroom_bill", id });

/** Which tab's nav item is lit for a route. A bill card (/bills/X) keeps the old Search chrome. */
export function tabOf(r: Route): TabId {
  if (r.kind === "tab") return r.tab;
  if (r.kind === "warroom_bill") return "warroom";
  return "search";
}

