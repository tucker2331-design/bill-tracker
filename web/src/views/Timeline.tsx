import { useMemo, useState } from "react";
import type { Bill, Chamber } from "../data/types";
import { deriveStage, type Stage } from "../data/derive";
import { BillBox } from "../components/BillBox";

// The crossover-lane pipeline (vision §3b) as a smooth integrated SPINE. Owner 2026-06-30: failure and the
// terminal outcomes must live IN the pipeline geometry, not a separate box below it. So death is shown WHERE
// it happened — a "✕ stranded here" sub-count at each stage — and the governor node BRANCHES into the decided
// outcomes (✓ Signed / ⧗ Awaiting / ▲ Vetoed), with veto reserved the attention color. Click any count to
// drill into those bills.
const COLUMNS: { stage: Stage; label: string }[] = [
  { stage: "prefiled", label: "Prefiled" },
  { stage: "committee1", label: "Committee" },
  { stage: "committee2", label: "Committee · 2nd" },
  { stage: "governor", label: "To Governor" },
];

// Stage of death for a dead/carried bill: the last stage it structurally reached. Derivable now from the same
// fields deriveStage uses (crossed / lastCommittee); committee-vs-floor granularity waits on the Floor-stage
// backend field ([[design/ui_redesign_spec]] item 4). deriveStage collapses all deaths into "died"; this
// recovers WHERE.
const lastReached = (b: Bill): Stage => {
  if (!b.lastCommittee) return "prefiled";
  // committee1 vs committee2 from the LAST committee's chamber vs the bill's ORIGIN chamber — NOT crossedOver,
  // which is an "ever crossed" flag that never unsets and so over-attributes deaths to committee2 when a
  // bill's latest committee-bearing action is back in its origin chamber (Qodo #187). If the last committee
  // is in the other chamber, the bill had crossed and died there (committee2); otherwise it's committee1.
  const inOtherChamber = b.chamber === "House" ? b.lastCommittee.startsWith("Senate")
    : b.chamber === "Senate" ? b.lastCommittee.startsWith("House") : false;
  return inOtherChamber ? "committee2" : "committee1";
};
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
        const kk = `${lastReached(b)}|${side}`;
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

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  const openDrill = (k: string, n: number) => n > 0 && setDrill(k);
  const kbd = (k: string, n: number) => (e: React.KeyboardEvent) => {
    if (n > 0 && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setDrill(k); }
  };

  // One side's counts at a stage: the advancing number + a small "✕ stranded here" sub-count (dead/carried
  // that died at this stage), so failure reads at the stage it occurred instead of a footnote below.
  const Count = ({ stage, side }: { stage: Stage; side: Chamber }) => {
    const kk = `${stage}|${side}`;
    const n = alive[kk] || 0;
    const dead = stranded[kk] || 0;
    const aliveKey = `alive|${kk}`, deadKey = `stranded|${kk}`;
    const stageLabel = COLUMNS.find((c) => c.stage === stage)?.label ?? stage;
    return (
      <div className="scount">
        <span className={`count ${side === "Senate" ? "s" : "h"} ${n === 0 ? "zero" : ""}`}
          onClick={() => openDrill(aliveKey, n)} role={n > 0 ? "button" : undefined} tabIndex={n > 0 ? 0 : undefined}
          onKeyDown={kbd(aliveKey, n)}
          aria-label={n > 0 ? `${side} advancing at ${stageLabel}: ${n} bills — list them` : `${side} advancing at ${stageLabel}: 0`}>{n}</span>
        {dead > 0 && (
          <span className="scount-dead" onClick={() => openDrill(deadKey, dead)} role="button" tabIndex={0}
            onKeyDown={kbd(deadKey, dead)}
            aria-label={`${side} died or carried over at ${stageLabel}: ${dead} bills — list them`}>✕{dead}</span>
        )}
        <span className="countlbl">{side}</span>
      </div>
    );
  };

  const OutBtn = ({ kind, label }: { kind: OutKind; label: string }) => {
    const n = outcome[kind]; const key = `out|${kind}`;
    return (
      <button type="button" className={`out-btn ${kind}${n === 0 ? " zero" : ""}`} disabled={n === 0}
        onClick={() => openDrill(key, n)} aria-label={`${label}: ${n} bills${n > 0 ? " — list them" : ""}`}>
        <span className="out-n">{n}</span><span className="out-l">{label}</span>
      </button>
    );
  };

  return (
    <div>
      <div className="spine-legend">
        <span><span className="swatch" style={{ background: "var(--senate)" }} />Senate · above</span>
        <span><span className="swatch" style={{ background: "var(--house)" }} />House · below</span>
        <span><span className="swatch" style={{ background: "var(--o-dead)" }} />✕ died / carried over at that stage</span>
        <span className="muted">Position is progress — a bill crosses the line at crossover; the spine ends in the decided outcome.</span>
      </div>

      <div className="spine">
        {/* Stage names as a clear HEADER row above the spine — kept OFF the count area so they no longer
            collide with the SENATE / HOUSE labels (owner 2026-06-30). */}
        <div className="stage-heads">
          {COLUMNS.map((c) => <div key={c.stage} className="stage-head">{c.stage === "governor" ? "Outcome" : c.label}</div>)}
        </div>
        <div className="spine-body">
          <div className="track" />
          <div className="seam" style={{ left: "50%" }}><span className="seamlbl">CROSSOVER</span></div>
          <div className="snodes">
            {COLUMNS.map((c) => c.stage === "governor" ? (
              <div className="snode outcome" key="gov">
                <div className="out-fork">
                  <OutBtn kind="signed" label="Signed" />
                  <OutBtn kind="awaiting" label="Awaiting" />
                  <OutBtn kind="vetoed" label="Vetoed" />
                  <OutBtn kind="carried" label="Carried over" />
                  <OutBtn kind="dead" label="Died" />
                </div>
              </div>
            ) : (
              <div className="snode" key={c.stage}>
                <div className="above"><Count stage={c.stage} side="Senate" /></div>
                <div className="dot" />
                <div className="below"><Count stage={c.stage} side="House" /></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {drill && (
        <div style={{ marginTop: "var(--s5)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--s2)" }}>
            <h3 className="h" style={{ margin: 0 }}>{drillLabel(drill)} — {drillBills.length} bill(s)</h3>
            <button type="button" className="filters" style={{ boxShadow: "none", background: "transparent" }} onClick={() => setDrill(null)}>✕ clear</button>
          </div>
          <div className="billgrid">
            {drillBills.slice(0, 200).map((b) => <BillBox key={b.bill} bill={b} onOpen={onOpen} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function drillLabel(key: string): string {
  const p = key.split("|");
  if (p[0] === "out") return ({ signed: "Signed by the Governor", vetoed: "Vetoed", awaiting: "Awaiting the Governor", carried: "Carried over to next session", dead: "Died / failed" } as Record<string, string>)[p[1]] ?? p[1];
  const stage = COLUMNS.find((c) => c.stage === p[1])?.label ?? p[1];
  if (p[0] === "stranded") return `Died / carried over · ${stage} · ${p[2]}`;
  return `${p[2]} · ${stage}`; // alive
}
