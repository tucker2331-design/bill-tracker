import { useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { furthestStage } from "../data/derive";
import { BillBox } from "../components/BillBox";
import { isCeremonial, splitByClass, ceremonialLabel } from "../data/billclass";
import { STATE } from "../states";
import { countPipeline } from "../data/pipeline_rules";
import { ChamberSubway } from "../components/ChamberSubway";

// The pipeline (vision §3b), drawn as the chamber subway: ONE map for every state, each state supplying settings
// (owner 2026-11-02; Virginia moved onto it 2026-11-16 -- its own v9 drawing retired). Two lines, one per chamber a
// bill started in, swapping tracks for the second chamber and meeting at the Governor. Every count opens the same
// grouped bill list. Rules: data/pipeline_rules.ts; drawing: components/ChamberSubway.tsx.
const PIPE = STATE.pipelineMap;
// Where a bill's stage comes from is a state setting: PA's job writes it; Virginia derives it from LIS's own floor
// and crossover fields (data/derive.ts furthestStage -- the same rule its old map used).
const stageOf = PIPE?.stageSource === "derived" ? (b: Bill) => furthestStage(b) : (b: Bill) => b.pipeline?.stage;
const STAGE_LABEL: Record<string, string> = Object.fromEntries(STATE.stages.map((x) => [x.id, x.label]));
// stations that share a label ("Committee" twice) get "· 1st" / "· 2nd" so the two columns read apart
const PIPE_LABELS: Record<string, string> = PIPE ? Object.fromEntries(PIPE.stations.map((st) => {
  const lab = STAGE_LABEL[st] ?? st, dup = PIPE.stations.filter((o) => (STAGE_LABEL[o] ?? o) === lab);
  return [st, dup.length > 1 ? `${lab} · ${dup.indexOf(st) === 0 ? "1st" : "2nd"}` : lab];
})) : {};
const PIPE_ALL_LABELS: Record<string, string> = { ...PIPE_LABELS, governor: STAGE_LABEL.governor ?? "Governor", law: STAGE_LABEL.law ?? "Law" };
const OUT_DRILL: Record<string, string> = { awaiting_governor: "Waiting for the Governor", vetoed: "Vetoed by the Governor" };

function pipeDrillLabel(key: string): string {
  const p = key.split("|");
  if (p[0] === "out") return p[1] === "signed" ? PIPE_ALL_LABELS.law : OUT_DRILL[p[1]] ?? p[1];
  if (p[0] === "tot") return p[1] === "ended" ? `All ${PIPE?.endedWord}` : p[1] === "parked" ? `All ${PIPE?.parkedWord}` : "All idle";
  const sub = p[3] === "ended" ? PIPE?.endedWord : p[3] === "parked" ? PIPE?.parkedWord : p[3];
  const where = `${p[2]} · ${PIPE_ALL_LABELS[p[1]] ?? p[1]}`;
  return p[0] === "at" ? `${where} · here now` : `${where} · ${sub}`;
}

export function Timeline({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const pipe = useMemo(() => PIPE ? countPipeline(bills, PIPE, STATE.chambers, new Date(), stageOf) : null, [bills]);
  // the drill lists: the subway's keys map to bill ids
  const cellBills = useMemo(() => {
    const byId = new Map(bills.map((b) => [b.bill, b]));
    return new Map([...(pipe?.keys ?? new Map<string, string[]>())].map(([k, ids]) => [k, ids.map((id) => byId.get(id)!).filter(Boolean)]));
  }, [pipe, bills]);

  const [drill, setDrill] = useState<string | null>(null);
  // Sort the drilled bills the way the rest of the app groups them (owner 2026-06-30): by chamber, then by
  // committee / subcommittee (lastCommittee sorts subcommittees under their parent since they're named
  // "Committee - Subcommittee"), then bill number. So a stranded/outcome list reads in a familiar order.
  const drillBills: Bill[] = useMemo(() => {
    const list = drill ? (cellBills.get(drill) ?? []) : [];
    return [...list].sort((a, b) =>
      (a.chamber ?? "").localeCompare(b.chamber ?? "")
      || (a.lastCommittee ?? "").localeCompare(b.lastCommittee ?? "")
      || a.bill.localeCompare(b.bill, undefined, { numeric: true }));
  }, [drill, cellBills]);

  // Grouped for scanning (owner 2026-07-03: "there are so many — group by House/Senate → committee →
  // sub"). drillBills is already sorted chamber→committee→bill, and lastCommittee is chamber-qualified and
  // names the subcommittee inline ("House Appropriations - Transportation & Public Safety Subcommittee"),
  // so walking it in order and breaking on a committee change yields exactly that hierarchy. Capped so a
  // huge stage (500+ bills) can't flood the DOM; the count in each header is the FULL group size.
  const DRILL_CAP = 300;
  const drillGroups = useMemo(() => {
    const groups: { committee: string; bills: Bill[] }[] = [];
    for (const b of drillBills) {
      const committee = b.lastCommittee || `${b.chamber} · not yet in committee`;
      const last = groups[groups.length - 1];
      if (last && last.committee === committee) last.bills.push(b);
      else groups.push({ committee, bills: [b] });
    }
    return groups;
  }, [drillBills]);

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  const openDrill = (k: string, n: number) => n > 0 && setDrill(k);
  // Every count on the map is a real control: click / Enter / Space opens the same grouped list the old spine did.
  const hit = (k: string, n: number, label: string) => n > 0 ? {
    "data-k": k, role: "button", tabIndex: 0, "aria-label": `${label}: ${n} bills — list them`,
    onClick: () => openDrill(k, n),
    onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDrill(k, n); } },
  } : { "aria-label": `${label}: 0` };

  return (
    <div>
      <div className="subway" aria-label="Where every bill stands">
        {PIPE && pipe ? <ChamberSubway s={PIPE} c={pipe} labels={PIPE_ALL_LABELS} hit={hit} />
          : <p className="center-msg">{STATE.name} has no pipeline map settings yet.</p>}
      </div>
      {pipe && pipe.skipped > 0 && (
        <p className="muted" style={{ marginTop: "var(--s2)" }}>{pipe.skipped.toLocaleString()} bills have no place on the map this cycle (no stage, or an outcome the map does not draw) and are not drawn.</p>
      )}
      {pipe && pipe.notDrawn > 0 && (
        <p className="muted" style={{ marginTop: "var(--s2)" }}>{pipe.notDrawn.toLocaleString()} resolutions are not drawn: they are settled in one chamber or never go to the Governor.</p>
      )}
      {drill && (
        <div style={{ marginTop: "var(--s5)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--s2)" }}>
            <h3 className="h" style={{ margin: 0 }}>{pipeDrillLabel(drill)} — {drillBills.length} bill(s)</h3>
            <button type="button" className="filters" style={{ boxShadow: "none", background: "transparent" }} onClick={() => setDrill(null)}>✕ clear</button>
          </div>
          {(() => { let shown = 0; return drillGroups.map((g) => {
            if (shown >= DRILL_CAP) return null;
            // SUBSTANTIVE FIRST, within the cap. The drill-down is capped, so in a session that is 98%
            // commending resolutions the cap would fill with ceremony and the real bills would never render
            // — the exact "digging through them for a real bill" problem. Ordering by class costs nothing
            // and guarantees the bills that matter are the ones that survive the cap.
            const ordered = [...g.bills].sort((a, b) => Number(isCeremonial(a)) - Number(isCeremonial(b)));
            const slice = ordered.slice(0, DRILL_CAP - shown); shown += slice.length;
            const gSplit = splitByClass(g.bills);
            return (
              <div key={g.committee} className="drill-group">
                <div className="drill-grouphdr">{g.committee} <span className="muted">· {g.bills.length}{slice.length < g.bills.length ? ` (showing first ${slice.length})` : ""}
                  {/* Counted in place, never removed: the reader can see WHY a group is large. */}
                  {gSplit.ceremonial.length > 0 && <> · incl. {ceremonialLabel(gSplit)}</>}</span></div>
                <div className="billgrid">
                  {slice.map((b) => <BillBox key={b.bill} bill={b} onOpen={onOpen} />)}
                </div>
              </div>
            );
          }); })()}
          {drillBills.length > DRILL_CAP && (
            <p className="muted" style={{ marginTop: "var(--s2)" }}>Showing the first {DRILL_CAP} of {drillBills.length} — narrow the scope or open a bill to see more.</p>
          )}
        </div>
      )}
    </div>
  );
}
