"""Goldens for tools/verification/trust_surface_guard.py — the pure verdict logic, network-free.
Run: python3 test_trust_surface_guard.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "verification"))
import trust_surface_guard as T  # noqa: E402

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
run = lambda h, concl, status="completed": {"created_at": iso(NOW - timedelta(hours=h)), "conclusion": concl,  # noqa: E731
                                             "status": status, "html_url": f"u{h}"}

# cron periods, read from structure
ok(T.cron_period("*/15 * * * *")[1] == "every 15 min", "15-minute cron")
ok(T.cron_period("0 12 * * *")[1] == "daily", "daily cron")
ok(T.cron_period("0 13 * * 1")[1] == "weekly", "weekly cron")
ok(T.cron_period("17 6 1 * *")[1] == "monthly", "monthly cron")
ok(T.cron_period("40 */6 * * *")[1] == "every 6 h", "6-hourly cron")
ok(T.cron_period("bad")[0] is None, "unreadable cron -> None")

day = T.cron_period("0 12 * * *")[0]
# 1. the 2026-10-26 case: a monthly job whose every run failed is NEVER_SUCCEEDED, not "scheduled"
v = T.judge_runs([run(26 * 24, "failure"), run(56 * 24, "failure"), run(87 * 24, "failure")], timedelta(days=31), NOW)
ok(v["state"] == "never_succeeded", f"all-failed history -> never_succeeded ({v['state']})")
# 2. healthy daily job
v = T.judge_runs([run(2, "success"), run(26, "success")], day, NOW)
ok(v["state"] == "ok" and v["fails"] == 0, f"healthy -> ok ({v})")
# 3. two failures after a success -> failing, since = the FIRST failure of the streak
v = T.judge_runs([run(2, "failure"), run(26, "failure"), run(50, "success")], day, NOW)
ok(v["state"] == "failing" and v["fails"] == 2, f"streak of 2 -> failing ({v})")
ok(v["since"] == NOW - timedelta(hours=26), f"since = first failure of the streak ({v['since']})")
# 4. cancelled / skipped runs are not evidence either way
v = T.judge_runs([run(1, "cancelled"), run(2, "success")], day, NOW)
ok(v["state"] == "ok", f"cancelled run ignored ({v['state']})")
# 5. overdue: a daily job whose last run is 5 days old
v = T.judge_runs([run(120, "success"), run(144, "success")], day, NOW)
ok(v["state"] == "overdue", f"5 days without a daily run -> overdue ({v['state']})")
# 6. the GitHub-throttling case: a */15 job that really fires every ~3-4 h is NOT overdue 2.5 h after its run
q = T.cron_period("*/15 * * * *")[0]
v = T.judge_runs([run(2.5, "success"), run(6, "success"), run(9.5, "success"), run(13, "success")], q, NOW)
ok(v["state"] == "ok", f"observed 3.5 h rhythm calibrates the grace ({v['state']})")
# 7. in-progress runs are skipped for the verdict
v = T.judge_runs([run(0.1, None, status="in_progress"), run(3, "success")], day, NOW)
ok(v["state"] == "ok", f"in-progress run skipped ({v['state']})")
# 8. no runs at all
ok(T.judge_runs([], day, NOW)["state"] == "never_run", "no runs -> never_run")

# payload detection by content
ok(T.payload_in_header(["Bill", "Title", '{"universe_count": 3633, "records_written": 3633}']), "payload found")
ok(not T.payload_in_header(["Bill", "Title", "2026-10-27T02:13:15Z"]), "timestamp in U1 -> payload missing (the #238 bug)")
ok(not T.payload_in_header(["Bill", '{"not json']), "brace-shaped non-JSON ignored")

# a failure's start date carries across runs instead of resetting
prior = {"bill_backend_checks": {"State": "failing", "SinceUTC": "2026-10-20T00:00:00Z"}}
rows = T._carry_since([{"check": "bill_backend_checks", "state": "failing", "since": None}], prior)
ok(T._iso(rows[0]["since"]) == "2026-10-20T00:00:00Z", f"since carried ({rows[0]['since']})")
rows = T._carry_since([{"check": "bill_backend_checks", "state": "ok", "since": NOW}], prior)
ok(rows[0]["since"] is None, "an OK check has no since")


# --- bot fold-ins on #247 ---
# Codex: a cancelled/skipped run must not refresh liveness. Daily job, last success 121 h ago, cancelled every 24 h since.
v = T.judge_runs([run(1, "cancelled"), run(25, "cancelled"), run(49, "cancelled"), run(73, "cancelled"),
                  run(97, "cancelled"), run(121, "success")], day, NOW)
ok(v["state"] == "overdue", f"cancellations do not keep a stalled job ok: {v['state']}")
# Codex: a diagnostic dispatch must not close a production failure.
ev = lambda r, e: {**r, "event": e}  # noqa: E731
hist = [ev(run(1, "success"), "workflow_dispatch"), ev(run(3, "failure"), "schedule"), ev(run(27, "success"), "schedule")]
ok(T.judge_runs(T.production_runs(hist, "ny_bill_tracker.yml"), day, NOW)["state"] == "failing",
   "a successful check-config dispatch does not erase a failed scheduled write")
ok(T.judge_runs(T.production_runs(hist, "incident_ledger.yml"), day, NOW)["state"] == "ok",
   "a workflow whose dispatch IS production work may recover by dispatch")
# Gemini: malformed inputs are reported, never a crash.
ok(T.cron_period(15)[0] is None and T.cron_period(None)[0] is None, "non-string cron -> unreadable, not a crash")
import tempfile  # noqa: E402
d = tempfile.mkdtemp()
open(os.path.join(d, "list.yml"), "w").write("- just\n- a list\n")
open(os.path.join(d, "ok.yml"), "w").write("name: x\non:\n  schedule:\n    - cron: '0 1 * * *'\n")
rows = {fn: (cron, why) for fn, _n, cron, why in T.scheduled_workflows(d)}
ok(rows["list.yml"][0] is None and "not a mapping" in rows["list.yml"][1], f"top-level list reported: {rows}")
ok(rows["ok.yml"] == ("0 1 * * *", ""), f"a normal workflow still parses: {rows}")

ok(T.judge_runs([run(0.05, None, status="in_progress")], timedelta(hours=6), NOW)["state"] == "running",
   "the guard's own first run (in progress, nothing completed) is not a failure")
ok("running" in T.STATES_OK, "running opens no incident")
# 2026-10-29 live false alarm: a brand-new workflow, dispatched once (filtered out), no scheduled run yet.
six = timedelta(hours=6)
ok(T.judge_runs([], six, NOW, born=NOW - timedelta(hours=1))["state"] == "not_yet_due", "new workflow, not yet due")
ok("not_yet_due" in T.STATES_OK, "not_yet_due opens no incident")
ok(T.judge_runs([], six, NOW, born=NOW - timedelta(days=3))["state"] == "never_run", "old workflow that never ran is still never_run")
ok(T.judge_runs([], six, NOW)["state"] == "never_run", "unknown birth -> no allowance (fail-closed)")
print(f"ALL {_checks} trust-surface guard tests passed")
