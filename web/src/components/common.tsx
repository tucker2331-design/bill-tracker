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
  return (
    <div className="trust">
      {/* Both freshness clocks live TOGETHER here (owner 2026-07-04) — the bill backend (6h cadence) and the
          calendar subsystem (3h) are separate workers, so their "as of" times differ; showing them side by
          side up top reads as "two feeds, two clocks" instead of a contradiction buried in the Calendar tab. */}
      <span className={`pill ${fresh.stale ? "warn" : "good"}`} title={`Bill data · ${dataAsOf?.toISOString() ?? "unknown"}`}>
        ● Bills as of {fresh.text}
      </span>
      {cal && (
        <span className={`pill ${cal.stale ? "warn" : "good"}`} title={`Calendar subsystem · ${calendarAsOf?.toISOString() ?? "unknown"}`}>
          🗓 Calendar as of {cal.text}
        </span>
      )}
      {universe != null && (
        <span className={`pill ${complete ? "good" : "warn"}`}
          title={`records ${written}/${universe}; ${anomalies} in-history-not-in-universe`}>
          {complete ? "✓" : "!"} Tracking {written}/{universe} bills
        </span>
      )}
      <span className="muted">Showing {shown.toLocaleString()}</span>
    </div>
  );
}
