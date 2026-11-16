#!/usr/bin/env python3
"""sheets_retry — a 429 is waited out (5/10/20/40 s), anything else raises at once, every retry is counted.
No network: fake APIError responses, an injected sleep."""
import sys
from gspread.exceptions import APIError
import sheets_retry as R

FAILS = 0
def check(name, ok):
    global FAILS
    print(("PASS " if ok else "FAIL ") + name); FAILS += 0 if ok else 1

class Resp:
    def __init__(self, code): self.status_code = code; self.text = "{}"
    def json(self): return {"error": {"code": self.status_code, "message": "x", "status": "x"}}

def err(code): return APIError(Resp(code))

def flaky(codes):
    seq = list(codes)
    def fn():
        if seq: raise err(seq.pop(0))
        return "ok"
    return fn

slept = []
R._counts.update(retries=0, exhausted=0)
check("two 429s then success -> result, waits 5 then 10", R.call_with_retry(flaky([429, 429]), slept.append) == "ok" and slept == [5, 10])
check("retries counted", R.retries() == 2 and R.exhausted() == 0)
slept.clear()
try:
    R.call_with_retry(flaky([403]), slept.append); check("403 raises", False)
except APIError:
    check("a 403 raises at once, no wait", slept == [])
try:
    R.call_with_retry(flaky([500]), slept.append); check("500 raises", False)
except APIError:
    check("a 500 raises at once (not a rate limit)", slept == [])
slept.clear()
try:
    R.call_with_retry(flaky([429] * 5), slept.append); check("persistent 429 raises", False)
except APIError:
    check("a 429 that outlasts every wait raises, after 75 s of waits", slept == [5, 10, 20, 40] and sum(slept) == 75)
check("the give-up is counted", R.exhausted() == 1 and R.retries() == 6)
check("waits span more than one quota minute", sum(R.WAITS_S) > 60)

# the real gspread client path: RetryingHTTPClient.request -> HTTPClient.request -> session.request
class OkResp(Resp):
    ok = True
class BadResp(Resp):
    ok = False
class FakeSession:
    def __init__(self, codes): self.codes = list(codes); self.calls = 0
    def request(self, **kw):
        self.calls += 1
        c = self.codes.pop(0)
        return OkResp(c) if c == 200 else BadResp(c)
client = R.RetryingHTTPClient(auth=None, session=FakeSession([429, 200]))
R.WAITS_S[:] = [0, 0, 0, 0]   # no real sleeping in the integration check
check("gspread's own request path retries a 429 and returns the 200", client.request("get", "https://x").status_code == 200
      and client.session.calls == 2)
check("authorize() hands gspread the retrying client", "http_client=RetryingHTTPClient" in open(R.__file__).read())
sys.exit(1 if FAILS else 0)
