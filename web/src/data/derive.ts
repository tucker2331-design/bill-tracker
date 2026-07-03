import type { Bill, Chamber } from "./types";
import type { Scope } from "../state/tracking";
import { dateSort } from "./dates";

// Structural derivations for the views — all from the fields bill_tracker already emits, no guessing.

export function scopedBills(bills: Bill[], scope: Scope, starred: Set<string>): Bill[] {
  return scope === "tracking" ? bills.filter((b) => starred.has(b.bill)) : bills;
}

// Is the outcome terminal? (governor acted / died) → "decided"; else the org can still act.
export function isDecided(b: Bill): boolean {
  return b.outcome === "signed" || b.outcome === "vetoed" || b.outcome === "dead" || b.outcome === "carried_over";
}

// The crossover-lane pipeline stage. Position = progress; the divider is crossover. The two FLOOR stages
// (origin-chamber floor before crossover, second-chamber floor after) are now first-class — the bill
// backend emits floorHouse/floorSenate structurally (LIS's controlled "passed/defeated by House/Senate"
// vocabulary), so a bill that reached a chamber's FLOOR is distinct from one still in that chamber's
// committee, and a floor DEFEAT strands its ✕ at Floor rather than Committee.
export type Stage = "prefiled" | "committee1" | "floor1" | "committee2" | "floor2" | "governor" | "died";

export interface StageCell { stage: Stage; side: Chamber; crossed: boolean; decided: boolean; }

// The FURTHEST pipeline stage a bill structurally reached (shared by deriveStage for live bills and
// lastReached for died bills — same progression, so a died bill's ✕ lands at the right spot). Origin is
// the bill's own chamber (HB→House, SB→Senate); the per-chamber floor events map onto origin-vs-second.
// A floor event of EITHER kind (passed OR defeated) means the bill reached that floor — a defeat is a
// floor death, so its ✕ belongs at Floor, not Committee. Checked furthest→nearest.
export function furthestStage(b: Bill): Stage {
  const origin: Chamber = b.bill[0]?.toUpperCase() === "S" ? "Senate" : "House";
  const floorOrigin = origin === "House" ? b.floorHouse : b.floorSenate;
  const floorSecond = origin === "House" ? b.floorSenate : b.floorHouse;
  if (floorSecond) return "floor2";                // reached the SECOND chamber's floor (passed or defeated there)
  if (b.crossedOver) return "committee2";          // reached a committee in the opposite chamber
  if (floorOrigin) return "floor1";                // reached the ORIGIN chamber's floor (passed or defeated there)
  if (b.lastCommittee) return "committee1";        // still in the origin chamber's committee
  return "prefiled";
}

export function deriveStage(b: Bill): StageCell {
  const side = b.chamber;
  const crossed = b.crossedOver;
  const decided = isDecided(b);
  let stage: Stage;
  if (b.outcome === "dead" || b.outcome === "carried_over") {
    stage = "died";
  } else if (b.outcome === "signed" || b.outcome === "vetoed" || b.outcome === "awaiting_governor") {
    stage = "governor";
  } else {
    stage = furthestStage(b);
  }
  return { stage, side, crossed, decided };
}

export const STAGE_LABEL: Record<Stage, string> = {
  prefiled: "Prefiled",
  committee1: "In Committee",
  floor1: "Floor",
  committee2: "In Committee (2nd)",
  floor2: "Floor (2nd)",
  governor: "To Governor",
  died: "Died",
};

// Left→right pipeline order, with the crossover divider sitting between floor1 and committee2.
export const STAGE_ORDER: Stage[] = ["prefiled", "committee1", "floor1", "committee2", "floor2", "governor"];

export interface OutcomeTally { signed: number; vetoed: number; awaiting_governor: number; dead: number; carried_over: number; in_progress: number; }

export function tallyOutcomes(bills: Bill[]): OutcomeTally {
  const t: OutcomeTally = { signed: 0, vetoed: 0, awaiting_governor: 0, dead: 0, carried_over: 0, in_progress: 0 };
  for (const b of bills) t[b.outcome]++;
  return t;
}

// Flatten every bill's history into a dated feed (newest first) for the "what's new" lens.
export interface FeedItem { bill: string; title: string; action: string; date: string; sortKey: number; }

export function buildFeed(bills: Bill[]): FeedItem[] {
  const items: FeedItem[] = [];
  for (const b of bills) {
    for (const h of b.history) {
      items.push({ bill: b.bill, title: b.title, action: h.action, date: h.date, sortKey: dateSort(h.date) });
    }
  }
  items.sort((a, b) => b.sortKey - a.sortKey);
  return items;
}
