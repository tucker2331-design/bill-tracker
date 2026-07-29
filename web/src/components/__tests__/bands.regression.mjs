/** The trust surface is BINARY (P25a; owner 2026-07-29 "no yellow — if it has a chance of being wrong
 *  then it might as well be wrong"). Build first:
 *    npx esbuild web/src/components/bands.ts --format=esm --outfile=/tmp/bands.mjs */
import { bandTone } from "/tmp/bands.mjs";
let pass=0,fail=0;
const is=(n,g,w)=>{const ok=g===w;console.log(`  ${ok?"ok  ":"FAIL"} ${n} -> ${g}${ok?"":` (want ${w})`}`);ok?pass++:fail++;};
const lower  = (good,warn,max)=>[{upto:good,tone:"good"},{upto:warn,tone:"warn"},{upto:max,tone:"danger"}];
const higher = (danger,warn,max=100)=>[{upto:danger,tone:"danger"},{upto:warn,tone:"warn"},{upto:max,tone:"good"}];

is("lower: inside good stays good", bandTone(0, lower(0.5,25,50)),   "good");
is("lower: MIDDLE band is red",     bandTone(10, lower(0.5,25,50)),  "danger");
is("lower: top band is red",        bandTone(40, lower(0.5,25,50)),  "danger");
is("higher: bottom band red",       bandTone(50, higher(98,99.99)),  "danger");
is("higher: MIDDLE band is red",    bandTone(99, higher(98,99.99)),  "danger");
is("higher: good target green",     bandTone(100, higher(98,99.99)), "good");

// THE INVARIANT: no input to any preset can yield "warn".
const probes=[];
for (let v=0; v<=100; v+=0.5) probes.push(bandTone(v, lower(0.5,25,50)), bandTone(v, higher(98,99.99)));
is("no value anywhere yields warn", probes.includes("warn"), false);
is("only good|danger appear",       [...new Set(probes)].sort().join(","), "danger,good");

console.log(`\n${pass} of ${pass+fail} passed`);
process.exit(fail?1:0);
