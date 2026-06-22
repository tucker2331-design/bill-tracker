import { useSyncExternalStore } from "react";

// The global Tracking ↔ full-GA switch + the org's tracked (starred) set. No backend yet for the
// tracked list (clients/positions are parked in the vision §9), so it lives in localStorage and the
// star in the bill card/box is how you build it. A module store keeps every view in sync.

export type Scope = "tracking" | "full";

const STAR_KEY = "bt.tracked";
const SCOPE_KEY = "bt.scope";

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };

function readStarred(): Set<string> {
  try { return new Set<string>(JSON.parse(localStorage.getItem(STAR_KEY) || "[]")); }
  catch { return new Set<string>(); }
}

// New users have 0 tracked bills, so default scope is "full" (otherwise the app looks empty); once
// they star bills they flip to "Tracking".
let starred: Set<string> = readStarred();
let scope: Scope = localStorage.getItem(SCOPE_KEY) === "tracking" ? "tracking" : "full";

const getScope = () => scope;
const getStarred = () => starred;   // identity is stable until a toggle replaces the Set (snapshot-safe)

export function setScope(s: Scope) { scope = s; localStorage.setItem(SCOPE_KEY, s); emit(); }

export function toggleTracked(id: string) {
  const next = new Set(starred);
  if (next.has(id)) next.delete(id); else next.add(id);
  starred = next;
  localStorage.setItem(STAR_KEY, JSON.stringify([...starred]));
  emit();
}

export function useScope(): [Scope, (s: Scope) => void] {
  return [useSyncExternalStore(subscribe, getScope), setScope];
}

export function useStarred(): Set<string> {
  return useSyncExternalStore(subscribe, getStarred);
}
