// Routing — queue item F1.
//
// WHY A HAND-ROLLED ROUTER AND NOT react-router:
// this app has exactly TWO runtime dependencies (react, react-dom) and the route set is flat — no nesting,
// no loaders, no layouts. A router library would triple the runtime dependency count and add an upgrade
// treadmill to a product that must run for years unattended (Standard #8). ~70 lines of History API is the
// smaller long-term liability here. If nested routes or data-loading routes ever appear, revisit.
//
// The server side is ALREADY correct: `wrangler.toml` sets `not_found_handling = "single-page-application"`,
// so a deep link like /legislators/S0098 serves index.html rather than 404ing. This file is the client half.
//
// WHY ROUTING AT ALL (docs/design/object_page_patterns §1b): every core object gets card / list / DETAIL
// representations. We had cards and lists and never built a detail, which is the same thing as saying our
// objects have no URLs. Nothing can be linked, bookmarked, or shared until they do.

import { useCallback, useEffect, useState } from "react";

/** The tabs that existed before routing. Kept as-is so nothing about them changes except the URL. */
export const TAB_IDS = ["today", "calendar", "search", "warroom", "health"] as const;
export type TabId = (typeof TAB_IDS)[number];

/** Entity kinds that have their own pages. `subject` is a filter AND a profile (owner, 2026-07-27). */
export const ENTITY_KINDS = ["bills", "legislators", "committees", "subjects"] as const;
export type EntityKind = (typeof ENTITY_KINDS)[number];

export type Route =
  | { kind: "tab"; tab: TabId }
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
  const entity = parts[0] as EntityKind | undefined;
  if (!entity || !(ENTITY_KINDS as readonly string[]).includes(entity)) return HOME;

  // Ids are decoded here so callers never see percent-encoding. A committee id may contain a space.
  if (parts.length === 1) return { kind: "list", entity };
  if (parts.length === 2) return { kind: "detail", entity, id: decodeURIComponent(parts[1]) };
  return HOME;
}

/** Build a path from a Route. The inverse of parseRoute — kept adjacent so they cannot drift apart. */
export function routePath(r: Route): string {
  if (r.kind === "tab") return TAB_PATH[r.tab];
  if (r.kind === "list") return `/${r.entity}`;
  return `/${r.entity}/${encodeURIComponent(r.id)}`;
}

export const tabPath = (t: TabId) => TAB_PATH[t];
export const detailPath = (entity: EntityKind, id: string) =>
  routePath({ kind: "detail", entity, id });

/** Imperative navigation. Exported for handlers that are not links. */
export function navigate(to: Route | string, opts: { replace?: boolean } = {}): void {
  const path = typeof to === "string" ? to : routePath(to);
  if (path === window.location.pathname) return;   // no-op: never stack duplicate history entries
  if (opts.replace) window.history.replaceState({}, "", path);
  else window.history.pushState({}, "", path);
  // pushState does NOT fire popstate, so subscribers would never hear about our own navigations.
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/** Current route, re-rendering on back/forward and on navigate(). */
export function useRoute(): [Route, (to: Route | string) => void] {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname));
  useEffect(() => {
    const onPop = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const go = useCallback((to: Route | string) => navigate(to), []);
  return [route, go];
}

/**
 * Props for an anchor that navigates in-app.
 *
 * A REAL `href` is non-negotiable: it is what makes middle-click, cmd-click, "copy link", and a screen
 * reader's link list work. Intercepting click on a <span> breaks all four silently. Modified clicks are
 * left to the browser on purpose.
 */
export function linkProps(to: Route | string) {
  const href = typeof to === "string" ? to : routePath(to);
  return {
    href,
    onClick: (e: React.MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      navigate(href);
    },
  };
}
