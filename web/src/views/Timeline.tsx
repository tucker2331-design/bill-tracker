import { useMemo, useState } from "react";
import type { Bill, Chamber } from "../data/types";
import { deriveStage, STAGE_LABEL, type Stage } from "../data/derive";
import { BillBox } from "../components/BillBox";

// The crossover-lane pipeline (vision §3b), redrawn as a smooth integrated SPINE rather than boxes:
// one centerline a bill literally crosses, Senate counts floating above it, House below, with the
// crossover as a thin seam (not a wide column). Click a count to drill into those bills.
const COLUMNS: { stage: Stage; label: string }[] = [
  { stage: "prefiled", label: "Prefiled" },
  { stage: "committee1", label: "Committee" },
  { stage: "committee2", label: "Committee · 2nd" },
  { stage: "governor", label: "To Governor" },
];

type DrillKey = string;

export function Timeline({ bills, onOpen, embedded = false }: { bills: Bill[]; onOpen: (b: Bill) => void; embedded?: boolean }) {
  const { counts, cellBills, died } = useMemo(() => {
    const counts: Record<string, number> = {};
    const cellBills = new Map<DrillKey, Bill[]>();
    const died = { Senate: [] as Bill[], House: [] as Bill[] };
    for (const b of bills) {
      const cell = deriveStage(b);
      if (cell.stage === "died") { died[cell.side].push(b); continue; }
      const key = `${cell.stage}|${cell.side}`;
      counts[key] = (counts[key] || 0) + 1;
      (cellBills.get(key) ?? cellBills.set(key, []).get(key)!).push(b);
    }
    return { counts, cellBills, died };
  }, [bills]);

  const [drill, setDrill] = useState<DrillKey | null>(null);

  const Count = ({ stage, side }: { stage: Stage; side: Chamber }) => {
    const key = `${stage}|${side}`;
    const n = counts[key] || 0;
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <span className={`count ${side === "Senate" ? "s" : "h"} ${n === 0 ? "zero" : ""}`}
          onClick={() => n > 0 && setDrill(key)} role={n > 0 ? "button" : undefined}
          tabIndex={n > 0 ? 0 : undefined}
          onKeyDown={(e) => { if (n > 0 && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setDrill(key); } }}
          title={n > 0 ? "List these bills" : ""}>{n}</span>
        <span className="countlbl">{side}</span>
      </div>
    );
  };

  const drillBills: Bill[] = drill
    ? (drill.startsWith("died|") ? died[drill.endsWith("Senate") ? "Senate" : "House"] : cellBills.get(drill) ?? [])
    : [];

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  return (
    <div>
      {!embedded && (
        <div className="spine-legend">
          <span><span className="swatch" style={{ background: "var(--senate)" }} />Senate · above the line</span>
          <span><span className="swatch" style={{ background: "var(--house)" }} />House · below the line</span>
          <span className="muted">Position is progress — a bill crosses the line at crossover.</span>
        </div>
      )}

      <div className="spine">
        <div className="track" />
        <div className="seam" style={{ left: "50%" }}><span className="seamlbl">CROSSOVER</span></div>
        <div className="snodes">
          {COLUMNS.map((c) => (
            <div className="snode" key={c.stage}>
              <div className="above"><Count stage={c.stage} side="Senate" /></div>
              <div className="dot" />
              <div className="below"><Count stage={c.stage} side="House" /></div>
              <div className="lbl">{c.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="died-row">
        <DiedStat side="Senate" bills={died.Senate} onClick={() => died.Senate.length && setDrill("died|Senate")} />
        <DiedStat side="House" bills={died.House} onClick={() => died.House.length && setDrill("died|House")} />
        <span className="muted">Died / carried over — stranded, no longer advancing this session.</span>
      </div>

      {drill && (
        <div style={{ marginTop: "var(--s5)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--s2)" }}>
            <h3 className="h" style={{ margin: 0 }}>{drillLabel(drill)} — {drillBills.length} bill(s)</h3>
            <button className="filters" style={{ boxShadow: "none", background: "transparent" }} onClick={() => setDrill(null)}>✕ clear</button>
          </div>
          <div className="billgrid">
            {drillBills.slice(0, 200).map((b) => <BillBox key={b.bill} bill={b} onOpen={onOpen} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function DiedStat({ side, bills, onClick }: { side: Chamber; bills: Bill[]; onClick: () => void }) {
  return (
    <div className="stat" style={{ cursor: bills.length ? "pointer" : "default", minWidth: 130, borderLeft: `3px solid var(--${side === "Senate" ? "senate" : "house"})` }} onClick={onClick}>
      <div className="n" style={{ color: side === "Senate" ? "var(--senate)" : "var(--house)" }}>{bills.length.toLocaleString()}</div>
      <div className="l">{side} died / carried</div>
    </div>
  );
}

function drillLabel(key: string): string {
  const [stage, side] = key.split("|");
  const label = stage === "died" ? "Died / carried over" : STAGE_LABEL[stage as Stage];
  return `${side} · ${label}`;
}
