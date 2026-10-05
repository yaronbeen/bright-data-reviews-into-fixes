"""Applicable shared contract cases C01-C20, named for auditability."""

import csv
import hashlib
import io
import itertools
import json
import socket
from copy import deepcopy
from pathlib import Path

import pytest

from reviews_into_fixes import cli
from reviews_into_fixes.brightdata import (
    HttpResponse, TransportError, _parse_web_markdown, _response_ok, collect, normalize_export, plan, resume,
)
from reviews_into_fixes.core import analyze, normalize_text
from reviews_into_fixes.export import render_csv, render_json, render_markdown


ROOT = Path(__file__).parents[1]
NOW = "2026-10-05T00:00:00Z"
AMAZON_URL = "https://www.amazon.com/dp/B012345678"
APPROVAL_SEQUENCE = itertools.count(10_000)


def demo():
    return json.loads((ROOT / "fixtures" / "demo.json").read_text())


def web_manifest(url="https://docs.python.org/3/"):
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "help", "kind": "web_page", "role": "product_instructions", "source_id": "help_live", "url": url,
    }]}


def amazon_manifest(count=1, urls=None):
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "amz",
        "urls": urls or [AMAZON_URL], "max_reviews": count,
    }]}


def approve(value, urls, records=50):
    sequence = next(APPROVAL_SEQUENCE)
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "approval_id": f"approval-{sequence}",
            "nonce": f"{sequence:064x}", "issued_at": "2026-10-04T23:50:00Z", "manifest_sha256": digest,
            "expires_at": "2026-10-05T00:05:00Z", "max_requests": 4, "max_retained_records": records,
            "approved_urls": urls, "account_budget_confirmed": True, "target_permissions_confirmed": True,
            "remote_resolution_risk_accepted": True}


def provider_record(record_id="R1", text="Setup fails.", url=AMAZON_URL, **extra):
    return {"url": url, "review_id": record_id, "review_header": "Setup", "review_text": text,
            "review_posted_date": "2026-10-04T10:00:00Z", **extra}


def pending_receipt():
    manifest = amazon_manifest(1)
    job = manifest["jobs"][0]
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "manifest_sha256": plan(manifest)["manifest_sha256"],
            "status": "pending", "provider_completeness": "unknown", "requests_made": 1, "returned_records": 0, "retained_records": 0,
            "excluded_records": 0, "jobs": [{"id": "reviews", "kind": "amazon_reviews", "state": "pending",
            "original_job": job, "requested_records": 1, "returned_records": 0, "retained_records": 0,
            "excluded_records": 0, "snapshot_id": "snap_1", "error_code": "pending_snapshot",
            "query_metadata": None}], "warnings": [], "provider_cost_usd": None}


def collect_with(manifest, transport, records=50):
    urls = [url for job in manifest["jobs"] for url in ([job["url"]] if job["kind"] == "web_page" else job["urls"])]
    return collect(manifest, approval=approve(manifest, urls, records), api_key="fake-token",
                   zones={"web_unlocker": "fake-zone"}, transport=transport, now=NOW)


def test_C01_positive_fixture_has_business_rows_and_evidence():
    report = analyze(demo())
    assert report["cards"] and all(card["report_refs"] and card["next_check"] for card in report["cards"])


def test_C02_offline_analysis_denies_network(monkeypatch, tmp_path):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert cli.main(["analyze", str(ROOT / "fixtures" / "demo.json"), "--out-dir", str(tmp_path)]) == 0


def test_C03_rendering_and_fixture_replay_are_byte_deterministic(monkeypatch):
    report = analyze(demo())
    monkeypatch.setenv("TZ", "Pacific/Honolulu")
    assert render_json(report) == render_json(analyze(demo()))
    assert render_markdown(report).encode() == (ROOT / "fixtures" / "expected" / "fixes.md").read_bytes()


def test_C04_unknown_oversize_and_boolean_inputs_fail():
    payload = demo()
    payload["unknown"] = True
    with pytest.raises(ValueError):
        analyze(payload)
    payload = demo()
    payload["sources"][0]["text"] = "x" * 5001
    with pytest.raises(ValueError):
        analyze(payload)
    with pytest.raises(ValueError):
        plan(amazon_manifest(True))


