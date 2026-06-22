import { useMemo, useState } from "react";
import type { Bill, Outcome } from "../data/types";
import { BillBox } from "../components/BillBox";

type Sort = "bill" | "recent";
const OUTCOME_FILTERS: { key: Outcome; label: string }[] = [
  { key: "in_progress", label: "In progress" }, { key: "awaiting_governor", label: "To Governor" },
  { key: "signed", label: "Signed" }, { key: "vetoed", label: "Vetoed" },
  { key: "dead", label: "Dead" }, { key: "carried_over", label: "Carried over" },
];

// Faceted search (Hearst): one bar for known-item lookup + stacking filter chips for browse.
export function Search({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const [q, setQ] = useState("");
  const [chamber, setChamber] = useState<"" | "House" | "Senate">("");
  const [outcomes, setOutcomes] = useState<Set<Outcome>>(new Set());
  const [crossedOnly, setCrossedOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("bill");

  const toggleOutcome = (o: Outcome) =>
    setOutcomes((prev) => { const n = new Set(prev); n.has(o) ? n.delete(o) : n.add(o); return n; });

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let r = bills.filter((b) => {
      if (chamber && b.chamber !== chamber) return false;
      if (outcomes.size && !outcomes.has(b.outcome)) return false;
      if (crossedOnly && !b.crossedOver) return false;
      if (needle) {
        const hay = `${b.bill} ${b.title} ${b.patron} ${b.lastCommittee}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
    r = [...r].sort(sort === "bill"
      ? (a, b) => a.bill.localeCompare(b.bill, undefined, { numeric: true })
      : (a, b) => (Date.parse(b.lastAction) || 0) - (Date.parse(a.lastAction) || 0));
    return r;
  }, [bills, q, chamber, outcomes, crossedOnly, sort]);

  const chipBtn = (key: string, on: boolean, label: string, onClick: () => void) => (
    <button key={key} className={on ? "on" : ""} onClick={onClick}>{label}</button>
  );

  return (
    <div>
      <div className="searchbar">
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search bill number, title keyword, or patron…" autoFocus />
      </div>
      <div className="filters">
        {chipBtn("house", chamber === "House", "House", () => setChamber(chamber === "House" ? "" : "House"))}
        {chipBtn("senate", chamber === "Senate", "Senate", () => setChamber(chamber === "Senate" ? "" : "Senate"))}
        {chipBtn("crossed", crossedOnly, "Crossed over", () => setCrossedOnly(!crossedOnly))}
        <span style={{ width: 8 }} />
        {OUTCOME_FILTERS.map((f) => chipBtn(f.key, outcomes.has(f.key), f.label, () => toggleOutcome(f.key)))}
        <span className="spacer" style={{ flex: 1 }} />
        {chipBtn("sort-bill", sort === "bill", "Sort: #", () => setSort("bill"))}
        {chipBtn("sort-recent", sort === "recent", "Sort: recent", () => setSort("recent"))}
      </div>
      <div className="muted" style={{ marginBottom: 8 }}>{results.length.toLocaleString()} bill(s)</div>
      <div className="billgrid">
        {results.slice(0, 400).map((b) => <BillBox key={b.bill} bill={b} onOpen={onOpen} />)}
      </div>
      {results.length > 400 && <p className="muted" style={{ marginTop: 12 }}>Showing first 400 — refine your search.</p>}
      {results.length === 0 && <p className="center-msg">No bills match. Try the Full GA scope or clear filters.</p>}
    </div>
  );
}
