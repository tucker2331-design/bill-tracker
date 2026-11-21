/**
 * Scheduled ticks for the two Virginia workers, offered from Cloudflare's cron (wrangler.toml [triggers]).
 *
 * WHY: GitHub delivered the workers' every-15-minute cron only every 4-7 hours (measured 2026-11-02: no run at all from
 * 08:15 to 17:30 UTC), so data age on Health was set by GitHub's scheduler, not by the legislature. Cloudflare's
 * cron fires on time and is free on the Workers Free plan (it already runs the Slack digest every 15 minutes).
 *
 * WHAT IT DOES NOT CHANGE: how often LIS is read. A tick only OFFERS a run. Each workflow is dispatched with the
 * required input tick=scheduled, and the workers treat that exactly like GitHub's cron
 * (cadence.is_scheduled_tick): quiet hours 11pm-6am ET, the activity-correlated floor (calendar ~3 h / bill ~6 h
 * when nothing is scheduled; every tick only inside a real meeting window) and jitter all still apply. A skipped
 * tick reads one Sheets cell and ZERO LIS. GitHub's own cron stays on as a second source of ticks; a duplicate
 * is skipped because the cadence markers record each cycle's START and a meeting window allows at most one full
 * cycle per 12 minutes (cadence.IN_WINDOW_MIN_INTERVAL). The concurrency group never runs two cycles at once.
 *
 * FAIL DIRECTION: the input is REQUIRED, so a dispatch without it is rejected by GitHub (422) -- it can never
 * arrive as an ungated run. Without the GH_DISPATCH_TOKEN secret each tick logs "not configured" and dispatches
 * nothing (GitHub's cron still runs). A failed dispatch is logged with its status and body and re-thrown so
 * Cloudflare records the cron run as failed -- never swallowed.
 */
import { gvizUrl, serviceToken } from "./sheets.js";
import { parseCsv } from "./alerts.js";

export const TICK_WORKFLOWS = ["calendar_worker.yml", "bill_tracker.yml"];

// ── The tick gate (going private A1, 2026-11-20) ─────────────────────────────────────────────────────────────────
// Every offer used to START a GitHub job, and the worker then skipped almost all of them (~190 of ~192 a day at the
// "daily" speed): ~9,000 of ~11,000 billed Actions minutes a month, measured 2026-11-20. Free while the repo is public,
// but a private repo gets 2,000 (docs/ideas/going_private.md A1). Each worker now writes, every time its own gate
// decides, WHEN its next full cycle could run (cadence.next_due -> the Tick_Gate tab). This reads that tab and starts
// only the jobs that are due. The rule lives in ONE place (cadence.py); this only compares two times.
// FAIL DIRECTION (unchanged behaviour on any doubt): no service account, an unreadable tab, a wrong header, a missing
// row, an unparseable time, or a row older than STALE_HOURS -> that job is offered, exactly as before.
export const TICK_GATE_TAB = "Tick_Gate";
export const TICK_GATE_HEADER = ["Workflow", "NextDueUTC", "WrittenUTC", "Reason"];   // cadence.TICK_GATE_HEADER
export const STALE_HOURS = 33;     // cadence.NEXT_DUE_HORIZON_H (32) + 1: a row is always rewritten by its own due time
export const EARLY_MS = 60_000;    // offer a job up to a minute early (a tick lands on the quarter hour)

/** Which ticked workflows are due now. PURE. `rows` = the Tick_Gate CSV (header first), or null if unread. */
export function dueWorkflows(rows, nowMs) {
  const all = (why) => ({ due: TICK_WORKFLOWS.map((wf) => ({ wf, why })), skipped: [], gate: "unavailable" });
  if (!Array.isArray(rows) || !rows.length) return all("no readable Tick_Gate tab");
  if (TICK_GATE_HEADER.some((h, i) => ((rows[0] || [])[i] || "").trim() !== h)) return all("Tick_Gate header is not ours");
  const byWf = new Map(rows.slice(1).map((r) => [((r || [])[0] || "").trim(), r]));
  const due = [], skipped = [];
  for (const wf of TICK_WORKFLOWS) {
    const r = byWf.get(wf);
    const next = r ? Date.parse((r[1] || "").trim()) : NaN;
    const written = r ? Date.parse((r[2] || "").trim()) : NaN;
    if (!r) due.push({ wf, why: "no gate row yet" });
    else if (!Number.isFinite(next) || !Number.isFinite(written)) due.push({ wf, why: "gate row unreadable" });
    else if (nowMs - written > STALE_HOURS * 3.6e6) due.push({ wf, why: `gate row stale (written ${r[2].trim()})` });
    else if (nowMs >= next - EARLY_MS) due.push({ wf, why: `due ${r[1].trim()}` });
    else skipped.push({ wf, why: `next due ${r[1].trim()}` });
  }
  return { due, skipped, gate: "ok" };
}

