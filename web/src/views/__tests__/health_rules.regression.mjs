/**
 * Health rules — binary clean, unconfirmed = red, rings from the same list as the dials, dial geometry, the
 * rhythm-calibrated freshness limit.
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/data/health_rules.ts /tmp/health_rules.mjs \
 *         && node web/src/views/__tests__/health_rules.regression.mjs
 */
import { isClean, rings, dialPos, rhythmLimitHours, verdictOf } from "/tmp/health_rules.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

const I = (id, cat, value, limit, extra = {}) => ({ id, cat, name: id, value, limit, max: limit * 4 + 10, impeaches: "no", ...extra });

// ---- binary + unconfirmed is red
is("within limit is clean", isClean(I("a", "Accuracy", 0, 0)), true);
is("over limit is not clean", isClean(I("a", "Accuracy", 1, 0)), false);
is("NO RESULT is not clean (red, never grey)", isClean(I("a", "Accuracy", null, 0)), false);
is("NaN is not clean", isClean(I("a", "Accuracy", NaN, 5)), false);

// ---- rings come from the same list the dials use
const insts = [I("s9", "Accuracy", 0, 0), I("wrong", "Accuracy", null, 0), I("miss", "Completeness", 0, 0), I("age", "Freshness", 3, 12)];
const r = rings(insts, [{ cat: "Stability", name: "breaker", ok: true }, { cat: "Stability", name: "ledger", ok: false }]);
is("ring counts", r.map((x) => [x.cat, x.ok, x.total]), [["Accuracy", 1, 2], ["Completeness", 1, 1], ["Freshness", 1, 1], ["Stability", 1, 2]]);
is("a ring segment flips with its dial", rings([I("s9", "Accuracy", 3, 0)], [])[0].segs[0].ok, false);

// ---- dial geometry: grey arc 0..limit = 0..0.6, red arc limit..max = 0.6..1
is("zero sits at the start", dialPos(I("x", "Freshness", 0, 12)), 0);
is("exactly at the limit = the grey/red seam", dialPos(I("x", "Freshness", 12, 12)), 0.6);
is("limit 0: any value is past the seam", dialPos(I("x", "Accuracy", 1, 0, { max: 5 })) > 0.6, true);
is("pinned at the far end", dialPos(I("x", "Accuracy", 999, 0, { max: 5 })), 1);
is("no result: needle not drawn (0)", dialPos(I("x", "Accuracy", null, 0)), 0);

// ---- the freshness limit follows the observed rhythm
const H = 3.6e6, now = Date.UTC(2026, 9, 29, 12);
const every6h = Array.from({ length: 12 }, (_, k) => now - k * 6 * H);
is("off-season 6-hourly writes -> 12 h limit, so a 6.6 h age is NOT an alarm", rhythmLimitHours(every6h), 12);
const every15m = Array.from({ length: 20 }, (_, k) => now - k * 0.25 * H);
is("in-session 15-minute writes -> the 6 h floor", rhythmLimitHours(every15m), 6);
is("too few heartbeats -> the floor, never looser", rhythmLimitHours([now, now - 30 * H]), 6);
const withGap = [now, now - 6 * H, now - 12 * H, now - 18 * H, now - 40 * H];
is("one long gap widens the limit to 1.5x it", rhythmLimitHours(withGap), 33);

// ---- verdict
is("nothing open -> clean", verdictOf(insts, []).clean, true);
is("verdict counts", verdictOf(insts, ["yes", "unknown", "no"]), { clean: false, problems: 3, wrong: 1, noResult: 1 });

// (the 90-day strip lives with the counter in incidents.ts; its goldens are in test_counter_display.py)

console.log(`\n${fail ? `${fail} FAILED` : "ALL PASS"} (${pass} ok)`);
process.exit(fail ? 1 : 0);
