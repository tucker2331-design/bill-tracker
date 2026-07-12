import { useEffect, useState } from "react";
import type { Bill } from "../data/types";
import { dayKey } from "../data/dates";
import { loadCalendar, type Meeting } from "../data/calendar";

// Today's calendar as a paper-planner day column (owner request): the day-of-week + numerical date at the
// head, the day's meetings down it. It reads the SAME source as the Calendar tab — the full LIS schedule via
// loadCalendar() (cached + shared, so opening the Calendar tab stays instant) — NOT each bill's `upcoming`
// list, which is empty off-season and never held the non-bill meetings (caucuses, commissions, interim
// committee meetings) that the LIS + Calendar-page views show. That mismatch is why this used to read "no
// meetings" while the Calendar tab showed a full week (owner 2026-07-08).
export function CalendarSliver({ bills, onOpen, calRefresh = 0 }: { bills: Bill[]; onOpen: (b: Bill) => void; calRefresh?: number }) {
  const today = new Date();
  const dow = today.toLocaleDateString("en-US", { weekday: "long" });
  const head = today.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const todayKey = dayKey(today);

  const [meetings, setMeetings] = useState<Meeting[] | null>(null); // null = still loading
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    loadCalendar()
      .then((cal) => { if (alive) setMeetings(cal.byDay.get(todayKey) ?? []); })
      .catch((e) => { if (alive) setErr(String(e?.message || e)); });
    return () => { alive = false; };
  }, [todayKey, calRefresh]); // calRefresh bumps when the freshness-gate invalidated the shared calendar cache

  const byBill = new Map(bills.map((b) => [b.bill, b])); // open a bill from an agenda item

  return (
    <div className="daycol">
      <div className="dchead">
        <div className="dow">{dow}</div>
        <div className="dnum">{head}</div>
      </div>
      <div className="dcbody scroll-hint">
        {err ? (
          <div className="dcempty">Couldn't load today's calendar.<br /><span className="muted">See the Calendar tab.</span></div>
        ) : meetings === null ? (
          <div className="dcempty muted">Loading today's meetings…</div>
        ) : meetings.length === 0 ? (
          <div className="dcempty">No meetings scheduled today.<br /><span className="muted">The full week is on the Calendar tab.</span></div>
        ) : meetings.map((m, i) => (
          <div className="ev" key={i} style={{ cursor: "default" }}>
            <div className="t">{m.time}</div>
            <div>
              <div className="b">{m.committee}</div>
              {m.bills.length > 0 && (
                <div className="evbills">
                  {m.bills.slice(0, 8).map((a) => {
                    const b = byBill.get(a.bill);
                    return (
                      <span key={a.bill} className={`evbill${b ? "" : " nolink"}`}
                        onClick={() => b && onOpen(b)} role={b ? "button" : undefined} tabIndex={b ? 0 : undefined}
                        onKeyDown={(e) => { if (b && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen(b); } }}>
                        {a.bill}
                      </span>
                    );
                  })}
                  {m.bills.length > 8 && <span className="muted" style={{ fontSize: 11 }}>+{m.bills.length - 8}</span>}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
