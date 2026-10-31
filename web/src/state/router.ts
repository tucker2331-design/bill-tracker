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
import { parseRoute, routePath, type Route } from "./routes";

export * from "./routes";

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
