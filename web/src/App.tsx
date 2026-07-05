import { useEffect, useMemo, useState } from "react";
import type { Bill, BillData } from "./data/types";
import { loadBillData } from "./data/gviz";
import { loadCalendarFreshness } from "./data/calendar";
import { scopedBills } from "./data/derive";
import { useScope, useStarred } from "./state/tracking";
import { ScopeSwitch, TrustHeader } from "./components/common";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { BillCard } from "./components/BillCard";
import { Landing } from "./views/Landing";
import { Calendar } from "./views/Calendar";
import { Search } from "./views/Search";
import { Health } from "./views/Health";

// No standalone Timeline tab — the timeline lives on the landing (owner, 2026-06-23: redundant).
type Tab = "today" | "calendar" | "search" | "health";
const TABS: { id: Tab; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "calendar", label: "Calendar" },
  { id: "search", label: "Search" },
  { id: "health", label: "Health" },
];

export default function App() {
  const [data, setData] = useState<BillData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("today");
  const [selected, setSelected] = useState<Bill | null>(null);
  // The calendar subsystem's own freshness (Sheet1!AA1) — undefined until loaded, null when unreadable.
  // Surfaced in the top trust header next to the bill clock so the two feeds' cadences read cohesively.
  const [calendarAsOf, setCalendarAsOf] = useState<Date | null | undefined>(undefined);
  const [scope] = useScope();
  const starred = useStarred();

  useEffect(() => {
    let alive = true;
    loadBillData().then((d) => alive && setData(d)).catch((e) => alive && setError(String(e?.message || e)));
    // Non-blocking: a lightweight AA1 read; failure just leaves the calendar clock "unknown" (never blocks).
    // loadCalendarFreshness() already resolves to null on error, but keep a defensive, OBSERVABLE catch —
    // never a silent swallow (Standard #4 / Qodo): log before falling back to "unknown".
    loadCalendarFreshness()
      .then((d) => alive && setCalendarAsOf(d))
      .catch((e) => { console.warn("calendar freshness load failed; header clock shows 'unknown'", e); if (alive) setCalendarAsOf(null); });
    return () => { alive = false; };
  }, []);

  const visible = useMemo(
    () => (data ? scopedBills(data.bills, scope, starred) : []),
    [data, scope, starred]
  );

  const open = (b: Bill) => setSelected(b);

  return (
    <div className="app">
      {/* one sticky container so the nav never overlaps a wrapped topbar (no hard-coded offset) */}
      <div className="appheader">
        <header className="topbar">
          <div className="brand"><span className="dot" /> VA Bill Tracker</div>
          <ScopeSwitch />
          <div className="spacer" />
          {data && <TrustHeader dataAsOf={data.dataAsOf} calendarAsOf={calendarAsOf} completeness={data.completeness} shown={visible.length} />}
        </header>

        <nav className="nav">
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      <main className="main">
        {error && <p className="center-msg" style={{ color: "var(--stale)" }}>
          Couldn't load data: {error}<br /><span className="muted">The Mastermind DB sheet must be link-readable for gviz.</span>
        </p>}
        {!data && !error && <p className="center-msg">Loading the General Assembly…</p>}
        {data && (
          <ErrorBoundary resetKey={tab}>
            {tab === "today" && <Landing bills={visible} onOpen={open} />}
            {/* Calendar reads the calendar subsystem (Sheet1) and scopes itself via the global switch,
                so it gets the FULL bill set for the agenda→card lookup, not the pre-scoped `visible`. */}
            {tab === "calendar" && <Calendar bills={data.bills} sessionCode={data.sessionCode} onOpen={open} />}
            {tab === "search" && <Search bills={visible} onOpen={open} />}
            {tab === "health" && <Health completeness={data.completeness} dataAsOf={data.dataAsOf} />}
          </ErrorBoundary>
        )}
      </main>

      {selected && data && (
        <BillCard bill={selected} sessionCode={data.sessionCode} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
