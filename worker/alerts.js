/**
 * Slack alerts — free (owner, 2026-09-28: "the email thing we have figured out with slack instead to keep it free").
 *
 * A Cron Trigger (wrangler.toml [triggers]) runs `runAlerts` every 15 minutes. For every bill the team has a
 * position on (D1 `positions` — Watching counts, it IS the tracking tier), it reads four structural cells from the
 * Bill_Tracker tab (LIS status, last-action date, latest vote, next hearing), compares them with what it saw last
 * time (D1 `alert_state`, migration 0003), and posts ONE digest to a Slack channel through an incoming webhook
 * (the `SLACK_WEBHOOK_URL` secret). Nothing is sent when nothing changed.
 *
 * Rules this file keeps:
 *   - Every line is one fixed template with substituted values (P25) — no prose written per bill.
 *   - A bill seen for the FIRST time is recorded silently. Otherwise adding a bill (or the first deploy) would
 *     fire an alert for everything at once, and a channel that cries wolf gets muted.
 *   - The snapshot is saved only AFTER Slack accepts the post. A failed post is retried next cycle rather than
 *     lost; a failure is logged, never swallowed.
 *   - Reads the sheet through the same token path as /api/sheet, and only the columns it needs (small, cheap).
 */
import { gvizUrl, serviceToken } from "./sheets.js";

const TAB = "Bill_Tracker";
// Column letters in Bill_Tracker (bill_tracker.BILL_TRACKER_HEADER): A Bill, C Status (LIS), K Last Action,
// L Latest Vote (JSON), M Upcoming (JSON). A header check below refuses to run if these ever move.
const SELECT = "select A,C,K,L,M";
const EXPECTED_HEADER = ["Bill", "Status (LIS)", "Last Action", "Latest Vote (JSON)", "Upcoming (JSON)"];

/** Minimal RFC 4180 parser (gviz quotes every field; JSON cells contain commas and doubled quotes). */
export function parseCsv(text) {
  const rows = []; let row = []; let f = ""; let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(f); f = ""; rows.push(row); row = []; }
    else f += c;
  }
  if (f.length || row.length) { row.push(f); rows.push(row); }
  return rows;
}

const parseJson = (s, fallback) => { try { return s ? JSON.parse(s) : fallback; } catch { return fallback; } };

/** The four facts we alert on, reduced to plain comparable values. */
export function snapshotOf(row) {
  const vote = parseJson(row[3], {}) || {};
  const next = (parseJson(row[4], []) || [])[0] || {};
  return {
    status: (row[1] || "").trim(),
    lastAction: (row[2] || "").trim(),
    vote: vote.tally ? `${vote.tally}|${vote.location || ""}|${vote.date || ""}` : "",
    voteText: vote.tally ? `${vote.tally}${vote.location ? ` in ${vote.location}` : ""}${vote.date ? ` (${vote.date})` : ""}` : "",
    hearing: next.date ? `${next.date}|${next.committee || ""}` : "",
    hearingText: next.date ? `${next.date}${next.committee ? `, ${next.committee}` : ""}` : "",
  };
}

/** Template lines for what changed between two snapshots of one bill. */
export function changeLines(prev, cur) {
  const out = [];
  if (cur.status && cur.status !== prev.status) out.push(`status is now ${cur.status}`);
  if (cur.vote && cur.vote !== prev.vote) out.push(`vote: ${cur.voteText}`);
  if (cur.hearing && cur.hearing !== prev.hearing) out.push(`hearing: ${cur.hearingText}`);
  if (!cur.hearing && prev.hearing) out.push("no hearing scheduled now");
  return out;
}

/** "HB1515" -> "HB 1515" for reading in Slack. */
const pretty = (b) => b.replace(/^([A-Z]+)(\d+)$/, "$1 $2");

export function digestText(changes, stanceOf) {
  const lines = changes.map(({ bill, lines }) =>
    `• *${pretty(bill)}*${stanceOf[bill] ? ` (${stanceOf[bill]})` : ""} — ${lines.join(" · ")}`);
  return `Bill updates from LIS\n${lines.join("\n")}`;
}

/**
 * The session the Bill_Tracker tab currently holds, read from its own completeness payload (the row-1 cell that
 * parses as JSON with `session_code`) -- found by CONTENT, as the front end does, so a cell move cannot break it.
 * Returns null when not found; the caller then refuses to run rather than mix sessions (HB1 of 2025 is not HB1
 * of 2026).
 */
export function sessionFromHeaderRow(cells) {
  for (const c of cells || []) {
    if (!c || !c.includes("session_code")) continue;
    const obj = parseJson(c, null);
    if (obj && typeof obj.session_code === "string" && obj.session_code) return obj.session_code;
  }
  return null;
}

