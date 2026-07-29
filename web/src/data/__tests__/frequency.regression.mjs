/** P26 as AMENDED (2026-07-27): print "k of n", nothing else. Run: node this file after esbuild. */
import { formatFrequency, complement, frequencyOf, rateForSort } from "/tmp/freq.mjs";
let pass=0,fail=0;
const is=(n,g,w)=>{const ok=JSON.stringify(g)===JSON.stringify(w);
  console.log(`  ${ok?"ok  ":"FAIL"} ${n} -> ${JSON.stringify(g)}${ok?"":` (want ${JSON.stringify(w)})`}`);ok?pass++:fail++;};

is("k of n",                    formatFrequency({k:7,n:9}),   "7 of 9");
is("zero successes still shows", formatFrequency({k:0,n:2}),  "0 of 2");   // no "too few" label (clause 4 struck)
is("large n gets separators",   formatFrequency({k:1284,n:3056}), "1,284 of 3,056");
is("n=0 is null, not '0 of 0'", formatFrequency({k:0,n:0}),   null);       // no observations != zero successes
is("negative n is null",        formatFrequency({k:1,n:-1}),  null);
is("null in, null out",         formatFrequency(null),        null);
is("NaN is null",               formatFrequency({k:NaN,n:5}), null);

// NO PERCENTAGE MAY EVER APPEAR (clauses 2/3): the formatter has no code path that emits one.
const outs = [{k:1,n:3},{k:2,n:2},{k:0,n:7},{k:99,n:100}].map(formatFrequency);
is("never emits a % sign", outs.some(o => (o||"").includes("%")), false);

is("complement",                complement({k:1,n:6}),        {k:5,n:6});
is("complement floors at 0",    complement({k:9,n:6}),        {k:0,n:6});

is("frequencyOf counts",        frequencyOf([1,2,3,4], x=>x%2===0), {k:2,n:4});
is("empty rows -> null",        frequencyOf([], ()=>true),    null);       // nothing to count != counted none

is("rateForSort ranks",         rateForSort({k:1,n:4}) < rateForSort({k:1,n:2}), true);
is("rateForSort n=0 sorts last", rateForSort({k:0,n:0}),      -1);
is("rateForSort null safe",     rateForSort(null),            -1);

console.log(`\n${pass} of ${pass+fail} passed`);
process.exit(fail?1:0);
