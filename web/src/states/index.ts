// The state this deployment serves. ⚠ Standard #6 seam, kept to ONE line on purpose: a deployment serves one
// state today, and when the user's profile carries the state this becomes a lookup, not a hunt. Nothing outside
// web/src/states/ may name a state or its publisher — read STATE instead.
import { VA } from "./va";
import type { StateConfig } from "./types";

export const STATES: Record<string, StateConfig> = { [VA.code]: VA };
export const STATE: StateConfig = VA;
export type { StateConfig, StageDef } from "./types";

/** The chamber a bill number names as its origin, from the STATE's prefix map; null for an unknown prefix (each
 *  caller keeps its own pre-split fallback, so the split moves no VA output). */
export const originChamber = (bill: string): "House" | "Senate" | null =>
  STATE.chambers[bill.charAt(0).toUpperCase()] ?? null;
