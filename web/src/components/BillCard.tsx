import { useEffect } from "react";
import type { Bill } from "../data/types";
import { OutcomeChip, ChamberChip, Star } from "./common";
import { lisBillUrl } from "../config";

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
            <OutcomeChip outcome={bill.outcome} />
            {bill.crossedOver && <span className="chip senate">crossed over</span>}
            {bill.referrals > 1 && <span className="chip referral">{bill.referrals} referrals</span>}
          </div>

          <div className="metarow"><span className="k">Status (LIS)</span><span>{bill.statusLis || "—"}</span></div>
          <div className="metarow"><span className="k">Where it is</span>
            <span>{bill.lastCommittee ? `${bill.lastCommittee}` : `${bill.chamber} (no current committee)`}</span></div>
          <div className="metarow"><span className="k">Patron</span><span>{bill.patron || "—"}{bill.patronId ? ` (${bill.patronId})` : ""}</span></div>
          <div className="metarow"><span className="k">Latest vote</span>
            <span>{v.tally ? <>{v.tally} <span className="muted">— {v.location || "Floor"}{v.date ? `, ${v.date}` : ""}</span></> : <span className="muted">no recorded vote</span>}</span></div>
          <div className="metarow"><span className="k">Next meeting</span>
            <span>{next ? <>{next.committee || "Committee"} <span className="muted">— {next.date}</span></> : <span className="muted">none scheduled</span>}</span></div>

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
