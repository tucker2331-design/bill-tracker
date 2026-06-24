import os

import requests

import ny_bill_tracker as ny


def _sample_bill(**overrides):
    bill = {
        "basePrintNo": "S1234",
        "session": 2025,
        "billType": {"chamber": "SENATE", "desc": "Senate", "resolution": False},
        "title": "Relates to clean water infrastructure",
        "signed": False,
        "status": {
            "statusType": "IN_ASSEMBLY_COMM",
            "statusDesc": "In Assembly Committee",
            "actionDate": "2025-06-01",
            "committeeName": "Environmental Conservation",
        },
        "sponsor": {"member": {"memberId": 42, "fullName": "Jane Q. Sponsor", "shortName": "SPONSOR"}},
        "summary": "Creates a program.",
        "actions": {
            "items": [
                {"date": "2025-01-10", "sequenceNo": 1, "chamber": "SENATE", "text": "INTRODUCED"},
                {"date": "2025-01-10", "sequenceNo": 2, "chamber": "SENATE", "text": "REFERRED TO FINANCE"},
                {"date": "2025-06-01", "sequenceNo": 1, "chamber": "ASSEMBLY", "text": "REFERRED TO ENVIRONMENTAL CONSERVATION"},
            ],
            "size": 3,
        },
        "pastCommittees": {
            "items": [
                {"chamber": "SENATE", "name": "Finance", "referenceDate": "2025-01-10T00:00"},
                {"chamber": "ASSEMBLY", "name": "Environmental Conservation", "referenceDate": "2025-06-01T00:00"},
            ],
            "size": 2,
        },
        "votes": {
            "items": [
                {
                    "voteType": "COMMITTEE",
                    "voteDate": "2025-05-01",
                    "committee": {"chamber": "SENATE", "name": "Finance"},
                    "memberVotes": {
                        "items": {
                            "AYE": {"items": [1, 2, 3], "size": 3},
                            "NAY": {"items": [4], "size": 1},
                        },
                        "size": 2,
                    },
                }
            ],
            "size": 1,
        },
        "committeeAgendas": {
            "items": [
                {
                    "agendaId": {"number": 12, "year": 2025},
                    "committeeId": {"chamber": "SENATE", "name": "Finance"},
                }
            ],
            "size": 1,
        },
    }
    bill.update(overrides)
    return bill


def test_bill_to_record_flattens_openleg_shape():
    record, counters = ny.bill_to_record(_sample_bill(), "2026-06-24T12:00:00Z")

    assert record["bill"] == "S1234"
    assert record["status_lis"] == "In Assembly Committee"
    assert record["outcome"] == "unknown_structural"
    assert record["patron"] == "Jane Q. Sponsor"
    assert record["chamber"] == "House"
    assert record["ny_origin_chamber"] == "Senate"
    assert record["ny_current_chamber"] == "Assembly"
    assert record["crossed_over"] is True
    assert record["last_committee"] == "Environmental Conservation"
    assert record["referral_count"] == 2
    assert record["last_action_date"] == "2025-06-01"
    assert [h["action"] for h in record["history"]] == [
        "INTRODUCED",
        "REFERRED TO FINANCE",
        "REFERRED TO ENVIRONMENTAL CONSERVATION",
    ]
    assert record["latest_vote"]["tally"] == "3-Y 1-N"
    assert counters["has_actions"] == 1
    assert counters["has_votes"] == 1
    assert counters["has_sponsor"] == 1
    assert counters["committee_agenda_refs"] == 1
    assert counters["outcome_source_unresolved_structural"] == 1


def test_outcome_prefers_structural_signed_boolean():
    record, counters = ny.bill_to_record(
        _sample_bill(signed=True, status={"statusType": "IN_SENATE_COMM", "statusDesc": "In Senate Committee"}),
        "2026-06-24T12:00:00Z",
    )

    assert record["outcome"] == "signed"
    assert counters["outcome_source_signed_boolean"] == 1


