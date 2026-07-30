/** Ceremonial split — measured against session 20262 (Senate origin: 91 = 65 + 25 + 1). */
import { isCeremonial, splitByClass, ceremonialLabel } from "/tmp/billclass.mjs";
let pass=0,fail=0;
const is=(n,g,w)=>{const ok=JSON.stringify(g)===JSON.stringify(w);
  console.log(`  ${ok?"ok  ":"FAIL"} ${n} -> ${JSON.stringify(g)}${ok?"":` (want ${JSON.stringify(w)})`}`);ok?pass++:fail++;};
const B=(bill,cls)=>({bill,legislationClass:cls});

is("commending is ceremonial", isCeremonial(B("SR2002","Commending Resolution")), true);
is("memorial is ceremonial",   isCeremonial(B("SR2006","Memorial Resolution")), true);
is("legislation is not",       isCeremonial(B("HB1","Legislation")), false);
is("budget is not",            isCeremonial(B("HB30","Budget")), false);
is("procedural is not",        isCeremonial(B("HJ4001","Procedural")), false);
// FAIL TOWARD VISIBILITY: unknown/blank must stay in the main list.
is("blank class stays visible",   isCeremonial(B("X1","")), false);
is("unknown class stays visible", isCeremonial(B("X2","Some New LIS Class")), false);
is("missing field stays visible", isCeremonial({bill:"X3"}), false);

// The real Senate-origin population of 20262.
const pop=[...Array(65)].map((_,i)=>B(`SR${2100+i}`,"Commending Resolution"))
  .concat([...Array(25)].map((_,i)=>B(`SR${2200+i}`,"Memorial Resolution")))
  .concat([B("SR2001","Legislation")]);
const s=splitByClass(pop);
is("substantive count", s.substantive.length, 1);
is("ceremonial count",  s.ceremonial.length, 90);
is("commending count",  s.commending, 65);
is("memorial count",    s.memorial, 25);
is("nothing lost",      s.substantive.length + s.ceremonial.length, pop.length);
is("label",             ceremonialLabel(s), "65 commending · 25 memorial");
// A regular session has none -> no group header should appear.
is("regular session: no ceremonial", splitByClass([B("HB1","Legislation"),B("HB2","Legislation")]).ceremonial.length, 0);
console.log(`\n${pass} of ${pass+fail} passed`); process.exit(fail?1:0);
