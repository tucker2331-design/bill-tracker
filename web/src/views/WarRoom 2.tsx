// The War Room — your tracked bills, drilled in. Queue item F1/M4.
//
// SCOPE OF THIS FILE, STATED PLAINLY SO IT IS NOT MISREAD AS FINISHED:
// this is the READ half. Positions, contacts, the whip board and the call sheet all live behind the write
// path (F2, PR #237) and the vote-history join (E1) — neither is wired to the front end yet. What ships here
// is the list that gives every tracked bill a URL, plus the honest statement of what is not built.
//
// It deliberately shows NOTHING it cannot source. No placeholder "0 of 15" whip counts, no invented
// positions: an example that cannot exist teaches the wrong shape (proposal audit check 1).

import type { Bill } from "../data/types";
import { detailPath, linkProps } from "../state/router";

export function WarRoom({ bills, starred }: { bills: Bill[]; starred: Set<string> }) {
  const ours = bills.filter((b) => starred.has(b.bill));

  if (ours.length === 0) {
    return (
      <div>
        <p className="center-msg">
          No bills tracked yet. Star a bill in Search or Today and it appears here.
        </p>
      </div>
    );
  }

  // Soonest meeting first — a bill being heard on Tuesday outranks one with no date. Bills with no upcoming
  // meeting sort last rather than being hidden; "nothing scheduled" is a state you need to see.
  const sorted = [...ours].sort((a, b) => {
    const am = a.upcoming[0]?.date ?? "";
    const bm = b.upcoming[0]?.date ?? "";
    if (am && bm) return am.localeCompare(bm);
    if (am) return -1;
    if (bm) return 1;
    return a.bill.localeCompare(b.bill, undefined, { numeric: true });
  });

  return (
    <div>
      <div className="muted" style={{ marginBottom: 10 }}>
        {sorted.length} bill{sorted.length === 1 ? "" : "s"} tracked · soonest hearing first
      </div>

      <div className="wr-list">
        {sorted.map((b) => {
          const next = b.upcoming[0];
          return (
            <a key={b.bill} className="wr-row" {...linkProps(detailPath("bills", b.bill))}>
              <span className="wr-num">{b.bill}</span>
              <span className="wr-patron">— {b.patron}</span>
              <span className="wr-title">{b.title}</span>
              <span className="wr-where">
                {b.lastCommittee || (b.outcome === "in_progress" ? "Floor" : "—")}
              </span>
              <span className="wr-when">
                {next ? `${next.date}${next.committee ? ` · ${next.committee}` : ""}` : "nothing scheduled"}
              </span>
            </a>
          );
        })}
      </div>

      {/* Say what is missing, in the place where it is missing. A screen that quietly omits the whip board
          reads as "there is no whip board"; this reads as "it is coming and here is what it waits on". */}
      <p className="muted" style={{ marginTop: 18, fontSize: 13 }}>
        Positions, the whip board and contact history are not here yet — they need the write path
        (PR&nbsp;#237) and the per-member vote join. Nothing on this page is a placeholder: every value shown
        is read from the tracker.
      </p>
    </div>
  );
}
