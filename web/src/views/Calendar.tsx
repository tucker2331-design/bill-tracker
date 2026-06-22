import { useMemo } from "react";
import type { Bill } from "../data/types";

// v1 calendar: upcoming committee meetings from the bills' DOCKET data (what bill_tracker carries).
// The FULL calendar (floor sessions, the crossover deadline marked, every meeting with its resolved
// time) is the calendar subsystem's job — it's the single source of truth for meeting times and will
// integrate here at the calendar↔product merge (see the vote-time architectural decision in the log).
export function Calendar({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const byDate = useMemo(() => {
    const m = new Map<string, { bill: string; committee: string; b: Bill }[]>();
    for (const b of bills) for (const mt of b.upcoming) {
      const key = mt.date || "Undated";
      (m.get(key) ?? m.set(key, []).get(key)!).push({ bill: b.bill, committee: mt.committee, b });
    }
    return [...m.entries()].sort((a, b) => (Date.parse(a[0]) || 0) - (Date.parse(b[0]) || 0));
  }, [bills]);

  return (
    <div>
      <p className="muted" style={{ marginBottom: 14 }}>
        Upcoming committee meetings for the bills in scope. The full calendar (floor order-of-business,
        the marked crossover deadline, exact meeting times) integrates from the calendar subsystem.
      </p>
      {byDate.length === 0 && (
        <p className="center-msg">No upcoming meetings — the General Assembly is adjourned (off-season).
          The docket repopulates when the 2027 session convenes.</p>
      )}
      {byDate.map(([date, items]) => (
        <div key={date} className="panel" style={{ marginBottom: 12 }}>
          <p className="feedday">{date}</p>
          {items.map((it, i) => (
            <div key={i} className="feedrow" onClick={() => onOpen(it.b)}>
              <span className="fnum">{it.bill}</span>
              <span className="fact">{it.committee || "Committee"}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
