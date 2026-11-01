// The War Room bill page — one tracked bill, drilled into from the War Room list (owner 2026-07-17: the War Room
// is its OWN tab, "your bills -> drill in"; layout from the approved HB 1515 mockup, built 2026-10-31).
//
// Built from EXISTING components only, and a mockup section with no data source is OMITTED, not faked:
//   Status        LIS (statusLis / outcome / lastCommittee / patron / co-patrons / latest vote / next meeting)
//   Members       the served calls (MemberCalls — frozen arm C, private War_Room_Calls tab)
//   Your position your team's entry (PositionControl, Worker+D1)
//   Contact log   your team's entries (ContactLog, Worker+D1)
//   More          LIS summary (Summary) + the LIS bill link
// Omitted because nothing in the product serves them yet: the "subcommittee record" tiles, "earlier versions"
// (VA + other states), and "factors tested and not used". Add a section here only when its source ships.
// A state with no vote model (PA) shows the current committee and its members (CommitteeMembers, from the state's
// roster feed) where the member calls would be; a state with no summary text hides the summary, keeping the link.
import type { Bill } from "../data/types";
import { OutcomeChip, Star } from "../components/common";
import { Copatrons, NextMeeting, Summary } from "../components/BillCard";
import { MemberCalls } from "../components/MemberCalls";
import { CommitteeMembers } from "../components/CommitteeMembers";
import { PositionControl } from "../components/PositionControl";
import { ContactLog } from "../components/ContactLog";
import { sourceBillUrl, SOURCE } from "../config";
import { STATE } from "../states";
import { linkProps, tabPath } from "../state/router";
import { useStarred } from "../state/tracking";

export function WarRoomBill({ id, bills, sessionCode }: { id: string; bills: Bill[]; sessionCode: string }) {
  const tracked = useStarred().has(id);
  const bill = bills.find((b) => b.bill === id);
  const back = <a className="wb-back" {...linkProps(tabPath("warroom"))}>‹ War Room</a>;

  if (!bill) {
    return (
      <div className="wb">
        <nav className="wb-nav">{back}</nav>
        <p className="center-msg">{id} is not in this session's bill list.</p>
      </div>
    );
  }
  const v = bill.latestVote;
  const last = bill.history.length ? bill.history[bill.history.length - 1] : null;
  const link = sourceBillUrl(sessionCode, bill.bill);   // "" = the state has no per-bill page we link to

  return (
    <div className="wb">
      <nav className="wb-nav">{back}<Star id={bill.bill} /></nav>

      <header className="wb-title">
        <h1>{bill.bill}</h1>
        <p>{bill.title}</p>
        {!tracked && <p className="muted wb-untracked">Not tracked — star it to keep it in your War Room.</p>}
      </header>

      <section className="wb-status" aria-label="Status">
        <div className="wb-kicker">Status <span className="muted">· {SOURCE}</span></div>
        <div className="wb-state">{bill.statusLis || "—"}</div>
        <div className="wb-where">
          {bill.lastCommittee || `${bill.chamber} (no current committee)`}
          {last ? ` · ${last.date}` : ""}
        </div>
        <div className="wb-facts">
          <OutcomeChip outcome={bill.outcome} bill={bill} />
          {bill.crossedOver && <span className="chip crossed">crossed over</span>}
          {bill.referrals > 1 && <span className="chip referral">{bill.referrals} referrals</span>}
        </div>
        <div className="wb-rows">
          <div className="metarow"><span className="k">Patron</span><span>{bill.patron || "—"}{bill.patronId ? ` (${bill.patronId})` : ""}</span></div>
          <div className="metarow"><span className="k">Co-patrons</span><Copatrons list={bill.copatrons} /></div>
          <div className="metarow"><span className="k">Latest vote</span>
            <span>{v.tally ? <>{v.tally} <span className="muted">— {v.location || "Floor"}{v.date ? `, ${v.date}` : ""}</span></> : <span className="muted">no recorded vote</span>}</span></div>
          <NextMeeting bill={bill} />
        </div>
      </section>

      {STATE.features.predictions && (
        <section className="wb-group" aria-label="Members">
          <MemberCalls bill={bill.bill} sessionCode={sessionCode} />
        </section>
      )}
      {STATE.features.committeeRoster && (
        <section className="wb-group" aria-label="Committee">
          <CommitteeMembers lastCommittee={bill.lastCommittee} chamber={bill.chamber} />
        </section>
      )}

      <section className="wb-group" aria-label="Your position">
        <h3 className="h">Your position</h3>
        <PositionControl bill={bill.bill} sessionCode={sessionCode} />
      </section>

      <section className="wb-group">
        <ContactLog key={`contacts-${bill.bill}`} bill={bill.bill} sessionCode={sessionCode} />
      </section>

      {(STATE.features.summaries || link) && (
        <section className="wb-group" aria-label="More">
          <h3 className="h">More</h3>
          {STATE.features.summaries && <Summary key={`summary-${bill.bill}`} bill={bill.bill} lisUrl={link} />}
          {link && <a href={link} target="_blank" rel="noopener noreferrer">Bill and history on {SOURCE} ↗</a>}
        </section>
      )}

      <p className="muted wb-foot">Status, votes, committees{STATE.features.summaries ? " and the summary" : ""}
        {STATE.features.committeeRoster ? ", committee members" : ""}: {STATE.sourceLongName}.
        {STATE.features.predictions ? " Member calls: the vote model's served calls." : ""} Position and contacts: your
        team's own entries, not from {SOURCE}.</p>
    </div>
  );
}
