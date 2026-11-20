#!/usr/bin/env python3
"""Fail if a live credential is committed — the check GitHub stops doing for us once the repo is private.

WHY (owner, 2026-11-19): the repo is going private. GitHub's free secret scanning covers PUBLIC repositories; a
private personal repo loses it. This keeps the scan ours, mechanical, and on every push (prepush_audit.py runs it
repo-wide; CI runs that on every PR). docs/ideas/going_private.md has the audit that motivated it.

WHAT: high-confidence credential shapes only — a private-key block WITH its body, service-account JSON, Google API
keys and OAuth client secrets, GitHub/Slack/Anthropic/OpenAI-project/AWS/Stripe tokens, Slack and Discord webhook
URLs. Deliberately NOT flagged, because they are public by design and documented as such:
  * the Google OAuth client ID (it ships in every sign-in page);
  * the two LIS `WebAPIKey` values (docs/knowledge/lis_api_reference.md: "Both are PUBLIC");
  * spreadsheet / D1 IDs (identifiers; access is governed by sharing and the Worker's gate).
A line that must hold such a shape on purpose (a test fixture) carries `secret-scan: allow` on the same line.

OUTPUT never prints a value: path:line, the kind, and a masked fingerprint (first 4 chars + length).

Usage:
  python3 tools/secret_scan.py            # every tracked file in the working tree (exit 1 on a hit)
  python3 tools/secret_scan.py --history  # every blob in every commit on every fetched branch
  python3 tools/secret_scan.py --commits origin/main..HEAD   # tree + every file version those commits wrote
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

PATTERNS: dict[str, re.Pattern[bytes]] = {
    "private key block": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----(?:\s|\\n)+[A-Za-z0-9+/=]{40,}"),
    "service-account private_key": re.compile(rb'"private_key"\s*:\s*"-----BEGIN'),
    "Google API key": re.compile(rb"AIza[0-9A-Za-z_\-]{35}"),
    "Google OAuth client secret": re.compile(rb"GOCSPX-[A-Za-z0-9_\-]{20,}"),
    "GitHub token": re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}"),
    "Anthropic key": re.compile(rb"\bsk-ant-[A-Za-z0-9_\-]{30,}"),
    "OpenAI project key": re.compile(rb"\bsk-proj-[A-Za-z0-9_\-]{30,}"),
    "Slack token": re.compile(rb"\bxox[abposr]-\d+-[A-Za-z0-9\-]{10,}"),
    "Slack webhook URL": re.compile(rb"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{12,}"),
    "Discord webhook URL": re.compile(rb"discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]{20,}"),
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "Stripe live key": re.compile(rb"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}"),
}
ALLOW = b"secret-scan: allow"
MAX_BYTES = 20 * 1024 * 1024


def scan_bytes(data: bytes) -> list[tuple[int, str, str]]:
    """(line number, kind, masked fingerprint) for every hit in one file's bytes. Pure, so it is testable."""
    if b"\x00" in data[:8192]:
        return []                                   # binary (sqlite, images): no text credential shapes to read
    hits = []
    for kind, rx in PATTERNS.items():
        for m in rx.finditer(data):
            start = data.rfind(b"\n", 0, m.start()) + 1
            end = data.find(b"\n", m.end())
            if ALLOW in data[start:end if end != -1 else len(data)]:
                continue
            value = m.group(0)
            hits.append((data.count(b"\n", 0, m.start()) + 1, kind, f"{value[:4].decode(errors='replace')}… len {len(value)}"))
    return hits


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def _read(path: str) -> bytes | None:
    """The file's bytes (capped), or None when a tracked path has nothing to read here: deleted in the working tree,
    or a submodule directory. The caller COUNTS those and prints them; they are never silently skipped."""
    try:
        with open(path, "rb") as f:
            return f.read(MAX_BYTES + 1)
    except (FileNotFoundError, IsADirectoryError):
        return None


