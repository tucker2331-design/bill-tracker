"""Read-only New York calendar source probe.

This module audits candidate New York calendar sources before any production
calendar rows or bill `Upcoming` values are written. It is intentionally a probe:
it fetches/parses official source shapes, emits health counters, and refuses to
pretend that an empty or partial source means "no events."
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html.parser
import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests


LOGGER = logging.getLogger(__name__)
DEFAULT_ASSEMBLY_AGENDA_URL = "https://nyassembly.gov/leg/?sh=agen"
DEFAULT_ASSEMBLY_FLOOR_URL = "https://nyassembly.gov/leg/?sh=sked"
DEFAULT_TIMEOUT_SECONDS = 30
SUPPORTED_SOURCES = {"openleg", "assembly"}
CHAMBER_CODE_MAP = {
    "SENATE": "Senate",
    "SEN": "Senate",
    "S": "Senate",
    "ASSEMBLY": "Assembly",
    "ASM": "Assembly",
    "A": "Assembly",
}
# Official relative-time labels are preserved as relative timing, never treated
# as exact clock events.
KNOWN_RELATIVE_TIMES = {
    "OFF THE FLOOR": "OFF_THE_FLOOR",
    "TBA": "TBA",
}


class NYCalendarProbeError(RuntimeError):
    """Raised when the probe cannot safely interpret a source response."""


@dataclass
class ProbeRow:
    date: str = ""
    time: str = "NO_CLOCK_SOURCE"
    sort_time: str = ""
    status: str = "source_observed"
    chamber: str = ""
    committee: str = ""
    bill: str = ""
    outcome: str = ""
    agenda_order: str = ""
    source: str = ""
    origin: str = ""
    diagnostic_hint: str = ""
    confidence: str = "gap"
    time_bucket: str = "no_clock_source"


@dataclass
class SourceAudit:
    source: str
    fetched: bool
    parsed: bool
    rows: int
    errors: List[str]
    counters: Dict[str, int]
    examples: List[Dict[str, Any]]


@dataclass
class Link:
    href: str
    text: str


class _AnchorParser(html.parser.HTMLParser):
    """Small structural HTML extractor for official Assembly anchors."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: List[Link] = []
        self.text_chunks: List[str] = []
        self._href_stack: List[Optional[str]] = []
        self._text_stack: List[List[str]] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        href = ""
        for key, value in attrs:
            if key.lower() == "href" and value:
                href = value
                break
        self._href_stack.append(href)
        self._text_stack.append([])

    def handle_data(self, data: str) -> None:
        text = " ".join(str(data or "").split())
        if not text:
            return
        self.text_chunks.append(text)
        if self._text_stack:
            self._text_stack[-1].append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href_stack:
            return
        href = self._href_stack.pop() or ""
        text_parts = self._text_stack.pop() if self._text_stack else []
        self.links.append(Link(href=href, text=" ".join(text_parts).strip()))


def _now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_from_to() -> tuple[str, str]:
    today = _dt.date.today()
    return today.isoformat(), (today + _dt.timedelta(days=14)).isoformat()


def _parse_sources(value: str) -> set[str]:
    sources = {part.strip().lower() for part in value.split(",") if part.strip()}
    unknown = sorted(sources - SUPPORTED_SOURCES)
    if unknown:
        raise ValueError(f"Unsupported source(s): {', '.join(unknown)}")
    if not sources:
        raise ValueError("At least one source is required.")
    return sources


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as err:
        raise SystemExit(f"{name} must be an integer") from err


def _parse_html(html: str) -> _AnchorParser:
    parser = _AnchorParser()
    parser.feed(html or "")
    return parser


def _query_map(href: str) -> Dict[str, str]:
    parsed = urlparse(href)
    query = parse_qs(parsed.query, keep_blank_values=True)
    return {key.lower(): " ".join(str(values[0]).split()) for key, values in query.items() if values}


def _full_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href).replace(" ", "%20")


def _sample_sources(rows: List[ProbeRow], limit: int) -> List[str]:
    seen: set[str] = set()
    sources: List[str] = []
    for row in rows:
        if not row.source or row.source in seen:
            # Structural skip: duplicate or sourceless rows are excluded from
            # detail sampling and remain visible through source-row counters.
            continue
        seen.add(row.source)
        sources.append(row.source)
        if len(sources) >= limit:
            break
    return sources


