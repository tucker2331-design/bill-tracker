// The chamber subway's counting rules (owner 2026-11-02: one map for every state, each state supplies settings).
// Pure and dependency-free so the bare-node golden (data/__tests__/pipeline.regression.mjs) runs the real code.
//
// A bill sits at a STATION (its stage) on a TRACK (the chamber that stage happens in: the bill's first chamber, or
// the other one for the state's second-chamber stages). Where the stage comes from is a setting: PA's job writes it
// (Bill.pipeline.stage); Virginia derives it from LIS's own floor/crossover fields (data/derive.ts furthestStage),
// passed in as `stageOf`. Each bill is counted at most once, most final first:
//   out    — an outcome at the Governor (signed / awaiting / vetoed): counted on the Governor's fork
//   ended  — the bill stopped for good at this station: an outcome the state lists as ended (VA: LIS's Failed flag ->
//            "dead"), or defeated on the floor of the chamber it sits in. Drawn as "✕ N", NOT in the station count.
//   parked — stopped but may return: an outcome the state lists as parked (VA: carried over to the next session), or
//            the source's own "tabled / re-committed" mark (PA: Bill.pipeline.parked)
//   idle   — no action for the state's idle threshold (derived from the last action date)
// The station count is every bill still on the line there (moving + idle + parked), so the sub-counts never overlap
// and every total is a plain sum. Bills the map does not draw are COUNTED (notDrawn / skipped), never dropped.

export interface PipelineSettings {
  stations: string[];          // the stages drawn as stations, in order
  otherChamber: string[];      // stages that happen in the second chamber
  mapBills: RegExp;            // which ids are bills on this map (resolutions end in one chamber: not drawn)
  idleDays: number;            // no action for this long = idle
  governorOutcomes: string[];  // outcomes the source carries at the Governor ("signed", "awaiting_governor", "vetoed")
  endedOutcomes: string[];     // outcomes that stop a bill for good where it stands (VA ["dead"]; PA none)
  parkedOutcomes: string[];    // outcomes that stop a bill but let it return (VA ["carried_over"]; PA none)
  stageSource: "pipeline" | "derived";   // PA: the job's Bill.pipeline.stage; VA: derived from LIS fields (stageOf)
  swapLabel: string;           // the first track change: "Crossover" (VA's deadline) or "to the other chamber"
  endedWord: string;           // what an ended bill is called on the map: "died" (VA) / "defeated" (PA)
  parkedWord: string;          // what a parked bill is called: "carried over" (VA) / "parked" (PA)
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
  skipped: number;                            // bills on the map with no stage, or an outcome the map has no place for
  notDrawn: number;                           // ids off the map's pattern (resolutions): counted, never placed
  keys: Map<string, string[]>;                // drill key -> bill ids
}

const origin = (bill: string, chambers: Record<string, Chamber>): Chamber | null => chambers[bill[0]] ?? null;
const other = (c: Chamber): Chamber => (c === "House" ? "Senate" : "House");

export function trackOf(stage: string, first: Chamber, s: PipelineSettings): Chamber {
  return s.otherChamber.includes(stage) ? other(first) : first;
}

// A last-action date as each source writes it: ISO "2026-10-29" (PA) or "4/8/2026" (VA LIS). Anything else -> NaN
// (never idle: an unreadable date is not evidence of quiet). Explicit, not Date.parse's engine-specific guesses.
export function dayOf(s: string): number {
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (iso) return Date.UTC(+iso[1], +iso[2] - 1, +iso[3]);
  const us = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s.trim());
  return us ? Date.UTC(+us[3], +us[1] - 1, +us[2]) : NaN;
}

export function countPipeline<B extends PipeBill>(bills: B[], s: PipelineSettings, chambers: Record<string, Chamber>, today: Date,
  stageOf: (b: B) => string | null | undefined = (b) => b.pipeline?.stage): PipelineCounts {
  const c: PipelineCounts = { at: {}, sub: {}, out: {}, totals: { ended: 0, parked: 0, idle: 0, moving: 0 }, skipped: 0, notDrawn: 0, keys: new Map() };
  const push = (k: string, id: string) => (c.keys.get(k) ?? c.keys.set(k, []).get(k)!).push(id);
  const idleBefore = today.getTime() - s.idleDays * 864e5;
  for (const b of bills) {
    if (!s.mapBills.test(b.bill)) { c.notDrawn++; continue; }
    if (s.governorOutcomes.includes(b.outcome)) { c.out[b.outcome] = (c.out[b.outcome] || 0) + 1; push(`out|${b.outcome}`, b.bill); continue; }
    const endedOutcome = s.endedOutcomes.includes(b.outcome), parkedOutcome = s.parkedOutcomes.includes(b.outcome);
    if (b.outcome !== "in_progress" && !endedOutcome && !parkedOutcome) { c.skipped++; continue; }   // an outcome with no place: counted
    const first = origin(b.bill, chambers);
    const st = stageOf(b);
    if (!first || !st || !s.stations.includes(st)) { c.skipped++; continue; }
    const track = trackOf(st, first, s);
    const k = `${st}|${track}`;
    const floor = track === "House" ? b.floorHouse : b.floorSenate;
    const t = dayOf(b.lastAction);
    const sub: SubState = endedOutcome || (st.startsWith("floor") && floor === "defeated") ? "ended"
      : parkedOutcome || b.pipeline?.parked ? "parked"
      : Number.isFinite(t) && t < idleBefore ? "idle" : "moving";
    c.totals[sub]++;
    if (sub !== "moving") push(`tot|${sub}`, b.bill);   // the totals row opens every bill in that sub-state
    if (sub !== "ended") { c.at[k] = (c.at[k] || 0) + 1; push(`at|${k}`, b.bill); }   // ended bills left the line
    if (sub !== "moving") { const kk = `${k}|${sub}`; c.sub[kk] = (c.sub[kk] || 0) + 1; push(`sub|${kk}`, b.bill); }
  }
  return c;
}
