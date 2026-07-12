"""Golden tests for _extract_meeting_links — the Schedule Description → (agenda, meeting, drift) parser.

LIS buries the agenda-PDF + livestream links in the Schedule API's `Description` HTML as anchors whose LABEL
is the only discriminator, and that HTML is MALFORMED (unbalanced parens, nested anchors — measured 2026-07-10).
The prior worker took the FIRST href whenever the text said agenda|docket|info, which pointed at a
registration/video page 89× on live data. This locks the label-based, BeautifulSoup parse. Fixtures are the
real shapes seen in session 20261.

Pure: no network. Run: python3 test_meeting_links.py
"""
import calendar_worker as cw

_checks = 0


def ok(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        raise AssertionError(msg)


A = "https://lis.blob.core.windows.net/files/1005520.PDF"
V = "https://virginia-senate.granicus.com/ViewPublisher.php?view_id=3"

# 1. Standard past meeting: an (Agenda) PDF + a (View Meeting) livestream → both extracted, to the right hrefs.
a, m, u = cw._extract_meeting_links(f'Senate Finance <a href="{A}">(Agenda)</a> <a href="{V}">(View Meeting)</a>')
ok(a == A and m == V, f"agenda+meeting split by label -> {a} | {m}")
ok(u == [], f"no drift for known labels -> {u}")

# 2. THE 89-BUG REGRESSION: a description with ONLY a livestream (video host) must NOT yield an agenda_url.
a, m, u = cw._extract_meeting_links(f'House Rules <a href="{V}">(View Meeting)</a>')
ok(a == "" and m == V, f"video-only → agenda stays empty (the 89-mis-fetch bug) -> {a!r} | {m}")

# 3. FUTURE meeting: livestream posted, agenda not yet → ("", meeting). The card shows "agenda not posted yet".
a, m, u = cw._extract_meeting_links('Upcoming <a href="https://www.youtube.com/watch?v=x">(View Meeting)</a>')
ok(a == "" and m.endswith("watch?v=x"), f"future meeting: meeting link, no agenda -> {a!r} | {m}")

# 4. Combined "(Agenda and View Meeting)" — one href fills BOTH roles.
a, m, u = cw._extract_meeting_links(f'<a href="{A}">(Agenda and View Meeting)</a>')
ok(a == A and m == A, f"combined label fills agenda AND meeting -> {a} | {m}")

# 5. MALFORMED HTML (unbalanced parens, trailing junk) — BeautifulSoup must still recover the two hrefs.
a, m, u = cw._extract_meeting_links(f'<a href="{A}">(Agenda) </a>(View Meeting) <a href="{V}">(View Meeting)</a>')
ok(a == A and m == V, f"malformed parens still parse -> {a} | {m}")

# 6. Committee-info page (and LIS's own typo 'Subommittee Info', ×17 live) → benign: no link, NO drift.
for label in ("Committee Info", "Subcommittee Info", "Subommittee Info"):
    a, m, u = cw._extract_meeting_links(f'<a href="https://hac.virginia.gov/">{label}</a>')
    ok(a == "" and m == "" and u == [], f"{label!r}: benign, not surfaced, not drift -> a={a!r} u={u}")

# 7. Registration / materials → benign (known non-agenda supporting links), NOT drift.
a, m, u = cw._extract_meeting_links('<a href="https://event.webinarjam.com/register/16/x">(Registration)</a>'
                                    '<a href="https://lis.blob.core.windows.net/files/9.PDF">(Meeting Materials)</a>')
ok(a == "" and m == "" and u == [], f"registration+materials are benign, not agenda -> a={a!r} u={u}")

# 8. A genuinely NEW label (not agenda/meeting/benign) → reported as drift, never mis-surfaced.
a, m, u = cw._extract_meeting_links('<a href="https://x/y">(Hologram Briefing)</a>')
ok(a == "" and m == "" and u == ["hologram briefing"], f"novel label → drift canary -> {u}")

# 9. No anchors at all → clean empties (a relative-time-only description).
a, m, u = cw._extract_meeting_links("30 minutes after adjournment")
ok(a == "" and m == "" and u == [], "no anchors → empties")
a, m, u = cw._extract_meeting_links("")
ok(a == "" and m == "" and u == [], "empty description → empties")
a, m, u = cw._extract_meeting_links(None)
ok(a == "" and m == "" and u == [], "None description → empties (locks the falsy-guard contract)")

# 10. Non-absolute href (root-relative/mailto) → never surfaced as a link, reported via the drift canary.
#     Measured 2026-07-12: 0/3,042 live anchors are non-absolute; this guards the day LIS changes that
#     (a relative href written to the sheet would break against the SPA's own domain). Gemini #214 fold-in.
a, m, u = cw._extract_meeting_links('<a href="/schedule/agenda.pdf">(Agenda)</a>')
ok(a == "" and m == "", f"root-relative href never surfaced -> a={a!r} m={m!r}")
ok(u == ["non-absolute href: agenda"], f"root-relative href reported as drift -> {u}")

# 11. Word-boundary guard on the meeting regex: "Preview Meeting"/"Downstream" must NOT classify as a
#     livestream (the label is drift, not a meeting link). Gemini #214 fold-in.
a, m, u = cw._extract_meeting_links('<a href="https://x/y">(Preview Meeting Notes)</a>')
ok(m == "", f"'preview meeting' must not match view-meeting -> m={m!r}")
a, m, u = cw._extract_meeting_links(f'<a href="{V}">(View Meeting)</a>')
ok(m == V, "real '(View Meeting)' still matches with boundaries")

# ── _agenda_fetch_target — the bill-extraction FETCH target selector (open_anti_patterns #13) ──
# The FETCH path must pick a REAL agenda/docket, or a committee homepage to mine, NEVER a livestream or a
# registration/notice page (the old first-href heuristic regexed bill numbers out of those, ~298 live).
C = "https://virginiageneralassembly.gov/house/committees/appropriations"   # a self-hosted committee homepage

# 12. A direct (Agenda) PDF wins outright — that's the fetch target.
ok(cw._agenda_fetch_target(f'<a href="{A}">(Agenda)</a> <a href="{V}">(View Meeting)</a>') == A,
   "agenda PDF is the fetch target over a livestream")

# 13. THE #13 BUG: livestream/registration first, agenda later → must still pick the agenda, not the video.
ok(cw._agenda_fetch_target(f'<a href="{V}">(View Meeting)</a> <a href="{A}">(Agenda)</a>') == A,
   "agenda wins even when the livestream anchor comes first (the 82 retargeted rows)")

# 14. Livestream / registration ONLY → NO fetch (was the 89-bug: fetching a video/webinar page for bills).
ok(cw._agenda_fetch_target(f'<a href="{V}">(View Meeting)</a>') == "",
   "video-only → no fetch target")
ok(cw._agenda_fetch_target('<a href="https://event.webinarjam.com/register/16/x">(Registration)</a>') == "",
   "registration-only → no fetch target")
ok(cw._agenda_fetch_target('<a href="https://lis.blob.core.windows.net/files/9.PDF">(Public Hearings Notice)</a>') == "",
   "a public-hearing NOTICE pdf is not an agenda → no fetch (the 15 dropped)")

# 15. No direct agenda, but a committee-info homepage → mine it (the ~194 self-hosted-docket cases).
ok(cw._agenda_fetch_target(f'<a href="{C}">Committee Info</a>') == C,
   "committee homepage is the rogue-nav fallback when no direct agenda")
ok(cw._agenda_fetch_target(f'<a href="{C}">Subcommittee Info</a>') == C, "subcommittee-info homepage too")

# 16. Direct agenda beats a committee homepage even if the homepage anchor is first.
ok(cw._agenda_fetch_target(f'<a href="{C}">Committee Info</a> <a href="{A}">(Agenda)</a>') == A,
   "a real agenda always outranks the homepage fallback")

# 17. Non-absolute / empty / no-anchor → no fetch (never a relative or malformed target).
ok(cw._agenda_fetch_target('<a href="/x/agenda.pdf">(Agenda)</a>') == "", "non-absolute agenda href → no fetch")
ok(cw._agenda_fetch_target("30 minutes after adjournment") == "", "no anchors → no fetch")
ok(cw._agenda_fetch_target(None) == "" and cw._agenda_fetch_target("") == "", "None/empty → no fetch")

print(f"ALL {_checks} meeting-link tests passed")