def test_assembly_origin_maps_to_product_house_with_ny_provenance():
    record, _ = ny.bill_to_record(
        _sample_bill(
            basePrintNo="A1234",
            billType={"chamber": "ASSEMBLY", "desc": "Assembly", "resolution": False},
            actions={
                "items": [
                    {"date": "2025-01-10", "sequenceNo": 1, "chamber": "ASSEMBLY", "text": "INTRODUCED"},
                ],
                "size": 1,
            },
            pastCommittees={
                "items": [{"chamber": "ASSEMBLY", "name": "Ways and Means", "referenceDate": "2025-01-10T00:00"}],
                "size": 1,
            },
        ),
        "2026-06-24T12:00:00Z",
    )

    assert record["chamber"] == "House"
    assert record["crossed_over"] is False
    assert record["ny_origin_chamber"] == "Assembly"
    assert record["ny_current_chamber"] == "Assembly"


def test_referral_count_distinguishes_same_named_committees_across_chambers():
    record, _ = ny.bill_to_record(
        _sample_bill(
            pastCommittees={
                "items": [
                    {"chamber": "SENATE", "name": "Rules", "referenceDate": "2025-01-10T00:00"},
                    {"chamber": "ASSEMBLY", "name": "Rules", "referenceDate": "2025-06-01T00:00"},
                ],
                "size": 2,
            },
        ),
        "2026-06-24T12:00:00Z",
    )

    assert record["referral_count"] == 2


def test_outcome_uses_structural_veto_messages_without_status_text():
    record, counters = ny.bill_to_record(
        _sample_bill(
            vetoMessages={"items": [{"message": "source object present"}], "size": 1},
            status={"statusType": "IN_SENATE_COMM", "statusDesc": "In Senate Committee"},
        ),
        "2026-06-24T12:00:00Z",
    )

    assert record["outcome"] == "vetoed"
    assert counters["outcome_source_veto_messages"] == 1


def test_unknown_chambers_and_missing_session_are_counted_not_inferred():
    record, counters = ny.bill_to_record(
        _sample_bill(
            session=None,
            billType={"chamber": "EXECUTIVE", "desc": "Executive"},
            actions={
                "items": [
                    {"date": "2025-01-10", "sequenceNo": 1, "chamber": "EXECUTIVE", "text": "DELIVERED"},
                ],
                "size": 1,
            },
            pastCommittees={"items": [], "size": 0},
            committeeAgendas={
                "items": [
                    {
                        "agendaId": {"number": 12, "year": 2025},
                        "committeeId": {"chamber": "EXECUTIVE", "name": "Governor"},
                    }
                ],
                "size": 1,
            },
        ),
        "2026-06-24T12:00:00Z",
    )

    assert record["chamber"] == ""
    assert record["ny_origin_chamber"] == ""
    assert record["ny_current_chamber"] == ""
    assert record["ny_origin_chamber_raw"] == "EXECUTIVE"
    assert record["source_url"] == ""
    assert record["history"][0]["chamber"] == ""
    assert record["history"][0]["chamber_raw"] == "EXECUTIVE"
    assert counters["unknown_origin_chamber"] == 1
    assert counters["unknown_action_chamber"] == 1
    assert counters["unknown_agenda_chamber"] == 1
    assert counters["source_url_missing_session"] == 1


def test_chamber_normalization_uses_exact_codes_not_prefixes():
    record, counters = ny.bill_to_record(
        _sample_bill(
            billType={"chamber": "SENIOR", "desc": "Unexpected future code"},
            actions={
                "items": [
                    {"date": "2025-01-10", "sequenceNo": 1, "chamber": "ASSEMBLYMAN", "text": "CODE SAMPLE"},
                ],
                "size": 1,
            },
            pastCommittees={"items": [], "size": 0},
        ),
        "2026-06-24T12:00:00Z",
    )

    assert record["chamber"] == ""
    assert record["ny_origin_chamber"] == ""
    assert record["history"][0]["chamber"] == ""
    assert record["history"][0]["chamber_raw"] == "ASSEMBLYMAN"
    assert counters["unknown_origin_chamber"] == 1
    assert counters["unknown_action_chamber"] == 1


