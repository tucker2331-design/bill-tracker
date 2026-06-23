import { useEffect, useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { loadCalendar, CROSSOVER_BY_SESSION, type CalendarData, type Meeting } from "../data/calendar";
import { useScope, useStarred } from "../state/tracking";
import { relativeTime } from "../components/common";
import { parseLisDate, dayKey } from "../data/dates";

// The full Calendar — the "by time" lens. A month grid (small multiples of days, per the reading:
// Tufte small multiples + Munzner time=position; design/reading_notes "Calendar UI patterns") for the
// macro shape, plus a day-agenda column for the micro read — one geometry, today + the crossover seam
// the only loud cells. The landing's CalendarSliver is the "today" window into the same idea.
const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

type YM = { y: number; m: number }; // m is 0-indexed

const ymOf = (key: string): YM => ({ y: +key.slice(0, 4), m: +key.slice(5, 7) - 1 });
const ymKey = (ym: YM) => `${ym.y}-${String(ym.m + 1).padStart(2, "0")}`;

export function Calendar({ bills, sessionCode, onOpen }: {
  bills: Bill[]; sessionCode: string; onOpen: (b: Bill) => void;
}) {
  const [cal, setCal] = useState<CalendarData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scope] = useScope();
  const starred = useStarred();

  useEffect(() => {
    let alive = true;
    loadCalendar().then((d) => alive && setCal(d)).catch((e) => alive && setError(String(e?.message || e)));
    return () => { alive = false; };
  }, []);

  // Bill lookup so a meeting's agenda chip can open the full card (when we carry that bill).
  const billMap = useMemo(() => {
    const m = new Map<string, Bill>();
    for (const b of bills) m.set(b.bill, b);
    return m;
  }, [bills]);

  // Scope filter: in Tracking, keep only meetings with ≥1 starred bill (the global switch governs every
  // lens — vision §2). Full GA shows every meeting.
  const byDay = useMemo(() => {
    if (!cal) return new Map<string, Meeting[]>();
    if (scope === "full") return cal.byDay;
    const out = new Map<string, Meeting[]>();
    for (const [dk, ms] of cal.byDay) {
      // Keep meetings that touch a tracked bill, and within each show ONLY the tracked bills — otherwise a
      // floor session kept for one tracked bill would dump its whole ~300-bill docket.
      const kept = ms
        .filter((m) => m.bills.some((b) => starred.has(b.bill)))
        .map((m) => ({ ...m, bills: m.bills.filter((b) => starred.has(b.bill)) }));
      if (kept.length) out.set(dk, kept);
    }
    return out;
  }, [cal, scope, starred]);

  const crossoverKey = CROSSOVER_BY_SESSION[sessionCode] ?? null;
  const todayKey = dayKey(new Date());

  const [month, setMonth] = useState<YM | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  // Default landing month: the busiest month (most meetings) so the user opens onto live data, not an
  // empty off-season month. Computed once from the unfiltered calendar for a stable anchor.
  useEffect(() => {
    if (!cal || month) return;
    const counts = new Map<string, number>();
    for (const [dk, ms] of cal.byDay) counts.set(dk.slice(0, 7), (counts.get(dk.slice(0, 7)) || 0) + ms.length);
    let best = "", bestN = -1;
    for (const [k, n] of counts) if (n > bestN) { bestN = n; best = k; }
    setMonth(best ? ymOf(best + "-01") : { y: new Date().getFullYear(), m: new Date().getMonth() });
  }, [cal, month]);

  // When the month changes, auto-select a meaningful day for the agenda (crossover if it lives here and
  // is non-empty, else the first day with meetings) — micro + macro visible together.
  useEffect(() => {
    if (!month) return;
    const mk = ymKey(month);
    if (selected && selected.slice(0, 7) === mk && (byDay.get(selected)?.length)) return; // keep a valid pick
    const daysHere = [...byDay.keys()].filter((k) => k.slice(0, 7) === mk).sort();
    const pick = (crossoverKey && byDay.get(crossoverKey)?.length && crossoverKey.slice(0, 7) === mk)
      ? crossoverKey : daysHere[0] ?? null;
    setSelected(pick);
  }, [month, byDay, crossoverKey, selected]);

  if (error) return (
    <p className="center-msg" style={{ color: "var(--stale)" }}>
      Couldn't load the calendar: {error}<br />
      <span className="muted">The Mastermind DB sheet (Sheet1) must be link-readable for gviz.</span>
    </p>
  );
  if (!cal || !month) return <p className="center-msg">Loading the session calendar…</p>;

  const fresh = relativeTime(cal.dataAsOf);
  const monthMeetings = [...byDay.keys()].filter((k) => k.slice(0, 7) === ymKey(month))
    .reduce((n, k) => n + (byDay.get(k)?.length ?? 0), 0);

  // 6×7 grid starting on the Sunday on/before the 1st.
  const first = new Date(month.y, month.m, 1);
  const gridStart = new Date(month.y, month.m, 1 - first.getDay());
  const cells = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart); d.setDate(gridStart.getDate() + i); return d;
  });

  const inRange = (mk: string) => mk >= cal.minKey.slice(0, 7) && mk <= cal.maxKey.slice(0, 7);
  const step = (delta: number) => setMonth((cur) => {
    if (!cur) return cur;
    const d = new Date(cur.y, cur.m + delta, 1); return { y: d.getFullYear(), m: d.getMonth() };
  });
  const jumpTo = (key: string | null) => { if (key) setMonth(ymOf(key)); };

  const selMeetings = selected ? (byDay.get(selected) ?? []) : [];

  return (
    <div>
      <div className="cal-top">
        <div className="cal-nav">
          <button className="cal-step" onClick={() => step(-1)} disabled={!inRange(ymKey({ y: month.y, m: month.m - 1 }))} aria-label="Previous month">‹</button>
          <h2 className="cal-title">{MONTHS[month.m]} {month.y}</h2>
          <button className="cal-step" onClick={() => step(1)} disabled={!inRange(ymKey({ y: month.y, m: month.m + 1 }))} aria-label="Next month">›</button>
          <span className="muted cal-count">{monthMeetings.toLocaleString()} meeting{monthMeetings === 1 ? "" : "s"}{scope === "tracking" ? " · tracked" : ""}</span>
        </div>
        <div className="cal-actions">
          {crossoverKey && <button className="cal-jump cross" onClick={() => jumpTo(crossoverKey)}>⚑ Crossover</button>}
          {inRange(todayKey.slice(0, 7)) && <button className="cal-jump" onClick={() => jumpTo(todayKey)}>Today</button>}
          <span className="trust" style={{ marginLeft: "auto" }}>
            <span className={`pill ${fresh.stale ? "warn" : "good"}`} title={cal.dataAsOf?.toISOString() ?? ""}>● Calendar as of {fresh.text}</span>
          </span>
        </div>
      </div>

      <div className="cal-cols">
        <div className="calgrid panel">
          <div className="cal-wk">{WEEKDAYS.map((w) => <div key={w} className="cal-wkd">{w}</div>)}</div>
          <div className="cal-cells">
            {cells.map((d, i) => {
              const dk = dayKey(d);
              const out = d.getMonth() !== month.m;
              const ms = byDay.get(dk) ?? [];
              const isToday = dk === todayKey;
              const isCross = dk === crossoverKey;
              const weekend = d.getDay() === 0 || d.getDay() === 6;
              const live = ms.length > 0;
              const cls = ["cell", out ? "out" : "", weekend ? "wknd" : "", isToday ? "today" : "",
                isCross ? "cross" : "", live ? "live" : "", selected === dk ? "sel" : ""].filter(Boolean).join(" ");
              return (
                <div key={i} className={cls}
                  onClick={() => live && setSelected(dk)}
                  role={live ? "button" : undefined} tabIndex={live ? 0 : undefined}
                  onKeyDown={(e) => { if (live && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setSelected(dk); } }}
                  aria-label={live ? `${MONTHS[d.getMonth()]} ${d.getDate()}, ${ms.length} meetings` : undefined}>
                  <div className="cell-d">{d.getDate()}</div>
                  {isCross && <div className="cell-cross">CROSSOVER</div>}
                  {live && <MeetingDots meetings={ms} />}
                </div>
              );
            })}
          </div>
        </div>

        <div className="calagenda daycol">
          {selected ? (
            <>
              <div className="dchead">
                <div className="dow">{parseLisDate(selected)?.toLocaleDateString("en-US", { weekday: "long" })}</div>
                <div className="dnum">{parseLisDate(selected)?.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</div>
              </div>
              {selected === crossoverKey && <div className="cal-crossbar">⚑ Crossover deadline — last day to act in the chamber of origin.</div>}
              <div className="dcbody">
                {selMeetings.length === 0 ? (
                  <div className="dcempty">No meetings this day.</div>
                ) : selMeetings.map((m, i) => <MeetingRow key={i} m={m} billMap={billMap} onOpen={onOpen} />)}
              </div>
            </>
          ) : (
            <div className="dcempty" style={{ padding: "var(--s7) var(--s4)" }}>
              {scope === "tracking"
                ? "No meetings for your tracked bills this month. Star bills, or switch to Full GA."
                : "Select a day to see its meetings."}
            </div>
          )}
        </div>
      </div>

      <p className="muted cal-legend">
        Committee &amp; floor meetings with their resolved times, from the calendar subsystem
        (<b>{cal.totalMeetings.toLocaleString()}</b> across {cal.minKey} → {cal.maxKey}). Administrative
        actions live in the bill history, not here. <span style={{ color: "var(--senate)" }}>● Senate</span>{" "}
        <span style={{ color: "var(--house)" }}>● House</span>.
      </p>
    </div>
  );
}

