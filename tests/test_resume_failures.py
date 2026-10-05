"""Resume-specific request accounting and durable recovery regressions."""

import hashlib
import json
import stat
from pathlib import Path

import pytest

from reviews_into_fixes import cli
from reviews_into_fixes.brightdata import HttpResponse, TransportError, plan


NOW = "2026-10-05T00:00:00Z"
AMAZON_URL = "https://www.amazon.com/dp/B012345678"
SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/snap_resume?format=json"


def approval_for(receipt, approval_id):
    digest = hashlib.sha256(json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version": "1.0", "project": "reviews-into-fixes", "approval_id": approval_id,
        "nonce": hashlib.sha256(approval_id.encode()).hexdigest(), "manifest_sha256": digest,
        "issued_at": "2026-10-04T23:50:00Z", "expires_at": "2026-10-05T00:05:00Z",
        "max_requests": 1, "max_retained_records": 2, "approved_urls": [SNAPSHOT_URL],
        "account_budget_confirmed": True, "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }


@pytest.fixture
def resume_case(monkeypatch, tmp_path):
    page_job = {"id": "help", "kind": "web_page", "role": "product_instructions", "source_id": "prior",
                "url": "https://docs.python.org/3/"}
    review_job = {"id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "resumed",
                  "urls": [AMAZON_URL], "max_reviews": 1}
    manifest = {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [page_job, review_job]}
    prior_source = {"id": "prior", "kind": "page", "role": "product_instructions", "url": page_job["url"],
                    "title": "Invented help", "text": "Setup instructions.", "status": "collected",
                    "observed_at": NOW, "published_at": None, "provider_date": None, "record_id": None,
                    "record_id_origin": "none", "provenance": "synthetic_fixture"}
    jobs = [
        {"id": "help", "kind": "web_page", "state": "processed", "original_job": page_job,
         "requested_records": None, "returned_records": 0, "retained_records": 1, "excluded_records": 0,
         "snapshot_id": None, "error_code": None, "query_metadata": None},
        {"id": "reviews", "kind": "amazon_reviews", "state": "pending", "original_job": review_job,
         "requested_records": 1, "returned_records": 0, "retained_records": 0, "excluded_records": 0,
         "snapshot_id": "snap_resume", "error_code": "pending_snapshot", "query_metadata": None},
    ]
    receipt = {"schema_version": "1.0", "project": "reviews-into-fixes",
               "manifest_sha256": plan(manifest)["manifest_sha256"], "status": "pending",
               "provider_completeness": "unknown", "requests_made": 2, "returned_records": 0,
               "retained_records": 1, "excluded_records": 0, "jobs": jobs, "warnings": [], "provider_cost_usd": None}
    library = {"schema_version": "1.0", "project": "reviews-into-fixes", "transport_contract_version": "1.0",
               "sources": [prior_source], "receipt": receipt}
    library_path = tmp_path / "pending.library.json"
    library_path.write_text(json.dumps(library))
    approval_path = tmp_path / "resume.approval.json"
    approval_path.write_text(json.dumps(approval_for(receipt, "resume-first")))
    output_path = tmp_path / "result.library.json"
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake-resume-token")
    monkeypatch.setattr(cli, "_system_now", lambda: NOW)
    argv = ["resume", str(library_path), "--out", str(output_path), "--live", "--accept-charges",
            "--approval", str(approval_path)]
    return argv, library, output_path, approval_path


@pytest.mark.parametrize("outcome,expected_code,expected_state,exit_code", [
    (TimeoutError("private timeout detail"), "transport_error", "completion_unknown", 4),
    (TransportError("completion_unknown"), "transport_error", "completion_unknown", 4),
    (TransportError("transport_error"), "transport_error", "transport_failed", 3),
    (OSError("private transport detail"), "transport_error", "transport_failed", 3),
    (HttpResponse(200, {}, b"invalid-json-private-detail"), "invalid_response", "transport_failed", 3),
    (HttpResponse(200, {}, b'{"not":"an array"}'), "invalid_response", "transport_failed", 3),
    (HttpResponse(200, {}, b"[1]"), "invalid_response", "transport_failed", 3),
    (HttpResponse(401, {}, b"private provider detail"), "provider_http_error", "transport_failed", 3),
    (HttpResponse(409, {"X-Brd-Error-Code": "private"}, b""), "provider_http_error", "transport_failed", 3),
])
def test_resume_transport_and_parse_failures_account_one_get_and_save_receipt(
        outcome, expected_code, expected_state, exit_code, resume_case, monkeypatch, capsys):
    argv, library, output_path, approval_path = resume_case
    calls = []
    def transport(request):
        calls.append(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(cli, "_transport", transport)

    assert cli.main(argv) == exit_code

    error = json.loads(capsys.readouterr().err)
    assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == SNAPSHOT_URL
    assert error["code"] == expected_code
    assert error["requests_made"] == 3 and error["requests_this_run"] == 1
    assert error["recovery_saved"] is True
    saved = json.loads(Path(error["recovery_path"]).read_text())
    assert saved["sources"] == library["sources"]
    assert saved["receipt"]["status"] == expected_state
    assert saved["receipt"]["requests_made"] == 3
    assert saved["receipt"]["jobs"][1]["snapshot_id"] == "snap_resume"
    assert "private" not in json.dumps(error)
    assert "fake-resume-token" not in json.dumps(saved)
    assert Path(error["recovery_path"]).stat().st_mode & 0o077 == 0

    # An explicit later resume uses a NEW approval and GET, never a new trigger.
    approval_path.write_text(json.dumps(approval_for(saved["receipt"], "resume-after-failure")))
    monkeypatch.setattr(cli, "_transport", lambda request: calls.append(request) or HttpResponse(200, {}, b"[]"))
    argv[1] = error["recovery_path"]
    argv[3] = str(output_path.with_name("after-failure.library.json"))
    assert cli.main(argv) == 0
    final = json.loads(Path(argv[3]).read_text())
    assert final["sources"] == library["sources"]
    assert final["receipt"]["requests_made"] == 4
    assert [request.method for request in calls] == ["GET", "GET"]


@pytest.mark.parametrize("outcome,expected_status", [
    (HttpResponse(200, {}, json.dumps([{"url": AMAZON_URL, "review_id": "R1", "review_header": "Setup",
                                      "review_text": "Setup fails.", "review_posted_date": NOW}]).encode()), "processed"),
    (HttpResponse(202, {}, b""), "pending"),
    (TransportError("transport_error"), "transport_failed"),
])
def test_resume_output_write_failure_saves_sources_snapshot_and_actual_count(
        outcome, expected_status, resume_case, monkeypatch, capsys):
    argv, library, output_path, _ = resume_case
    calls = []
    def transport(request):
        calls.append(request)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(cli, "_transport", transport)
    original_replace = cli.os.replace
    def fail_output(source, destination):
        if Path(destination) == output_path:
            raise OSError("private output detail")
        return original_replace(source, destination)
    monkeypatch.setattr(cli.os, "replace", fail_output)

    assert cli.main(argv) == 2

    error = json.loads(capsys.readouterr().err)
    assert error["code"] == "output_persist_failed"
    assert error["requests_made"] == 3 and error["requests_this_run"] == 1
    assert len(calls) == 1 and calls[0].method == "GET"
    saved = json.loads(Path(error["recovery_path"]).read_text())
    assert saved["sources"][0] == library["sources"][0]
    assert saved["receipt"]["status"] == expected_status
    assert saved["receipt"]["jobs"][1]["id"] == "reviews"
    assert saved["receipt"]["requests_made"] == 3
    assert stat.S_IMODE(Path(error["recovery_path"]).stat().st_mode) == 0o600
    if expected_status == "processed":
        assert len(saved["sources"]) == 2 and saved["sources"][1]["record_id"] == "R1"
    else:
        assert saved["receipt"]["jobs"][1]["snapshot_id"] == "snap_resume"
    assert not output_path.exists()
    assert not list(output_path.parent.glob(f".{output_path.name}.*"))


def test_resume_recovery_failure_still_reports_attempt_and_identifiers(resume_case, monkeypatch, capsys):
    argv, _, output_path, _ = resume_case
    calls = []
    def transport(request):
        calls.append(request)
        raise TransportError("transport_error")
    monkeypatch.setattr(cli, "_transport", transport)
    monkeypatch.setattr(cli, "_atomic_write", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("output")))
    monkeypatch.setattr(cli, "_write_recovery_library", lambda *args: (_ for _ in ()).throw(OSError("recovery")))

    assert cli.main(argv) == 2

    error = json.loads(capsys.readouterr().err)
    assert error["requests_made"] == 3 and error["requests_this_run"] == 1
    assert error["recovery_saved"] is False
    assert error["source_ids"] == ["prior"] and error["job_ids"] == ["help", "reviews"]
    assert len(calls) == 1 and not output_path.exists()
