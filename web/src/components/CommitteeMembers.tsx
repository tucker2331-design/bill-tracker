// The bill's current committee and who sits on it — the War Room bill page's member list for a state with no vote
// model (PA). Facts only, from the source's committee-assignments feed: name, party, district, and the role the
// source gives (Chair / Vice Chair / Secretary). No call, no chance, no order by likely vote.
import { useEffect, useState } from "react";
import { loadRoster, rosterFor, partySplit, type RosterLoad } from "../data/roster";
import { SOURCE } from "../config";

export function CommitteeMembers({ lastCommittee, chamber }: { lastCommittee: string; chamber: string }) {
  const [res, setRes] = useState<RosterLoad | undefined>(undefined);
  useEffect(() => { let alive = true; loadRoster().then((r) => { if (alive) setRes(r); }); return () => { alive = false; }; }, []);
  if (!lastCommittee) {
    return <div className="metarow"><span className="k">Committee</span>
      <span className="muted">{chamber ? `${chamber} · ` : ""}no committee yet</span></div>;
  }
  if (!res) return null;
  if (res.status !== "ok") {
    return <div className="metarow"><span className="k">Committee</span>
      <span className="muted">{lastCommittee} · member list unavailable right now</span></div>;
  }
  const c = rosterFor(res.byKey, lastCommittee);
  if (!c) {
    return <div className="metarow"><span className="k">Committee</span>
      <span className="muted">{lastCommittee} · {SOURCE} publishes no member list for this committee</span></div>;
  }
  const officers = c.seats.filter((s) => s.role), members = c.seats.filter((s) => !s.role);
  return (
    <div className="mc">
      <h3 className="h" style={{ marginTop: 16 }}>Committee · {c.chamber} {c.name}</h3>
      <p className="mc-sum">{c.seats.length} members{partySplit(c.seats) ? ` · ${partySplit(c.seats)}` : ""}</p>
      {([["Officers", officers], ["Members", members]] as const).map(([label, list]) => list.length > 0 && (
        <div key={label}>
          <div className="mc-sub">{label} · {list.length}</div>
          {list.map((s) => (
            <div key={`${s.memberId}-${s.role}`} className="mc-m mc-row">
              <span className="mc-who">{s.member} <span className="muted">{s.party}{s.district ? ` · district ${s.district}` : ""}</span></span>
              {s.role && <span className="mc-call on">{s.role}</span>}
            </div>
          ))}
        </div>
      ))}
      <p className="mc-foot">Members and roles: {SOURCE}'s committee assignments.
        {res.unplaced > 0 && <> {res.unplaced} roster row{res.unplaced === 1 ? "" : "s"} named no committee and could not be placed.</>}</p>
    </div>
  );
}
