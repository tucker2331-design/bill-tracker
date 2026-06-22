import { useMemo, useState } from "react";
import type { Bill, Chamber } from "../data/types";
import { deriveStage, STAGE_LABEL, type Stage } from "../data/derive";
import { BillBox } from "../components/BillBox";

// The crossover-lane pipeline (vision §3b). Senate ABOVE the centerline, House BELOW — so a bill
// literally crosses the line at crossover. Overview = a count per side per stage; click a count to
// drill into those bills. Floor stages are folded into the committee flow for v1 (the data doesn't
// separate them; the calendar subsystem owns that granularity).
const COLUMNS: { stage: Stage; label: string }[] = [
  { stage: "prefiled", label: "Prefiled" },
  { stage: "committee1", label: "Committee · origin" },
  { stage: "committee2", label: "Committee · 2nd chamber" },
  { stage: "governor", label: "To Governor" },
];

type DrillKey = `${Stage}|${Chamber}`;

export function Timeline({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const { counts, cellBills, died } = useMemo(() => {
    const counts: Record<string, number> = {};
    const cellBills = new Map<DrillKey, Bill[]>();
    const died = { Senate: [] as Bill[], House: [] as Bill[] };
    for (const b of bills) {
      const cell = deriveStage(b);
      if (cell.stage === "died") { died[cell.side].push(b); continue; }
      const key = `${cell.stage}|${cell.side}` as DrillKey;
      counts[key] = (counts[key] || 0) + 1;
      (cellBills.get(key) ?? cellBills.set(key, []).get(key)!).push(b);
    }
    return { counts, cellBills, died };
  }, [bills]);

  const [drill, setDrill] = useState<DrillKey | "died|Senate" | "died|House" | null>(null);

  const Count = ({ stage, side }: { stage: Stage; side: Chamber }) => {
    const key = `${stage}|${side}` as DrillKey;
    const n = counts[key] || 0;
    return (
      <>
        <span className={`count ${side === "Senate" ? "s" : "h"} ${n === 0 ? "zero" : ""}`}
          onClick={() => n > 0 && setDrill(key)} title={n > 0 ? "Click to list these bills" : ""}>
          {n}
        </span>
        <span className="countlbl">{side}</span>
      </>
    );
  };

  const drillBills: Bill[] = drill
    ? (drill.startsWith("died|")
        ? died[drill.endsWith("Senate") ? "Senate" : "House"]
        : cellBills.get(drill as DrillKey) ?? [])
    : [];

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  return (
    <div>
      <div className="lane-legend">
        <span><span className="swatch" style={{ background: "var(--senate)" }} />Senate (above the line)</span>
        <span><span className="swatch" style={{ background: "var(--house)" }} />House (below the line)</span>
        <span className="muted">Position = progress. A bill crosses the centerline at crossover.</span>
      </div>

      <div className="lanes" style={{ ["--stage-cols" as string]: COLUMNS.length + 1 }}>
        {/* Prefiled + origin committee, then the crossover divider, then 2nd-chamber + governor */}
        <LaneCol label={COLUMNS[0].label}><Count stage="prefiled" side="Senate" /><Line /><Count stage="prefiled" side="House" /></LaneCol>
        <LaneCol label={COLUMNS[1].label}><Count stage="committee1" side="Senate" /><Line /><Count stage="committee1" side="House" /></LaneCol>
        <div className="lanecol crossover">
          <div className="scell" />
          <div className="crosslabel">✦ CROSSOVER ✦</div>
          <div className="hcell" />
          <div className="stagename">deadline</div>
        </div>
        <LaneCol label={COLUMNS[2].label}><Count stage="committee2" side="Senate" /><Line /><Count stage="committee2" side="House" /></LaneCol>
        <LaneCol label={COLUMNS[3].label}><Count stage="governor" side="Senate" /><Line /><Count stage="governor" side="House" /></LaneCol>
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
        <DiedStat side="Senate" bills={died.Senate} onClick={() => died.Senate.length && setDrill("died|Senate")} />
        <DiedStat side="House" bills={died.House} onClick={() => died.House.length && setDrill("died|House")} />
        <span className="muted" style={{ alignSelf: "center" }}>
          Died / carried over — stranded, no longer advancing this session.
        </span>
      </div>

      {drill && (
        <div style={{ marginTop: 18 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <h3 className="h" style={{ margin: 0 }}>
              {drillLabel(drill)} — {drillBills.length} bill(s)
            </h3>
            <button className="filters" style={{ border: 0 }} onClick={() => setDrill(null)}>✕ clear</button>
          </div>
          <div className="billgrid">
            {drillBills.slice(0, 200).map((b) => <BillBox key={b.bill} bill={b} onOpen={onOpen} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function LaneCol({ label, children }: { label: string; children: React.ReactNode }) {
  const [s, line, h] = children as React.ReactNode[];
  return (
    <div className="lanecol">
      <div className="scell">{s}</div>
      {line}
      <div className="hcell">{h}</div>
      <div className="stagename">{label}</div>
    </div>
  );
}
const Line = () => <div className="center" />;

function DiedStat({ side, bills, onClick }: { side: Chamber; bills: Bill[]; onClick: () => void }) {
  return (
    <div className="stat" style={{ cursor: bills.length ? "pointer" : "default", minWidth: 120 }} onClick={onClick}>
      <div className="n" style={{ color: side === "Senate" ? "var(--senate)" : "var(--house)" }}>{bills.length}</div>
      <div className="l">{side} died/carried</div>
    </div>
  );
}

function drillLabel(key: string): string {
  const [stage, side] = key.split("|");
  const label = stage === "died" ? "Died / carried over" : STAGE_LABEL[stage as Stage];
  return `${side} · ${label}`;
}
