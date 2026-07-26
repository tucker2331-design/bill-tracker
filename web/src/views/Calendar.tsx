import { useEffect, useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { loadCalendar, CROSSOVER_BY_SESSION, type CalendarData, type Meeting } from "../data/calendar";
import { useScope, useStarred } from "../state/tracking";
import { parseLisDate, dayKey } from "../data/dates";

// The full Calendar — the "by time" lens, relaid out (owner 2026-06-30): a large 7-DAY WEEK VIEW is the
// primary module (events listed out per day), with a COMPACT month grid ALONGSIDE it as a dual-cue
// selector. One piece of state — `focusedDay` — drives everything: the week view shows that day's week;
// the mini month highlights that whole week (a 7-cell "week band") AND marks the focused day, so clicking
// any day BOTH jumps the week and focuses it. The landing's CalendarSliver is the "today" window into the
// same data. (design/ui_redesign_spec 2026-06-30 item 3.)
const MONTHS = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

type YM = { y: number; m: number }; // m is 0-indexed

const ymOf = (key: string): YM => ({ y: +key.slice(0, 4), m: +key.slice(5, 7) - 1 });
const ymKey = (ym: YM) => `${ym.y}-${String(ym.m + 1).padStart(2, "0")}`;
const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const weekStartOf = (d: Date) => addDays(d, -d.getDay()); // Sunday on/before d
const BILL_CAP = 16; // floor sessions can carry a few hundred bills — show a sample, expand on demand

// A quiet density cue per mini-month day: up to three neutral dots. The COUNT is the signal, so the dots are
// one muted colour — chamber-tinting them was a hue that varied without meaning anything here (owner Option A,
// 2026-07-09; docs/design: a signal must vary to exist).
function DensityDots({ meetings }: { meetings: Meeting[] }) {
  const dots = meetings.slice(0, 3);
  return (
    <span className="mini-dots">
      {dots.map((_, i) => <span key={i} className="mini-dot" />)}
    </span>
  );
}

// A COMPACT meeting card: time + committee (clamped to 2 lines), with the bill list hidden behind a
// click-to-expand dropdown (owner 2026-06-30 — inline bills made each day too tall to see the week). The
// full committee name is the hover title; clicking expands the bills below.
function MeetingRow({ m, billMap, onOpen }: {
  m: Meeting; billMap: Map<string, Bill>; onOpen: (b: Bill) => void;
}) {
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState(false);
  const hasBills = m.bills.length > 0;
  // A meeting is FUTURE if its day is today or later — an agenda that isn't there yet is "not posted yet"
  // (it drops shortly before the meeting), vs a PAST meeting where a missing agenda simply isn't linked.
  const isFuture = m.dateKey >= dayKey(new Date());
  const hasLinks = !!(m.agendaUrl || m.meetingUrl);
  const shown = all ? m.bills : m.bills.slice(0, BILL_CAP);
  const extra = m.bills.length - shown.length;
  // A FLOOR session marker (chamber convening / recessing / adjourning) is session context, not a committee
  // meeting the lobbyist tracks — render it quiet + centered + uppercase, distinct by FORM, not a colored bar
  // (owner 2026-06-30). It keeps the bill dropdown because a convening carries the day's floor calendar.
  const isFloor = m.kind === "floor";
  const head = (
    <>
      <span className="cal-mtg-top">
        {/* §7.2 (owner 2026-06-30): an UNRESOLVED relative time can't be placed on the clock — flag it
            honestly ("position unknown") instead of letting it sit in a silently-wrong slot. The meeting
            is already sorted to the top of its day by calendar.ts. */}
        {m.unresolved && <span className="cal-mtg-unres" title="LIS lists this meeting only relative to another event whose time is unknown — we can't place it on the clock, so it's surfaced first.">⚠ unplaceable</span>}
        <span className={`cal-mtg-t${m.tba ? " tba" : ""}`}>{m.time}</span>
        <span className="cal-mtg-n">{hasBills ? m.bills.length : ""}{open ? " ▴" : " ▾"}</span>
      </span>
      {/* Subcommittee LINEAGE cue (owner 2026-07-03): when two same-time parents' subcommittees tie and
          interleave in the time-sorted day, the family link must stay readable. The chamber-qualified name
          already carries lineage ("House Appropriations - Transportation…"); render it as a muted parent +
          ↳ sub. Pure typography over the structural name — both parts always shown, nothing inferred. */}
      {(() => {
        const p = /^((?:House|Senate|Joint)[^-]+?)\s*-\s*(.+)$/.exec(m.committee);
        return p ? (
          <span className={`cal-mtg-c${open ? " open" : ""}`} title={m.committee}>
            <span className="cal-sub-parent">{p[1].trim()}</span>
            <span className="cal-sub-name">↳ {p[2].trim()}</span>
          </span>
        ) : (
          <span className={`cal-mtg-c${open ? " open" : ""}`} title={m.committee}>{m.committee}</span>
        );
      })()}
    </>
  );
  return (
    <div className={`cal-mtg${isFloor ? " floor" : ""}${m.unresolved ? " unres" : ""}`}>
      {/* Every meeting is now click-to-expand (owner 2026-07-08): expanding UNCLAMPS the committee title (so a
          cut-off name is fully readable) and, when present, reveals the agenda bills below. */}
      <button className="cal-mtg-h has" title={m.committee} onClick={() => setOpen((o) => !o)} aria-expanded={open}>{head}</button>
      {open && hasBills && (
        <div className="cal-bills">
          {shown.map((it) => {
            const b = billMap.get(it.bill);
            return b ? (
              <button key={it.bill} className="cal-bchip on" title={it.action || b.title} onClick={() => onOpen(b)}>{it.bill}</button>
            ) : (
              <span key={it.bill} className="cal-bchip" title={it.action}>{it.bill}</span>
            );
          })}
          {extra > 0 && <button className="cal-more" onClick={() => setAll(true)}>+{extra} more</button>}
        </div>
      )}
      {/* Meeting + agenda links (docs/ideas/meeting_agenda_links). Only when present — a dead/empty link is
          never rendered (Standard #3, honest-absent). For a FUTURE meeting whose livestream exists but whose
          agenda isn't posted yet, say so; a PAST meeting with no agenda link just shows the watch link. */}
      {open && (hasLinks || (isFuture && m.meetingUrl)) && (
        <div className="cal-links">
          {m.agendaUrl ? (
            <a className="cal-link" href={m.agendaUrl} target="_blank" rel="noopener noreferrer">📄 Agenda</a>
          ) : (isFuture && m.meetingUrl) ? (
            <span className="cal-link none">Agenda not posted yet</span>
          ) : null}
          {m.meetingUrl && (
            <a className="cal-link" href={m.meetingUrl} target="_blank" rel="noopener noreferrer">▶ Watch meeting</a>
          )}
        </div>
      )}
    </div>
  );
}

export function Calendar({ bills, sessionCode, onOpen, calRefresh = 0 }: {
  bills: Bill[]; sessionCode: string; onOpen: (b: Bill) => void; calRefresh?: number;
}) {
  const [cal, setCal] = useState<CalendarData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scope] = useScope();
  const starred = useStarred();

  useEffect(() => {
    let alive = true;
    loadCalendar().then((d) => alive && setCal(d)).catch((e) => alive && setError(String(e?.message || e)));
    return () => { alive = false; };
  }, [calRefresh]); // re-run when the freshness-gate invalidated the shared calendar cache

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
      const kept = ms
        .filter((m) => m.bills.some((b) => starred.has(b.bill)))
        .map((m) => ({ ...m, bills: m.bills.filter((b) => starred.has(b.bill)) }));
      if (kept.length) out.set(dk, kept);
    }
    return out;
  }, [cal, scope, starred]);

  const crossoverKey = CROSSOVER_BY_SESSION[sessionCode] ?? null;
  const todayKey = dayKey(new Date());

  const [focusedDay, setFocusedDay] = useState<string | null>(null);
  const [miniMonth, setMiniMonth] = useState<YM | null>(null);

  // Default focus (owner 2026-07-08: "start on this week / Today, NOT crossover"). Set ONCE when the calendar
  // data arrives — computed during render (guarded so it runs a single time), not in an effect. In-session →
  // today's week; off-season (today outside the data range) → the nearest week that HAS data (the most recent
  // once the session has ended), so it opens onto real meetings, but it NEVER jumps to the crossover week.
  if (cal && focusedDay === null) {
    setFocusedDay((todayKey >= cal.minKey && todayKey <= cal.maxKey)
      ? todayKey                                          // in-session → this week
      : (todayKey > cal.maxKey ? cal.maxKey : cal.minKey)); // off-season → nearest week with data
  }

  // The mini month follows the focused day (so a week-arrow page or a Today/Crossover jump re-centers the
  // mini), but stays independently browsable between focus changes via its own arrows.
  useEffect(() => {
    if (focusedDay) setMiniMonth(ymOf(focusedDay));
  }, [focusedDay]);

  if (error) return (
    <p className="center-msg" style={{ color: "var(--stale)" }}>
      Couldn't load the calendar: {error}<br />
      <span className="muted">The Mastermind DB sheet (Sheet1) must be link-readable for gviz.</span>
    </p>
  );
  if (!cal || !focusedDay || !miniMonth) return <p className="center-msg">Loading the session calendar…</p>;

  const focusedDate = parseLisDate(focusedDay) ?? new Date();
  const weekStart = weekStartOf(focusedDate);
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const weekKeys = new Set(weekDays.map(dayKey));

  // Week nav, clamped to the data range so we never page into an empty void beyond the session.
  const prevKey = dayKey(addDays(focusedDate, -7));
  const nextKey = dayKey(addDays(focusedDate, 7));
  const canPrev = prevKey >= cal.minKey;
  const canNext = nextKey <= cal.maxKey;
  const shiftWeek = (delta: number) => {
    const k = dayKey(addDays(focusedDate, delta * 7));
    if (k >= cal.minKey && k <= cal.maxKey) setFocusedDay(k);
  };
  const jumpTo = (key: string | null) => { if (key) setFocusedDay(key); };

  // Mini-month grid (compact): 6×7 from the Sunday on/before the 1st. Browsing the mini does NOT change the
  // focus — only clicking a day does.
  const inRange = (mk: string) => mk >= cal.minKey.slice(0, 7) && mk <= cal.maxKey.slice(0, 7);
  const shiftYM = (delta: number): YM => { const d = new Date(miniMonth.y, miniMonth.m + delta, 1); return { y: d.getFullYear(), m: d.getMonth() }; };
  // Compute from the updater's CURRENT value, not the closed-over miniMonth, so rapid clicks can't act on
  // stale state (Gemini #185).
  const stepMonth = (delta: number) => setMiniMonth((cur) => {
    if (!cur) return cur;
    const d = new Date(cur.y, cur.m + delta, 1);
    return { y: d.getFullYear(), m: d.getMonth() };
  });
  const monthFirst = new Date(miniMonth.y, miniMonth.m, 1);
  const monthGridStart = new Date(miniMonth.y, miniMonth.m, 1 - monthFirst.getDay());
  const monthCells = Array.from({ length: 42 }, (_, i) => addDays(monthGridStart, i));

  const weekLabel = `${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })} – ${addDays(weekStart, 6).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
  const weekMeetingCount = weekDays.reduce((n, d) => n + (byDay.get(dayKey(d))?.length ?? 0), 0);

  return (
    <div>
      <div className="cal-top">
        <div className="cal-nav">
          <button className="cal-step" onClick={() => shiftWeek(-1)} disabled={!canPrev} aria-label="Previous week">‹</button>
          <h2 className="cal-title">{weekLabel}</h2>
          <button className="cal-step" onClick={() => shiftWeek(1)} disabled={!canNext} aria-label="Next week">›</button>
          <span className="muted cal-count">{weekMeetingCount.toLocaleString()} meeting{weekMeetingCount === 1 ? "" : "s"} this week{scope === "tracking" ? " · tracked" : ""}</span>
        </div>
        <div className="cal-actions">
          {/* Crossover JUMP button removed (owner 2026-07-08 — testing-only); the crossover DAY marker (the ⚑
              + red top-border on the crossover date) stays as informative context on the calendar itself. */}
          {todayKey >= cal.minKey && todayKey <= cal.maxKey && <button className="cal-jump" onClick={() => jumpTo(todayKey)}>Today</button>}
          {/* "Calendar as of" moved up to the global TrustHeader (owner 2026-07-04) so both feed clocks sit
              together — see components/common.tsx TrustHeader. Not duplicated here to avoid two stamps. */}
        </div>
      </div>

      <div className="cal-week-layout">
        {/* PRIMARY: the work week as COLUMNS so Mon–Fri are visible together (owner 2026-06-30). An empty
            weekend day shrinks to 0.4fr — "pushed to the side" — and expands to a full column when it has
            meetings (rare). Meetings are compact (bills behind a dropdown), so a day's column stays short. */}
        <div className="cal-week" style={{
          gridTemplateColumns: weekDays.map((d) => {
            const wknd = d.getDay() === 0 || d.getDay() === 6;
            const has = (byDay.get(dayKey(d))?.length ?? 0) > 0;
            // Readable min width so work-day columns never crush. The minimum comes from `--cal-day-min`
            // (index.css) so it can STEP DOWN on narrower viewports instead of clipping a day behind a
            // scrollbar — a hidden day is a P12 violation at any width (owner-reported 2026-07-25).
            return wknd && !has ? "minmax(40px,0.4fr)" : "minmax(var(--cal-day-min,158px),1fr)";
          }).join(" "),
        }}>
          {weekDays.map((d) => {
            const dk = dayKey(d);
            const ms = byDay.get(dk) ?? [];
            const isToday = dk === todayKey;
            const isCross = dk === crossoverKey;
            const isFocus = dk === focusedDay;
            const wknd = d.getDay() === 0 || d.getDay() === 6;
            const aside = wknd && ms.length === 0;
            const cls = ["cal-wcol", isToday ? "today" : "", isCross ? "cross" : "", isFocus ? "focus" : "",
              ms.length ? "live" : "empty", aside ? "aside" : ""].filter(Boolean).join(" ");
            return (
              <div key={dk} className={cls}>
                <div className="cal-wcol-h">
                  <span className="cal-wcol-dow">{WEEKDAYS[d.getDay()]}</span>
                  <span className="cal-wcol-date">{d.getDate()}</span>
                  {isToday && <span className="cal-wcol-tag today" title="Today">●</span>}
                  {isCross && <span className="cal-wcol-tag cross" title="Crossover deadline">⚑</span>}
                  {ms.length > 0 && <span className="cal-wcol-n">{ms.length}</span>}
                </div>
                <div className="cal-wcol-body">
                  {ms.length === 0
                    ? <div className="cal-wcol-empty">{aside ? "" : "—"}</div>
                    : ms.map((m, i) => <MeetingRow key={i} m={m} billMap={billMap} onOpen={onOpen} />)}
                </div>
              </div>
            );
          })}
        </div>

        {/* SELECTOR: compact month grid — dates + density dots only. A 7-cell WEEK BAND shows the week the
            big view is displaying; a ring marks the focused day. Click any day to jump+focus. */}
        <aside className="cal-mini">
          <div className="cal-mini-nav">
            <button className="cal-mini-step" onClick={() => stepMonth(-1)} disabled={!inRange(ymKey(shiftYM(-1)))} aria-label="Previous month">‹</button>
            <span className="cal-mini-title">{MONTHS[miniMonth.m].slice(0, 3)} {miniMonth.y}</span>
            <button className="cal-mini-step" onClick={() => stepMonth(1)} disabled={!inRange(ymKey(shiftYM(1)))} aria-label="Next month">›</button>
          </div>
          <div className="cal-mini-wk">{WEEKDAYS.map((w) => <div key={w} className="cal-mini-wkd">{w[0]}</div>)}</div>
          <div className="cal-mini-cells">
            {monthCells.map((d) => {
              const dk = dayKey(d);
              const out = d.getMonth() !== miniMonth.m;
              const ms = byDay.get(dk) ?? [];
              const inWeek = weekKeys.has(dk);
              // A date outside the session range must NOT be pickable — focusing it would trap week paging,
              // which clamps to [minKey, maxKey] (Qodo #185).
              const dayInRange = dk >= cal.minKey && dk <= cal.maxKey;
              const cls = ["mini-cell", out ? "out" : "", inWeek ? "band" : "", dk === focusedDay ? "focus" : "",
                dk === todayKey ? "today" : "", dk === crossoverKey ? "cross" : "", ms.length ? "live" : ""].filter(Boolean).join(" ");
              return (
                <button key={dk} className={cls} disabled={!dayInRange} onClick={() => setFocusedDay(dk)}
                  aria-label={`${MONTHS[d.getMonth()]} ${d.getDate()}${ms.length ? `, ${ms.length} meetings` : ""}${inWeek ? " (shown week)" : ""}`}
                  aria-pressed={dk === focusedDay}>
                  <span className="mini-d">{d.getDate()}</span>
                  {ms.length > 0 && <DensityDots meetings={ms} />}
                </button>
              );
            })}
          </div>
          <div className="cal-mini-legend muted">
            <span><span className="swatch band" /> shown week</span>
            <span><span className="swatch focus" /> picked day</span>
          </div>
        </aside>
      </div>

      {/* The "● Senate / ● House" key is gone with the chamber colour-coding (owner Option A, 2026-07-09) —
          a legend for a colour nothing uses would be a lie. The committee name states its own chamber. */}
      <p className="muted cal-legend">
        Committee &amp; floor meetings with their resolved times, from the calendar subsystem
        (<b>{cal.totalMeetings.toLocaleString()}</b> across {cal.minKey} → {cal.maxKey}). Administrative
        actions live in the bill history, not here.
      </p>
    </div>
  );
}
