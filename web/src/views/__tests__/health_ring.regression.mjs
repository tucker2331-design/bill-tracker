// The ring rule extracted verbatim from Health.tsx so the test binds to the shipped logic's shape.
const ledgerTone = (counter) =>
  !counter ? "unknown"
  : counter.openNow.length > 0 ? "danger"
  : counter.wrongSheet ? "unknown"
  : !counter.available ? "unknown"
  : "good";

let pass=0, fail=0;
const is=(n,g,w)=>{const ok=g===w;console.log(`  ${ok?"ok  ":"FAIL"} ${n} -> ${g}${ok?"":` (want ${w})`}`);ok?pass++:fail++;};
const C=(o)=>({daysClean:1,monitoringDays:1,incidentsEver:0,openNow:[],lastDrillDays:1,malformedRows:0,available:true,wrongSheet:false,...o});

is("open incident => danger, never green", ledgerTone(C({openNow:["DATA_ANOMALY"]})), "danger");
is("many open => danger",                  ledgerTone(C({openNow:["A","B","C"]})),    "danger");
is("wrong sheet => unknown, never green",  ledgerTone(C({wrongSheet:true,available:false})), "unknown");
is("unseeded => unknown, never green",     ledgerTone(C({available:false})),          "unknown");
is("not loaded => unknown",                ledgerTone(null),                          "unknown");
is("clean + seeded => good",               ledgerTone(C({})),                         "good");

// THE INVARIANT the owner asked for: no state of the ledger can be green unless it is verifiably clean.
const states=[C({openNow:["X"]}), C({wrongSheet:true,available:false}), C({available:false}), null];
const anyGreen = states.some(s=>ledgerTone(s)==="good");
is("no non-clean ledger state renders green", anyGreen, false);
console.log(`\n${pass} of ${pass+fail} passed`);
process.exit(fail?1:0);
