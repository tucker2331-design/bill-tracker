import { useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { buildFeed, tallyOutcomes } from "../data/derive";
import { OutcomeChip } from "../components/common";

// The daily driver (vision §3a): what's-new feed up top (the anxiety-killer), an outcome summary,
// and a "next up" strip. Full-day feed, paged by day — no per-user read marker (multi-user system).
export function Landing({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const feed = useMemo(() => buildFeed(bills), [bills]);
  const byBill = useMemo(() => new Map(bills.map((b) => [b.bill, b])), [bills]);
  const tally = useMemo(() => tallyOutcomes(bills), [bills]);

  // Group the feed by calendar day (the day's whole set), newest day first.
  const days = useMemo(() => {
    const m = new Map<string, typeof feed>();
    for (const it of feed) {
      const key = it.date || "Undated";
      (m.get(key) ?? m.set(key, []).get(key)!).push(it);
    }
    return [...m.entries()].sort((a, b) => (Date.parse(b[0]) || 0) - (Date.parse(a[0]) || 0));
  }, [feed]);

  const [dayIdx, setDayIdx] = useState(0);
  const upcoming = useMemo(() =>
    bills.flatMap((b) => b.upcoming.map((m) => ({ ...m, bill: b.bill, b })))
      .sort((a, b) => (Date.parse(a.date) || 0) - (Date.parse(b.date) || 0)).slice(0, 8),
    [bills]);

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  const [curDay, items] = days[Math.min(dayIdx, days.length - 1)] ?? ["", []];

  return (
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
          <p className="feedday">{curDay || "—"} <span className="muted">· {items.length} action(s)</span></p>
          {items.slice(0, 80).map((it, i) => {
            const b = byBill.get(it.bill);
            return (
              <div key={i} className="feedrow" onClick={() => b && onOpen(b)}>
                <span className="fnum">{it.bill}</span>
                <span className="fact">{it.action}</span>
              </div>
            );
          })}
          {items.length === 0 && <p className="muted">No actions on this day.</p>}
        </div>
      </div>

      <div>
        <h2 className="h">Where the bills stand</h2>
        <div className="panel" style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          <Summary n={tally.in_progress} o="in_progress" />
          <Summary n={tally.awaiting_governor} o="awaiting_governor" />
          <Summary n={tally.signed} o="signed" />
          <Summary n={tally.vetoed} o="vetoed" />
          <Summary n={tally.dead} o="dead" />
          <Summary n={tally.carried_over} o="carried_over" />
        </div>

        <h2 className="h">Next up</h2>
        <div className="panel">
          {upcoming.length === 0 && <p className="muted">No upcoming committee meetings (the GA is adjourned off-season).</p>}
          {upcoming.map((m, i) => (
            <div key={i} className="feedrow" onClick={() => onOpen(m.b)}>
              <span className="fnum">{m.bill}</span>
              <span className="fact">{m.committee || "Committee"} <span className="muted">— {m.date}</span></span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Summary({ n, o }: { n: number; o: Bill["outcome"] }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span className="count" style={{ fontSize: 20 }}>{n.toLocaleString()}</span>
      <OutcomeChip outcome={o} />
    </div>
  );
}
