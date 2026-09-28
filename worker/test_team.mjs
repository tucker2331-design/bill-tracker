/** Team gate tests. Run: node worker/test_team.mjs */
import { membership, teamGate, teamSet } from "./team.js";
import { readFileSync } from "node:fs";

let pass = 0, fail = 0;
const is = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : ` (got ${JSON.stringify(got)}, want ${JSON.stringify(want)})`}`);
  ok ? pass++ : fail++;
};
const env = { TEAM_EMAILS: " Tucker@Example.org, dana@example.org ;x" };

// FAIL CLOSED: a missing or empty list is "not_configured", never "member", and never "not_member" either.
is("unset -> not_configured",            membership("a@b.c", {}), "not_configured");
is("empty -> not_configured",            membership("a@b.c", { TEAM_EMAILS: "  " }), "not_configured");
is("junk only -> not_configured",        membership("a@b.c", { TEAM_EMAILS: "nobody, , ;" }), "not_configured");
is("non-string secret -> not_configured", membership("a@b.c", { TEAM_EMAILS: 42 }), "not_configured");
is("null env -> not_configured",         membership("a@b.c", null), "not_configured");
// Membership is exact on the normalised address.
is("member, case-insensitive",           membership("tucker@example.org", env), "member");
is("member, padded",                     membership("  DANA@example.org ", env), "member");
is("stranger -> not_member",             membership("eve@example.org", env), "not_member");
is("suffix trick -> not_member",         membership("xtucker@example.org", env), "not_member");
is("empty email -> not_member",          membership("", env), "not_member");
is("entries without @ dropped",          [...teamSet(env)].sort(), ["dana@example.org", "tucker@example.org"]);
// The gate the Worker applies.
is("positions: stranger -> 403",         teamGate("/positions", "eve@example.org", env)?.status, 403);
is("positions: reason carried",          teamGate("/positions", "eve@example.org", env)?.body.reason, "not_member");
is("interactions: unconfigured -> 403",  teamGate("/interactions", "tucker@example.org", {})?.body.reason, "not_configured");
is("positions: member -> proceed",       teamGate("/positions", "tucker@example.org", env), null);
is("/me: open to any signed-in user",    teamGate("/me", "eve@example.org", {}), null);
is("unknown route: still gated",         teamGate("/anything-new", "eve@example.org", env)?.status, 403);
// The handler must apply the gate BEFORE the first route that touches org data.
const src = readFileSync(new URL("./index.js", import.meta.url), "utf8");
const gateAt = src.indexOf("teamGate(path, email, env)");
const firstOrgRoute = src.indexOf('path === "/positions"');
is("gate precedes the first org route in index.js", gateAt > 0 && gateAt < firstOrgRoute, true);
is("gate follows authentication",        src.indexOf("await authenticatedEmail(request, env)") < gateAt, true);

console.log(`\n${fail ? `${fail} FAILED` : "ALL PASS"} (${pass} ok)`);
process.exit(fail ? 1 : 0);
