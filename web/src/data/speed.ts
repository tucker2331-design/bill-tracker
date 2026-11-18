// The speed each state's jobs run at (repo-root cadence_profiles.json, baked in at build — web/vite.config.ts) and
// the freshness limit it implies. Mirrors cadence.py SPEED_INTERVAL_HOURS; test_states.py checks the two agree.
import { STATE } from "../states";

declare const __SPEED_PROFILES__: Record<string, unknown>;

/** Hours each speed promises between runs. null = activity-correlated (the site keeps its learned rhythm). */
export const SPEED_INTERVAL_HOURS: Record<string, number | null> = { daily: 24, "4h": 4, instant: 0.25, fast: null, slow: null };
const ALIASES: Record<string, string> = { normal: "fast" };
/** Overnight quiet hours the jobs skip (bill_tracker.py: 23:00–06:00 ET) — a run due then waits for the morning. */
export const QUIET_HOURS = 7;

export function speedOf(code: string = STATE.code): string {
  const raw = typeof __SPEED_PROFILES__ === "object" && __SPEED_PROFILES__ ? __SPEED_PROFILES__[code] : undefined;
  const w = String(raw ?? "fast").trim().toLowerCase();
  const word = ALIASES[w] ?? w;
  return word in SPEED_INTERVAL_HOURS ? word : "fast";
}

/** The freshness limit the speed sets (and the source's own floor, e.g. California publishes daily): 1.25 × the
 *  promised interval + the quiet hours. null = no fixed promise — keep the learned rhythm / schedule limit. */
export function speedLimitHours(code: string = STATE.code, sourceMinH: number = STATE.sourceMinIntervalHours ?? 0): number | null {
  const iv = SPEED_INTERVAL_HOURS[speedOf(code)];
  if (iv == null && sourceMinH < 6) return null;
  const eff = Math.max(iv ?? 0, sourceMinH);
  return Math.round((1.25 * eff + QUIET_HOURS) * 10) / 10;
}
