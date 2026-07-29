import { useEffect, useMemo, useRef, useState } from "react";
import type { Bill, BillData } from "./data/types";
import { loadBillData } from "./data/gviz";
import { loadCalendarFreshness, invalidateCalendar } from "./data/calendar";
import { fetchBillStamp, fetchCalendarStamp } from "./data/refresh";
import { scopedBills } from "./data/derive";
import { useScope, useStarred } from "./state/tracking";
import { ScopeSwitch, TrustHeader } from "./components/common";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { RefreshNotice } from "./components/RefreshNotice";
import { BillCard } from "./components/BillCard";
import { Landing } from "./views/Landing";
import { Calendar } from "./views/Calendar";
import { Search } from "./views/Search";
import { Health } from "./views/Health";
import { WarRoom } from "./views/WarRoom";
import { useRoute, navigate, tabPath, linkProps, detailPath, type TabId } from "./state/router";

// Freshness-gate cadence: poll the two ~22-byte stamp cells this often (and on window-focus). Well under any
// worker cadence, and cheap enough that an idle off-season tab costs a few bytes a minute. (auto_refresh doc)
const POLL_MS = 90_000;

// No standalone Timeline tab — the timeline lives on the landing (owner, 2026-06-23: redundant).
// Tab identity now comes from the URL (state/router.ts) rather than useState — every tab is linkable.
const TABS: { id: TabId; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "calendar", label: "Calendar" },
  { id: "search", label: "Search" },
  { id: "warroom", label: "War Room" },
  { id: "health", label: "Health" },
];

