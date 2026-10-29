// Each member's call with its evidence (P23), on the bill page — the member list of the approved bill-level War
// Room page. A call is the frozen model's (yes / no only when the chance is at least 81 in 100 either way); the
// evidence is the model's OWN inputs for that member, measured before the vote, as k-of-n (P26). Every line is
// one fixed template over those fields (P25): no sentence is written per member.
import { useEffect, useState } from "react";
import { loadCalls, callsFor, type BillCalls, type CallsLoad, type MemberCall } from "../data/warroom";

const EVIDENCE: [string, string][] = [
  ["mpat", "this patron's bills"], ["mroom", "this room"], ["sim", "similar bills"], ["msubj", "this subject"],
];
const CALL_LABEL = { yes: "yes", no: "no", cant_call: "can't call" } as const;

export function MemberCalls({ bill, sessionCode }: { bill: string; sessionCode: string }) {
  const [res, setRes] = useState<CallsLoad | undefined>(undefined);
  useEffect(() => { let alive = true; loadCalls().then((r) => { if (alive) setRes(r); }); return () => { alive = false; }; }, []);
  if (!res) return null;
  const c: BillCalls | null = res.status === "ok" ? callsFor(res.byBill, bill, sessionCode) : null;
  if (!c) {
    return (
      <div className="metarow"><span className="k">Members</span>
        <span className="muted">can't call · no member calls for this bill</span></div>
    );
  }
  const called = c.members.filter((m) => m.call !== "cant_call"), cant = c.members.filter((m) => m.call === "cant_call");
  const s = res.status === "ok" ? res.summary : null;
  return (
    <div className="mc">
      <h3 className="h" style={{ marginTop: 16 }}>Members · {c.room}</h3>
      <p className="mc-sum">{c.calledYes} yes · {c.calledNo} no · {c.cantCall} can't call · needs {c.yesNeeded} of {c.ballots}
        {c.voteDate && <> · first vote {c.voteDate}</>}</p>
      {[["Called", called], ["Can't call", cant]].map(([label, list]) => (list as MemberCall[]).length > 0 && (
        <div key={label as string}>
          <div className="mc-sub">{label as string} · {(list as MemberCall[]).length}</div>
          {(list as MemberCall[]).map((m) => <Member key={m.who} m={m} />)}
        </div>
      ))}
      {s && <p className="mc-foot">{s.mode === "replay" ? `${s.testYear} replay: ` : ""}calls were right {s.calledRight.toLocaleString()} of
        {" "}{s.called.toLocaleString()}; {s.cantCall.toLocaleString()} of {s.ballots.toLocaleString()} votes were can't call.</p>}
    </div>
  );
}

function Member({ m }: { m: MemberCall }) {
  return (
    <details className="mc-m">
      <summary>
        <span className="mc-who">{m.who} <span className="muted">{m.party}</span></span>
        <span className={`mc-call${m.call === "cant_call" ? "" : " on"}`}>{CALL_LABEL[m.call]}</span>
      </summary>
      <div className="mc-ev">
        <div><span>chance of a yes</span><b>{Math.round(m.p * 100)} in 100</b></div>
        {m.actual && <div><span>recorded vote</span><b>{m.actual}</b></div>}
        {EVIDENCE.map(([k, label]) => {
          const [yes, of] = Array.isArray(m.ev[k]) ? m.ev[k] : [0, 0];   // malformed evidence reads as none, never a crash (Gemini #250)
          return <div key={k}><span>{label}</span><b>{of ? `yes on ${yes} of ${of}` : "none before"}</b></div>;
        })}
      </div>
    </details>
  );
}
