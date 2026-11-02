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
 * tick is skipped by the same floor, and the workflow's concurrency group never runs two cycles at once.
 *
 * FAIL DIRECTION: the input is REQUIRED, so a dispatch without it is rejected by GitHub (422) -- it can never
 * arrive as an ungated run. Without the GH_DISPATCH_TOKEN secret each tick logs "not configured" and dispatches
 * nothing (GitHub's cron still runs). A failed dispatch is logged with its status and body and re-thrown so
 * Cloudflare records the cron run as failed -- never swallowed.
 */
export const TICK_WORKFLOWS = ["calendar_worker.yml", "bill_tracker.yml"];
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

export async function offerTicks(env, fetchFn = fetch) {
  if (!env.GH_DISPATCH_TOKEN) {
    console.log("ticks: GH_DISPATCH_TOKEN not configured -- no dispatch (GitHub's own cron still runs)");
    return { dispatched: [], failed: [], configured: false };
  }
  const dispatched = [], failed = [];
  for (const wf of TICK_WORKFLOWS) {
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
  else console.log(`ticks: offered ${dispatched.join(", ")}`);
  return { dispatched, failed, configured: true };
}
