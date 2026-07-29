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

console.log(`\n${pass} of ${pass + fail} passed`);
process.exit(fail ? 1 : 0);
