/**
 * REGRESSION TESTS — Health reads job history from Guard_Status, not from GitHub in the browser (2026-11-20,
 * docs/ideas/going_private.md A2: a private repo answers the browser's token-free GitHub read with 404).
 *
 * Run:  node web/tools/ts2mjs.mjs web/src/data/guard_rules.ts /tmp/guard_rules.mjs \
 *         && node web/src/data/__tests__/guard_rules.regression.mjs
 */
import { parseRecent, verdictOf } from "/tmp/guard_rules.mjs";
let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = JSON.stringify(g) === JSON.stringify(w);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n}${ok ? "" : `  got ${JSON.stringify(g)} want ${JSON.stringify(w)}`}`); ok ? pass++ : fail++; };

// the strip: newest first, exactly what the guard wrote
is("strip parses", parseRecent("pfnp", true), ["pass", "fail", "none", "pass"]);
is("empty strip = no runs yet", parseRecent("", true), []);
// an older guard wrote no Recent column: the page must say "unreadable", never invent a strip
is("column absent -> null", parseRecent("pppp", false), null);
is("not the guard's shape -> null", parseRecent("success,failure", true), null);
is("undefined cell with column present -> []", parseRecent(undefined, true), []);

// the four outside checks: only ok is a clean pass; anything the guard could not judge is unknown, never pass
is("ok", verdictOf("ok"), { status: "pass", stale: false });
is("overdue = last good result, but stale", verdictOf("overdue"), { status: "pass", stale: true });
is("failing", verdictOf("failing"), { status: "fail", stale: false });
is("never_succeeded", verdictOf("never_succeeded"), { status: "fail", stale: false });
is("running", verdictOf("running"), { status: "running", stale: false });
for (const st of ["never_run", "not_yet_due", "disabled", "unknown", "", undefined])
  is(`${JSON.stringify(st)} -> unknown`, verdictOf(st), { status: "unknown", stale: false });

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
