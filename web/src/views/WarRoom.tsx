// The War Room list — your tracked bills, one card each, grouped by when they are next heard (v9, owner-approved
// 2026-10-27; built 2026-10-29). Each card answers four questions at a glance: where is it, when is it heard next,
// how is that room called to vote, what has my team done.
//
// Sources, and nothing else: status / where / next hearing / last action = LIS (the same fields as the bill page);
// the member bar = the served calls (frozen arm C, private War_Room_Calls tab — a call only at |p-.5| >= .31,
// otherwise "can't call"); position and contacts = your team's own entries (#241 / #243). A bill with no served
// calls shows "can't call", never a guess. Grey by default; accent = times / links; amber = carried over;
// red = dead / vetoed. State is small-caps text.
// A state with no vote model (STATE.features.predictions false — PA) gets the same list with the member bar, its key
// and the call-based order hidden: calls are never fetched, every group keeps bill-number order.
// SCOPE (owner 2026-11-01: "follow the switch"): Tracking = your starred bills; Full GA = every bill, in the same
// groups, 50 per group at a time. In Full GA a card shows the position (one bulk read) but not the contact count —
// that would be one request per card; the count is on the bill page.
import { useEffect, useMemo, useState } from "react";
import type { Bill } from "../data/types";
import { warRoomBillPath, linkProps } from "../state/router";
import { PositionTag } from "../components/PositionControl";
import { usePositions, STANCES, STANCE_LABEL, type Stance } from "../state/positions";
import { loadContacts, type ContactsResult } from "../state/contacts";
import { dayKey } from "../data/dates";
import { useScope } from "../state/tracking";
import { OutcomeChip } from "../components/common";
import { SOURCE } from "../config";
import { STATE } from "../states";
import {
  loadCalls, callsFor, groupOf, sortGroup, dateKeyOf, WR_GROUPS, type BillCalls, type CallsLoad, type WrGroup,
} from "../data/warroom";

