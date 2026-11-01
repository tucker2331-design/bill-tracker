// What's new — one line per bill: `SB509 (In the House) Referred to Transportation` (owner 2026-11-01).
// Reads the `Action_Where` tab (action_where.py): per bill, one code per history row saying WHERE that action
// happened (H / S / G = the Governor / "-" unknown), derived by each state's job from STRUCTURAL fields, plus an
// optional short line per row (PA: built from the export's verb + committee + tally). Pure and dependency-free so
// the bare-node golden (data/__tests__/action_where.regression.mjs) runs the real code.

export const ACTION_WHERE_HEADER = ["Bill", "Where", "Short"];
export interface BillWhere { where: string; short: string[] | null }
export type WhereLoad = { status: "ok"; byBill: Map<string, BillWhere>; unreadable: number }
  | { status: "unavailable"; reason: "no_tab" | "bad_header" | "empty" };

export function parseWhereGrid(grid: string[][]): WhereLoad {
  const rows = grid.filter((r) => r.some((c) => c.trim() !== ""));
  if (!rows.length) return { status: "unavailable", reason: "empty" };
  if (rows[0].slice(0, 3).map((c) => c.trim()).join("|") !== ACTION_WHERE_HEADER.join("|")) return { status: "unavailable", reason: "bad_header" };
  const byBill = new Map<string, BillWhere>();
  let unreadable = 0;
  for (const r of rows.slice(1)) {
    const bill = (r[0] ?? "").trim(), where = (r[1] ?? "").trim(), raw = (r[2] ?? "").trim();
    let short: string[] | null = null;
    if (raw) {
      try {
        const v = JSON.parse(raw);
        short = Array.isArray(v) && v.length === where.length ? v.map(String) : null;
        if (!short) unreadable++;              // counted: a short list that does not line up is not used
      } catch { unreadable++; }                // counted: the source's own text is shown instead
    }
    if (bill) byBill.set(bill, { where, short });
  }
  return byBill.size ? { status: "ok", byBill, unreadable } : { status: "unavailable", reason: "empty" };
}

export const WHERE_LABEL: Record<string, string> = { H: "In the House", S: "In the Senate", G: "With the Governor" };

/** Display only: a source line in sentence case — an all-capitals line is lowered after its first letter;
 *  otherwise only the first letter is raised. Nothing is decided from the text. */
export function sentenceCase(s: string): string {
  const t = s.trim();
  if (!t) return t;
  return t === t.toUpperCase() && /[A-Z]/.test(t) ? t[0] + t.slice(1).toLowerCase() : t[0].toUpperCase() + t.slice(1);
}

export interface FeedLineIn { bill: string; idx: number; action: string; n: number }   // n = the bill's history length
export interface FeedLine { bill: string; where: string; text: string; action: string; others: number }

/**
 * One line per bill for a day: the bill's LATEST action that day (highest history index), with where it happened.
 * `stripCode` removes a source's fixed-position code field from its text (VA: LIS's "H "/"S " chamber column);
 * a state's own short line, when present, replaces the source text.
 */
export function feedLines(items: FeedLineIn[], where: Map<string, BillWhere> | null, stripCode: RegExp | null): FeedLine[] {
  const latest = new Map<string, FeedLineIn>(), count = new Map<string, number>();
  for (const it of items) {
    count.set(it.bill, (count.get(it.bill) ?? 0) + 1);
    const cur = latest.get(it.bill);
    if (!cur || it.idx > cur.idx) latest.set(it.bill, it);
  }
  const out: FeedLine[] = [];
  for (const it of latest.values()) {
    const w = where?.get(it.bill);
    // the codes must describe THIS history: a length mismatch means a different snapshot — not used (Codex #260)
    const same = !!w && w.where.length === it.n;
    const code = same ? w!.where[it.idx] : "";
    const own = same ? w!.short?.[it.idx] : undefined;
    const text = own ?? (stripCode ? it.action.replace(stripCode, "") : it.action);
    out.push({ bill: it.bill, where: WHERE_LABEL[code] ?? "", text: sentenceCase(text), action: it.action,
      others: (count.get(it.bill) ?? 1) - 1 });
  }
  return out;
}
