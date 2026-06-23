import { useEffect, useMemo, useState } from "react";
import type { Bill, BillData } from "./data/types";
import { loadBillData } from "./data/gviz";
import { scopedBills } from "./data/derive";
import { useScope, useStarred } from "./state/tracking";
import { ScopeSwitch, TrustHeader } from "./components/common";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { BillCard } from "./components/BillCard";
import { Landing } from "./views/Landing";
import { Timeline } from "./views/Timeline";
import { Calendar } from "./views/Calendar";
import { Search } from "./views/Search";
import { Health } from "./views/Health";

type Tab = "today" | "timeline" | "calendar" | "search" | "health";
const TABS: { id: Tab; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "timeline", label: "Timeline" },
  { id: "calendar", label: "Calendar" },
  { id: "search", label: "Search" },
  { id: "health", label: "Health" },
];

export default function App() {
  const [data, setData] = useState<BillData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("today");
  const [selected, setSelected] = useState<Bill | null>(null);
  const [scope] = useScope();
  const starred = useStarred();

  useEffect(() => {
    let alive = true;
    loadBillData().then((d) => alive && setData(d)).catch((e) => alive && setError(String(e?.message || e)));
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
          {data && <TrustHeader dataAsOf={data.dataAsOf} completeness={data.completeness} shown={visible.length} />}
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
            {tab === "timeline" && <Timeline bills={visible} onOpen={open} />}
            {tab === "calendar" && <Calendar bills={visible} onOpen={open} />}
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
