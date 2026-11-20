/** Security-header tests. Run: node worker/test_headers.mjs */
import { SECURITY_HEADERS, withSecurityHeaders } from "./headers.js";
import worker from "./index.js";
import { readFileSync } from "node:fs";

let pass = 0, fail = 0;
const is = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`}`);
  ok ? pass++ : fail++;
};
const hasAll = (r) => Object.entries(SECURITY_HEADERS).every(([k, v]) => r.headers.get(k) === v);

// a fetched response's headers are immutable: the helper must copy, not mutate
const locked = Response.redirect("https://example.org/next", 302);
const out = withSecurityHeaders(locked);
is("immutable response copied, headers added", hasAll(out), true);
is("status kept", out.status, 302);
is("Location kept", out.headers.get("Location"), "https://example.org/next");
const page = withSecurityHeaders(new Response("<html>ok</html>", { status: 200, headers: { "content-type": "text/html" } }));
is("content type kept", page.headers.get("content-type"), "text/html");
is("body kept", await page.text(), "<html>ok</html>");
is("no framing by other sites", SECURITY_HEADERS["Content-Security-Policy"], "frame-ancestors 'none'");

// through the real Worker: an app page and an API answer both carry the headers
const env = { ASSETS: { fetch: async () => new Response("<html></html>", { headers: { "content-type": "text/html" } }) } };
const app = await worker.fetch(new Request("https://site.example/"), env, {});
is("app page has the headers", hasAll(app), true);
const api = await worker.fetch(new Request("https://site.example/api/health"), env, {});
is("API answer has the headers", hasAll(api), true);
is("API answer still JSON", (api.headers.get("content-type") || "").includes("application/json"), true);
const denied = await worker.fetch(new Request("https://site.example/api/sheet?tab=Bill_Tracker"), env, {});
is("an unauthenticated read is still refused", denied.status, 401);
is("the refusal carries the headers too", hasAll(denied), true);

// The asset server serves the pages without running the Worker, so web/public/_headers carries the same set (Codex
// #279). One list, two places: this keeps them identical.
const file = readFileSync(new URL("../web/public/_headers", import.meta.url), "utf8").split("\n");
const start = file.findIndex((l) => l.trim() === "/*");
const fromFile = {};
for (const l of file.slice(start + 1)) {
  if (!/^\s+\S/.test(l)) break;
  const i = l.indexOf(":");
  fromFile[l.slice(0, i).trim()] = l.slice(i + 1).trim();
}
is("_headers has a /* rule", start >= 0, true);
is("_headers matches SECURITY_HEADERS exactly", fromFile, SECURITY_HEADERS);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
