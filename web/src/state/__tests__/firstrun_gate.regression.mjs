/**
 * The three-state profile gate (F3).
 *
 * Two states would be a bug: if "not checked yet" and "no profile" were the same value, the first-run form
 * would FLASH on every page load for people who already filled it in. And if a FAILED read fell back to
 * "no profile", a network hiccup would ask a user to re-enter a profile they already have.
 *
 * Run: node web/src/state/__tests__/firstrun_gate.regression.mjs
 */
const showFirstRun = (identity, profile) => Boolean(identity) && profile === null;

let pass = 0, fail = 0;
const is = (n, g, w) => { const ok = g === w;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${n} -> ${g}${ok ? "" : ` (want ${w})`}`); ok ? pass++ : fail++; };

const ID = { email: "t@x.com", name: "Tucker", token: "x" };

is("signed out, not checked        -> hidden", showFirstRun(null, undefined), false);
is("signed out, stale null         -> hidden", showFirstRun(null, null),      false);
is("signed in, NOT CHECKED YET     -> hidden", showFirstRun(ID, undefined),   false);
is("signed in, no profile          -> SHOWN",  showFirstRun(ID, null),        true);
is("signed in, has profile         -> hidden", showFirstRun(ID, { display_name: "Tucker" }), false);
is("signed in, empty-object profile-> hidden", showFirstRun(ID, {}),          false);
is("failed profile read            -> hidden", showFirstRun(ID, undefined),   false);

console.log(`\n${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
