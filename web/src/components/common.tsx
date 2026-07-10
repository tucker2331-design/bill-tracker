import type { Bill, Outcome } from "../data/types";
import { useScope, useStarred, toggleTracked, type Scope } from "../state/tracking";
import { STALE_AFTER_HOURS } from "../config";
import type { Completeness } from "../data/types";

const OUTCOME_LABEL: Record<Outcome, string> = {
  signed: "Signed", vetoed: "Vetoed", awaiting_governor: "To Governor",
  dead: "Dead", carried_over: "Carried over", in_progress: "In progress",
};

export function OutcomeChip({ outcome }: { outcome: Outcome }) {
  return <span className={`chip ${outcome}`}>{OUTCOME_LABEL[outcome]}</span>;
}

export function ChamberChip({ chamber }: { chamber: Bill["chamber"] }) {
  return <span className={`chip ${chamber.toLowerCase()}`}>{chamber}</span>;
}

export function Star({ id }: { id: string }) {
  const starred = useStarred();
  const on = starred.has(id);
  return (
    <button
      className={`star ${on ? "on" : ""}`}
      aria-pressed={on}
      aria-label={on ? "Tracking — click to untrack" : "Track this bill"}
      title={on ? "Tracking — click to untrack" : "Track this bill"}
      onClick={(e) => { e.stopPropagation(); toggleTracked(id); }}
    >
      {on ? "★" : "☆"}
    </button>
  );
}

export function ScopeSwitch() {
  const [scope, setScope] = useScope();
  const opt = (val: Scope, label: string) => (
    <button className={scope === val ? "on" : ""} onClick={() => setScope(val)}>{label}</button>
  );
  return (
    <div className="scope" role="group" aria-label="Scope">
      {opt("tracking", "Tracking")}
      {opt("full", "Full GA")}
    </div>
  );
}

export function relativeTime(d: Date | null): { text: string; stale: boolean } {
  if (!d) return { text: "unknown", stale: true };
  const ms = Date.now() - d.getTime();
  const hrs = ms / 3.6e6;
  const stale = hrs >= STALE_AFTER_HOURS;
  if (hrs < 1) return { text: `${Math.max(1, Math.round(ms / 6e4))} min ago`, stale };
  if (hrs < 48) return { text: `${Math.round(hrs)} hr ago`, stale };
  return { text: `${Math.round(hrs / 24)} days ago`, stale };
}

export function TrustHeader({ dataAsOf, calendarAsOf, completeness, shown }: {
  dataAsOf: Date | null; calendarAsOf?: Date | null; completeness: Completeness | null; shown: number;
}) {
  const fresh = relativeTime(dataAsOf);
  const cal = calendarAsOf !== undefined ? relativeTime(calendarAsOf) : null;
  const universe = completeness?.universe_count;
  const written = completeness?.records_written;
  const anomalies = completeness?.in_history_not_in_universe?.length ?? 0;
  // Completeness is the top trust signal: do we have every bill LIS has?
  const complete = universe != null && written != null && universe === written && anomalies === 0;
  // Masthead of numbers (owner 2026-07-08): the two freshness clocks (bill backend 6h · calendar subsystem 3h
  // are separate workers, shown side by side) + the tracking count, organized with thin dividers — no dots,
  // no verdict text. Each value is dark ink; a STALE clock (or an incomplete count) turns its VALUE red — a
  // colour signal, not interpretive language, so a lobbyist is reassured by default and only concerned when a
  // number goes red (docs/design: a signal must vary to exist; reserve colour for the exception).
  return (
    <div className="trust">
      <span className="tr-item" title={`Bill data · ${dataAsOf?.toISOString() ?? "unknown"}`}>
        Bills <b className={fresh.stale ? "stale" : ""}>{fresh.text}</b>
      </span>
      {cal && (<>
        <span className="tr-div" aria-hidden="true" />
        <span className="tr-item" title={`Calendar subsystem · ${calendarAsOf?.toISOString() ?? "unknown"}`}>
          Calendar <b className={cal.stale ? "stale" : ""}>{cal.text}</b>
        </span>
      </>)}
      {universe != null && (<>
        <span className="tr-div" aria-hidden="true" />
        <span className="tr-item" title={`records ${written}/${universe}; ${anomalies} in-history-not-in-universe`}>
          Tracking <b className={complete ? "" : "stale"}>{written?.toLocaleString()} / {universe.toLocaleString()}</b>
        </span>
      </>)}
      <span className="tr-showing">Showing {shown.toLocaleString()}</span>
    </div>
  );
}