def scan_tree(notes: list[str]) -> list[str]:
    out, unreadable = [], []
    for path in os.fsdecode(_git("ls-files", "-z")).split("\0"):
        if not path:
            continue                                # the trailing NUL's empty field, not a path
        data = _read(path)
        if data is None:
            unreadable.append(path)
            continue
        if b"\x00" in data[:8192]:
            continue                                # binary (sqlite, pickle, images) at any size: no text shapes
        if len(data) > MAX_BYTES:
            out.append(f"{path}: larger than {MAX_BYTES // 2**20} MB — not scanned, check it by hand")
            continue
        out += [f"{path}:{ln}: {kind} ({fp})" for ln, kind, fp in scan_bytes(data)]
    if unreadable:
        notes.append(f"{len(unreadable)} tracked path(s) not in the working tree, not scanned: "
                     + ", ".join(unreadable[:5]) + (" …" if len(unreadable) > 5 else ""))
    return out


def _scan_blobs(paths: dict[str, set[str]], label: str) -> list[str]:
    """Scan each blob once; report it under one of the paths it was seen at. Objects this clone lacks are counted."""
    cat = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert cat.stdin and cat.stdout
    out, missing = [], 0
    try:
        for sha, ps in paths.items():
            cat.stdin.write(sha.encode() + b"\n")
            cat.stdin.flush()
            header = cat.stdout.readline().split()
            if len(header) < 3:
                missing += 1                        # "<sha> missing": an object this clone lacks — counted, reported
                continue
            data = cat.stdout.read(int(header[2]))
            cat.stdout.read(1)
            if header[1] != b"blob":
                continue                            # trees and commits carry no file text
            for ln, kind, fp in scan_bytes(data):
                out.append(f"{sorted(ps)[0]}:{ln}: {kind} ({fp}) [{label} {sha[:8]}]")
    finally:
        cat.stdin.close()
        cat.wait()
    if missing:
        out.append(f"{missing} object(s) missing from this clone — NOT fully scanned (run `git fetch --unshallow`)")
    return out


def _shallow() -> bool:
    return _git("rev-parse", "--is-shallow-repository").strip() == b"true"


def scan_history() -> list[str]:
    """Every blob in every commit on every fetched branch. A shallow clone cannot see its omitted ancestry, so it is
    reported as an incomplete scan (a failure), never as clean (Codex #278)."""
    if _shallow():
        return ["this is a shallow clone — history NOT fully scanned; run `git fetch --unshallow` first"]
    paths: dict[str, set[str]] = {}
    for line in os.fsdecode(_git("rev-list", "--all", "--objects")).splitlines():
        sha, _, p = line.partition(" ")
        if p:
            paths.setdefault(sha, set()).add(p)
    return _scan_blobs(paths, "history blob")


def scan_commits(rev_range: str) -> list[str]:
    """Every file version written by the commits in `rev_range` (e.g. origin/main..HEAD). A push whose first commit
    adds a token and second removes it leaves the token in history; the tree scan alone cannot see it (Codex #278)."""
    paths: dict[str, set[str]] = {}
    raw = _git("log", "--raw", "--no-abbrev", "--no-renames", "--format=", rev_range)
    for line in os.fsdecode(raw).splitlines():
        if not line.startswith(":"):
            continue                                # blank separator lines between commits, not file entries
        meta, _, path = line.partition("\t")
        new_sha = meta.split()[3]
        if new_sha.strip("0"):                      # all zeros = the file was deleted: nothing written
            paths.setdefault(new_sha, set()).add(path)
    return _scan_blobs(paths, "commit blob")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", action="store_true", help="every blob in every commit on every fetched branch")
    ap.add_argument("--commits", metavar="RANGE", help="also every file version written by the commits in RANGE")
    ns = ap.parse_args()
    notes: list[str] = []
    hits = scan_history() if ns.history else scan_tree(notes)
    if ns.commits:
        hits += scan_commits(ns.commits)
    for n in notes:
        print("secret_scan: note: " + n)
    if hits:
        print("secret_scan: possible committed credential(s) — rotate first, then remove:")
        for h in hits:
            print("  ✗ " + h)
        return 1
    where = "in any commit" if ns.history else "in tracked files" + (f" or the commits in {ns.commits}" if ns.commits else "")
    print("secret_scan: no credential shapes found " + where)
    return 0


if __name__ == "__main__":
    sys.exit(main())
