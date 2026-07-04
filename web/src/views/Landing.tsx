import { useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { buildFeed, tallyOutcomes } from "../data/derive";
import { parseLisDate, dateSort, dayKey } from "../data/dates";
import { OutcomeChip } from "../components/common";
import { CalendarSliver } from "../components/CalendarSliver";
import { Timeline } from "./Timeline";

// The daily driver (vision §3a). Top: what's-new (the anxiety-killer) + today's calendar sliver.
// Below: where the bills stand (outcome summary) + the timeline pipeline. Full-day feed, paged by day.

// When the newest action day is older than this, the feed header says so explicitly (off-season honesty,
// owner 2026-07-03) — 2 days tolerates a quiet in-session weekend without flagging it as "nothing newer."
const FEED_STALE_MS = 2 * 24 * 60 * 60 * 1000;

export function Landing({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const feed = useMemo(() => buildFeed(bills), [bills]);
  const byBill = useMemo(() => new Map(bills.map((b) => [b.bill, b])), [bills]);
  const tally = useMemo(() => tallyOutcomes(bills), [bills]);

  const days = useMemo(() => {
    const m = new Map<string, typeof feed>();
    for (const it of feed) {
      const d = parseLisDate(it.date);                 // normalize so one day buckets once, any format
      const key = d ? dayKey(d) : "Undated";
      (m.get(key) ?? m.set(key, []).get(key)!).push(it);
    }
    return [...m.entries()].sort((a, b) => dateSort(b[0]) - dateSort(a[0]));
  }, [feed]);

  const [dayIdx, setDayIdx] = useState(0);

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  const [curDay, items] = days[Math.min(dayIdx, days.length - 1)] ?? ["", []];
  const curDate = parseLisDate(curDay);
  const dayLabel = curDate ? curDate.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : curDay || "—";

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
            {/* Off-season honesty (owner 2026-07-03: "the date is from days ago — why?"): the feed opens on
                the newest day WITH actions; when that day isn't recent, say so instead of looking stale. */}
            <p className="feedday">{dayLabel} <span className="muted">· {items.length} action{items.length === 1 ? "" : "s"}{dayIdx === 0 && curDate && (Date.now() - curDate.getTime()) > FEED_STALE_MS ? " · the most recent legislative activity — nothing newer has happened" : ""}</span></p>
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
        <h2 className="h">The pipeline</h2>
        <Timeline bills={bills} onOpen={onOpen} />
        <h2 className="h" style={{ marginTop: "var(--s6)" }}>Where the bills stand</h2>
        <div className="panel summaryrow">
          <Summary n={tally.in_progress} o="in_progress" />
          <Summary n={tally.awaiting_governor} o="awaiting_governor" />
          <Summary n={tally.signed} o="signed" />
          <Summary n={tally.vetoed} o="vetoed" />
          <Summary n={tally.dead} o="dead" />
          <Summary n={tally.carried_over} o="carried_over" />
        </div>
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
