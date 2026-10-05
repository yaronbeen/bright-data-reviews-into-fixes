"""Frozen-candidate regressions for snapshot mapping and decoder failures."""

import hashlib
import io
import json
import stat
from contextlib import nullcontext
from http.client import IncompleteRead
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from reviews_into_fixes import cli
from reviews_into_fixes.brightdata import AMAZON_DATASET, HttpRequest, HttpResponse, TransportError, plan, resume


NOW = "2026-10-05T00:00:00Z"
AMAZON_A = "https://www.amazon.com/dp/B012345678"
AMAZON_B = "https://www.amazon.com/dp/B098765432"
UNAPPROVED_URL = "https://www.amazon.com/dp/B111111111"
SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/snap_mapping?format=json"
DEEP_JSON = b"[" * 2000 + b"0" + b"]" * 2000


@pytest.fixture
def pending_case(request, monkeypatch, tmp_path):
    urls = getattr(request, "param", [AMAZON_A, AMAZON_B])
    page_job = {
        "id": "help", "kind": "web_page", "role": "product_instructions",
        "source_id": "prior", "url": "https://docs.python.org/3/",
    }
    review_job = {
        "id": "reviews", "kind": "amazon_reviews", "role": "review",
        "source_prefix": "resumed", "urls": urls, "max_reviews": 1,
    }
    manifest = {
        "schema_version": "1.0", "project": "reviews-into-fixes",
        "jobs": [page_job, review_job],
    }
    prior_source = {
        "id": "prior", "kind": "page", "role": "product_instructions",
        "url": page_job["url"], "title": "Invented help", "text": "Setup instructions.",
        "status": "collected", "observed_at": NOW, "published_at": None,
        "provider_date": None, "record_id": None, "record_id_origin": "none",
        "provenance": "synthetic_fixture",
    }
    receipt = {
        "schema_version": "1.0", "project": "reviews-into-fixes",
        "manifest_sha256": plan(manifest)["manifest_sha256"], "status": "pending",
        "provider_completeness": "unknown", "requests_made": 2,
        "returned_records": 0, "retained_records": 1, "excluded_records": 0,
        "jobs": [
            {
                "id": "help", "kind": "web_page", "state": "processed",
                "original_job": page_job, "requested_records": None,
                "returned_records": 0, "retained_records": 1, "excluded_records": 0,
                "snapshot_id": None, "error_code": None, "query_metadata": None,
            },
            {
                "id": "reviews", "kind": "amazon_reviews", "state": "pending",
                "original_job": review_job, "requested_records": len(urls),
                "returned_records": 0, "retained_records": 0, "excluded_records": 0,
                "snapshot_id": "snap_mapping", "error_code": "pending_snapshot",
                "query_metadata": None,
            },
        ],
        "warnings": [], "provider_cost_usd": None,
    }
    library = {
        "schema_version": "1.0", "project": "reviews-into-fixes",
        "transport_contract_version": "1.0", "sources": [prior_source], "receipt": receipt,
    }
    nonce = hashlib.sha256(request.node.nodeid.encode()).hexdigest()
    approval = {
        "schema_version": "1.0", "project": "reviews-into-fixes",
        "approval_id": "regression-" + nonce[:16], "nonce": nonce,
        "manifest_sha256": hashlib.sha256(json.dumps(
            receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "issued_at": "2026-10-04T23:50:00Z", "expires_at": "2026-10-05T00:05:00Z",
        "max_requests": 1, "max_retained_records": 1 + len(urls),
        "approved_urls": [SNAPSHOT_URL], "account_budget_confirmed": True,
        "target_permissions_confirmed": True, "remote_resolution_risk_accepted": True,
    }
    library_path = tmp_path / "pending.library.json"
    library_path.write_text(json.dumps(library))
    approval_path = tmp_path / "resume.approval.json"
    approval_path.write_text(json.dumps(approval))
    output = tmp_path / "result.library.json"
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake-mapping-token")
    monkeypatch.setattr(cli, "_system_now", lambda: NOW)
    record = {
        "url": AMAZON_B, "review_id": "invented-second-review",
        "review_header": "Invented setup report", "review_text": "Setup fails.",
        "review_posted_date": NOW,
    }
    return {
        "library": library, "approval": approval, "review_job": review_job,
        "record": record, "output": output, "state": tmp_path / "state",
        "argv": ["resume", str(library_path), "--out", str(output), "--live",
                 "--accept-charges", "--approval", str(approval_path)],
        "approval_path": approval_path,
    }


def test_resume_second_approved_input_keeps_its_own_citation(pending_case):
    calls = []
    result = resume(
        pending_case["library"]["receipt"], approval=pending_case["approval"],
        api_key="fake-mapping-token", now=NOW,
        transport=lambda request: calls.append(request) or HttpResponse(
            200, {}, json.dumps([pending_case["record"]]).encode()
        ),
    )

    assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == SNAPSHOT_URL
    assert len(result["sources"]) == 1
    assert result["sources"][0]["url"] == AMAZON_B
    assert result["sources"][0]["record_id"] == "invented-second-review"
    assert result["receipt"]["requests_made"] == 3
    assert result["receipt"]["retained_records"] == 2
    assert result["receipt"]["jobs"][0] == pending_case["library"]["receipt"]["jobs"][0]


@pytest.mark.parametrize("record_url", [None, UNAPPROVED_URL], ids=["missing", "out-of-scope"])
def test_resume_multi_input_excludes_unmapped_records(pending_case, record_url):
    record = dict(pending_case["record"])
    if record_url is None:
        record.pop("url")
    else:
        record["url"] = record_url
    calls = []
    result = resume(
        pending_case["library"]["receipt"], approval=pending_case["approval"],
        api_key="fake-mapping-token", now=NOW,
        transport=lambda request: calls.append(request) or HttpResponse(
            200, {}, json.dumps([record]).encode()
        ),
    )

    assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == SNAPSHOT_URL
    assert result["sources"] == []
    receipt = result["receipt"]
    assert receipt["status"] == "processed_with_exclusions"
    assert receipt["requests_made"] == 3
    assert (receipt["returned_records"], receipt["retained_records"], receipt["excluded_records"]) == (1, 1, 1)
    assert receipt["jobs"][1]["excluded_records"] == 1
    assert receipt["jobs"][0] == pending_case["library"]["receipt"]["jobs"][0]
    assert any(warning["code"] == "invalid_record" for warning in receipt["warnings"])


def test_resume_excludes_provider_error_even_with_valid_review_fields(pending_case):
    record = {**pending_case["record"], "error_code": "dead_page"}
    calls = []
    result = resume(
        pending_case["library"]["receipt"], approval=pending_case["approval"],
        api_key="fake-mapping-token", now=NOW,
        transport=lambda request: calls.append(request) or HttpResponse(
            200, {}, json.dumps([record]).encode()
        ),
    )

    assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == SNAPSHOT_URL
    assert result["sources"] == []
    receipt = result["receipt"]
    assert receipt["status"] == "processed_with_exclusions"
    assert receipt["requests_made"] == 3
    assert (receipt["returned_records"], receipt["retained_records"], receipt["excluded_records"]) == (1, 1, 1)
    assert receipt["jobs"][1]["excluded_records"] == 1
    assert any(warning["code"] == "dead_page" for warning in receipt["warnings"])


@pytest.mark.parametrize("pending_case", [[AMAZON_A]], indirect=True)
@pytest.mark.parametrize("record_url", [None, UNAPPROVED_URL], ids=["missing", "out-of-scope"])
def test_resume_sole_input_maps_record_to_the_only_approved_target(pending_case, record_url):
    record = dict(pending_case["record"])
    if record_url is None:
        record.pop("url")
    else:
        record["url"] = record_url
    calls = []
    result = resume(
        pending_case["library"]["receipt"], approval=pending_case["approval"],
        api_key="fake-mapping-token", now=NOW,
        transport=lambda request: calls.append(request) or HttpResponse(
            200, {}, json.dumps([record]).encode()
        ),
    )

    assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == SNAPSHOT_URL
    assert len(result["sources"]) == 1 and result["sources"][0]["url"] == AMAZON_A
    assert result["receipt"]["status"] == "processed"
    assert result["receipt"]["requests_made"] == 3
    assert result["receipt"]["excluded_records"] == 0


@pytest.mark.parametrize("body", [DEEP_JSON, b"[" * 10000 + b"0" + b"]" * 10000], ids=["depth-2000", "depth-10000"])
def test_resume_cli_deep_json_is_accounted_invalid_response_with_saved_library(pending_case, monkeypatch, capsys, body):
    calls = []
    monkeypatch.setattr(cli, "_transport", lambda request: calls.append(request) or HttpResponse(200, {}, body))

    try:
        code = cli.main(pending_case["argv"])
    except RecursionError as exc:
        captured = capsys.readouterr()
        recoveries = list(pending_case["state"].rglob("*.library.json"))
        pytest.fail(
            f"RecursionError escaped after {len(calls)} GET; stderr={captured.err!r}; "
            f"output_exists={pending_case['output'].exists()}; recovery_libraries={len(recoveries)}: {exc}",
            pytrace=False,
        )
    finally:
        assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == SNAPSHOT_URL

    assert code == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["code"] == "invalid_response"
    assert error["requests_made"] == 3 and error["requests_this_run"] == 1
    assert error["recovery_saved"] is True
    assert error["source_ids"] == ["prior"] and error["job_ids"] == ["help", "reviews"]
    saved_path = Path(error["recovery_path"])
    saved = json.loads(saved_path.read_text())
    assert saved["sources"] == pending_case["library"]["sources"]
    assert saved["receipt"]["status"] == "transport_failed"
    assert saved["receipt"]["requests_made"] == 3
    assert saved["receipt"]["jobs"] == pending_case["library"]["receipt"]["jobs"]
    assert saved["receipt"]["jobs"][1]["snapshot_id"] == "snap_mapping"
    assert saved["receipt"]["provider_completeness"] == "unknown"
    assert any(warning["code"] == "invalid_response" for warning in saved["receipt"]["warnings"])
    assert stat.S_IMODE(saved_path.stat().st_mode) == 0o600
    assert "fake-mapping-token" not in json.dumps(saved) + captured.err


@pytest.mark.parametrize("body", [DEEP_JSON, b"[" * 10000 + b"0" + b"]" * 10000], ids=["depth-2000", "depth-10000"])
def test_collect_cli_deep_json_is_accounted_invalid_response_inside_dispatch(pending_case, monkeypatch, capsys, body):
    manifest = {
        "schema_version": "1.0", "project": "reviews-into-fixes",
        "jobs": [pending_case["review_job"]],
    }
    manifest_path = pending_case["output"].with_name("collect.manifest.json")
    manifest_path.write_text(json.dumps(manifest))
    approval = {
        **pending_case["approval"],
        "manifest_sha256": plan(manifest)["manifest_sha256"],
        "approved_urls": [AMAZON_A, AMAZON_B],
    }
    pending_case["approval_path"].write_text(json.dumps(approval))
    calls = []
    monkeypatch.setattr(cli, "_transport", lambda request: calls.append(request) or HttpResponse(200, {}, body))

    try:
        code = cli.main([
            "collect", str(manifest_path), "--out", str(pending_case["output"]),
            "--live", "--accept-charges", "--approval", str(pending_case["approval_path"]),
        ])
    except RecursionError as exc:
        captured = capsys.readouterr()
        recoveries = list(pending_case["state"].rglob("*.library.json"))
        pytest.fail(
            f"RecursionError escaped after {len(calls)} POST; stderr={captured.err!r}; "
            f"output_exists={pending_case['output'].exists()}; recovery_libraries={len(recoveries)}: {exc}",
            pytrace=False,
        )
    finally:
        assert len(calls) == 1 and calls[0].method == "POST"
        assert calls[0].url == (
            "https://api.brightdata.com/datasets/v3/scrape?"
            f"dataset_id={AMAZON_DATASET}&format=json&include_errors=true"
        )

    assert code == 3
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "status": "transport_failed", "requests_made": 1, "out": str(pending_case["output"]),
    }
    saved = json.loads(pending_case["output"].read_text())
    assert saved["sources"] == []
    assert saved["receipt"]["status"] == "transport_failed"
    assert saved["receipt"]["requests_made"] == 1
    assert saved["receipt"]["provider_completeness"] == "unknown"
    assert len(saved["receipt"]["jobs"]) == 1
    job = saved["receipt"]["jobs"][0]
    assert job["id"] == "reviews" and job["original_job"] == pending_case["review_job"]
    assert job["state"] == "transport_failed" and job["error_code"] == "invalid_response"
    assert job["snapshot_id"] is None
    assert stat.S_IMODE(pending_case["output"].stat().st_mode) == 0o600
    assert "fake-mapping-token" not in json.dumps(saved) + captured.out


@pytest.mark.parametrize("second_text", ["Setup fails.", "Setup fails after activation."], ids=["same-text", "different-text"])
def test_resume_same_record_id_across_approved_urls_is_not_deduped(pending_case, second_text):
    records = [
        {**pending_case["record"], "url": AMAZON_A, "review_id": "invented-shared-id", "review_text": "Setup fails."},
        {**pending_case["record"], "url": AMAZON_B, "review_id": "invented-shared-id", "review_text": second_text},
    ]
    calls = []
    result = resume(
        pending_case["library"]["receipt"], approval=pending_case["approval"],
        api_key="fake-mapping-token", now=NOW,
        transport=lambda request: calls.append(request) or HttpResponse(200, {}, json.dumps(records).encode()),
    )

    assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == SNAPSHOT_URL
    assert len(result["sources"]) == 2
    assert {(source["url"], source["record_id"]) for source in result["sources"]} == {
        (AMAZON_A, "invented-shared-id"), (AMAZON_B, "invented-shared-id"),
    }
    assert len({source["id"] for source in result["sources"]}) == 2
    receipt = result["receipt"]
    assert receipt["status"] == "processed" and receipt["requests_made"] == 3
    assert (receipt["returned_records"], receipt["retained_records"], receipt["excluded_records"]) == (2, 3, 0)
    assert receipt["jobs"][0] == pending_case["library"]["receipt"]["jobs"][0]
    assert not any(warning["code"] in {"duplicate_record", "conflicting_record"} for warning in receipt["warnings"])


@pytest.fixture
def real_opener(request, monkeypatch):
    shape = request.param
    calls, read_sizes = [], []
    original_transport = cli._transport

    class ShortBody(io.BytesIO):
        def read(self, size=-1):
            read_sizes.append(size)
            raise IncompleteRead(b"private partial body", 7)

    def open_request(raw_request, timeout):
        calls.append((raw_request, timeout))
        if shape == "wrapped-timeout":
            raise URLError(TimeoutError("private detail"))
        if shape == "http-error-incomplete":
            raise HTTPError(raw_request.full_url, 502, "private HTTP reason", {}, ShortBody())
        assert shape == "normal-incomplete"
        return nullcontext(SimpleNamespace(status=200, headers={}, read=ShortBody().read))

    monkeypatch.setattr(cli.urllib.request, "build_opener", lambda *handlers: SimpleNamespace(open=open_request))
    return {
        "shape": shape, "calls": calls, "read_sizes": read_sizes,
        "original_transport": original_transport,
    }


@pytest.mark.parametrize("real_opener", ["normal-incomplete", "http-error-incomplete"], indirect=True)
def test_real_transport_normalizes_incomplete_read(real_opener):
    try:
        with pytest.raises(TransportError) as failure:
            cli._transport(HttpRequest("GET", SNAPSHOT_URL, {}, b"", 5))
    finally:
        assert cli._transport is real_opener["original_transport"]
        assert len(real_opener["calls"]) == 1
        raw_request, timeout = real_opener["calls"][0]
        assert raw_request.get_method() == "GET" and raw_request.full_url == SNAPSHOT_URL and timeout == 5
        assert real_opener["read_sizes"] == [2 * 1024 * 1024 + 1]

    assert failure.value.code == "transport_error"
    assert str(failure.value) == "transport_error"


@pytest.mark.parametrize("real_opener", ["wrapped-timeout"], indirect=True)
def test_real_transport_wrapped_timeout_is_completion_unknown(real_opener):
    with pytest.raises(TransportError) as failure:
        cli._transport(HttpRequest("GET", SNAPSHOT_URL, {}, b"", 5))

    assert cli._transport is real_opener["original_transport"]
    assert len(real_opener["calls"]) == 1 and real_opener["read_sizes"] == []
    assert failure.value.code == "completion_unknown"
    assert str(failure.value) == "completion_unknown"


@pytest.mark.parametrize(("real_opener", "command", "output_failure"), [
    ("normal-incomplete", "resume", False),
    ("http-error-incomplete", "resume", False),
    ("wrapped-timeout", "resume", False),
    ("normal-incomplete", "collect", False),
    ("http-error-incomplete", "collect", False),
    ("wrapped-timeout", "collect", False),
    ("http-error-incomplete", "resume", True),
    ("http-error-incomplete", "collect", True),
], indirect=["real_opener"], ids=[
    "resume-normal-body", "resume-http-error-body", "resume-wrapped-timeout",
    "collect-normal-body", "collect-http-error-body", "collect-wrapped-timeout",
    "resume-private-recovery", "collect-private-recovery",
])
def test_cli_real_transport_failure_preserves_accounting_and_recovery(
        pending_case, real_opener, command, output_failure, monkeypatch, capsys):
    output = pending_case["output"]
    if command == "resume":
        argv = pending_case["argv"]
        expected_method, expected_url, expected_requests = "GET", SNAPSHOT_URL, 3
    else:
        manifest = {
            "schema_version": "1.0", "project": "reviews-into-fixes",
            "jobs": [pending_case["review_job"]],
        }
        manifest_path = output.with_name("collect.manifest.json")
        manifest_path.write_text(json.dumps(manifest))
        approval = {
            **pending_case["approval"], "manifest_sha256": plan(manifest)["manifest_sha256"],
            "approved_urls": [AMAZON_A, AMAZON_B],
        }
        pending_case["approval_path"].write_text(json.dumps(approval))
        argv = ["collect", str(manifest_path), "--out", str(output), "--live",
                "--accept-charges", "--approval", str(pending_case["approval_path"])]
        expected_method, expected_requests = "POST", 1
        expected_url = (
            "https://api.brightdata.com/datasets/v3/scrape?"
            f"dataset_id={AMAZON_DATASET}&format=json&include_errors=true"
        )
    if output_failure:
        original_replace = cli.os.replace
        def fail_output(source, destination):
            if Path(destination) == output:
                raise OSError("private write detail")
            return original_replace(source, destination)
        monkeypatch.setattr(cli.os, "replace", fail_output)

    try:
        code = cli.main(argv)
    except IncompleteRead:
        captured = capsys.readouterr()
        recoveries = list(pending_case["state"].rglob("*.library.json"))
        pytest.fail(
            f"IncompleteRead escaped from real cli._transport after {len(real_opener['calls'])} "
            f"{expected_method}; stderr={captured.err!r}; output_exists={output.exists()}; "
            f"recovery_libraries={len(recoveries)}",
            pytrace=False,
        )
    finally:
        assert cli._transport is real_opener["original_transport"]
        assert len(real_opener["calls"]) == 1
        raw_request, timeout = real_opener["calls"][0]
        assert raw_request.get_method() == expected_method and raw_request.full_url == expected_url
        assert 1 <= timeout <= 75
        assert real_opener["read_sizes"] == ([] if real_opener["shape"] == "wrapped-timeout" else [2 * 1024 * 1024 + 1])

    captured = capsys.readouterr()
    if output_failure:
        assert captured.out == ""
        error = json.loads(captured.err)
        assert error["code"] == "output_persist_failed"
        assert error["requests_made"] == expected_requests and error["recovery_saved"] is True
        assert error["source_ids"] == (["prior"] if command == "resume" else [])
        assert error["job_ids"] == (["help", "reviews"] if command == "resume" else ["reviews"])
        saved_path = Path(error["recovery_path"])
        assert saved_path.parent == pending_case["state"] / "reviews-into-fixes" / "recovery"
        assert not output.exists()
        if command == "resume":
            assert error["requests_this_run"] == 1
    elif command == "resume":
        assert captured.out == ""
        error = json.loads(captured.err)
        assert error["code"] == "transport_error"
        assert error["requests_made"] == 3 and error["requests_this_run"] == 1
        assert error["recovery_saved"] is True
        assert error["source_ids"] == ["prior"] and error["job_ids"] == ["help", "reviews"]
        saved_path = Path(error["recovery_path"])
    else:
        assert captured.err == ""
        summary = json.loads(captured.out)
        assert summary["requests_made"] == 1 and summary["out"] == str(output)
        saved_path = output

    saved = json.loads(saved_path.read_text())
    assert saved["receipt"]["requests_made"] == expected_requests
    assert saved["receipt"]["provider_completeness"] == "unknown"
    assert stat.S_IMODE(saved_path.stat().st_mode) == 0o600
    assert all(detail not in json.dumps(saved) + captured.out + captured.err for detail in (
        "private detail", "private partial body", "private HTTP reason", "private write detail", "fake-mapping-token",
    ))
    if command == "resume":
        assert saved["sources"] == pending_case["library"]["sources"]
        assert saved["receipt"]["jobs"] == pending_case["library"]["receipt"]["jobs"]
        assert saved["receipt"]["jobs"][1]["snapshot_id"] == "snap_mapping"
    else:
        assert saved["sources"] == [] and len(saved["receipt"]["jobs"]) == 1
        assert saved["receipt"]["jobs"][0]["id"] == "reviews"
        assert saved["receipt"]["jobs"][0]["original_job"] == pending_case["review_job"]
        assert saved["receipt"]["jobs"][0]["error_code"] == "transport_error"

    timed_out = real_opener["shape"] == "wrapped-timeout"
    expected_status = "completion_unknown" if timed_out else "transport_failed"
    assert code == (2 if output_failure else 4 if timed_out else 3), {
        "command": command, "exit": code, "status": saved["receipt"]["status"],
        "requests_made": saved["receipt"]["requests_made"],
    }
    assert saved["receipt"]["status"] == expected_status
    if command == "collect":
        assert saved["receipt"]["jobs"][0]["state"] == expected_status