// A quiet density cue per day cell: the count + up to a few chamber-tinted dots (Senate indigo / House
// teal / other grey). Position/number carry the data; color stays muted (Munzner: hue is the redundant cue).
function MeetingDots({ meetings }: { meetings: Meeting[] }) {
  const dots = meetings.slice(0, 6);
  return (
    <div className="cell-meet">
      <span className="cell-n">{meetings.length}</span>
      <span className="cell-dots">
        {dots.map((m, i) => (
          <span key={i} className="dot" style={{
            background: m.chamber === "Senate" ? "var(--senate)" : m.chamber === "House" ? "var(--house)" : "var(--ink-faint)",
          }} />
        ))}
      </span>
    </div>
  );
}

const BILL_CAP = 16; // floor sessions can carry a few hundred bills — show a sample, expand on demand

function MeetingRow({ m, billMap, onOpen }: {
  m: Meeting; billMap: Map<string, Bill>; onOpen: (b: Bill) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const side = m.chamber === "Senate" ? "var(--senate)" : m.chamber === "House" ? "var(--house)" : "var(--ink-faint)";
  const shown = expanded ? m.bills : m.bills.slice(0, BILL_CAP);
  const extra = m.bills.length - shown.length;
  return (
    <div className="cal-mtg" style={{ borderLeftColor: side }}>
      <div className="cal-mtg-h">
        <span className={`cal-mtg-t${m.tba ? " tba" : ""}`}>{m.time}</span>
        <span className="cal-mtg-c" style={{ color: side }}>{m.committee}</span>
        {m.bills.length > 0 && <span className="cal-mtg-n">{m.bills.length}</span>}
      </div>
      {m.bills.length > 0 && (
        <div className="cal-bills">
          {shown.map((it) => {
            const b = billMap.get(it.bill);
            return b ? (
              <button key={it.bill} className="cal-bchip on" title={it.action || b.title} onClick={() => onOpen(b)}>{it.bill}</button>
            ) : (
              <span key={it.bill} className="cal-bchip" title={it.action}>{it.bill}</span>
            );
          })}
          {extra > 0 && <button className="cal-more" onClick={() => setExpanded(true)}>+{extra} more</button>}
        </div>
      )}
    </div>
  );
}
