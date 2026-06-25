import ny_calendar_probe as probe


def test_parse_sources_rejects_unknown_source_names():
    try:
        probe._parse_sources("assembly,typo")
    except ValueError as err:
        assert "typo" in str(err)
    else:
        raise AssertionError("unknown source name should fail")


def test_parse_openleg_meetings_builds_canonical_senate_rows():
    payload = {
        "success": True,
        "result": {
            "items": [
                {
                    "meetingDateTime": "2026-01-12T10:30:00",
                    "committeeId": {"chamber": "SENATE", "name": "Finance"},
                    "agendaId": {"year": 2026, "number": 4},
                }
            ],
            "size": 1,
        },
    }

    rows = probe.parse_openleg_meetings(payload, source_path="/agendas/meetings/2026-01-01/2026-02-01")

    assert len(rows) == 1
    assert rows[0].date == "2026-01-12"
    assert rows[0].time == "10:30"
    assert rows[0].time_bucket == "exact_clock"
    assert rows[0].committee == "Finance"
    assert rows[0].chamber == "Senate"
    assert rows[0].agenda_order == "4"
    assert rows[0].origin == "ny_openleg_senate_agenda"
    assert rows[0].confidence == "canonical"


def test_parse_openleg_meetings_counts_missing_time_explicitly():
    payload = {
        "result": {
            "items": [
                {
                    "meetingDate": "2026-01-12",
                    "committee": {"chamber": "SENATE", "name": "Rules"},
                }
            ]
        }
    }

    rows = probe.parse_openleg_meetings(payload, source_path="/agendas/meetings/2026-01-01/2026-02-01")

    assert rows[0].date == "2026-01-12"
    assert rows[0].time == "NO_CLOCK_SOURCE"
    assert rows[0].time_bucket == "no_clock_source"


def test_parse_assembly_agenda_index_uses_structural_detail_links():
    html = """
    <html><body>
      <a href="/leg/?agenda=2026-06-05-16.43.35.308843&ano=20&com=Rules&sh=agen2">Rules</a>
      <a href="/leg/?agenda=2026-06-05-16.43.35.308843&ano=20&com=Rules&sh=agen2">Rules duplicate</a>
      <a href="/leg/?sh=agen">Ignore self</a>
    </body></html>
    """

    rows = probe.parse_assembly_agenda_index(html, source_url="https://nyassembly.gov/leg/?sh=agen")

    assert len(rows) == 1
    assert rows[0].chamber == "Assembly"
    assert rows[0].committee == "Rules"
    assert rows[0].agenda_order == "20"
    assert rows[0].time == "NO_CLOCK_SOURCE"
    assert rows[0].origin == "ny_assembly_agenda_dom"
    assert rows[0].source.startswith("https://nyassembly.gov/leg/?agenda=")


def test_parse_assembly_agenda_detail_preserves_relative_time_label():
    html = """
    <html><body>
      <h2>Rules</h2>
      <p>OFF THE FLOOR, Monday June 1, 2026</p>
      <a href="/leg/?bn=A08495&term=2025">A08495</a>
      <a href="/leg/?bn=S01234&term=2025">S01234</a>
      <a href="/leg/?bn=A08495&term=2025">A08495 duplicate</a>
    </body></html>
    """
    url = "https://nyassembly.gov/leg/?agenda=2026-06-05-16.43.35.308843&ano=20&com=Rules&sh=agen2"

    rows = probe.parse_assembly_agenda_detail(html, source_url=url)

    assert [row.bill for row in rows] == ["A08495", "S01234"]
    assert {row.time for row in rows} == {"OFF_THE_FLOOR"}
    assert {row.time_bucket for row in rows} == {"relative_time"}
    assert {row.committee for row in rows} == {"Rules"}