def _clean_label(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def _clean_bill(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace(" ", "").upper().strip()


def _first_present(source: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return _clean_label(value)
    return ""


def _nested_name(source: Dict[str, Any], *keys: str) -> str:
    node: Any = source
    for key in keys:
        if not isinstance(node, dict):
            return ""
        node = node.get(key)
    return _clean_label(node)


def _date_part(value: str) -> str:
    value = _clean_label(value)
    if not value:
        return ""
    return value[:10]


def _time_part(value: str) -> str:
    value = _clean_label(value)
    if not value:
        return ""
    if "T" in value and len(value) >= 16:
        return value[11:16]
    return ""


def _relative_time_from_text(chunks: List[str]) -> str:
    upper_chunks = [_clean_label(chunk).upper() for chunk in chunks]
    for label, token in KNOWN_RELATIVE_TIMES.items():
        if any(label in chunk for chunk in upper_chunks):
            return token
    return ""


def _items(container: Any) -> List[Any]:
    if isinstance(container, list):
        return container
    if isinstance(container, dict):
        for key in ("items", "results", "result"):
            value = container.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = _items(value)
                if nested:
                    return nested
    return []


def _norm_chamber(value: Any) -> str:
    raw = _clean_label(value).upper()
    return CHAMBER_CODE_MAP.get(raw, "")


def _result_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_result = payload.get("result")
    result = raw_result if isinstance(raw_result, (dict, list)) else {}
    items = _items(result)
    return [item for item in items if isinstance(item, dict)]


def parse_openleg_meetings(payload: Dict[str, Any], *, source_path: str) -> List[ProbeRow]:
    """Parse OpenLeg agenda meeting objects into high-confidence Senate rows."""
    rows: List[ProbeRow] = []
    for meeting in _result_items(payload):
        committee = (
            _nested_name(meeting, "committee", "name")
            or _nested_name(meeting, "committeeId", "name")
            or _first_present(meeting, ("committeeName", "name"))
        )
        chamber = (
            _norm_chamber(_nested_name(meeting, "committee", "chamber"))
            or _norm_chamber(_nested_name(meeting, "committeeId", "chamber"))
            or "Senate"
        )
        date_time = _first_present(meeting, ("meetingDateTime", "dateTime", "startDateTime", "meetingTime"))
        date = _date_part(date_time) or _first_present(meeting, ("meetingDate", "date"))
        time = _time_part(date_time) or _first_present(meeting, ("time",))
        agenda_id = meeting.get("agendaId") if isinstance(meeting.get("agendaId"), dict) else {}
        agenda_order = _first_present(agenda_id, ("number", "agendaNo"))
        if not agenda_order:
            agenda_order = _first_present(meeting, ("agendaNo", "agendaNumber"))

        if time:
            time_bucket = "exact_clock"
            rendered_time = time
            sort_time = time
        else:
            time_bucket = "no_clock_source"
            rendered_time = "NO_CLOCK_SOURCE"
            sort_time = "99:99"
        rows.append(ProbeRow(
            date=date,
            time=rendered_time,
            sort_time=sort_time,
            status="scheduled",
            chamber=chamber,
            committee=committee,
            agenda_order=agenda_order,
            source=source_path,
            origin="ny_openleg_senate_agenda",
            diagnostic_hint="openleg_agenda_meeting",
            confidence="canonical",
            time_bucket=time_bucket,
        ))
    return rows


def parse_assembly_agenda_index(html: str, *, source_url: str) -> List[ProbeRow]:
    """Parse official Assembly agenda-detail links from the agenda index page."""
    parser = _parse_html(html)
    rows: List[ProbeRow] = []
    seen: set[tuple[str, str, str]] = set()
    for link in parser.links:
        query = _query_map(link.href)
        if query.get("sh", "").lower() != "agen2":
            # Structural skip: only agenda-detail links belong in this parser.
            continue
        agenda_id = query.get("agenda", "")
        agenda_no = query.get("ano", "")
        committee = _clean_label(query.get("com", ""))
        key = (agenda_id, agenda_no, committee)
        if not agenda_id or key in seen:
            # Structural skip: source gaps are counted per audited source, while
            # malformed/duplicate links are ignored as non-rows.
            continue
        seen.add(key)
        rows.append(ProbeRow(
            time="NO_CLOCK_SOURCE",
            sort_time="99:99",
            status="agenda_link_observed",
            chamber="Assembly",
            committee=committee,
            agenda_order=agenda_no,
            source=_full_url(source_url, link.href),
            origin="ny_assembly_agenda_dom",
            diagnostic_hint="assembly_agenda_detail_link",
            confidence="official_dom",
            time_bucket="no_clock_source",
        ))
    return rows


def parse_assembly_agenda_detail(html: str, *, source_url: str) -> List[ProbeRow]:
    """Parse bill links from an official Assembly committee agenda detail page."""
    parser = _parse_html(html)
    page_query = _query_map(source_url)
    committee = _clean_label(page_query.get("com", ""))
    agenda_order = page_query.get("ano", "")
    relative_time = _relative_time_from_text(parser.text_chunks)
    rendered_time = relative_time or "NO_CLOCK_SOURCE"
    time_bucket = "relative_time" if relative_time else "no_clock_source"
    seen: set[str] = set()
    rows: List[ProbeRow] = []
    for link in parser.links:
        query = _query_map(link.href)
        bill = _clean_bill(query.get("bn") or query.get("billno") or query.get("bill"))
        if not bill or bill in seen:
            # Structural skip: only first-observed bill links are audit rows.
            continue
        seen.add(bill)
        rows.append(ProbeRow(
            time=rendered_time,
            sort_time="98:98" if relative_time else "99:99",
            status="agenda_bill_observed",
            chamber="Assembly",
            committee=committee,
            bill=bill,
            agenda_order=agenda_order,
            source=source_url,
            origin="ny_assembly_agenda_dom",
            diagnostic_hint="assembly_agenda_bill_link",
            confidence="official_dom",
            time_bucket=time_bucket,
        ))
    return rows


def parse_assembly_floor_index(html: str, *, source_url: str) -> List[ProbeRow]:
    """Parse official Assembly floor-calendar detail links."""
    parser = _parse_html(html)
    rows: List[ProbeRow] = []
    seen: set[tuple[str, str]] = set()
    for link in parser.links:
        query = _query_map(link.href)
        if query.get("sh", "").lower() != "sked2":
            # Structural skip: only floor-calendar detail links belong here.
            continue
        calnum = query.get("calnum", "")
        calver = query.get("calver", "")
        key = (calnum, calver)
        if not calnum or key in seen:
            # Structural skip: source gaps are per audited source; duplicate
            # calendar links are not emitted as rows.
            continue
        seen.add(key)
        rows.append(ProbeRow(
            time="CALENDAR_RELEASE_ONLY",
            sort_time="97:97",
            status="floor_calendar_link_observed",
            chamber="Assembly",
            agenda_order=calnum,
            source=_full_url(source_url, link.href),
            origin="ny_assembly_floor_calendar_dom",
            diagnostic_hint=f"assembly_floor_calendar_detail_link:{calver}",
            confidence="official_dom",
            time_bucket="terminal_or_timeless",
        ))
    return rows


def parse_assembly_floor_detail(html: str, *, source_url: str) -> List[ProbeRow]:
    """Parse bill links from an official Assembly floor calendar detail page."""
    parser = _parse_html(html)
    query = _query_map(source_url)
    calnum = query.get("calnum", "")
    seen: set[str] = set()
    rows: List[ProbeRow] = []
    for link in parser.links:
        link_query = _query_map(link.href)
        bill = _clean_bill(link_query.get("bn") or link_query.get("billno") or link_query.get("bill"))
        if not bill or bill in seen:
            # Structural skip: only first-observed bill links are audit rows.
            continue
        seen.add(bill)
        rows.append(ProbeRow(
            time="CALENDAR_RELEASE_ONLY",
            sort_time="97:97",
            status="floor_calendar_bill_observed",
            chamber="Assembly",
            bill=bill,
            agenda_order=calnum,
            source=source_url,
            origin="ny_assembly_floor_calendar_dom",
            diagnostic_hint="assembly_floor_calendar_bill_link",
            confidence="official_dom",
            time_bucket="terminal_or_timeless",
        ))
    return rows


def _counter_for_rows(rows: List[ProbeRow]) -> Dict[str, int]:
    counters: Dict[str, int] = {
        "rows": len(rows),
        "exact_clock": 0,
        "relative_time": 0,
        "no_clock_source": 0,
        "terminal_or_timeless": 0,
        "source_gap": 0,
        "with_bill": 0,
        "with_committee": 0,
        "with_source_url": 0,
        "unknown_time_bucket": 0,
    }
    for row in rows:
        if row.time_bucket in ("exact_clock", "relative_time", "no_clock_source", "terminal_or_timeless", "source_gap"):
            counters[row.time_bucket] += 1
        else:
            counters["unknown_time_bucket"] += 1
        if row.bill:
            counters["with_bill"] += 1
        if row.committee:
            counters["with_committee"] += 1
        if row.source:
            counters["with_source_url"] += 1
    denominator = (
        counters["exact_clock"]
        + counters["relative_time"]
        + counters["no_clock_source"]
        + counters["terminal_or_timeless"]
        + counters["source_gap"]
    )
    counters["time_bucket_denominator"] = denominator
    counters["time_bucket_denominator_drift"] = 1 if denominator != len(rows) else 0
    return counters


def _audit(source: str, rows: List[ProbeRow], *, fetched: bool = False, errors: Optional[List[str]] = None) -> SourceAudit:
    parsed = not errors
    counters = _counter_for_rows(rows)
    if fetched and parsed and not rows:
        counters["source_gap"] = 1
    return SourceAudit(
        source=source,
        fetched=fetched,
        parsed=parsed,
        rows=len(rows),
        errors=errors or [],
        counters=counters,
        examples=[asdict(row) for row in rows[:5]],
    )


def build_probe_report(audits: List[SourceAudit]) -> Dict[str, Any]:
    all_rows: List[Dict[str, Any]] = []
    health_findings: List[Dict[str, Any]] = []
    totals: Dict[str, int] = {
        "sources": len(audits),
        "sources_with_errors": 0,
        "rows": 0,
        "exact_clock": 0,
        "relative_time": 0,
        "no_clock_source": 0,
        "terminal_or_timeless": 0,
        "source_gap": 0,
        "unknown_time_bucket": 0,
        "time_bucket_denominator_drift": 0,
    }
    for audit in audits:
        totals["rows"] += audit.rows
        if audit.errors:
            totals["sources_with_errors"] += 1
            health_findings.append({
                "severity": "WARN",
                "code": "SOURCE_PROBE_ERROR",
                "source": audit.source,
                "errors": audit.errors,
            })
        if audit.fetched and audit.parsed and audit.rows == 0:
            health_findings.append({
                "severity": "WARN",
                "code": "SOURCE_GAP",
                "source": audit.source,
                "message": "Source fetched and parsed but produced zero rows; this is not a claim of no events.",
            })
        for key in ("exact_clock", "relative_time", "no_clock_source", "terminal_or_timeless", "source_gap", "unknown_time_bucket"):
            totals[key] += int(audit.counters.get(key, 0))
        if audit.counters.get("time_bucket_denominator_drift"):
            totals["time_bucket_denominator_drift"] += 1
            health_findings.append({
                "severity": "CRITICAL",
                "code": "TIME_BUCKET_DENOMINATOR_DRIFT",
                "source": audit.source,
            })
        all_rows.extend(audit.examples)

    if totals["rows"] == 0:
        health_findings.append({
            "severity": "WARN",
            "code": "NO_ROWS_OBSERVED",
            "message": "Probe produced no rows. This is a source-coverage result, not a claim of no events.",
        })

    status = "CRITICAL" if any(f["severity"] == "CRITICAL" for f in health_findings) else "WARN" if health_findings else "INFO"
    return {
        "state": "NY",
        "probe": "calendar_source_probe",
        "checked_at_utc": _now_utc(),
        "status": status,
        "totals": totals,
        "health_findings": health_findings,
        "audits": [asdict(audit) for audit in audits],
        "sample_rows": all_rows[:10],
        "production_write": False,
        "scope_note": "Read-only source probe. Does not write NY calendar rows or bill Upcoming JSON.",
    }


def _fetch_text(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def _record_source_error(source: str, err: Exception) -> str:
    LOGGER.warning(
        "NY calendar probe source failed source=%s error_type=%s",
        source,
        type(err).__name__,
        exc_info=True,
    )
    return f"{type(err).__name__}: {err}"


def run_probe(
    *,
    from_date: str,
    to_date: str,
    include_openleg: bool,
    include_assembly: bool,
    detail_limit: int = 3,
) -> Dict[str, Any]:
    audits: List[SourceAudit] = []
    if include_openleg:
        try:
            from ny_bill_tracker import NYOpenLegClient

            client = NYOpenLegClient(api_key=os.environ.get("NY_OPENLEG_API_KEY", ""))
            path = f"/agendas/meetings/{from_date}/{to_date}"
            payload = client.get_json(path)
            audits.append(_audit("openleg_agenda_meetings", parse_openleg_meetings(payload, source_path=path), fetched=True))
        except Exception as err:
            audits.append(_audit("openleg_agenda_meetings", [], fetched=False, errors=[_record_source_error("openleg_agenda_meetings", err)]))

    if include_assembly:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "bill-tracker-ny-calendar-probe/0.1 (+https://github.com/tucker2331-design/bill-tracker)",
            "Accept": "text/html,application/xhtml+xml",
        })
        try:
            html = _fetch_text(session, DEFAULT_ASSEMBLY_AGENDA_URL)
            agenda_rows = parse_assembly_agenda_index(html, source_url=DEFAULT_ASSEMBLY_AGENDA_URL)
            audits.append(_audit("assembly_agenda_index", agenda_rows, fetched=True))
        except Exception as err:
            agenda_rows = []
            audits.append(_audit("assembly_agenda_index", [], fetched=False, errors=[_record_source_error("assembly_agenda_index", err)]))

        try:
            html = _fetch_text(session, DEFAULT_ASSEMBLY_FLOOR_URL)
            floor_rows = parse_assembly_floor_index(html, source_url=DEFAULT_ASSEMBLY_FLOOR_URL)
            audits.append(_audit("assembly_floor_index", floor_rows, fetched=True))
        except Exception as err:
            floor_rows = []
            audits.append(_audit("assembly_floor_index", [], fetched=False, errors=[_record_source_error("assembly_floor_index", err)]))

        if detail_limit > 0 and agenda_rows:
            detail_rows: List[ProbeRow] = []
            detail_errors: List[str] = []
            for url in _sample_sources(agenda_rows, detail_limit):
                try:
                    detail_rows.extend(parse_assembly_agenda_detail(_fetch_text(session, url), source_url=url))
                except Exception as err:
                    detail_errors.append(f"{url}: {_record_source_error('assembly_agenda_detail_sample', err)}")
            audits.append(_audit("assembly_agenda_detail_sample", detail_rows, fetched=True, errors=detail_errors))

        if detail_limit > 0 and floor_rows:
            detail_rows = []
            detail_errors = []
            for url in _sample_sources(floor_rows, detail_limit):
                try:
                    detail_rows.extend(parse_assembly_floor_detail(_fetch_text(session, url), source_url=url))
                except Exception as err:
                    detail_errors.append(f"{url}: {_record_source_error('assembly_floor_detail_sample', err)}")
            audits.append(_audit("assembly_floor_detail_sample", detail_rows, fetched=True, errors=detail_errors))

    return build_probe_report(audits)


def runtime_requirements(*, include_openleg: bool) -> List[Dict[str, str]]:
    checks: List[Dict[str, str]] = []
    if include_openleg:
        checks.append({
            "name": "NY_OPENLEG_API_KEY",
            "required_for": "OpenLeg agenda meeting probe",
            "status": "ok" if os.environ.get("NY_OPENLEG_API_KEY", "").strip() else "missing",
            "how_to_get": "Use the same free OpenLeg API key as the NY bill engine.",
        })
    return checks


def main() -> None:
    default_from, default_to = _default_from_to()
    parser = argparse.ArgumentParser(description="Run the read-only NY calendar source probe.")
    parser.add_argument("--from-date", default=os.environ.get("NY_CALENDAR_PROBE_FROM", default_from))
    parser.add_argument("--to-date", default=os.environ.get("NY_CALENDAR_PROBE_TO", default_to))
    parser.add_argument("--sources", default=os.environ.get("NY_CALENDAR_PROBE_SOURCES", "openleg,assembly"))
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=_env_int("NY_CALENDAR_PROBE_DETAIL_LIMIT", 3),
        help="Assembly agenda/floor detail pages to sample from each index. Use 0 for index-only.",
    )
    parser.add_argument("--check-config", action="store_true", help="Print required runtime inputs and exit.")
    parser.add_argument("--output", default="", help="Optional local JSON artifact path. No Google Sheet writes are performed.")
    args = parser.parse_args()

    try:
        sources = _parse_sources(args.sources)
    except ValueError as err:
        raise SystemExit(str(err)) from err
    include_openleg = "openleg" in sources
    include_assembly = "assembly" in sources

    if args.check_config:
        checks = runtime_requirements(include_openleg=include_openleg)
        print(json.dumps({"requirements": checks}, indent=2))
        raise SystemExit(0 if all(check["status"] == "ok" for check in checks) else 1)

    report = run_probe(
        from_date=args.from_date,
        to_date=args.to_date,
        include_openleg=include_openleg,
        include_assembly=include_assembly,
        detail_limit=max(0, args.detail_limit),
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.write("\n")
    print(rendered)


if __name__ == "__main__":
    main()