def test_missing_action_text_is_preserved_and_counted():
    record, counters = ny.bill_to_record(
        _sample_bill(
            actions={
                "items": [
                    {"date": "2025-01-10", "sequenceNo": 1, "chamber": "SENATE", "text": ""},
                ],
                "size": 1,
            },
            pastCommittees={"items": [], "size": 0},
        ),
        "2026-06-24T12:00:00Z",
    )

    assert record["history"][0]["action"] == ""
    assert record["history"][0]["action_missing"] is True
    assert record["last_action_date"] == "2025-01-10"
    assert counters["missing_action_text"] == 1


def test_build_ny_bill_records_counts_completeness():
    class FakeClient:
        def iter_bills(self, session_year, *, full, limit, max_pages):
            assert session_year == 2025
            assert full is True
            yield _sample_bill()
            yield _sample_bill(basePrintNo="A9", sponsor={"member": None}, actions={"items": [], "size": 0})

    records, completeness = ny.build_ny_bill_records(FakeClient(), 2025, limit=1000)

    assert len(records) == 2
    assert completeness["records_written"] == 2
    assert completeness["bills_seen"] == 2
    assert completeness["patron_present"] == 1
    assert completeness["patron_missing"] == 1
    assert completeness["has_actions"] == 1
    assert completeness["has_actions_rate"] == 0.5
    assert completeness["unknown_structural_outcome"] == 2
    assert completeness["unknown_structural_outcome_rate"] == 1.0
    assert completeness["health"]["status"] == "WARN"
    assert completeness["health"]["findings"][0]["code"] == "UNKNOWN_STRUCTURAL_OUTCOME"
    assert "Assembly calendar/committee data" in completeness["calendar_scope_note"]


def test_get_json_redacts_request_exception_details():
    client = ny.NYOpenLegClient(api_key="secret-key")

    class FakeSession:
        headers = {}

        def get(self, url, params, timeout):
            response = requests.Response()
            response.status_code = 503
            response.url = f"{url}?key={params['key']}"
            raise requests.HTTPError(f"503 Server Error for url: {response.url}", response=response)

    old_sleep = ny.time.sleep
    try:
        client.session = FakeSession()
        ny.time.sleep = lambda _seconds: None
        client.get_json("/bills/2025")
    except ny.NYOpenLegError as err:
        text = str(err)
        assert "secret-key" not in text
        assert "key=" not in text
        assert "HTTPError status=503" in text
    else:
        raise AssertionError("Expected NYOpenLegError")
    finally:
        ny.time.sleep = old_sleep


def test_iter_bills_rejects_empty_page_before_declared_end():
    client = ny.NYOpenLegClient(api_key="test")

    def fake_get_json(path, **params):
        assert params["offset"] == 1
        return {"success": True, "total": 10, "offsetEnd": 1, "result": {"items": [], "size": 0}}

    client.get_json = fake_get_json
    try:
        list(client.iter_bills(2025))
    except ny.NYOpenLegError as err:
        assert "empty page before the declared end" in str(err)
    else:
        raise AssertionError("Expected NYOpenLegError")


def test_iter_bills_requires_pagination_metadata():
    client = ny.NYOpenLegClient(api_key="test")

    def fake_get_json(path, **params):
        return {"success": True, "result": {"items": [{"basePrintNo": "S1"}], "size": 1}}

    client.get_json = fake_get_json
    try:
        list(client.iter_bills(2025))
    except ny.NYOpenLegError as err:
        assert "missing pagination metadata" in str(err)
    else:
        raise AssertionError("Expected NYOpenLegError")


def test_runtime_requirements_separate_fetch_and_write():
    keys = ["NY_OPENLEG_API_KEY", "NY_SPREADSHEET_ID", "GCP_CREDENTIALS"]
    old = {k: os.environ.get(k) for k in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)

        dry = ny.runtime_requirements(write=False)
        assert [c["name"] for c in dry] == ["NY_OPENLEG_API_KEY"]
        assert dry[0]["status"] == "missing"

        write = ny.runtime_requirements(write=True)
        assert [c["name"] for c in write] == ["NY_OPENLEG_API_KEY", "NY_SPREADSHEET_ID", "GCP_CREDENTIALS"]
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