export default function App() {
  const [data, setData] = useState<BillData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [route] = useRoute();
  // The tab is derived from the route. A detail/list route keeps the surrounding chrome on its parent tab so
  // the nav never blanks out while a bill card is open.
  const tab: TabId = route.kind === "tab" ? route.tab : "search";
  // `selected` is DERIVED from the route, not stored. Two sources of truth for "which bill is open" would
  // drift the moment someone used Back, and the card would outlive its URL.
  const selected: Bill | null =
    route.kind === "detail" && route.entity === "bills" && data
      ? data.bills.find((b) => b.bill === route.id) ?? null
      : null;
  // The calendar subsystem's own freshness (Sheet1!AA1) — undefined until loaded, null when unreadable.
  // Surfaced in the top trust header next to the bill clock so the two feeds' cadences read cohesively.
  const [calendarAsOf, setCalendarAsOf] = useState<Date | null | undefined>(undefined);
  // Calendar refresh signal: the calendar payload is cached module-side and consumed by three components
  // (Landing, its CalendarSliver, and the Calendar tab). Bumping this after invalidateCalendar() makes each
  // re-run its loadCalendar() effect and pick up the new data — without threading the payload through App.
  const [calRefresh, setCalRefresh] = useState(0);
  // Transient "why did this just change" notice (owner 2026-07-10). token bumps per refresh so the notice
  // re-mounts and re-times; label says which feed moved. NOT a persistent freshness readout — that's the header.
  const [refresh, setRefresh] = useState<{ token: number; label: string }>({ token: 0, label: "" });
  const [scope] = useScope();
  const starred = useStarred();

  // The last-seen freshness STAMPS. These hold the RAW cell strings ONLY (never a Date round-trip): the poll
  // compares them against the raw cells it re-reads, so any formatting difference (e.g. "…54Z" vs a Date's
  // "…54.000Z") would read as a phantom change. Refs, not state — the poll reads them without re-subscribing.
  const billStamp = useRef<string>("");
  const calStamp = useRef<string>("");

  useEffect(() => {
    let alive = true;
    loadBillData().then((d) => { if (alive) setData(d); })
      .catch((e) => alive && setError(String(e?.message || e)));
    // Non-blocking: a lightweight AA1 read; failure just leaves the calendar clock "unknown" (never blocks).
    // loadCalendarFreshness() already resolves to null on error, but keep a defensive, OBSERVABLE catch —
    // never a silent swallow (Standard #4 / Qodo): log before falling back to "unknown".
    loadCalendarFreshness()
      .then((d) => { if (alive) setCalendarAsOf(d); })
      .catch((e) => { console.warn("calendar freshness load failed; header clock shows 'unknown'", e); if (alive) setCalendarAsOf(null); });
    // Seed the stamp refs from the SAME raw cells the poll reads, so the first comparison is like-for-like.
    fetchBillStamp().then((s) => { if (alive && s) billStamp.current = s; }).catch(() => {});
    fetchCalendarStamp().then((s) => { if (alive && s) calStamp.current = s; }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // ── Freshness-gated background refresh (docs/ideas/auto_refresh_on_new_data) ──
  // Poll the two cheap stamp cells on an interval AND whenever the tab regains focus. Only when a stamp has
  // ACTUALLY advanced do we pay for the full re-fetch. A blank read ("") is "unknown" and never triggers a
  // refresh — a transient blip can miss an update but can never invent one.
  useEffect(() => {
    let alive = true;
    let running = false;
    const check = async () => {
      if (!alive || running || document.visibilityState === "hidden") return;
      running = true;
      try {
        const [bs, cs] = await Promise.all([fetchBillStamp(), fetchCalendarStamp()]);
        if (!alive) return;
        const billMoved = bs !== "" && billStamp.current !== "" && bs !== billStamp.current;
        const calMoved = cs !== "" && calStamp.current !== "" && cs !== calStamp.current;
        // Adopt the new RAW stamps immediately (before the slow re-fetch) so a second poll mid-refetch doesn't
        // re-trigger. The refs stay raw-only — never overwritten with a Date round-trip.
        if (bs) billStamp.current = bs;
        if (cs) calStamp.current = cs;
        if (billMoved) {
          const d = await loadBillData();
          if (!alive) return;
          setData(d);
        }
        if (calMoved) {
          invalidateCalendar();
          setCalRefresh((n) => n + 1);
          loadCalendarFreshness().then((d) => { if (alive) setCalendarAsOf(d); }).catch(() => {});
        }
        if (billMoved || calMoved) {
          const label = billMoved && calMoved ? "Updated with the latest bill & calendar data"
            : billMoved ? "Updated with the latest bill data"
            : "Updated with the latest calendar data";
          setRefresh((r) => ({ token: r.token + 1, label }));
        }
      } catch (e) {
        console.warn("freshness poll failed; will retry next tick", e);
      } finally {
        running = false;
      }
    };
    const id = setInterval(check, POLL_MS);
    const onFocus = () => { void check(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    return () => { alive = false; clearInterval(id); window.removeEventListener("focus", onFocus); document.removeEventListener("visibilitychange", onFocus); };
  }, []);

  const visible = useMemo(
    () => (data ? scopedBills(data.bills, scope, starred) : []),
    [data, scope, starred]
  );

  // Opening a bill pushes /bills/:number so the card is linkable and Back closes it. The card itself stays
  // a modal — this changes the URL, not the interaction.
  const open = (b: Bill) => navigate(detailPath("bills", b.bill));

  return (
    <div className="app">
      {/* one sticky container so the nav never overlaps a wrapped topbar (no hard-coded offset) */}
      <div className="appheader">
        <header className="topbar">
          <div className="brand">VA Bill Tracker</div>
          <ScopeSwitch />
          <div className="spacer" />
          {data && <TrustHeader dataAsOf={data.dataAsOf} calendarAsOf={calendarAsOf} completeness={data.completeness} shown={visible.length} />}
        </header>

        <nav className="nav">
          {TABS.map((t) => (
            <a key={t.id} className={tab === t.id ? "active" : ""} {...linkProps(tabPath(t.id))}>
              {t.label}
            </a>
          ))}
        </nav>
      </div>

      {/* Calendar needs the wider container (7 day columns + month picker); see `.main-wide` in index.css. */}
      <main className={tab === "calendar" ? "main main-wide" : "main"}>
        {error && <p className="center-msg" style={{ color: "var(--stale)" }}>
          Couldn't load data: {error}<br /><span className="muted">The Mastermind DB sheet must be link-readable for gviz.</span>
        </p>}
        {!data && !error && <p className="center-msg">Loading the General Assembly…</p>}
        {data && (
          <ErrorBoundary resetKey={tab}>
            {tab === "today" && <Landing bills={visible} onOpen={open} calRefresh={calRefresh} />}
            {/* Calendar reads the calendar subsystem (Sheet1) and scopes itself via the global switch,
                so it gets the FULL bill set for the agenda→card lookup, not the pre-scoped `visible`. */}
            {tab === "calendar" && <Calendar bills={data.bills} sessionCode={data.sessionCode} onOpen={open} calRefresh={calRefresh} />}
            {tab === "search" && <Search bills={visible} onOpen={open} />}
            {tab === "warroom" && <WarRoom bills={data.bills} starred={starred} />}
            {tab === "health" && <Health completeness={data.completeness} dataAsOf={data.dataAsOf} />}
          </ErrorBoundary>
        )}
      </main>

      {selected && data && (
        <BillCard bill={selected} sessionCode={data.sessionCode} onClose={() => window.history.back()} />
      )}

      {/* Transient "why did this just change" cue after a background refresh — self-dismisses.
          key={token} remounts it per refresh so each notice restarts its fade cleanly. */}
      <RefreshNotice key={refresh.token} token={refresh.token} label={refresh.label} />
    </div>
  );
}
