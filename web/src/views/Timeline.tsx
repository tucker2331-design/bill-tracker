import { useMemo, useState } from "react";
import type { Bill, Chamber } from "../data/types";
import { deriveStage, furthestStage, stageSide, STAGE_ORDER, type Stage } from "../data/derive";
import { BillBox } from "../components/BillBox";
import { isCeremonial, splitByClass, ceremonialLabel } from "../data/billclass";

// The pipeline (vision §3b), drawn as the SUBWAY (owner-approved v9, 2026-10-27). The counting is unchanged from
// the spine it replaces: still-here per stage per side, "✕ ended here" per stage per side, and the outcome fork.
// Death is shown WHERE it happened, and every count opens the same grouped bill list.
// The spine's SHORT display labels, over the single-sourced STAGE_ORDER (CodeRabbit #191: the order must
// never fork from derive.ts — only the compact wording is local to this view).
const SPINE_LABEL: Record<Stage, string> = {
  prefiled: "Prefiled", committee1: "Committee", floor1: "Floor",
  committee2: "Committee · 2nd", floor2: "Floor · 2nd", governor: "To Governor", died: "Died",
};
const COLUMNS: { stage: Stage; label: string }[] = STAGE_ORDER.map((s) => ({ stage: s, label: SPINE_LABEL[s] }));

// Stage of death for a dead/carried bill: the last stage it structurally reached — now the SAME
// furthestStage() the live pipeline uses (origin/second floor via passedHouse/passedSenate), so a ✕ lands
// at the true stage (e.g. a bill that cleared its origin floor then died crossing shows ✕ at Floor, not
// Committee). deriveStage collapses all deaths into "died"; this recovers WHERE.
const lastReached = (b: Bill): Stage => furthestStage(b);
type OutKind = "signed" | "awaiting" | "vetoed" | "carried" | "dead";