def test_C05_unavailable_source_never_becomes_evidence():
    payload = demo()
    payload["sources"][0].update(status="unavailable", text="")
    report = analyze(payload)
    assert all(ref["source_id"] != "r1" for card in report["cards"] for ref in card["report_refs"])


def test_C06_every_citation_quote_matches_a_normalized_body_block():
    payload = demo()
    report = analyze(payload)
    sources = {source["id"]: source for source in payload["sources"]}
    for card in report["cards"]:
        for ref in card["report_refs"] + card["instruction_refs"] + card["counterevidence_refs"]:
            _, blocks = normalize_text(sources[ref["source_id"]]["text"])
            block = next(block for block in blocks if block["id"] == ref["block_id"])
            assert block["kind"] == "body" and ref["quote"] in block["text"]


def test_C07_provider_person_metadata_is_not_retained():
    library = normalize_export("amazon_reviews", [provider_record(username="drop", author_hash="drop", replies=[1])],
        role="review", source_url=AMAZON_URL, observed_at=NOW, source_prefix="amz")
    assert not ({"username", "author_hash", "replies"} & set(library["sources"][0]))


def test_C08_csv_and_markdown_treat_hostile_text_as_data():
    payload = demo()
    payload["areas"][1]["next_check"] = "+CMD()"
    payload["sources"][0]["text"] = "Setup stops at step 3. <script>x</script> | `code`"
    report = analyze(payload)
    row = next(row for row in csv.DictReader(io.StringIO(render_csv(report))) if row["classification"] == "request")
    assert row["next_check"].startswith("'")
    markdown = render_markdown(report)
    assert "<script>" not in markdown and "&lt;script&gt;" in markdown
    assert "<script>x</script>" in render_json(report)


@pytest.mark.parametrize("change", ["approval", "key", "zone"])
def test_C09_missing_live_gate_makes_zero_requests(change):
    manifest = web_manifest()
    calls = []
    kwargs = {"approval": approve(manifest, [manifest["jobs"][0]["url"]]), "api_key": "key",
              "zones": {"web_unlocker": "zone"}, "transport": lambda request: calls.append(request), "now": NOW}
    if change == "approval": kwargs["approval"] = {}
    if change == "key": kwargs["api_key"] = ""
    if change == "zone": kwargs["zones"] = {}
    with pytest.raises(ValueError):
        collect(manifest, **kwargs)
    assert calls == []


def test_C10_live_dry_run_validates_and_makes_zero_requests(monkeypatch, tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(web_manifest()))
    monkeypatch.setattr(cli, "_transport", lambda request: (_ for _ in ()).throw(AssertionError("request")))
    assert cli.main(["collect", str(manifest_path), "--out", str(tmp_path / "none"), "--live", "--dry-run"]) == 2
    assert not (tmp_path / "none").exists()


def test_C10_live_amazon_dry_run_validates_and_makes_zero_requests(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(amazon_manifest()))
    monkeypatch.setattr(cli, "_transport", lambda request: (_ for _ in ()).throw(AssertionError("request")))
    assert cli.main(["collect", str(manifest_path), "--out", str(tmp_path / "none"), "--live", "--dry-run"]) == 0
    assert not (tmp_path / "none").exists()


def test_C11_web_live_collection_fails_closed_without_final_target_verification():
    manifest = web_manifest()
    calls = []
    with pytest.raises(ValueError, match="redirect scope"):
        collect_with(manifest, lambda request: calls.append(request))
    assert calls == []


@pytest.mark.parametrize("response,code", [
    (HttpResponse(200, {"X-Brd-Status-Code": "429"}, b"secret"), "provider_target_error"),
    (HttpResponse(302, {}, b"redirect"), "provider_http_error"),
    (HttpResponse(200, {}, b"x" * (2 * 1024 * 1024 + 1)), "response_too_large"),
])
def test_C12_bad_web_responses_never_become_evidence(response, code):
    with pytest.raises(TransportError, match=code):
        _response_ok(response)
        _parse_web_markdown(response.body)


def test_C12_web_raw_markdown_and_documented_envelope_normalize_identically():
    raw = b"# Setup\n\nFollow setup step 3."
    envelope = json.dumps({"status_code": 200, "headers": {"content-type": "text/markdown"},
                           "body": raw.decode()}).encode()
    assert _parse_web_markdown(raw) == _parse_web_markdown(envelope)


