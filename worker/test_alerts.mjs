/** Slack digest tests (worker/alerts.js). Run: node worker/test_alerts.mjs — fetch and D1 are fakes. */
import { runAlerts, changeLines, snapshotOf, digestText, sessionFromHeaderRow, parseCsv } from "./alerts.js";
let pass = 0, fail = 0;
const is = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`}`);
  ok ? pass++ : fail++;
};
const q = (s) => `"${String(s).replace(/"/g, '""')}"`;
const csv = (rows) => rows.map((r) => r.map(q).join(",")).join("\n");

// ---- pure pieces ----
const row = ["HB1515", "In Committee", "2/6/2026", JSON.stringify({ tally: "5-Y 3-N", location: "Rules", date: "2/6/2026" }), JSON.stringify([{ date: "2027-01-20", committee: "Rules" }])];
const snap = snapshotOf(row);
is("snapshot vote text", snap.voteText, "5-Y 3-N in Rules (2/6/2026)");
is("snapshot hearing text", snap.hearingText, "2027-01-20, Rules");
is("no change -> no lines", changeLines(snap, snap), []);
is("status change line", changeLines({ ...snap, status: "Prefiled" }, snap), ["status is now In Committee"]);
is("hearing dropped line", changeLines(snap, { ...snap, hearing: "", hearingText: "" }), ["no hearing scheduled now"]);
is("digest template", digestText([{ bill: "HB1515", lines: ["status is now X"] }], { HB1515: "supporting" }),
   "Bill updates from LIS\n• *HB 1515* (supporting) — status is now X");
is("session found by content", sessionFromHeaderRow(["Bill", "Title", "", JSON.stringify({ universe_count: 3, session_code: "20261" })]), "20261");
is("no payload -> null", sessionFromHeaderRow(["Bill", "Title"]), null);
is("csv parser keeps JSON commas", parseCsv(csv([["a", '{"x":1,"y":"z"}']]))[0][1], '{"x":1,"y":"z"}');

// ---- a fake D1 ----
function fakeDb(positions) {
  const alertState = new Map();
  return {
    alertState,
    prepare(sql) {
      const st = { sql, args: [], bind(...a) { st.args = a; return st; },
        async all() {
          if (sql.includes("FROM positions")) return { results: positions.filter((p) => p.state === st.args[0] && p.session_code === st.args[1]) };
          if (sql.includes("FROM alert_state")) return { results: [...alertState].map(([bill_number, snapshot]) => ({ bill_number, snapshot })) };
          return { results: [] };
        },
        async run() { alertState.set(st.args[1], st.args[2]); } };
      return st;
    },
    async batch(stmts) { for (const s of stmts) await s.run(); },
  };
}

let sheetRows, slackOk = true, headerRow, slackPosts = [];
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (u.startsWith("https://hooks.slack.test")) { slackPosts.push(JSON.parse(init.body).text); return new Response("ok", { status: slackOk ? 200 : 500 }); }
  const p = new URL(u).searchParams;
  const body = p.get("range") ? csv([headerRow]) : csv([["Bill", "Status (LIS)", "Last Action", "Latest Vote (JSON)", "Upcoming (JSON)"], ...sheetRows]);
  return new Response(body, { status: 200, headers: { "content-type": "text/csv" } });
};
const positions = [
  { state: "VA", session_code: "20261", bill_number: "HB1515", stance: "supporting" },
  { state: "VA", session_code: "20251", bill_number: "HB1", stance: "opposing" },   // an OLD session: must be ignored
];
const env = { DB: fakeDb(positions), SLACK_WEBHOOK_URL: "https://hooks.slack.test/x", SPREADSHEET_ID: "S", BILL_TRACKER_STATE: "VA" };
headerRow = ["Bill", "Title", JSON.stringify({ universe_count: 1, session_code: "20261" })];
sheetRows = [row];

let r = await runAlerts(env);
is("first run seeds silently", [r.alerted, slackPosts.length, env.DB.alertState.has("HB1515")], [0, 0, true]);
is("old-session position ignored", r.watched, 1);
r = await runAlerts(env);
is("nothing changed -> nothing sent", [r.alerted, slackPosts.length], [0, 0]);
sheetRows = [["HB1515", "Reported from Rules", "1/20/2027", row[3], "[]"]];
r = await runAlerts(env);
is("a change sends ONE digest", [r.alerted, slackPosts.length], [1, 1]);
is("digest text", slackPosts[0], "Bill updates from LIS\n• *HB 1515* (supporting) — status is now Reported from Rules · no hearing scheduled now");
sheetRows = [["HB1515", "Passed House", "1/25/2027", row[3], "[]"]];
slackOk = false;
let threw = false; try { await runAlerts(env); } catch { threw = true; }
is("Slack refusal throws", threw, true);
is("…and the snapshot is NOT advanced (retried next cycle)", JSON.parse(env.DB.alertState.get("HB1515")).status, "Reported from Rules");
slackOk = true;
r = await runAlerts(env);
is("retry succeeds next cycle", [r.alerted, JSON.parse(env.DB.alertState.get("HB1515")).status], [1, "Passed House"]);
headerRow = ["Bill", "Title"];
threw = false; try { await runAlerts(env); } catch { threw = true; }
is("no session in the sheet -> refuses to run", threw, true);
is("not configured -> skipped", (await runAlerts({ DB: env.DB })).skipped, "not_configured");
is("bad state config -> skipped", (await runAlerts({ ...env, BILL_TRACKER_STATE: "va" })).skipped, "not_configured");

console.log(`\n${fail ? `${fail} FAILED` : "ALL PASS"} (${pass} ok)`);
process.exit(fail ? 1 : 0);
