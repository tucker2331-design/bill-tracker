/** Cron tick tests (worker/ticks.js). Run: node worker/test_ticks.mjs — fetch is a fake, no network. */
import { dispatchRequest, offerTicks, TICK_WORKFLOWS, dueWorkflows, TICK_GATE_HEADER, STALE_HOURS } from "./ticks.js";
let pass = 0, fail = 0;
const is = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`}`);
  ok ? pass++ : fail++;
};

const r = dispatchRequest("calendar_worker.yml", "T");
is("dispatch URL", r.url, "https://api.github.com/repos/tucker2331-design/bill-tracker/actions/workflows/calendar_worker.yml/dispatches");
is("POST", r.init.method, "POST");
// the gate depends on this exact input: without tick=scheduled the run would be a human "Run Now" (ungated)
is("body carries the REQUIRED tick=scheduled input on main", JSON.parse(r.init.body), { ref: "main", inputs: { tick: "scheduled" } });
is("token in the Authorization header", r.init.headers.Authorization, "Bearer T");
is("both Virginia workers, nothing else", TICK_WORKFLOWS, ["calendar_worker.yml", "bill_tracker.yml"]);

const calls = [];
const ok204 = async (url, init) => { calls.push([url, JSON.parse(init.body).inputs.tick]); return { status: 204, text: async () => "" }; };
const errs = [], logs = [];
const origErr = console.error, origLog = console.log;
console.error = (...a) => errs.push(a.join(" ")); console.log = (...a) => logs.push(a.join(" "));
const none = await offerTicks({ BILL_TRACKER_STATE: "VA" }, ok204);
const good = await offerTicks({ BILL_TRACKER_STATE: "VA", GH_DISPATCH_TOKEN: "T" }, ok204);
const paCalls = calls.length;
const pa = await offerTicks({ BILL_TRACKER_STATE: "PA", GH_DISPATCH_TOKEN: "T" }, ok204);
const bad = await offerTicks({ BILL_TRACKER_STATE: "VA", GH_DISPATCH_TOKEN: "T" }, async (url) =>
  url.includes("bill_tracker") ? { status: 422, text: async () => "Workflow does not have 'workflow_dispatch' trigger" } : { status: 204, text: async () => "" });
const thrown = await offerTicks({ BILL_TRACKER_STATE: "VA", GH_DISPATCH_TOKEN: "T" }, async () => { throw new Error("network down"); });
console.error = origErr; console.log = origLog;

is("no token -> nothing dispatched, said so", [none.configured, none.dispatched, logs.some((l) => l.includes("not configured"))], [false, [], true]);
is("token -> both dispatched, each with tick=scheduled", [good.dispatched, calls.map((c) => c[1])], [TICK_WORKFLOWS, ["scheduled", "scheduled"]]);
is("PA Worker with a token: starts nothing, says the token is misplaced", [pa.dispatched, calls.length === paCalls, errs.some((e) => e.startsWith("ticks_misplaced"))], [[], true, true]);
is("a 422 is a named failure, the other still dispatched", [bad.dispatched, bad.failed.length, bad.failed[0].startsWith("bill_tracker.yml: HTTP 422")], [["calendar_worker.yml"], 1, true]);
is("a network error is a named failure for each workflow", thrown.failed.length, 2);
is("failures are logged, never swallowed", errs.filter((e) => e.startsWith("ticks_failed")).length, 2);

// ── the tick gate (going private A1): start a GitHub job only when the worker's own gate says one is due ──
const NOW = Date.parse("2026-11-20T15:07:00Z");
// Pinned as LITERALS (Gemini #279): the header is a contract the Python workers write (cadence.TICK_GATE_HEADER, pinned
// the same way in cadence_test.py). A rename must break a test on both sides, never pass silently on one.
const H = ["Workflow", "NextDueUTC", "WrittenUTC", "Reason"];
is("the JS header is the pinned contract", TICK_GATE_HEADER, H);
const row = (wf, next, written = "2026-11-20T15:00:00Z") => [wf, next, written, "reason"];
const both = (a, b) => [H, row("calendar_worker.yml", a), row("bill_tracker.yml", b)];
const d1 = dueWorkflows(both("2026-11-21T14:55:00Z", "2026-11-20T15:05:00Z"), NOW);
is("calendar not due yet, bill due -> only the bill job", [d1.due.map((x) => x.wf), d1.skipped.map((x) => x.wf), d1.gate],
   [["bill_tracker.yml"], ["calendar_worker.yml"], "ok"]);
is("offered up to a minute early (tick on the quarter hour)",
   dueWorkflows(both("2026-11-20T15:07:50Z", "2026-11-20T15:08:00Z"), NOW).due.map((x) => x.wf), TICK_WORKFLOWS);
// every doubt -> offer (the behaviour before the gate)
for (const [name, rows] of [["unread (null)", null], ["empty", []], ["wrong header (gviz served another tab)", [["Date", "Time"], ["x", "y"]]]]) {
  const p = dueWorkflows(rows, NOW);
  is(`${name} -> every job offered, gate unavailable`, [p.due.map((x) => x.wf), p.gate], [TICK_WORKFLOWS, "unavailable"]);
}
is("a missing row -> that job is offered", dueWorkflows([H, row("bill_tracker.yml", "2026-11-21T00:00:00Z")], NOW).due.map((x) => x.wf), ["calendar_worker.yml"]);
is("an unparseable time -> offered", dueWorkflows([H, row("calendar_worker.yml", "soon"), row("bill_tracker.yml", "2026-11-21T00:00:00Z")], NOW).due.map((x) => x.wf), ["calendar_worker.yml"]);
const old = new Date(NOW - (STALE_HOURS + 1) * 3.6e6).toISOString();
is("a stale row (writer broken) -> offered even if its next-due is far off",
   dueWorkflows([H, row("calendar_worker.yml", "2026-11-22T00:00:00Z", old), row("bill_tracker.yml", "2026-11-22T00:00:00Z")], NOW).due.map((x) => x.wf), ["calendar_worker.yml"]);

// through offerTicks: the gate decides, a gate read error falls back to offering every job (and is logged)
const gcalls = [];
const okg = async (url) => { gcalls.push(url.includes("calendar") ? "calendar" : "bill"); return { status: 204, text: async () => "" }; };
const glogs = [], gerrs = [];
console.log = (...a) => glogs.push(a.join(" ")); console.error = (...a) => gerrs.push(a.join(" "));
const gated = await offerTicks({ BILL_TRACKER_STATE: "VA", GH_DISPATCH_TOKEN: "T" }, okg,
  async () => both("2099-01-01T00:00:00Z", "2099-01-01T00:00:00Z").map((r, i) => (i ? [r[0], r[1], new Date().toISOString(), r[3]] : r)));
const fallback = await offerTicks({ BILL_TRACKER_STATE: "VA", GH_DISPATCH_TOKEN: "T" }, okg, async () => { throw new Error("HTTP 500"); });
console.log = origLog; console.error = origErr;
is("nothing due -> no GitHub job started", [gated.dispatched, gated.skipped, gated.gate], [[], TICK_WORKFLOWS, "ok"]);
is("gate read error -> both offered, gate unavailable", [fallback.dispatched, fallback.gate], [TICK_WORKFLOWS, "unavailable"]);
is("the gate read error is logged, never swallowed", gerrs.some((e) => e.startsWith("tick_gate_unreadable")), true);
is("each skipped job is logged with its next-due time", glogs.filter((l) => l.includes("not offered (next due")).length, 2);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