@pytest.mark.parametrize("payload", [
    {"status_code": 429, "headers": {}, "body": "rate limited"},
    {"status_code": 200, "headers": {"x-brd-error-code": "target_error"}, "body": "secret"},
    {"status_code": 200, "headers": {}, "body": {"not": "text"}},
])
def test_C12_web_envelope_errors_never_become_markdown(payload):
    with pytest.raises(TransportError):
        _parse_web_markdown(json.dumps(payload).encode())


def test_C13_http_or_transport_failure_stops_once_without_secret():
    manifest = amazon_manifest()
    calls = []
    def transport(request):
        calls.append(request)
        raise TransportError("transport_error")
    result = collect_with(manifest, transport)
    assert len(calls) == 1 and result["receipt"]["status"] == "transport_failed"
    assert result["receipt"]["provider_completeness"] == "unknown"
    assert "fake-token" not in json.dumps(result)


def test_C14_202_creates_pending_receipt_without_polling():
    calls = []
    result = collect_with(amazon_manifest(), lambda request: calls.append(request) or HttpResponse(202, {}, b'{"snapshot_id":"snap_1"}'), 1)
    assert len(calls) == 1 and result["sources"] == []
    assert result["receipt"]["status"] == "pending" and result["receipt"]["jobs"][0]["snapshot_id"] == "snap_1"


@pytest.mark.parametrize("status,expected", [(202, "pending"), (409, "pending"), (200, "empty")])
def test_C15_resume_is_one_pinned_get(status, expected):
    receipt = pending_receipt()
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_1?format=json"
    calls = []
    body = b"[]" if status == 200 else b""
    result = resume(receipt, approval=approve(receipt, [url], 1), api_key="fake-token",
                    transport=lambda request: calls.append(request) or HttpResponse(status, {}, body), now=NOW)
    assert len(calls) == 1 and calls[0].method == "GET" and calls[0].url == url
    assert result["receipt"]["status"] == expected


def test_C16_zero_error_and_overreturn_have_truthful_counts():
    empty = collect_with(amazon_manifest(), lambda request: HttpResponse(200, {}, b"[]"), 1)
    assert (empty["receipt"]["returned_records"], empty["receipt"]["retained_records"]) == (0, 0)
    errored = collect_with(amazon_manifest(), lambda request: HttpResponse(200, {}, b'[{"error_code":"unknown-secret"}]'), 1)
    assert empty["receipt"]["status"] == "empty"
    assert errored["receipt"]["excluded_records"] == 1 and errored["receipt"]["status"] == "processed_with_exclusions"
    over = collect_with(amazon_manifest(), lambda request: HttpResponse(200, {}, json.dumps([
        provider_record("R1"), provider_record("R2", "Setup broken.")]).encode()), 1)
    assert (over["receipt"]["returned_records"], over["receipt"]["retained_records"], over["receipt"]["excluded_records"]) == (2, 1, 1)
    assert over["receipt"]["status"] == "processed_with_exclusions"
    assert all(item["receipt"]["provider_completeness"] == "unknown" for item in (empty, errored, over))


@pytest.mark.parametrize("url", [
    "http://docs.python.org/3/", "https://" + "user" + ":" + "pass" + "@docs.python.org/3/", "https://127.0.0.1/x",
    "https://example.com/x", "https://docs.python.org/x?token=secret",
])
def test_C17_unsafe_live_targets_are_rejected_before_request(url):
    manifest = web_manifest(url)
    calls = []
    with pytest.raises(ValueError):
        collect(manifest, approval={}, api_key="key", zones={"web_unlocker": "zone"},
                transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


def test_C18_planning_never_authorizes_or_fetches_destinations():
    planned = plan(web_manifest())
    assert planned["requests_made"] == 0 and planned["request_count"] == 1


def test_C19_collision_validation_happens_before_any_write(tmp_path):
    report = tmp_path / "report.json"
    report.write_text("keep")
    with pytest.raises(ValueError):
        cli._write_many({report: "new", tmp_path / "fixes.md": "new", tmp_path / "fixes.csv": "new"}, False)
    assert report.read_text() == "keep" and len(list(tmp_path.iterdir())) == 1


def test_C20_output_states_scope_method_unknowns_and_limitations():
    markdown = render_markdown(analyze(demo()))
    for expected in ("## Scope", "deterministic_rules_v1", "Warnings And Unknowns", "does not validate defects", "Synthetic demonstration data"):
        assert expected in markdown
