// The chamber subway's counting rules (owner 2026-11-02: one map for every state, each state supplies settings).
// Pure and dependency-free so the bare-node golden (data/__tests__/pipeline.regression.mjs) runs the real code.
//
// A bill sits at a STATION (its stage, from the state's own job: Bill.pipeline.stage) on a TRACK (the chamber that
// stage happens in: the bill's first chamber, or the other one for the state's second-chamber stages). Each bill is
// counted ONCE at its station, and at most once in ONE sub-state, most specific first:
//   ended  — defeated on the floor of the chamber it sits in (the source's floor result, structural)
//   parked — the source's own "tabled / re-committed" mark (Bill.pipeline.parked), may return
//   idle   — no action for the state's idle threshold (derived from the last action date)
// so the sub-counts never overlap and every total is a plain sum.

export interface PipelineSettings {
  stations: string[];          // the stages drawn as stations, in order
  otherChamber: string[];      // stages that happen in the second chamber
  mapBills: RegExp;            // which ids are bills on this map (resolutions end in one chamber: not drawn)
  idleDays: number;            // no action for this long = idle
  governorOutcomes: string[];  // outcomes the source carries at the Governor ("signed", "awaiting_governor", "vetoed")
}

export interface PipeBill {
  bill: string; outcome: string; lastAction: string;   // date of the most recent action (Bill.lastAction)
  floorHouse: string; floorSenate: string;
  pipeline?: { stage: string; parked: boolean } | null;
}
type Chamber = "House" | "Senate";
export type SubState = "ended" | "parked" | "idle" | "moving";

export interface PipelineCounts {
  at: Record<string, number>;                 // "stage|track" -> bills sitting there
  sub: Record<string, number>;                // "stage|track|ended|parked|idle" -> bills
  out: Record<string, number>;                // governor outcome -> bills
  totals: Record<SubState, number>;
  skipped: number;                            // bills on the map's id pattern with no pipeline field (counted, never placed)
  keys: Map<string, string[]>;                // drill key -> bill ids
}

const origin = (bill: string, chambers: Record<string, Chamber>): Chamber | null => chambers[bill[0]] ?? null;
const other = (c: Chamber): Chamber => (c === "House" ? "Senate" : "House");

export function trackOf(stage: string, first: Chamber, s: PipelineSettings): Chamber {
  return s.otherChamber.includes(stage) ? other(first) : first;
}

export function countPipeline(bills: PipeBill[], s: PipelineSettings, chambers: Record<string, Chamber>, today: Date): PipelineCounts {
  const c: PipelineCounts = { at: {}, sub: {}, out: {}, totals: { ended: 0, parked: 0, idle: 0, moving: 0 }, skipped: 0, keys: new Map() };
  const push = (k: string, id: string) => (c.keys.get(k) ?? c.keys.set(k, []).get(k)!).push(id);
  const idleBefore = today.getTime() - s.idleDays * 864e5;
  for (const b of bills) {
    if (!s.mapBills.test(b.bill)) continue;
    if (s.governorOutcomes.includes(b.outcome)) { c.out[b.outcome] = (c.out[b.outcome] || 0) + 1; push(`out|${b.outcome}`, b.bill); continue; }
    if (b.outcome !== "in_progress") continue;          // e.g. adopted: not a bill outcome on this map
    const first = origin(b.bill, chambers);
    const st = b.pipeline?.stage;
    if (!first || !st || !s.stations.includes(st)) { c.skipped++; continue; }
    const track = trackOf(st, first, s);
    const k = `${st}|${track}`;
    c.at[k] = (c.at[k] || 0) + 1; push(`at|${k}`, b.bill);
    const floor = track === "House" ? b.floorHouse : b.floorSenate;
    const t = Date.parse(b.lastAction);
    const sub: SubState = st.startsWith("floor") && floor === "defeated" ? "ended"
      : b.pipeline?.parked ? "parked"
      : Number.isFinite(t) && t < idleBefore ? "idle" : "moving";
    c.totals[sub]++;
    if (sub !== "moving") { const kk = `${k}|${sub}`; c.sub[kk] = (c.sub[kk] || 0) + 1; push(`sub|${kk}`, b.bill); }
  }
  return c;
}
