import { useMemo, useState } from "react";
import type { Bill, Outcome, Chamber } from "../data/types";
import { BillBox } from "../components/BillBox";

type Sort = "bill" | "recent";
type Ch = "" | Chamber;
const PAGE_SIZE = 50;
const OUTCOME_FILTERS: { key: Outcome; label: string }[] = [
  { key: "in_progress", label: "In progress" }, { key: "awaiting_governor", label: "To Governor" },
  { key: "signed", label: "Signed" }, { key: "vetoed", label: "Vetoed" },
  { key: "dead", label: "Dead" }, { key: "carried_over", label: "Carried over" },
];

// A bill's ORIGIN chamber is structural — the id prefix (H* = House, S* = Senate). Its CURRENT chamber is
// `bill.chamber`, which flips to the opposite once the bill crosses over. These are DIFFERENT questions, and
// conflating them is the bug the owner hit: the old single "Senate" filter matched `bill.chamber` (current),
// so it surfaced crossed-over HOUSE bills — and with the old 400-row cap, those crowded out every real
// Senate-origin bill. We now filter origin and current independently.
const billOrigin = (b: Bill): Chamber => (b.bill.charAt(0).toUpperCase() === "H" ? "House" : "Senate");

// Faceted search (Hearst): one bar for known-item lookup + stacking filter chips for browse. Filters AND
// across categories; the outcome chips OR within their group (a bill has one outcome).
export function Search({ bills, onOpen }: { bills: Bill[]; onOpen: (b: Bill) => void }) {
  const [q, setQ] = useState("");
  const [originCh, setOriginCh] = useState<Ch>("");   // where the bill STARTED (id prefix)
  const [nowCh, setNowCh] = useState<Ch>("");         // where the bill IS now (bill.chamber)
  const [outcomes, setOutcomes] = useState<Set<Outcome>>(new Set());
  const [crossedOnly, setCrossedOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("bill");
  const [page, setPage] = useState(1);

  const toggleOutcome = (o: Outcome) =>
    setOutcomes((prev) => { const n = new Set(prev); if (n.has(o)) n.delete(o); else n.add(o); return n; });

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const r = bills.filter((b) => {
      if (originCh && billOrigin(b) !== originCh) return false;
      if (nowCh && b.chamber !== nowCh) return false;
      if (outcomes.size && !outcomes.has(b.outcome)) return false;
      if (crossedOnly && !b.crossedOver) return false;
      if (needle) {
        const hay = `${b.bill} ${b.title} ${b.patron} ${b.lastCommittee}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
    return [...r].sort(sort === "bill"
      ? (a, b) => a.bill.localeCompare(b.bill, undefined, { numeric: true })
      : (a, b) => (Date.parse(b.lastAction) || 0) - (Date.parse(a.lastAction) || 0));
  }, [bills, q, originCh, nowCh, outcomes, crossedOnly, sort]);

  // Reset to page 1 whenever the query/filters/sort change, so you're never stranded past the end. Done during
  // render (the idiomatic "adjust state when a prop changes" pattern) rather than in an effect — no extra pass.
  const filterKey = `${q}|${originCh}|${nowCh}|${crossedOnly}|${sort}|${[...outcomes].sort().join(",")}`;
  const [prevKey, setPrevKey] = useState(filterKey);
  if (prevKey !== filterKey) { setPrevKey(filterKey); setPage(1); }

  // Page-turner instead of a hard "first 400" cut — every matching bill is reachable, none silently dropped.
  const totalPages = Math.max(1, Math.ceil(results.length / PAGE_SIZE));
  const pageNow = Math.min(Math.max(1, page), totalPages);
  const pageRows = results.slice((pageNow - 1) * PAGE_SIZE, pageNow * PAGE_SIZE);
  const firstIdx = results.length ? (pageNow - 1) * PAGE_SIZE + 1 : 0;
  const lastIdx = Math.min(pageNow * PAGE_SIZE, results.length);

  const chipBtn = (key: string, on: boolean, label: string, onClick: () => void, title?: string) => (
    <button key={key} className={on ? "on" : ""} onClick={onClick} title={title}>{label}</button>
  );
  const setOrigin = (c: Chamber) => setOriginCh(originCh === c ? "" : c);
  const setNow = (c: Chamber) => setNowCh(nowCh === c ? "" : c);

  return (
    <div>
      <div className="searchbar">
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search bill number, title keyword, or patron…" autoFocus />
      </div>
      <div className="filters">
        {chipBtn("o-h", originCh === "House", "House (origin)", () => setOrigin("House"), "Bills that STARTED in the House — HB/HJ/HR")}
        {chipBtn("o-s", originCh === "Senate", "Senate (origin)", () => setOrigin("Senate"), "Bills that STARTED in the Senate — SB/SJ/SR")}
        <span style={{ width: 8 }} />
        {chipBtn("n-h", nowCh === "House", "House (now)", () => setNow("House"), "Bills CURRENTLY in the House (after any crossover)")}
        {chipBtn("n-s", nowCh === "Senate", "Senate (now)", () => setNow("Senate"), "Bills CURRENTLY in the Senate (after any crossover)")}
        <span style={{ width: 8 }} />
        {chipBtn("crossed", crossedOnly, "Crossed over", () => setCrossedOnly(!crossedOnly), "Bills that reached the opposite chamber")}
        <span style={{ width: 8 }} />
        {OUTCOME_FILTERS.map((f) => chipBtn(f.key, outcomes.has(f.key), f.label, () => toggleOutcome(f.key)))}
        <span className="spacer" style={{ flex: 1 }} />
        {chipBtn("sort-bill", sort === "bill", "Sort: #", () => setSort("bill"))}
        {chipBtn("sort-recent", sort === "recent", "Sort: recent", () => setSort("recent"))}
      </div>
      <div className="muted" style={{ marginBottom: 8 }}>
        {results.length.toLocaleString()} bill(s)
        {results.length > PAGE_SIZE && <> · showing {firstIdx.toLocaleString()}–{lastIdx.toLocaleString()}</>}
      </div>
      <div className="billgrid">
        {pageRows.map((b) => <BillBox key={b.bill} bill={b} onOpen={onOpen} />)}
      </div>
      {results.length === 0 && <p className="center-msg">No bills match. Try the Full GA scope or clear filters.</p>}
      {totalPages > 1 && (
        <div className="pager">
          <button disabled={pageNow <= 1} onClick={() => setPage(pageNow - 1)}>← Prev</button>
          <span className="muted">Page {pageNow.toLocaleString()} of {totalPages.toLocaleString()}</span>
          <button disabled={pageNow >= totalPages} onClick={() => setPage(pageNow + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
