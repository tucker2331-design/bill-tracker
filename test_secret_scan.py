#!/usr/bin/env python3
"""tools/secret_scan.py catches real credential shapes and leaves the documented public values alone.

Fake credentials are assembled at runtime so this file never holds a matching string itself (the repo-wide scan
would otherwise flag its own test)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
from secret_scan import scan_bytes  # noqa: E402

fails = 0


def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


A = "A" * 40
must_hit = {
    "GitHub token": "token = '" + "gh" + "p_" + "a1B2" * 9 + "'",
    "Google API key": "key=" + "AI" + "za" + "x" * 35,
    "Google OAuth client secret": "GOC" + "SPX-" + "y" * 28,
    "Slack webhook URL": "https://hooks." + "slack.com/services/T0ABC/B0DEF/" + "z" * 24,
    "private key block": "-----BEGIN PRIVATE" + " KEY-----\n" + A + "\n",
    "service-account private_key": '{"private_' + 'key": "-----BEGIN PRIVATE' + ' KEY-----\\n' + A + '"}',
    "Anthropic key": "sk-" + "ant-" + "q" * 40,
    "AWS access key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
}
for kind, text in must_hit.items():
    hits = scan_bytes(text.encode())
    check(f"catches {kind}", any(k == kind for _, k, _ in hits))
    check(f"{kind}: fingerprint never carries the value", all(text[6:30] not in fp for _, _, fp in hits))

must_pass = {
    "PEM parser regex (worker/sheets.js shape)": "const m = /-----BEGIN PRIVATE" + " KEY-----([\\s\\S]+?)-----END PRIVATE KEY-----/",
    "test fixture template (worker/test_sheets.mjs shape)": "`-----BEGIN PRIVATE" + " KEY-----\\n${b64}\\n-----END PRIVATE KEY-----`",
    "OAuth client ID (public by design)": "831223690000-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com",
    "words that contain sk- (risk-of, task-for)": "the risk-of-loss and task-for-tomorrow columns",
    "explicit allow tag": "gh" + "p_" + "b" * 36 + "  # secret-scan: allow (fixture)",
}
for name, text in must_pass.items():
    check(f"ignores {name}", scan_bytes(text.encode()) == [])

check("binary files are skipped", scan_bytes(b"\x00\x01" + ("gh" + "p_" + "c" * 36).encode()) == [])
check("line number is right", scan_bytes(("a\nb\n" + "AK" + "IA" + "QRSTUVWXYZ012345").encode())[0][0] == 3)

sys.exit(1 if fails else 0)
