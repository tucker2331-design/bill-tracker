#!/usr/bin/env node
/**
 * Transpile ONE dependency-free .ts module to .mjs so a bare-`node` golden can import the REAL code.
 *
 * WHY THIS EXISTS: the `web/src/**\/__tests__/*.regression.mjs` goldens import from `/tmp/<name>.mjs`, and
 * until now that file was produced by hand — an ad-hoc `sed` invented per session. That already broke once
 * (a type-annotation regex whose two patterns were order-dependent, so stripping `: string[]` first made the
 * next pattern miss). A golden that depends on a hand-run text transform is not a regression test; it is a
 * ritual. This makes the step reproducible and uses the TypeScript compiler's own transpiler, so nothing
 * is stripped by regex at all.
 *
 * SCOPE (deliberate): transpile-only, single file, imports NOT resolved. The target module must therefore
 * have no runtime imports — which is exactly why `src/data/agenda.ts` was split out of `calendar.ts`.
 * If you point this at a module with runtime imports, node will fail loudly at import time on the unresolved
 * specifier. That is the correct failure: it means the module was not golden-testable, not that the
 * transpiler needs a workaround.
 *
 * Usage:  node web/tools/ts2mjs.mjs src/data/agenda.ts /tmp/agenda.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const [src, out] = process.argv.slice(2);
if (!src || !out) {
  console.error("usage: node web/tools/ts2mjs.mjs <input.ts> <output.mjs>");
  process.exit(2);
}

// `typescript` is already a devDependency (it backs `npm run build`'s typecheck) — reuse it rather than
// adding a transpiler. Resolved relative to THIS file so the script works from any cwd.
const require = createRequire(import.meta.url);
let ts;
try {
  ts = require("typescript");
} catch (e) {
  // Standard #4: a missing tool is a categorised, actionable failure — never a silent no-op that leaves a
  // stale /tmp file in place and lets the golden "pass" against yesterday's code.
  console.error(`ts2mjs: cannot load the TypeScript compiler (${e.message}).\n` +
    `Run 'npm install' in web/ first — this script deliberately adds no new dependency.`);
  process.exit(1);
}

const source = readFileSync(src, "utf8");
const { outputText, diagnostics } = ts.transpileModule(source, {
  fileName: src,
  reportDiagnostics: true,
  compilerOptions: {
    target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.ESNext,
    isolatedModules: true,
  },
});

// transpileModule cannot type-check (no program), but it DOES report syntactic errors. Surface them and
// fail — emitting a broken .mjs would produce a confusing golden failure three steps downstream.
if (diagnostics && diagnostics.length) {
  for (const d of diagnostics) {
    console.error(`ts2mjs: ${ts.flattenDiagnosticMessageText(d.messageText, " ")}`);
  }
  process.exit(1);
}

writeFileSync(out, outputText);
console.log(`ts2mjs: ${src} -> ${out} (${outputText.length} bytes)`);