/** Read the Tick_Gate tab the same way every /api/sheet read works (worker/sheets.js handleSheet): with the service
 *  account when GCP_SA_JSON is set, otherwise unauthenticated, which works while the sheet is still link-shared.
 *  Measured 2026-11-21: the first version required the service account, the VA Worker has none yet, so every tick
 *  read "unavailable" and offered every job (~9,500 min/month). null = no spreadsheet configured; throws on a failed
 *  read (a private sheet without a token answers with Google's HTML sign-in page, caught by the CSV check). */
export async function readTickGate(env, fetchFn = fetch) {
  if (!env.SPREADSHEET_ID) return null;
  const token = await serviceToken(env);           // null without GCP_SA_JSON
  const res = await fetchFn(gvizUrl(env.SPREADSHEET_ID, { tab: TICK_GATE_TAB, range: "A1:D4", headers: "0" }),
    token ? { headers: { Authorization: `Bearer ${token}` } } : {});
  if (!res.ok) throw new Error(`Tick_Gate read HTTP ${res.status}`);
  // case-insensitive, like handleSheet's /text\/csv/i (Gemini #281)
  if (!/csv/i.test(res.headers.get("content-type") || "")) throw new Error("Tick_Gate read was not CSV (sign-in page?)");
  return parseCsv(await res.text());
}
export const REPO = "tucker2331-design/bill-tracker";

/** The one dispatch request per workflow. Pure; tested in worker/test_ticks.mjs. */
export function dispatchRequest(workflow, token, ref = "main") {
  return {
    url: `https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`,
    init: {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bill-tracker-cron-tick",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref, inputs: { tick: "scheduled" } }),
    },
  };
}

// The ticks start VIRGINIA's two jobs, so only Virginia's Worker offers them. Pennsylvania's Worker runs this same
// code on its own cron (wrangler.pa.toml); a token added there by mistake must not start Virginia's jobs twice.
// Read from the Worker's own BILL_TRACKER_STATE var (wrangler.toml "VA", wrangler.pa.toml "PA") -- config, not a guess.
export const TICK_STATE = "VA";

export async function offerTicks(env, fetchFn = fetch, readGate = readTickGate) {
  if (env.BILL_TRACKER_STATE !== TICK_STATE) {
    if (env.GH_DISPATCH_TOKEN) console.error(`ticks_misplaced: GH_DISPATCH_TOKEN is set on the ${env.BILL_TRACKER_STATE || "unknown-state"} Worker; it is ignored -- only the ${TICK_STATE} Worker starts Virginia's jobs. Remove it.`);
    return { dispatched: [], failed: [], configured: false };
  }
  if (!env.GH_DISPATCH_TOKEN) {
    console.log("ticks: GH_DISPATCH_TOKEN not configured -- no dispatch (GitHub's own cron still runs)");
    return { dispatched: [], failed: [], configured: false };
  }
  let rows = null, gateErr = "";
  try {
    rows = await readGate(env, fetchFn);
  } catch (err) {
    gateErr = err && err.message ? err.message : String(err);
    console.error("tick_gate_unreadable", gateErr);   // logged, then every job is offered (the old behaviour)
  }
  const plan = dueWorkflows(rows, Date.now());
  for (const s of plan.skipped) console.log(`ticks: ${s.wf} not offered (${s.why})`);
  if (plan.gate !== "ok") console.log(`ticks: gate unavailable (${gateErr || plan.due[0].why}) -- offering every job`);
  const dispatched = [], failed = [];
  for (const { wf } of plan.due) {
    const { url, init } = dispatchRequest(wf, env.GH_DISPATCH_TOKEN);
    try {
      const res = await fetchFn(url, init);
      if (res.status === 204) dispatched.push(wf);
      else failed.push(`${wf}: HTTP ${res.status} ${(await res.text()).slice(0, 200)}`);
    } catch (err) {
      failed.push(`${wf}: ${err && err.message ? err.message : String(err)}`);
    }
  }
  if (failed.length) console.error("ticks_failed", failed.join(" | "));
  else console.log(`ticks: offered ${dispatched.join(", ") || "nothing (nothing due)"}`);
  return { dispatched, failed, skipped: plan.skipped.map((x) => x.wf), configured: true, gate: plan.gate };
}
