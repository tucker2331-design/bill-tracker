// The state this deployment serves. ⚠ Standard #6 seam, kept to ONE line on purpose: a deployment serves one
// state today, and when the user's profile carries the state this becomes a lookup, not a hunt. Nothing outside
// web/src/states/ may name a state or its publisher — read STATE instead.
import { VA } from "./va";
import { PA } from "./pa";
import type { StateConfig } from "./types";

export const STATES: Record<string, StateConfig> = { [VA.code]: VA, [PA.code]: PA };
// Chosen WHEN THE SITE IS BUILT (VITE_STATE=PA npm run build); unset = Virginia, the existing site. An unknown code
// fails the build's first page load loudly rather than silently serving Virginia's rules under another name.
const wanted = String(import.meta.env.VITE_STATE || "VA").toUpperCase();
if (!STATES[wanted]) throw new Error(`Unknown VITE_STATE ${wanted}; known: ${Object.keys(STATES).join(", ")}`);
export const STATE: StateConfig = STATES[wanted];
export type { StateConfig, StageDef } from "./types";

/** The chamber a bill number names as its origin, from the STATE's prefix map; null for an unknown prefix (each
 *  caller keeps its own pre-split fallback, so the split moves no VA output). */
export const originChamber = (bill: string): "House" | "Senate" | null =>
  STATE.chambers[bill.charAt(0).toUpperCase()] ?? null;
