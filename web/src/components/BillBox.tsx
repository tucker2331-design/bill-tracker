import type { Bill } from "../data/types";
import { OutcomeChip, Star } from "./common";

// The ONE bill component reused in every view (search, timeline drill-down, feed targets).
export function BillBox({ bill, onOpen }: { bill: Bill; onOpen: (b: Bill) => void }) {
  return (
    <div className={`billbox ${bill.chamber === "Senate" ? "senate" : "house"}`} onClick={() => onOpen(bill)} role="button" tabIndex={0}
      onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen(bill); } }}>
      <Star id={bill.bill} />
      <div style={{ minWidth: 0 }}>
        <div className="num">{bill.bill}</div>
        <div className="cat" title={bill.title}>{bill.title}</div>
      </div>
      <div className="meta">
        {bill.referrals > 1 && <span className="chip referral">{ordinal(bill.referrals)} ref</span>}
        <OutcomeChip outcome={bill.outcome} />
      </div>
    </div>
  );
}

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
