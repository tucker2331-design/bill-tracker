import { useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { buildFeed, tallyOutcomes } from "../data/derive";
import { OutcomeChip } from "../components/common";
import { CalendarSliver } from "../components/CalendarSliver";
import { Timeline } from "./Timeline";

// The daily driver (vision §3a). Top: what's-new (the anxiety-killer) + today's calendar sliver.
// Below: where the bills stand (outcome summary) + the timeline pipeline. Full-day feed, paged by day.
export function Landing({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const feed = useMemo(() => buildFeed(bills), [bills]);
  const byBill = useMemo(() => new Map(bills.map((b) => [b.bill, b])), [bills]);
  const tally = useMemo(() => tallyOutcomes(bills), [bills]);

  const days = useMemo(() => {
    const m = new Map<string, typeof feed>();
    for (const it of feed) (m.get(it.date || "Undated") ?? m.set(it.date || "Undated", []).get(it.date || "Undated")!).push(it);
    return [...m.entries()].sort((a, b) => (Date.parse(b[0]) || 0) - (Date.parse(a[0]) || 0));
  }, [feed]);

  const [dayIdx, setDayIdx] = useState(0);

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  const [curDay, items] = days[Math.min(dayIdx, days.length - 1)] ?? ["", []];
  const dayLabel = curDay && Date.parse(curDay) ? new Date(curDay).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : curDay || "—";

  return (
    <div>
      <div className="cols">
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 className="h">What's new</h2>
            <div className="filters" style={{ margin: 0 }}>
              <button disabled={dayIdx >= days.length - 1} onClick={() => setDayIdx((i) => i + 1)}>← Older</button>
              <button disabled={dayIdx <= 0} onClick={() => setDayIdx((i) => Math.max(0, i - 1))}>Newer →</button>
            </div>
          </div>
          <div className="panel">
            <p className="feedday">{dayLabel} <span className="muted">· {items.length} action{items.length === 1 ? "" : "s"}</span></p>
            {items.length === 0 && <p className="muted" style={{ padding: "8px 4px" }}>No actions on this day.</p>}
            {items.slice(0, 80).map((it, i) => {
              const b = byBill.get(it.bill);
              return (
                <div key={i} className="feedrow" onClick={() => b && onOpen(b)} role="button" tabIndex={0}
                  onKeyDown={(e) => { if (b && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen(b); } }}>
                  <span className="fnum">{it.bill}</span>
                  <span className="fact">{it.action}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <h2 className="h">Today</h2>
          <CalendarSliver bills={bills} onOpen={onOpen} />
        </div>
      </div>

      <div style={{ marginTop: "var(--s6)" }}>
        <h2 className="h">Where the bills stand</h2>
        <div className="panel summaryrow" style={{ marginBottom: "var(--s4)" }}>
          <Summary n={tally.in_progress} o="in_progress" />
          <Summary n={tally.awaiting_governor} o="awaiting_governor" />
          <Summary n={tally.signed} o="signed" />
          <Summary n={tally.vetoed} o="vetoed" />
          <Summary n={tally.dead} o="dead" />
          <Summary n={tally.carried_over} o="carried_over" />
        </div>
        <Timeline bills={bills} onOpen={onOpen} embedded />
      </div>
    </div>
  );
}

function Summary({ n, o }: { n: number; o: Bill["outcome"] }) {
  return (
    <div className="it">
      <span className="sn">{n.toLocaleString()}</span>
      <OutcomeChip outcome={o} />
    </div>
  );
}
