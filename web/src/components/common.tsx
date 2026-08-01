import { useEffect, useRef, useState } from "react";
import type { Bill, Outcome } from "../data/types";
import { useScope, useStarred, toggleTracked, type Scope } from "../state/tracking";
import { STALE_AFTER_HOURS } from "../config";
import type { Completeness } from "../data/types";

const OUTCOME_LABEL: Record<Outcome, string> = {
  signed: "Signed", vetoed: "Vetoed", awaiting_governor: "To Governor",
  dead: "Dead", carried_over: "Carried over", in_progress: "In progress",
};

/**
 * How far has a bill actually got? "In progress" covers everything from "filed yesterday" to "passed both
 * chambers and waiting on enrollment", which is the complaint: a volunteer reads it as "nothing has
 * happened" and misses that the bill is one step from law.
 *
 * STRUCTURAL, not text (Standard #3): `floorHouse`/`floorSenate` are validated enums the worker writes from
 * LIS's own floor columns — this is set logic on two fields, never a scan of the status prose. Only
 * `in_progress` is refined; a bill that is Signed or Dead has a terminal answer already, and appending
 * "passed the House" to it would be noise.
 */
export function progressLabel(bill: Pick<Bill, "outcome" | "floorHouse" | "floorSenate">): string {
  if (bill.outcome !== "in_progress") return OUTCOME_LABEL[bill.outcome];
  const h = bill.floorHouse === "passed";
  const s = bill.floorSenate === "passed";
  if (h && s) return "Passed both chambers";
  if (h) return "Passed the House";
  if (s) return "Passed the Senate";
  return OUTCOME_LABEL.in_progress;
}

/**
 * `bill` refines the label with floor progress. Without it the chip falls back to the plain outcome word —
 * which is what the Landing legend wants, since there it labels the OUTCOME CATEGORY itself, not one bill.
 */
export function OutcomeChip({ outcome, bill }: {
  outcome: Outcome; bill?: Pick<Bill, "outcome" | "floorHouse" | "floorSenate">;
}) {
  return <span className={`chip ${outcome}`}>{bill ? progressLabel(bill) : OUTCOME_LABEL[outcome]}</span>;
}

export function ChamberChip({ chamber }: { chamber: Bill["chamber"] }) {
  return <span className={`chip ${chamber.toLowerCase()}`}>{chamber}</span>;
}

export function Star({ id }: { id: string }) {
  const starred = useStarred();
  const on = starred.has(id);
  // Two-step UNtrack (owner 2026-07-13): a lit star no longer untracks on a single click — a misclick
  // silently dropping a tracked bill is state destruction. Starring stays one click. The confirm's
  // default (autofocused) button is "Keep tracking", so Enter/space can't destroy state either.
  const [confirming, setConfirming] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!confirming) return;
    // CAPTURE-phase + containment check (Gemini #219): the wrapper's bubbling stopPropagation (needed so a
    // star click doesn't open the bill card) would otherwise let a click on ANOTHER bill's star leave this
    // confirm stuck open — capture runs before any stopPropagation can swallow the event.
    const onDoc = (e: MouseEvent) => { if (!wrapRef.current?.contains(e.target as Node)) setConfirming(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setConfirming(false); };
    window.addEventListener("click", onDoc, { capture: true });
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("click", onDoc, { capture: true }); window.removeEventListener("keydown", onKey); };
  }, [confirming]);
  return (
    <span className="starwrap" ref={wrapRef} onClick={(e) => e.stopPropagation()}>
      <button
        className={`star ${on ? "on" : ""}`}
        aria-pressed={on}
        aria-label={on ? "Tracking — click to untrack" : "Track this bill"}
        title={on ? "Tracking — click to untrack" : "Track this bill"}
        onClick={() => { if (!on) { toggleTracked(id); return; } setConfirming((c) => !c); }}
      >
        {on ? "★" : "☆"}
      </button>
      {confirming && (
        <span className="star-confirm" role="alertdialog" aria-label={`Stop tracking ${id}?`}>
          <b>Stop tracking {id}?</b>
          <span className="btns">
            <button className="keep" autoFocus onClick={() => setConfirming(false)}>Keep tracking</button>
            <button className="untrack" onClick={() => { toggleTracked(id); setConfirming(false); }}>Untrack</button>
          </span>
        </span>
      )}
    </span>
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

export function TrustHeader({ dataAsOf, calendarAsOf, completeness }: {
  dataAsOf: Date | null; calendarAsOf?: Date | null; completeness: Completeness | null;
}) {
  const fresh = relativeTime(dataAsOf);
  const cal = calendarAsOf !== undefined ? relativeTime(calendarAsOf) : null;
  const universe = completeness?.universe_count;
  const written = completeness?.records_written;
  const anomalies = completeness?.in_history_not_in_universe?.length ?? 0;
  // Completeness is the top trust signal: do we have every bill LIS has?
  const complete = universe != null && written != null && universe === written && anomalies === 0;
  // Which session are these numbers about? ONLY from what the backend STAMPED — LIS's own DisplayName,
  // else the authoritative code. Never the front end's inferred `${year}1`: measured 2026-07-31, that
  // inference reads "20261" while the sheet holds session 20262, so printing it would label special-session
  // data with the regular session's name. A missing label renders nothing, which is honest; a confidently
  // wrong one is the failure this masthead exists to prevent.
  const sessionLabel = (completeness?.session_display || "").trim()
    || (completeness?.session_code ? `Session ${completeness.session_code}` : "");
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
      {sessionLabel && (
        <span className="tr-showing" title={`Session ${completeness?.session_code ?? ""}`}>{sessionLabel}</span>
      )}
    </div>
  );
}
