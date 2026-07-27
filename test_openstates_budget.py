#!/usr/bin/env python3
"""Goldens for the Open States request budget (500/day, 1/s — we sit below both). Offline, no network."""
import os
import sys
import tempfile

sys.path.insert(0, "tools/text_corpus")
import budget as B  # noqa: E402

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"  {'✓' if ok else '✗'} {label}")
    if not ok:
        print(f"      got: {got!r}  want: {want!r}")
        FAILURES.append(label)


class Clock:
    """Injected time: nothing here waits on a real second."""
    def __init__(self, t=1_700_000_000.0):
        self.t, self.slept = t, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


def fresh(clock=None):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    c = clock or Clock()
    return B.RequestBudget(state_path=path, now=c.now, sleep=c.sleep), c, path


print("— we stay UNDER the provider's limits —")
cap, spacing = B._ceiling()
check("our daily cap never exceeds theirs (500)", cap <= B.THEIR_DAILY_LIMIT, True)
check("our spacing is never faster than theirs (1.0s)", spacing >= B.THEIR_MIN_SPACING_S, True)
check("we leave real headroom rather than sitting on the edge", cap < B.THEIR_DAILY_LIMIT, True)

print("\n— an env var can LOWER the cap but never raise it past theirs —")
os.environ["OPENSTATES_DAILY_CAP"] = "99999"
try:
    import importlib
    importlib.reload(B)
    check("a huge env cap is clamped to the provider's limit", B._ceiling()[0], B.THEIR_DAILY_LIMIT)
finally:
    del os.environ["OPENSTATES_DAILY_CAP"]
    importlib.reload(B)

print("\n— spacing —")
b, c, _ = fresh()
b.spend()
b.spend()
check("a second immediate request WAITS (never bursts past 1/s)", len(c.slept), 1)
check("...and waits at least the provider's minimum", c.slept[0] >= B.THEIR_MIN_SPACING_S - 1e-9, True)

print("\n— the daily ceiling —")
b, c, _ = fresh()
cap, _ = B._ceiling()
for _ in range(cap):
    b.spend()
check("spend is tracked exactly", b.snapshot()["used"], cap)
check("remaining hits zero, not negative", b.remaining(), 0)
try:
    b.spend()
    raised = False
except B.BudgetExceeded:
    raised = True
check("exceeding the cap RAISES rather than quietly proceeding", raised, True)
check("it is a BaseException, so a broad `except Exception` cannot swallow a runaway loop",
      issubclass(B.BudgetExceeded, BaseException) and not issubclass(B.BudgetExceeded, Exception), True)

print("\n— persistence: a crash-loop must not reset the day's spend —")
b, c, path = fresh()
for _ in range(5):
    b.spend()
b2 = B.RequestBudget(state_path=path, now=c.now, sleep=c.sleep)
check("a NEW process resumes the same day's count", b2.snapshot()["used"], 5)

print("\n— UTC day rollover —")
b, c, path = fresh()
for _ in range(10):
    b.spend()
c.t += 86_400                      # next UTC day
check("the budget resets on the day boundary", b.remaining(), B._ceiling()[0])

print("\n— unreadable state never crashes a run —")
fd, bad = tempfile.mkstemp(suffix=".json")
os.close(fd)
with open(bad, "w", encoding="utf-8") as fh:
    fh.write("{not json")
b3 = B.RequestBudget(state_path=bad, now=Clock().now, sleep=lambda _s: None)
check("garbled state starts the day at zero instead of raising", b3.snapshot()["used"], 0)

print()
if FAILURES:
    print(f"❌ {len(FAILURES)} failure(s): {FAILURES}")
    sys.exit(1)
print("✅ all Open States budget goldens pass")
