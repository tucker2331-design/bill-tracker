import { useMemo } from "react";
import type { Bill } from "../data/types";
import { parseLisDate, dayKey } from "../data/dates";

// Today's calendar as a paper-planner day column (owner request): the day-of-week + numerical date at
// the head, the day's committee meetings down it, a fixed-height widget that scrolls internally. The
// full calendar lives in the Calendar tab; this is the "what's happening today" sliver on the landing.
export function CalendarSliver({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const today = new Date();
  const dow = today.toLocaleDateString("en-US", { weekday: "long" });
  const head = today.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const todayKey = dayKey(today);

  const events = useMemo(() => {
    const evs: { bill: string; committee: string; b: Bill }[] = [];
    for (const b of bills) for (const m of b.upcoming ?? []) {
      const d = parseLisDate(m.date);                      // robust local parse (no Date.parse drift)
      if (d && dayKey(d) === todayKey) evs.push({ bill: b.bill, committee: m.committee || "Committee", b });
    }
    return evs.sort((a, b) => a.committee.localeCompare(b.committee));
  }, [bills, todayKey]);

  return (
    <div className="daycol">
      <div className="dchead">
        <div className="dow">{dow}</div>
        <div className="dnum">{head}</div>
      </div>
      <div className="dcbody">
        {events.length === 0 ? (
          <div className="dcempty">
            <div style={{ fontSize: 22, marginBottom: 6 }}>🗓️</div>
            No meetings scheduled today.<br />
            <span className="muted">The General Assembly is adjourned — this fills during session.</span>
          </div>
        ) : events.map((e, i) => (
          <div className="ev" key={i} onClick={() => onOpen(e.b)} role="button" tabIndex={0}
            onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); onOpen(e.b); } }}>
            <div className="t" style={{ color: e.b.chamber === "Senate" ? "var(--senate)" : "var(--house)" }}>
              {e.b.chamber === "Senate" ? "SEN" : "HOU"}
            </div>
            <div>
              <div className="b">{e.bill}</div>
              <div className="c">{e.committee}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
