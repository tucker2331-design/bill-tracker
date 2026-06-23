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

// The crossover-lane pipeline stage. Position = progress; the divider is crossover. Floor stages are
// folded into the committee flow for v1 (the Bill_Tracker data doesn't cleanly separate floor from
// between-committee; the calendar subsystem owns that granularity).
export type Stage = "prefiled" | "committee1" | "committee2" | "governor" | "died";

export interface StageCell { stage: Stage; side: Chamber; crossed: boolean; decided: boolean; }

export function deriveStage(b: Bill): StageCell {
  const side = b.chamber;
  const crossed = b.crossedOver;
  const decided = isDecided(b);
  let stage: Stage;
  if (b.outcome === "dead" || b.outcome === "carried_over") {
    stage = "died";
  } else if (b.outcome === "signed" || b.outcome === "vetoed" || b.outcome === "awaiting_governor") {
    stage = "governor";
  } else if (crossed) {
    stage = "committee2";                       // second chamber, still moving
  } else if (b.lastCommittee) {
    stage = "committee1";                       // first chamber committee
  } else {
    stage = "prefiled";
  }
  return { stage, side, crossed, decided };
}

export const STAGE_LABEL: Record<Stage, string> = {
  prefiled: "Prefiled",
  committee1: "In Committee",
  committee2: "In Committee (2nd)",
  governor: "To Governor",
  died: "Died",
};

// Left→right pipeline order, with the crossover divider sitting between committee1 and committee2.
export const STAGE_ORDER: Stage[] = ["prefiled", "committee1", "committee2", "governor"];

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
