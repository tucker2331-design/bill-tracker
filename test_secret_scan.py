#!/usr/bin/env python3
"""tools/secret_scan.py catches real credential shapes and leaves the documented public values alone.

Fake credentials are assembled at runtime so this file never holds a matching string itself (the repo-wide scan
would otherwise flag its own test)."""
import os
import subprocess
import sys
import tempfile

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

# Codex #278: a token added then removed inside one push stays in history — the tree scan can't see it, --commits can.
TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "secret_scan.py")
with tempfile.TemporaryDirectory() as repo:
    def git(*a, cwd=repo):
        subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    open(os.path.join(repo, "a.txt"), "w").write("hello\n")
    git("add", "."); git("commit", "-q", "-m", "base")
    open(os.path.join(repo, "a.txt"), "w").write("tok = " + "gh" + "p_" + "d" * 36 + "\n")
    git("commit", "-q", "-am", "add")
    open(os.path.join(repo, "a.txt"), "w").write("hello\n")
    git("commit", "-q", "-am", "remove")
    run = lambda *a, cwd=repo: subprocess.run([sys.executable, TOOL, *a], cwd=cwd, capture_output=True, text=True)
    check("tree scan alone passes (the token is gone from the files)", run().returncode == 0)
    r = run("--commits", "HEAD~2..HEAD")
    check("--commits catches the token added and removed in the range", r.returncode == 1 and "GitHub token" in r.stdout)
    check("--commits output never carries the value", ("d" * 20) not in r.stdout)
    check("--history catches it too", run("--history").returncode == 1)
    # Codex #278: a shallow clone must not report its unseen ancestry as clean.
    shallow = os.path.join(repo, "shallow")
    subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + repo, shallow], check=True, capture_output=True)
    r = run("--history", cwd=shallow)
    check("--history in a shallow clone fails as incomplete, not clean", r.returncode == 1 and "shallow" in r.stdout)
    r = run("--commits", "no-such-ref..HEAD")
    check("a bad range is an error, not a pass", r.returncode != 0)

sys.exit(1 if fails else 0)