const shortDate = (key: string) => {
  const [y, m, d] = key.split("-").map(Number);
  return y ? new Date(y, m - 1, d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : key;
};

const PAGE = 50;   // Full GA: cards per group before "Show more" (no group is ever cut silently)

export function WarRoom({ bills, starred, sessionCode }: { bills: Bill[]; starred: Set<string>; sessionCode: string }) {
  const [calls, setCalls] = useState<CallsLoad | undefined>(undefined);
  const [scope] = useScope();
  const all = scope === "full";
  const [shown, setShown] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<Stance | "all">("all");
  const positions = usePositions(sessionCode);
  const predictions = STATE.features.predictions;
  useEffect(() => {
    if (!predictions) return;   // no model for this state: nothing to read, the bar is not drawn
    let alive = true; loadCalls().then((r) => { if (alive) setCalls(r); }); return () => { alive = false; };
  }, [predictions]);

  const today = dayKey(new Date());
  const ours = useMemo(() => bills.filter((b) => (all || starred.has(b.bill))
    && (filter === "all" || positions.byBill.get(b.bill)?.stance === filter)), [bills, starred, all, filter, positions.byBill]);
  const byBill = calls?.status === "ok" ? calls.byBill : null;

  const groups = useMemo(() => {
    const g: Record<WrGroup, { bill: string; calls: BillCalls | null }[]> = { next7: [], later: [], none: [], decided: [] };
    for (const b of ours) g[groupOf(b.outcome, b.upcoming[0]?.date ?? "", today)].push({ bill: b.bill, calls: byBill ? callsFor(byBill, b.bill, sessionCode) : null });
    return (Object.keys(g) as WrGroup[]).reduce((acc, k) => ({ ...acc, [k]: sortGroup(g[k], k) }), g);
  }, [ours, byBill, sessionCode, today]);
  const billOf = useMemo(() => new Map(bills.map((b) => [b.bill, b])), [bills]);

  if (!all && bills.filter((b) => starred.has(b.bill)).length === 0) {
    return <p className="center-msg">No bills tracked yet. Star a bill in Search or Today and it appears here,
      or switch to <b>Full GA</b> to see every bill.</p>;
  }

  // the coming week, day by day: which of your bills are heard (the same next-hearing field the groups use)
  const week = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return dayKey(d); });
  const heardOn = (k: string) => ours.filter((b) => dateKeyOf(b.upcoming[0]?.date) === k).map((b) => b.bill);
  const s = calls?.status === "ok" ? calls.summary : null;
  // the bar key is said once, above the first group whose cards carry a member bar
  const firstBarGroup = !predictions ? undefined : WR_GROUPS.find(({ id }) => id !== "decided" ? groups[id].length > 0 : groups.decided.some((x) => !["signed", "vetoed"].includes(billOf.get(x.bill)!.outcome)))?.id;

  return (
    <div className="wl">
      <div className="wl-head">
        <span className="seg" role="group" aria-label="Filter by your position">
          {(["all", ...STANCES] as const).map((k) => (
            <button key={k} type="button" className={filter === k ? "on" : ""} aria-pressed={filter === k}
              onClick={() => setFilter(k)}>{k === "all" ? "All" : STANCE_LABEL[k]}</button>
          ))}
        </span>
      </div>

      <div className="wl-grp"><span>This week · {all ? "all bills" : "your bills"}</span>
        <span className="n">{(() => { const h = week.reduce((t, k) => t + heardOn(k).length, 0); return `${h} hearing${h === 1 ? "" : "s"}`; })()}</span></div>
      <div className="wl-week">
        {week.map((k) => {
          const [y, m, d] = k.split("-").map(Number);
          const day = new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
          return <div key={k} className="wl-wd"><b>{day}</b>{heardOn(k).map((n) => <span key={n} className="hit">{n}</span>)}</div>;
        })}
      </div>

      {WR_GROUPS.map(({ id, label }) => groups[id].length > 0 && (
        <section key={id}>
          <div className="wl-grp"><span>{label}</span><span className="n">{groups[id].length}</span></div>
          {id === firstBarGroup && <BarKey />}
          <div className="wl-cards">
            {groups[id].slice(0, all ? (shown[id] ?? PAGE) : undefined).map(({ bill, calls: c }) =>
              <Card key={bill} b={billOf.get(bill)!} calls={c} sessionCode={sessionCode} predictions={predictions} contacts={!all} />)}
          </div>
          {all && groups[id].length > (shown[id] ?? PAGE) && (
            <button type="button" className="wl-more" onClick={() => setShown((s) => ({ ...s, [id]: (s[id] ?? PAGE) + PAGE }))}>
              Show {Math.min(PAGE, groups[id].length - (shown[id] ?? PAGE))} more of {(groups[id].length - (shown[id] ?? PAGE)).toLocaleString()}
            </button>
          )}
        </section>
      ))}

      {predictions ? (
      <div className="wl-why">
        <b>Showing.</b> {all ? "Every bill in the session (Full GA), 50 per group at a time." : "Your tracked bills (Tracking)."}
        <br /><br /><b>Order inside each group.</b> Least likely to pass first: most called-yes votes still needed to reach a
        majority, then most called no, then most can't call. A bill that already has enough called yes goes to the
        bottom. Nothing scheduled and Decided keep bill-number order.
        <br /><br /><b>Where each card's facts come from.</b> Status, where it is, next hearing and last action: {SOURCE}.
        Members: the vote model's calls for the room's first vote — yes or no only when the chance is at least
        81 in 100 either way, otherwise can't call.
        {s ? <> In the {s.testYear} replay, calls were right {s.calledRight.toLocaleString()} of {s.called.toLocaleString()};
          {" "}{s.cantCall.toLocaleString()} of {s.ballots.toLocaleString()} votes were can't call.</>
          : <> No calls are served right now, so every member reads can't call.</>}
        {" "}Position and contacts: your team's own entries.
      </div>
      ) : (
      <div className="wl-why">
        <b>Showing.</b> {all ? "Every bill in the session (Full GA), 50 per group at a time." : "Your tracked bills (Tracking)."}
        <br /><br /><b>Order inside each group.</b> Bill-number order.
        <br /><br /><b>Where each card's facts come from.</b> Status, where it is, next hearing and last action: {SOURCE}.
        Position and contacts: your team's own entries.
      </div>
      )}
    </div>
  );
}

