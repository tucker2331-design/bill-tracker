/** Structural tests for Google ID-token verification. Run: node worker/test_auth.mjs */
import { verifyGoogleIdToken } from "./auth.js";

const CLIENT = "831223695835-cqd2fmjq3l61jc1t6pr9elobra0imhf5.apps.googleusercontent.com";
const b64u = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const tok = (h, p, sig = "AAAA") => `${b64u(h)}.${b64u(p)}.${sig}`;
const now = Math.floor(Date.now() / 1000);
const goodClaims = { iss: "https://accounts.google.com", aud: CLIENT, exp: now + 3600,
                     iat: now, email: "t@x.com", email_verified: true };

let pass = 0, fail = 0;
async function is(name, got, want) {
  const ok = got === want;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (got ${JSON.stringify(got)})`}`);
  ok ? pass++ : fail++;
}

// Nothing below reaches a real signature check, but each must be rejected BEFORE that point --
// these are the cheap structural rejections, and every one of them is a real attack shape.
await is("empty token",            await verifyGoogleIdToken("", CLIENT), null);
await is("missing client id",      await verifyGoogleIdToken(tok({alg:"RS256",kid:"k"}, goodClaims), ""), null);
await is("not three parts",        await verifyGoogleIdToken("a.b", CLIENT), null);
await is("garbage base64",         await verifyGoogleIdToken("!!!.???.###", CLIENT), null);
await is("alg=none rejected",      await verifyGoogleIdToken(tok({alg:"none",kid:"k"}, goodClaims), CLIENT), null);
await is("alg=HS256 rejected",     await verifyGoogleIdToken(tok({alg:"HS256",kid:"k"}, goodClaims), CLIENT), null);
await is("missing kid rejected",   await verifyGoogleIdToken(tok({alg:"RS256"}, goodClaims), CLIENT), null);
// aud/iss/exp/email_verified are checked AFTER signature, so with a bogus signature these also return null;
// the point of listing them is that each is an independent gate in the source, not that the test isolates it.
await is("wrong aud",              await verifyGoogleIdToken(tok({alg:"RS256",kid:"k"}, {...goodClaims, aud:"someone-else"}), CLIENT), null);
await is("wrong iss",              await verifyGoogleIdToken(tok({alg:"RS256",kid:"k"}, {...goodClaims, iss:"evil.example"}), CLIENT), null);
await is("expired",                await verifyGoogleIdToken(tok({alg:"RS256",kid:"k"}, {...goodClaims, exp: now-7200}), CLIENT), null);
await is("email_verified false",   await verifyGoogleIdToken(tok({alg:"RS256",kid:"k"}, {...goodClaims, email_verified:false}), CLIENT), null);
await is("unknown kid",            await verifyGoogleIdToken(tok({alg:"RS256",kid:"no-such-kid"}, goodClaims), CLIENT), null);

// ── THE SUCCESS PATH (CodeRabbit, 2026-07-28) ────────────────────────────────────────────────────────────
// Everything above proves REJECTION. A verifier that returns null unconditionally would pass all of it --
// the tests would be green and the feature dead. So: mint a real RSA key, sign a real token, serve a real
// JWKS from a stub fetch, and assert the email comes back. This is the only case that proves the thing works.
import { webcrypto } from "node:crypto";
const { subtle } = webcrypto;
const b64uBuf = (buf) => Buffer.from(buf).toString("base64url");

const kp = await subtle.generateKey(
  { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1,0,1]), hash: "SHA-256" },
  true, ["sign", "verify"],
);
const jwk = await subtle.exportKey("jwk", kp.publicKey);
const KID = "test-kid-1";
const jwks = { keys: [{ ...jwk, kid: KID, alg: "RS256", use: "sig" }] };

// Stub only the JWKS endpoint; anything else still hits the network and would be an obvious failure.
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) =>
  String(url).includes("googleapis.com/oauth2/v3/certs")
    ? new Response(JSON.stringify(jwks), { status: 200, headers: { "content-type": "application/json" } })
    : realFetch(url, init);

async function mint(claims, kid = KID) {
  const header = b64uBuf(JSON.stringify({ alg: "RS256", kid, typ: "JWT" }));
  const payload = b64uBuf(JSON.stringify(claims));
  const sig = await subtle.sign("RSASSA-PKCS1-v1_5", kp.privateKey, new TextEncoder().encode(`${header}.${payload}`));
  return `${header}.${payload}.${b64uBuf(sig)}`;
}

await is("VALID token -> email returned",
  await verifyGoogleIdToken(await mint(goodClaims), CLIENT), "t@x.com");
await is("email is lowercased",
  await verifyGoogleIdToken(await mint({ ...goodClaims, email: "T@X.COM" }), CLIENT), "t@x.com");
await is('email_verified "true" (string) accepted',
  await verifyGoogleIdToken(await mint({ ...goodClaims, email_verified: "true" }), CLIENT), "t@x.com");
await is("bare accounts.google.com issuer accepted",
  await verifyGoogleIdToken(await mint({ ...goodClaims, iss: "accounts.google.com" }), CLIENT), "t@x.com");

// Signed by the RIGHT key but for the WRONG audience -- the confused-deputy case. Now provable, because
// only a genuinely-signed token can reach the aud check at all.
await is("SIGNED but wrong aud -> rejected",
  await verifyGoogleIdToken(await mint({ ...goodClaims, aud: "other-app.apps.googleusercontent.com" }), CLIENT), null);
await is("SIGNED but expired -> rejected",
  await verifyGoogleIdToken(await mint({ ...goodClaims, exp: now - 7200 }), CLIENT), null);
await is("SIGNED but email_verified false -> rejected",
  await verifyGoogleIdToken(await mint({ ...goodClaims, email_verified: false }), CLIENT), null);
await is("SIGNED but unknown kid -> rejected",
  await verifyGoogleIdToken(await mint(goodClaims, "not-in-jwks"), CLIENT), null);

// Tamper: valid signature, payload swapped afterwards. The signature must fail.
const signedOk = await mint(goodClaims);
const [h, , sg] = signedOk.split(".");
const tampered = `${h}.${b64uBuf(JSON.stringify({ ...goodClaims, email: "attacker@evil.com" }))}.${sg}`;
await is("TAMPERED payload -> rejected", await verifyGoogleIdToken(tampered, CLIENT), null);

globalThis.fetch = realFetch;

console.log(`\n${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