export function Timeline({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const { alive, stranded, outcome, cellBills } = useMemo(() => {
    const alive: Record<string, number> = {};      // "stage|side" -> advancing count
    const stranded: Record<string, number> = {};   // "stage|side" -> died/carried AT that stage
    const outcome: Record<OutKind, number> = { signed: 0, awaiting: 0, vetoed: 0, carried: 0, dead: 0 };
    const cellBills = new Map<string, Bill[]>();    // drill key -> bills
    const push = (k: string, b: Bill) => (cellBills.get(k) ?? cellBills.set(k, []).get(k)!).push(b);
    for (const b of bills) {
      const cell = deriveStage(b);
      const side = cell.side;
      if (cell.stage === "died") {
        // Lane from the DEATH stage (stageSide), not b.chamber — a crossed-then-returned bill would
        // otherwise key an impossible cell like committee2|origin (Qodo #191).
        const ds = lastReached(b);
        const kk = `${ds}|${stageSide(b, ds)}`;
        stranded[kk] = (stranded[kk] || 0) + 1;
        push(`stranded|${kk}`, b);
        // ALSO tally the terminal END-STATE so the Outcome fork shows the full branching tail (carried over /
        // died) alongside the governor outcomes — the aggregate the old died-row tiles carried, now integrated
        // into the spine's terminal fork (owner 2026-07-02). The per-stage ✕N above still shows WHERE it died.
        const term: OutKind = b.outcome === "carried_over" ? "carried" : "dead";
        outcome[term] += 1;
        push(`out|${term}`, b);
      } else if (cell.stage === "governor") {
        const oc: OutKind = b.outcome === "signed" ? "signed" : b.outcome === "vetoed" ? "vetoed" : "awaiting";
        outcome[oc] += 1;
        push(`out|${oc}`, b);
      } else {
        const kk = `${cell.stage}|${side}`;
        alive[kk] = (alive[kk] || 0) + 1;
        push(`alive|${kk}`, b);
      }
    }
    return { alive, stranded, outcome, cellBills };
  }, [bills]);

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
        <svg viewBox="0 0 1000 410" role="img" aria-label="Pipeline: two lines, one per starting chamber, that swap tracks at crossover and meet at the Governor">
          <SubwayMap alive={alive} stranded={stranded} outcome={outcome} hit={hit} />
        </svg>
      </div>
      {drill && (
        <div style={{ marginTop: "var(--s5)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--s2)" }}>
            <h3 className="h" style={{ margin: 0 }}>{drillLabel(drill)} — {drillBills.length} bill(s)</h3>
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

// ── The subway (v9, owner-approved 2026-10-27; built on real data 2026-10-29) ────────────────────────────────────
// Two LINES, one per chamber a bill STARTED in. Before crossover each runs on its own chamber's track; at crossover
// they swap tracks (a House bill is heard on the Senate side afterwards — the Timeline's "side" semantics, so every
// station count is exactly the old spine's alive[stage|side]). "✕ N" branches off a station = bills that ENDED there
// (died or carried over). The lines meet at the Governor, which forks into signed / awaiting / vetoed.
// Colour: the two lines are greys (they only need telling apart); colour is reserved for standing meanings —
// red = ended / vetoed, amber = carried over, accent = awaiting, near-white = signed. Geometry from the mockup.
const SX: Partial<Record<Stage, number>> = { prefiled: 90, committee1: 230, floor1: 370, committee2: 570, floor2: 710 };
const Y_SENATE = 140, Y_HOUSE = 280, GX = 840, GY = 210;
const LINE_SENATE = "#C9D0D4", LINE_HOUSE = "#6E787E";   // the Senate-started and House-started lines
const OUT_COLOR: Record<"signed" | "awaiting" | "vetoed", string> = { signed: "var(--o-signed)", awaiting: "var(--accent)", vetoed: "var(--red)" };
type Hit = (k: string, n: number, label: string) => Record<string, unknown>;

function SubwayMap({ alive, stranded, outcome, hit }: {
  alive: Record<string, number>; stranded: Record<string, number>; outcome: Record<OutKind, number>; hit: Hit;
}) {
  const n = (v: number) => v.toLocaleString();
  const stations = COLUMNS.filter((c) => c.stage !== "governor");
  return (
    <g className="sw">
      <line x1="470" x2="470" y1="52" y2="352" stroke="var(--line-strong)" strokeDasharray="4 5" />
      <text x="470" y="368" className="sw-th" textAnchor="middle">Crossover</text>
      <text x="24" y={Y_SENATE - 50} className="sw-th">Senate</text>
      <text x="24" y={Y_HOUSE + 66} className="sw-th">House</text>
      {/* the Senate-started line: Senate track, swaps to the House track at crossover, ends at the Governor */}
      <path d={`M20 ${Y_SENATE} H410 C470 ${Y_SENATE} 470 ${Y_HOUSE} 530 ${Y_HOUSE} H760 C805 ${Y_HOUSE} 805 ${GY} ${GX} ${GY}`}
        fill="none" stroke={LINE_SENATE} strokeWidth="6" strokeLinecap="round" />
      <path d={`M20 ${Y_HOUSE} H410 C470 ${Y_HOUSE} 470 ${Y_SENATE} 530 ${Y_SENATE} H760 C805 ${Y_SENATE} 805 ${GY} ${GX} ${GY}`}
        fill="none" stroke={LINE_HOUSE} strokeWidth="6" strokeLinecap="round" />
      {stations.map(({ stage, label }) => {
        const x = SX[stage]!;
        return (
          <g key={stage}>
            <text x={x} y="40" className="sw-th" textAnchor="middle">{label}</text>
            {(["Senate", "House"] as Chamber[]).map((side) => {
              const y = side === "Senate" ? Y_SENATE : Y_HOUSE, up = side === "Senate";
              const post = stage === "committee2" || stage === "floor2";
              const line = (side === "Senate") !== post ? LINE_SENATE : LINE_HOUSE;   // which line runs here
              const kk = `${stage}|${side}`, still = alive[kk] || 0, ended = stranded[kk] || 0, dy = up ? 34 : -34;
              return (
                <g key={side}>
                  <circle cx={x} cy={y} r="10" fill="var(--surface)" stroke={line} strokeWidth="4" />
                  <text x={x} y={up ? y - 24 : y + 38} textAnchor="middle" className={`sw-n${still ? "" : " zero"}`}
                    {...hit(`alive|${kk}`, still, `${side} · ${label} · still here`)}>{n(still)}</text>
                  {ended > 0 && <>
                    <line x1={x} y1={y} x2={x + 20} y2={y + dy} stroke="var(--red)" strokeOpacity=".7" strokeWidth="3" strokeLinecap="round" />
                    <text x={x + 26} y={y + dy + (up ? 10 : 0)} className="sw-e"
                      {...hit(`stranded|${kk}`, ended, `${side} · ${label} · ended here`)}>✕ {n(ended)}</text>
                  </>}
                </g>
              );
            })}
          </g>
        );
      })}
      <circle cx={GX} cy={GY} r="16" fill="var(--surface)" stroke="var(--o-signed)" strokeWidth="4" />
      <text x={GX} y={GY + 40} className="sw-th" textAnchor="middle">Governor</text>
      {([["signed", 150, "Signed"], ["awaiting", 210, "Awaiting"], ["vetoed", 270, "Vetoed"]] as const).map(([o, y, label]) => (
        <g key={o}>
          <path d={`M${GX + 16} ${GY} C${GX + 40} ${GY} ${GX + 40} ${y} ${GX + 66} ${y}`} fill="none" stroke={OUT_COLOR[o]} strokeWidth="3" />
          <text x={GX + 74} y={y + 6} className={`sw-m${outcome[o] ? "" : " zero"}`} {...hit(`out|${o}`, outcome[o], label)}>{n(outcome[o])}</text>
          <text x={GX + 74 + 12 + 9 * n(outcome[o]).length} y={y + 5} className="sw-l">{label}</text>
        </g>
      ))}
      <text x="20" y="392" className="sw-l">Ended along the line:</text>
      <text x="150" y="392" className="sw-carry" {...hit("out|carried", outcome.carried, "Carried over")}>{n(outcome.carried)} carried over</text>
      <text x="290" y="392" className="sw-e" {...hit("out|dead", outcome.dead, "Died")}>{n(outcome.dead)} died</text>
      <line x1="560" x2="590" y1="388" y2="388" stroke={LINE_SENATE} strokeWidth="5" />
      <text x="598" y="392" className="sw-l">started in the Senate</text>
      <line x1="760" x2="790" y1="388" y2="388" stroke={LINE_HOUSE} strokeWidth="5" />
      <text x="798" y="392" className="sw-l">started in the House</text>
    </g>
  );
}

function drillLabel(key: string): string {
  const p = key.split("|");
  if (p[0] === "out") return ({ signed: "Signed by the Governor", vetoed: "Vetoed", awaiting: "Awaiting the Governor", carried: "Carried over to next session", dead: "Died / failed" } as Record<string, string>)[p[1]] ?? p[1];
  const stage = COLUMNS.find((c) => c.stage === p[1])?.label ?? p[1];
  if (p[0] === "stranded") return `Died / carried over · ${stage} · ${p[2]}`;
  return `${p[2]} · ${stage}`; // alive
}