/** One cron run. Returns a summary object (also logged) so a test or a manual trigger can see what happened. */
export async function runAlerts(env, now = new Date()) {
  // The Bill_Tracker tab holds ONE state's bills; which one is config (Standard #6), never assumed here.
  const state = env.BILL_TRACKER_STATE;
  if (!env.DB || !env.SLACK_WEBHOOK_URL || !env.SPREADSHEET_ID || !/^[A-Z]{2}$/.test(state || "")) {
    const why = { db: !!env.DB, slack: !!env.SLACK_WEBHOOK_URL, sheet: !!env.SPREADSHEET_ID, state: state || null };
    console.log("alerts: not configured, skipped", JSON.stringify(why));
    return { skipped: "not_configured", ...why };
  }
  const token = await serviceToken(env);
  const auth = token ? { headers: { Authorization: `Bearer ${token}` } } : {};
  const head = await fetch(gvizUrl(env.SPREADSHEET_ID, { tab: TAB, range: "A1:AZ1", headers: "0" }), auth);
  if (!head.ok || !/text\/csv/i.test(head.headers.get("content-type") || "")) {
    throw new Error(`alerts: could not read the Bill_Tracker header row (HTTP ${head.status})`);
  }
  const session = sessionFromHeaderRow(parseCsv(await head.text())[0]);
  if (!session) throw new Error("alerts: Bill_Tracker carries no session_code — refusing to mix sessions");

  const { results: pos } = await env.DB.prepare(
    "SELECT bill_number, stance FROM positions WHERE state = ? AND session_code = ?").bind(state, session).all();
  if (!pos || pos.length === 0) return { skipped: "no_positions" };
  const stanceOf = Object.fromEntries(pos.map((p) => [p.bill_number, p.stance]));
  const bills = [...new Set(pos.map((p) => p.bill_number).filter((b) => /^[A-Z]+\d+$/.test(b)))];

  // Read only the watched rows, in chunks so the query stays short.
  const rows = new Map();
  for (let i = 0; i < bills.length; i += 40) {
    const chunk = bills.slice(i, i + 40);
    const tq = `${SELECT} where ${chunk.map((b) => `A = '${b}'`).join(" or ")}`;
    const res = await fetch(gvizUrl(env.SPREADSHEET_ID, { tab: TAB, tq }), auth);
    const type = res.headers.get("content-type") || "";
    if (!res.ok || !/text\/csv/i.test(type)) throw new Error(`alerts: sheet read failed (HTTP ${res.status}, ${type})`);
    const grid = parseCsv(await res.text());
    const header = (grid[0] || []).map((h) => h.trim());
    if (EXPECTED_HEADER.some((h, j) => header[j] !== h)) {
      throw new Error(`alerts: Bill_Tracker columns moved (got ${JSON.stringify(header)}) — refusing to guess`);
    }
    for (const r of grid.slice(1)) if (r[0]) rows.set(r[0].trim(), snapshotOf(r));
  }

  const { results: seen } = await env.DB.prepare("SELECT bill_number, snapshot FROM alert_state WHERE state = ?").bind(state).all();
  const prevOf = Object.fromEntries((seen || []).map((s) => [s.bill_number, parseJson(s.snapshot, null)]));

  const changes = [];
  for (const [bill, cur] of rows) {
    const prev = prevOf[bill];
    if (!prev) continue;                                   // first sighting: record silently (see header)
    const lines = changeLines(prev, cur);
    if (lines.length) changes.push({ bill, lines });
  }

  if (changes.length) {
    const post = await fetch(env.SLACK_WEBHOOK_URL, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ text: digestText(changes, stanceOf) }),
    });
    // Do NOT save the snapshot if Slack refused: next cycle sees the same change and tries again.
    if (!post.ok) throw new Error(`alerts: Slack webhook HTTP ${post.status}`);
  }

  const stamp = now.toISOString();
  const stmts = [...rows].map(([bill, cur]) => env.DB.prepare(
    `INSERT INTO alert_state (state, bill_number, snapshot, updated_at) VALUES (?1, ?2, ?3, ?4)
     ON CONFLICT(state, bill_number) DO UPDATE SET snapshot = ?3, updated_at = ?4`,
  ).bind(state, bill, JSON.stringify(cur), stamp));
  if (stmts.length) await env.DB.batch(stmts);

  const summary = { session, watched: bills.length, found: rows.size, alerted: changes.length, missing: bills.length - rows.size };
  console.log("alerts:", JSON.stringify(summary));
  return summary;
}
