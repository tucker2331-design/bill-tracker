/** Data-gate tests (worker/sheets.js). Run: node worker/test_sheets.mjs — no network: fetch is stubbed. */
import { validateSheetParams, gvizUrl, pemToPkcs8, claimSet, serviceToken, handleSheet } from "./sheets.js";
import { readFileSync } from "node:fs";

let pass = 0, fail = 0;
const is = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`}`);
  ok ? pass++ : fail++;
};

// ---- parameter shape (the proxy must not become a general fetcher) ----
is("valid tab",               validateSheetParams({ tab: "Bill_Tracker" }), null);
is("missing tab",             typeof validateSheetParams({}), "string");
is("tab with slash rejected", typeof validateSheetParams({ tab: "../x" }), "string");
is("tab with & rejected",     typeof validateSheetParams({ tab: "a&sheet=b" }), "string");
is("range A1 ok",             validateSheetParams({ tab: "Sheet1", range: "AA1" }), null);
is("range column ok",         validateSheetParams({ tab: "Sheet1", range: "O" }), null);
is("range junk rejected",     typeof validateSheetParams({ tab: "Sheet1", range: "A1;drop" }), "string");
is("huge tq rejected",        typeof validateSheetParams({ tab: "Sheet1", tq: "x".repeat(2001) }), "string");
is("headers digit ok",        validateSheetParams({ tab: "Sheet1", headers: "0" }), null);
const u = new URL(gvizUrl("SHEETID", { tab: "Bill Summaries", tq: "select A where A = 'HB1'", headers: "0" }));
is("upstream host fixed",     u.host, "docs.google.com");
is("upstream sheet id from config", u.pathname, "/spreadsheets/d/SHEETID/gviz/tq");
is("tq carried intact",       u.searchParams.get("tq"), "select A where A = 'HB1'");
is("csv output",              u.searchParams.get("tqx"), "out:csv");

// ---- service-account token: a real RS256 round trip with a throwaway key ----
const kp = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
const pkcs8 = new Uint8Array(await crypto.subtle.exportKey("pkcs8", kp.privateKey));
const pem = `-----BEGIN PRIVATE KEY-----\n${Buffer.from(pkcs8).toString("base64").match(/.{1,64}/g).join("\n")}\n-----END PRIVATE KEY-----\n`;
is("PEM decodes to the same bytes", Buffer.from(pemToPkcs8(pem)).equals(Buffer.from(pkcs8)), true);
let threw = false; try { pemToPkcs8("not a key"); } catch { threw = true; }
is("non-PEM throws", threw, true);
is("claim scope is READ-ONLY", claimSet("sa@x.iam", 1000).scope, "https://www.googleapis.com/auth/spreadsheets.readonly");

const realFetch = globalThis.fetch;
let assertion = null, upstreamAuth = null;
globalThis.fetch = async (url, init = {}) => {
  if (String(url).startsWith("https://oauth2.googleapis.com/token")) {
    assertion = new URLSearchParams(init.body).get("assertion");
    return new Response(JSON.stringify({ access_token: "tok123", expires_in: 3600 }), { status: 200 });
  }
  upstreamAuth = init.headers?.Authorization ?? null;
  return globalThis.__upstream();
};
const env = { SPREADSHEET_ID: "SHEETID", GCP_SA_JSON: JSON.stringify({ client_email: "sa@x.iam", private_key: pem }) };
is("token minted", await serviceToken(env, Date.now()), "tok123");
const [h, p, s] = assertion.split(".");
const sigOk = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", kp.publicKey, Buffer.from(s, "base64url"), new TextEncoder().encode(`${h}.${p}`));
is("assertion signature verifies with the public key", sigOk, true);
is("assertion header RS256", JSON.parse(Buffer.from(h, "base64url")).alg, "RS256");
is("assertion iss = client_email", JSON.parse(Buffer.from(p, "base64url")).iss, "sa@x.iam");
is("no service account -> null token (reported, not hidden)", await serviceToken({}), null);

// ---- the handler ----
const call = (qs, e = env) => handleSheet(new URL(`https://x/api/sheet?${qs}`), e);
globalThis.__upstream = () => new Response('"Bill"\n"HB1"\n', { status: 200, headers: { "content-type": "text/csv; charset=UTF-8" } });
let r = await call("tab=Bill_Tracker");
is("csv passes through",      [r.status, await r.text()], [200, '"Bill"\n"HB1"\n']);
is("auth mode reported",      r.headers.get("x-sheet-auth"), "service_account");
is("bearer sent upstream",    upstreamAuth, "Bearer tok123");
is("never cached",            r.headers.get("cache-control"), "private, no-store");
globalThis.__upstream = () => new Response("<html>Sign in</html>", { status: 200, headers: { "content-type": "text/html" } });
r = await call("tab=Bill_Tracker", { SPREADSHEET_ID: "SHEETID" });
is("private sheet w/o token -> 502, not HTML to a CSV parser", r.status, 502);
is("502 says why",            (await r.json()).sheet_auth, "none");
r = await call("tab=../../etc");
is("bad tab -> 400",          r.status, 400);
r = await call("tab=Sheet1", { GCP_SA_JSON: env.GCP_SA_JSON });
is("no SPREADSHEET_ID -> 500", r.status, 500);
globalThis.fetch = realFetch;

// ---- wiring: the sheet route sits behind authentication AND the team gate ----
const src = readFileSync(new URL("./index.js", import.meta.url), "utf8");
const at = (needle) => src.indexOf(needle);
is("/sheet route after the team gate", at("teamGate(path, email, env)") > 0 && at("teamGate(path, email, env)") < at('path === "/sheet"'), true);
is("team gate after authentication", at("await authenticatedEmail(request, env)") < at("teamGate(path, email, env)"), true);

console.log(`\n${fail ? `${fail} FAILED` : "ALL PASS"} (${pass} ok)`);
process.exit(fail ? 1 : 0);
