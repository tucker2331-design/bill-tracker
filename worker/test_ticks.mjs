/** Cron tick tests (worker/ticks.js). Run: node worker/test_ticks.mjs — fetch is a fake, no network. */
import { dispatchRequest, offerTicks, TICK_WORKFLOWS } from "./ticks.js";
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
const none = await offerTicks({}, ok204);
const good = await offerTicks({ GH_DISPATCH_TOKEN: "T" }, ok204);
const bad = await offerTicks({ GH_DISPATCH_TOKEN: "T" }, async (url) =>
  url.includes("bill_tracker") ? { status: 422, text: async () => "Workflow does not have 'workflow_dispatch' trigger" } : { status: 204, text: async () => "" });
const thrown = await offerTicks({ GH_DISPATCH_TOKEN: "T" }, async () => { throw new Error("network down"); });
console.error = origErr; console.log = origLog;

is("no token -> nothing dispatched, said so", [none.configured, none.dispatched, logs.some((l) => l.includes("not configured"))], [false, [], true]);
is("token -> both dispatched, each with tick=scheduled", [good.dispatched, calls.map((c) => c[1])], [TICK_WORKFLOWS, ["scheduled", "scheduled"]]);
is("a 422 is a named failure, the other still dispatched", [bad.dispatched, bad.failed.length, bad.failed[0].startsWith("bill_tracker.yml: HTTP 422")], [["calendar_worker.yml"], 1, true]);
is("a network error is a named failure for each workflow", thrown.failed.length, 2);
is("failures are logged, never swallowed", errs.filter((e) => e.startsWith("ticks_failed")).length, 2);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) process.exit(1);
