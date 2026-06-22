import { useSyncExternalStore } from "react";

// The global Tracking ↔ full-GA switch + the org's tracked (starred) set. No backend yet for the
// tracked list (clients/positions are parked in the vision §9), so it lives in localStorage and the
// star in the bill card/box is how you build it. A module store keeps every view in sync.

export type Scope = "tracking" | "full";

const STAR_KEY = "bt.tracked";
const SCOPE_KEY = "bt.scope";

// localStorage can throw (private mode, blocked, quota) — never let storage access crash the app.
function safeGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeSet(key: string, val: string) {
  try { localStorage.setItem(key, val); } catch { /* storage unavailable — in-memory only this session */ }
}

function readStarred(): Set<string> {
  try {
    const v = JSON.parse(safeGet(STAR_KEY) || "[]");
    // Guard the shape: a stray non-array (e.g. a bare string) must NOT be spread into a Set, or
    // `new Set("HB1")` would split it into characters {'H','B','1'} (Gemini/Qodo #164).
    return new Set<string>(Array.isArray(v) ? v.filter((x) => typeof x === "string") : []);
  } catch { return new Set<string>(); }
}

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };

// New users have 0 tracked bills, so default scope is "full" (otherwise the app looks empty); once
// they star bills they flip to "Tracking".
let starred: Set<string> = readStarred();
let scope: Scope = safeGet(SCOPE_KEY) === "tracking" ? "tracking" : "full";

const getScope = () => scope;
const getStarred = () => starred;   // identity is stable until a toggle replaces the Set (snapshot-safe)

export function setScope(s: Scope) { scope = s; safeSet(SCOPE_KEY, s); emit(); }

export function toggleTracked(id: string) {
  const next = new Set(starred);
  if (next.has(id)) next.delete(id); else next.add(id);
  starred = next;
  safeSet(STAR_KEY, JSON.stringify([...starred]));
  emit();
}

export function useScope(): [Scope, (s: Scope) => void] {
  return [useSyncExternalStore(subscribe, getScope), setScope];
}

export function useStarred(): Set<string> {
  return useSyncExternalStore(subscribe, getStarred);
}
