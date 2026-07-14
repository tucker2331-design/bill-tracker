"""Golden tests for the LIS endpoint-parity audit (tools/parity/endpoint_audit.py).

Network-FREE (CI-safe): the classifier is a pure function, and the "manifest covers today's LIS surface"
guarantee is checked against a FROZEN snapshot (tools/parity/testdata_live_routes_snapshot.json), not a live
fetch. That snapshot is refreshed deliberately when LIS's surface legitimately changes; a manifest edit that
stops covering a known route fails here instead of going silent in a weekly job.

Run: python3 test_endpoint_audit.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "parity"))
import endpoint_audit as ea  # noqa: E402

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


MANIFEST = json.load(open(os.path.join("tools", "parity", "consumed_endpoints.json")))

# 1. Classifier buckets a synthetic route set correctly (pure, no network).
synthetic = {
    "/Schedule/api/GetScheduleListAsync",              # consumed
    "/Authentication/api/LoginAsync",                  # non-public area
    "/Legislation/api/SaveLegislationAsync",           # write verb
    "/Vote/api/GetVoteTypeReferencesAsync",            # reference suffix
    "/LegislationText/api/getlegislationtextlistasync",# parked
    "/Zzzz/api/GetSomethingBrandNewAsync",             # NEW (the drift signal)
}
c = ea.classify(synthetic, MANIFEST)
ok("/Schedule/api/GetScheduleListAsync" in c["consumed"], "consumed route mis-bucketed")
ok("/Authentication/api/LoginAsync" in c["non_public"], "non-public AREA mis-bucketed")
ok("/Legislation/api/SaveLegislationAsync" in c["non_public"], "write VERB mis-bucketed")
ok("/Vote/api/GetVoteTypeReferencesAsync" in c["reference"], "reference SUFFIX mis-bucketed")
ok("/LegislationText/api/getlegislationtextlistasync" in c["parked"], "parked route mis-bucketed")
ok(c["new"] == ["/Zzzz/api/GetSomethingBrandNewAsync"], f"NEW detection wrong -> {c['new']}")

# 2. Case-insensitive matching (LIS ships mixed casing).
c2 = ea.classify({"/schedule/API/getschedulelistasync"}, MANIFEST)
ok("/schedule/API/getschedulelistasync" in c2["consumed"], "consumed match must be case-insensitive")

# 3. THE COVERAGE GUARANTEE: the committed manifest fully covers today's frozen LIS surface → new == 0.
snapshot = set(json.load(open(os.path.join("tools", "parity", "testdata_live_routes_snapshot.json"))))
c3 = ea.classify(snapshot, MANIFEST)
ok(c3["new"] == [], f"manifest no longer covers the LIS surface — untriaged routes: {c3['new'][:10]}")
ok(len(c3["consumed"]) >= 8, f"expected >=8 consumed routes, got {len(c3['consumed'])}")

# NB (learned 2026-07-13): a consumed route need NOT appear in the SPA bundle snapshot. Some routes we call
# directly were discovered independently and the public SPA fetches equivalents differently — verified
# GetLegislationStatusListAsync returns HTTP 200 while absent from the SPA. So there is deliberately no
# "every consumed route is in the snapshot" assertion; the reverse-parity liveness hint lives in the tool.

print(f"ALL {_checks} endpoint-audit tests passed")