function BarKey() {
  return (
    <div className="wl-key">
      <span><span className="sw yes" />called yes</span><span><span className="sw no" />called no</span>
      <span><span className="sw cant" />can't call</span><span><span className="sw tick" />yes votes needed</span>
    </div>
  );
}

function Card({ b, calls, sessionCode, predictions, contacts }: { b: Bill; calls: BillCalls | null; sessionCode: string; predictions: boolean; contacts: boolean }) {
  const next = b.upcoming[0];
  const last = b.history.length ? b.history[b.history.length - 1] : null;
  return (
    <a className="wl-card" {...linkProps(warRoomBillPath(b.bill))}>
      <div className="l1">
        <span><span className="num">{b.bill}</span> <span className="pat">· {b.patron}</span></span>
        <OutcomeChip outcome={b.outcome} bill={b} />
      </div>
      <div className="ttl">{b.title}</div>
      <dl className="kv">
        <dt>Where</dt><dd>{b.lastCommittee || "—"}</dd>
        {next && <><dt>Next</dt><dd className="when">{shortDate(dateKeyOf(next.date)) || next.date}{next.committee ? ` · ${next.committee}` : ""}</dd></>}
        <dt>Last</dt><dd>{last ? `${shortDate(dateKeyOf(last.date)) || last.date} · ${last.action}` : "—"}</dd>
        {predictions && b.outcome !== "signed" && b.outcome !== "vetoed" && <><dt>Members</dt><dd><MemberBar c={calls} /></dd></>}
      </dl>
      <TeamRow bill={b.bill} sessionCode={sessionCode} contacts={contacts} />
    </a>
  );
}

function MemberBar({ c }: { c: BillCalls | null }) {
  if (!c) return <span className="ml"><span>can't call · no member calls for this bill</span></span>;
  const tick = c.ballots ? (100 * c.yesNeeded) / c.ballots : 0;
  return (
    <>
      <span className="ml">
        <span>{c.calledYes} yes · {c.calledNo} no · {c.cantCall} can't call</span>
        <span>needs {c.yesNeeded} of {c.ballots}</span>
      </span>
      <span className="bar" aria-hidden="true">
        {c.calledYes > 0 && <i className="yes" style={{ flex: c.calledYes }} />}
        {c.calledNo > 0 && <i className="no" style={{ flex: c.calledNo }} />}
        {c.cantCall > 0 && <i className="cant" style={{ flex: c.cantCall }} />}
        <span className="need" style={{ left: `${tick}%` }} />
      </span>
    </>
  );
}

// The team's own facts for the bill. An absence is set in words, not as a zero (P27 corollary).
function TeamRow({ bill, sessionCode, contacts: withContacts }: { bill: string; sessionCode: string; contacts: boolean }) {
  const [res, setRes] = useState<ContactsResult | undefined>(undefined);
  useEffect(() => {
    if (!withContacts) return;   // Full GA: no per-card request; the count is on the bill page
    let alive = true; loadContacts(sessionCode, bill).then((r) => { if (alive) setRes(r); }); return () => { alive = false; };
  }, [bill, sessionCode, withContacts]);
  if (!withContacts) return <div className="team"><PositionTag bill={bill} sessionCode={sessionCode} /><span>contacts on the bill page</span></div>;
  const contacts = res?.status === "ok" ? res.contacts : null;
  const lastOn = contacts && contacts.length ? contacts.map((c) => c.occurredOn).sort().slice(-1)[0] : "";
  return (
    <div className="team">
      <PositionTag bill={bill} sessionCode={sessionCode} />
      <span>{contacts === null ? (res ? "contacts unavailable" : "") : contacts.length
        ? `${contacts.length} contact${contacts.length === 1 ? "" : "s"} logged · last ${shortDate(lastOn)}`
        : "no contacts logged"}</span>
    </div>
  );
}
