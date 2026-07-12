import { useEffect, useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { buildFeed, tallyOutcomes } from "../data/derive";
import { parseLisDate, dateSort, dayKey } from "../data/dates";
import { OutcomeChip } from "../components/common";
import { CalendarSliver } from "../components/CalendarSliver";
import { loadCalendar } from "../data/calendar";
import { Timeline } from "./Timeline";

// A bill ACTION carries no time of its own — LIS history rows are date-only. The TIME of an action is the time
// of the meeting it happened in, which is exactly what the calendar subsystem resolves. So we join
// STRUCTURALLY on the worker's own pairing: each meeting publishes its time plus the bills on its agenda AND
// the action taken on each. Key on (day | bill | action) — an EXACT match only.
//
// Deliberately NO "same bill, same day" fallback: it would stamp a meeting's clock onto that bill's
// ADMINISTRATIVE rows too (a "Fiscal Impact statement" is not something that happened in the 8:59 PM
// subcommittee). That's a plausible-but-wrong time, which Standard #3 forbids on the lobbyist-facing path.
// An action with no matching meeting shows "—": honest-absent, never a guess.
// Sheet1's Outcome cell sometimes carries a diagnostic tag THE WORKER ITSELF prepended — e.g.
// "📝 [Memory Anchor: admin] H House subcommittee offered", "⚙️ [Memory Anchor] H Subcommittee recommends…".
// The bill-history action has no such tag, so we strip OUR OWN decoration before comparing. This reverses a
// prefix we added; it is NOT parsing LIS prose. Fail-safe: if the tag format ever changes, the match simply
// misses and the row renders "—" (honest-absent) — it can never produce a WRONG time.
const stripWorkerTag = (s: string) => (s || "").replace(/^\s*[^\w\s([]*\s*\[[^\]]*\]\s*/, "");
const normAction = (s: string) => stripWorkerTag(s).trim().toLowerCase().replace(/\s+/g, " ");
interface TimeEntry { time: string; minutes: number; }   // minutes = the worker's authoritative SortTime key
type TimeIndex = Map<string, TimeEntry>;

// The daily driver (vision §3a). Top: what's-new (the anxiety-killer) + today's calendar sliver.
// Below: where the bills stand (outcome summary) + the timeline pipeline. Full-day feed, paged by day.

// When the newest action day is older than this, the feed header says so explicitly (off-season honesty,
// owner 2026-07-03) — 2 days tolerates a quiet in-session weekend without flagging it as "nothing newer."
const FEED_STALE_MS = 2 * 24 * 60 * 60 * 1000;

export function Landing({ bills, onOpen, calRefresh = 0 }: { bills: Bill[]; onOpen: (b: Bill) => void; calRefresh?: number }) {
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
  const [nowMs] = useState(() => Date.now()); // stable per mount — for the off-season "staleness" check below

  // Build the (day, bill, action) → meeting-time index from the calendar (cached load, shared with the sliver).
  const [times, setTimes] = useState<TimeIndex | null>(null);
  useEffect(() => {
    let alive = true;
    loadCalendar().then((cal) => {
      if (!alive) return;
      const exact: TimeIndex = new Map();
      for (const [dk, meetings] of cal.byDay) {
        for (const mt of meetings) {
          if (!mt.time || mt.tba || mt.unresolved) continue;  // no concrete clock → nothing honest to show
          const entry: TimeEntry = { time: mt.time, minutes: mt.minutes };
          for (const a of mt.bills) exact.set(`${dk}|${a.bill}|${normAction(a.action)}`, entry);
        }
      }
      setTimes(exact);
    }).catch(() => { if (alive) setTimes(new Map()); });
    return () => { alive = false; };
  }, [calRefresh]); // re-run when the freshness-gate invalidated the calendar cache (App bumps calRefresh)

  const timeFor = (day: string, bill: string, action: string): TimeEntry | null =>
    times?.get(`${day}|${bill}|${normAction(action)}`) ?? null;

  if (bills.length === 0) {
    return <p className="center-msg">No bills in scope. Star some bills, or switch to <b>Full GA</b>.</p>;
  }

  const [curDay, items] = days[Math.min(dayIdx, days.length - 1)] ?? ["", []];
  const curDate = parseLisDate(curDay);
  const dayLabel = curDate ? curDate.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : curDay || "—";
  // Off-season: the newest ACTION day (bills) is stale because the GA has adjourned — nothing is being voted
  // on. Say so plainly so the date doesn't read as "stuck", and point to the Today panel for current meetings
  // (owner 2026-07-08: "it shows Jun 29, not today"). Meetings ARE current — they're in the sliver, not here.
  const isStale = dayIdx === 0 && !!curDate && nowMs - curDate.getTime() > FEED_STALE_MS;

  // LATEST FIRST. Meeting actions sort by the meeting's authoritative minute key (descending); administrative
  // actions carry no clock, so they follow in their original order — we never invent a time to sort by. Not a
  // useMemo: this sits after an early return, and a conditional hook would break the rules of hooks. A single
  // day's actions are bounded, so the sort is trivial. No row cap either — the panel scrolls (never cut data).
  const ordered = (() => {
    const rows = items.map((it) => ({ it, t: timeFor(curDay, it.bill, it.action) }));
    const timed = rows.filter((r) => r.t).sort((a, b) => b.t!.minutes - a.t!.minutes);
    return [...timed, ...rows.filter((r) => !r.t)];
  })();

  return (
    <div>
      {/* Capped to ~2/3 of the viewport so the pipeline below always PEEKS into the bottom third — a
          first-time visitor can see there's more to scroll to (owner 2026-07-09). Panels scroll internally. */}
      <div className="cols landing-top">
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 className="h">What's new</h2>
            <div className="filters" style={{ margin: 0 }}>
              <button disabled={dayIdx >= days.length - 1} onClick={() => setDayIdx((i) => i + 1)}>← Older</button>
              <button disabled={dayIdx <= 0} onClick={() => setDayIdx((i) => Math.max(0, i - 1))}>Newer →</button>
            </div>
          </div>
          <div className="panel scroll-hint">
            {/* Off-season honesty (owner 2026-07-03/08): the feed opens on the newest day WITH bill actions;
                when that isn't recent, the header says so plainly (no box) — the date is the latest in data. */}
            <p className="feedday">
              {isStale
                ? <>No bill action since <strong>{dayLabel}</strong></>
                : <>{dayLabel} <span className="muted">· {items.length} action{items.length === 1 ? "" : "s"}</span></>}
            </p>
            {items.length === 0 && <p className="muted" style={{ padding: "8px 4px" }}>No actions on this day.</p>}
            {ordered.map(({ it, t }, i) => {
              const b = byBill.get(it.bill);
              return (
                <div key={i} className="feedrow" onClick={() => b && onOpen(b)} role="button" tabIndex={0}
                  onKeyDown={(e) => { if (b && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen(b); } }}>
                  <span className={`ftime${t ? "" : " none"}`} title={t ? "Time of the meeting this action happened in" : "Administrative action — no meeting time"}>{t?.time ?? "—"}</span>
                  <span className="fnum">{it.bill}</span>
                  <span className="fact">{it.action}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <h2 className="h">Today</h2>
          <CalendarSliver bills={bills} onOpen={onOpen} calRefresh={calRefresh} />
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
