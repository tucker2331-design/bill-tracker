// Committee roster rules (PA War Room) — reading the `Committee_Roster` tab that pa_bill_tracker.py writes from PA's
// committee-assignments RSS (states/pa_roster.py). Pure and dependency-free so the bare-node golden
// (data/__tests__/roster.regression.mjs) runs the real code.
//
// The lookup key is the bill's own `lastCommittee` ("House EDUCATION"), which the backend's committee_key produces
// for every roster row, so the join here is exact string equality — no matching logic lives in the browser.

export const ROSTER_HEADER = ["Chamber", "CommitteeKey", "Committee", "MemberId", "Member", "Party", "District", "Role"];

export interface RosterSeat { memberId: string; member: string; party: string; district: string; role: string }
export interface RosterCommittee { key: string; chamber: string; name: string; seats: RosterSeat[] }
export type RosterLoad =
  | { status: "ok"; byKey: Map<string, RosterCommittee>; unplaced: number }
  | { status: "unavailable"; reason: "no_tab" | "bad_header" | "empty" };

export function parseRosterGrid(grid: string[][]): RosterLoad {
  const rows = grid.filter((r) => r.some((c) => c.trim() !== ""));
  if (!rows.length) return { status: "unavailable", reason: "empty" };
  const head = rows[0].slice(0, ROSTER_HEADER.length).map((c) => c.trim());
  if (head.join("|") !== ROSTER_HEADER.join("|")) return { status: "unavailable", reason: "bad_header" };
  const byKey = new Map<string, RosterCommittee>();
  let unplaced = 0;
  for (const r of rows.slice(1)) {
    const [chamber, key, name, memberId, member, party, district, role] = ROSTER_HEADER.map((_, i) => (r[i] ?? "").trim());
    if (!key) { unplaced++; continue; }   // counted and shown on the page; the backend never writes one (golden-checked)
    let c = byKey.get(key);
    if (!c) { c = { key, chamber, name, seats: [] }; byKey.set(key, c); }
    c.seats.push({ memberId, member, party, district, role });
  }
  return byKey.size ? { status: "ok", byKey, unplaced } : { status: "unavailable", reason: "empty" };
}

/** The roster for a bill's current committee, or null when the bill names none or the roster has no such room. */
export function rosterFor(byKey: Map<string, RosterCommittee>, lastCommittee: string): RosterCommittee | null {
  return lastCommittee ? byKey.get(lastCommittee) ?? null : null;
}

/** "26 members · 13 R, 13 D" — the party split, largest first, ties in letter order. */
export function partySplit(seats: RosterSeat[]): string {
  const n = new Map<string, number>();
  for (const s of seats) if (s.party) n.set(s.party, (n.get(s.party) ?? 0) + 1);
  return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([p, k]) => `${k} ${p}`).join(", ");
}
