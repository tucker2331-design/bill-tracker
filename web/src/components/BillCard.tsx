import { useEffect, useState } from "react";
import type { Bill } from "../data/types";
import { OutcomeChip, ChamberChip, Star } from "./common";
import { lisBillUrl } from "../config";
import { loadCalendar, nextMeetingFor, minutesUntil, type Meeting as CalMeeting } from "../data/calendar";
import { dayKey, parseLisDate } from "../data/dates";

// The bill card — every fact tied to its source location so they correlate (vision §6), with the
// recovered pin (§5) and the deterministic LIS link. Used as a modal over any view.
export function BillCard({ bill, sessionCode, onClose }: { bill: Bill; sessionCode: string; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // The pin (shadow_v2.py:420): if LIS's current status names an action not yet in the published
  // history, synthesize a provisional top row — labelled WHY, never invented.
  const statusKey = bill.statusLis.toLowerCase().trim();
  const inHistory = !!statusKey && bill.history.some((h) => h.action.toLowerCase().includes(statusKey));
  const showPin = !!statusKey && !inHistory;

  const rows = [...bill.history].reverse();   // newest first

  const v = bill.latestVote;
  const next = bill.upcoming[0];

  // Option 2 (owner 2026-07-13): the Next-meeting row carries the full answer — when, which committee,
  // the agenda/livestream links — joined from the calendar data (shared cached load), so nobody detours
  // to the Calendar tab to find their bill. `undefined` = still loading (render the thin `upcoming`
  // fallback meanwhile); `null` = calendar loaded, nothing scheduled (honest "none scheduled").
  const [nextMtg, setNextMtg] = useState<CalMeeting | null | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    loadCalendar()
      .then((cal) => { if (alive) setNextMtg(nextMeetingFor(cal, bill.bill, dayKey(new Date()))); })
      .catch(() => { if (alive) setNextMtg(null); }); // calendar unavailable → same as no join (fallback row)
    return () => { alive = false; };
  }, [bill.bill]);

  // <48h to a CONCRETE clock → the amber "pending/caution" row (the design system's one urgency tint).
  // TBA / unresolved / relative phrases never go amber — no urgency claimed for a time we can't place.
  const minsAway = nextMtg ? minutesUntil(nextMtg, new Date()) : null;
  const soon = minsAway !== null && minsAway <= 48 * 60;
  const countdown = minsAway === null ? "" :
    minsAway < 60 ? `in ${minsAway} min` :
    minsAway < 48 * 60 ? `in ${Math.round(minsAway / 60)} hours` :
    `in ${Math.round(minsAway / (24 * 60))} days`;
  const mtgDate = (m: CalMeeting) => {
    const d = parseLisDate(m.dateKey);   // local-safe + rollover-rejecting (Gemini #219: reuse, don't re-split)
    return d ? d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : m.dateKey;
  };

  return (
    <div className="cardwrap" onClick={onClose}>
      <div className="card" onClick={(e) => e.stopPropagation()}>
        <header>
          <Star id={bill.bill} />
          <div style={{ flex: 1 }}>
            <div><span className="num">{bill.bill}</span> <ChamberChip chamber={bill.chamber} /></div>
            <div className="cat">{bill.title}</div>
          </div>
          <button className="close" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="body">
          <div style={{ marginBottom: 12, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <OutcomeChip outcome={bill.outcome} bill={bill} />
            {/* neutral grey (owner 2026-07-13): a routine status milestone — the purple MEANS Senate
                everywhere else, and one-meaning-per-color is the doctrine (was `chip senate`). */}
            {bill.crossedOver && <span className="chip crossed">crossed over</span>}
            {bill.referrals > 1 && <span className="chip referral">{bill.referrals} referrals</span>}
          </div>

          <div className="metarow"><span className="k">Status (LIS)</span><span>{bill.statusLis || "—"}</span></div>
          <div className="metarow"><span className="k">Where it is</span>
            <span>{bill.lastCommittee ? `${bill.lastCommittee}` : `${bill.chamber} (no current committee)`}</span></div>
          <div className="metarow"><span className="k">Patron</span><span>{bill.patron || "—"}{bill.patronId ? ` (${bill.patronId})` : ""}</span></div>
          <div className="metarow"><span className="k">Latest vote</span>
            <span>{v.tally ? <>{v.tally} <span className="muted">— {v.location || "Floor"}{v.date ? `, ${v.date}` : ""}</span></> : <span className="muted">no recorded vote</span>}</span></div>
          <div className={`metarow${soon ? " next-soon" : ""}`}><span className="k">Next meeting</span>
            <span>
              {nextMtg ? (
                <>
                  <b className={soon ? "soon-ink" : undefined}>{mtgDate(nextMtg)} · {nextMtg.time}</b>
                  {countdown && <span className="muted"> · {countdown}</span>}
                  <br />
                  <span className="muted">{nextMtg.committee}</span>
                  {nextMtg.agendaUrl && <> · <a href={nextMtg.agendaUrl} target="_blank" rel="noopener noreferrer">📄 Agenda</a></>}
                  {!nextMtg.agendaUrl && nextMtg.meetingUrl && <> · <span className="muted" style={{ fontStyle: "italic" }}>agenda not posted yet</span></>}
                  {nextMtg.meetingUrl && <> · <a href={nextMtg.meetingUrl} target="_blank" rel="noopener noreferrer">▶ Watch live</a></>}
                </>
              ) : next ? (
                // thin Bill_Tracker fallback (calendar still loading, or its rows had no agenda hit)
                <>{next.committee || "Committee"} <span className="muted">— {next.date}</span></>
              ) : (
                <span className="muted">none scheduled</span>
              )}
            </span></div>

          <h3 className="h" style={{ marginTop: 16 }}>History</h3>
          <table className="histtable">
            <thead><tr><th>Action</th><th>Date</th></tr></thead>
            <tbody>
              {showPin && (
                <tr className="pinned" title="Status feed is ahead of the published history; shown provisionally, never invented.">
                  <td>📍 {bill.statusLis} <span className="chip provisional">provisional</span></td>
                  <td className="date">pending</td>
                </tr>
              )}
              {rows.map((h, i) => (
                <tr key={i}><td>{h.action}</td><td className="date">{h.date}</td></tr>
              ))}
              {rows.length === 0 && !showPin && (
                <tr><td className="muted" colSpan={2}>No history yet (prefiled / not yet acted).</td></tr>
              )}
            </tbody>
          </table>

          <div style={{ marginTop: 14 }}>
            <a href={lisBillUrl(sessionCode, bill.bill)} target="_blank" rel="noopener noreferrer">
              View on LIS ↗
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