def test_parse_assembly_floor_index_and_detail_mark_timeless_rows():
    index_html = """
    <a href="/leg/?calnum=63&calver=A&sh=sked2">Calendar No. 63 A</a>
    <a href="/leg/?calnum=63&calver=A&sh=sked2">duplicate</a>
    """
    detail_html = """
    <a href="/leg/?bn=A01000&term=2025">A01000</a>
    <a href="/leg/?bn=A01001&term=2025">A01001</a>
    """

    index_rows = probe.parse_assembly_floor_index(index_html, source_url="https://nyassembly.gov/leg/?sh=sked")
    detail_rows = probe.parse_assembly_floor_detail(
        detail_html,
        source_url="https://nyassembly.gov/leg/?calnum=63&calver=A&sh=sked2",
    )

    assert len(index_rows) == 1
    assert index_rows[0].time == "CALENDAR_RELEASE_ONLY"
    assert index_rows[0].time_bucket == "terminal_or_timeless"
    assert [row.bill for row in detail_rows] == ["A01000", "A01001"]
    assert {row.time_bucket for row in detail_rows} == {"terminal_or_timeless"}


def test_probe_report_keeps_time_denominator_balanced():
    rows = [
        probe.ProbeRow(time="10:30", time_bucket="exact_clock"),
        probe.ProbeRow(time="OFF_THE_FLOOR", time_bucket="relative_time"),
        probe.ProbeRow(time="NO_CLOCK_SOURCE", time_bucket="no_clock_source"),
        probe.ProbeRow(time="CALENDAR_RELEASE_ONLY", time_bucket="terminal_or_timeless"),
    ]
    audit = probe._audit("fixture", rows)

    report = probe.build_probe_report([audit])

    assert report["status"] == "INFO"
    assert report["totals"]["rows"] == 4
    assert report["totals"]["exact_clock"] == 1
    assert report["totals"]["relative_time"] == 1
    assert report["totals"]["no_clock_source"] == 1
    assert report["totals"]["terminal_or_timeless"] == 1
    assert report["totals"]["time_bucket_denominator_drift"] == 0


def test_probe_report_flags_empty_probe_as_source_gap_not_no_events():
    report = probe.build_probe_report([probe._audit("empty", [])])

    assert report["status"] == "WARN"
    assert report["health_findings"][0]["code"] == "NO_ROWS_OBSERVED"
    assert "not a claim of no events" in report["health_findings"][0]["message"]


def test_run_probe_samples_assembly_detail_pages_without_writes():
    pages = {
        probe.DEFAULT_ASSEMBLY_AGENDA_URL: """
          <a href="/leg/?agenda=2026-06-05-16.43.35.308843&ano=20&com=Rules&sh=agen2">Rules</a>
        """,
        "https://nyassembly.gov/leg/?agenda=2026-06-05-16.43.35.308843&ano=20&com=Rules&sh=agen2": """
          <p>OFF THE FLOOR</p>
          <a href="/leg/?bn=A08495&term=2025">A08495</a>
        """,
        probe.DEFAULT_ASSEMBLY_FLOOR_URL: """
          <a href="/leg/?calnum=63&calver=A&sh=sked2">Calendar No. 63 A</a>
        """,
        "https://nyassembly.gov/leg/?calnum=63&calver=A&sh=sked2": """
          <a href="/leg/?bn=A01000&term=2025">A01000</a>
        """,
    }

    old_fetch = probe._fetch_text
    try:
        probe._fetch_text = lambda _session, url: pages[url]
        report = probe.run_probe(
            from_date="2026-01-01",
            to_date="2026-02-01",
            include_openleg=False,
            include_assembly=True,
            detail_limit=1,
        )
    finally:
        probe._fetch_text = old_fetch

    audits = {audit["source"]: audit for audit in report["audits"]}
    assert report["production_write"] is False
    assert audits["assembly_agenda_index"]["rows"] == 1
    assert audits["assembly_agenda_detail_sample"]["rows"] == 1
    assert audits["assembly_agenda_detail_sample"]["counters"]["relative_time"] == 1
    assert audits["assembly_floor_detail_sample"]["rows"] == 1
    assert audits["assembly_floor_detail_sample"]["counters"]["terminal_or_timeless"] == 1
