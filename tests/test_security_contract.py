import csv
import hashlib
import io
import json
import multiprocessing
import os
import stat
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from reviews_into_fixes import cli
import reviews_into_fixes.brightdata as brightdata
from reviews_into_fixes.brightdata import HttpResponse, TransportError, collect, normalize_export, plan, resume
from reviews_into_fixes.core import analyze
from reviews_into_fixes.export import render_csv, render_markdown


NOW = "2026-10-05T00:00:00Z"
AMAZON_A = "https://www.amazon.com/dp/B012345678"
AMAZON_B = "https://www.amazon.com/dp/B098765432"
ROOT = Path(__file__).parents[1]


def manifest(urls=None, count=1):
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "secure",
        "urls": urls or [AMAZON_A], "max_reviews": count,
    }]}


def approval(value, *, identity="security-approval", nonce="a" * 64, records=10,
             issued="2026-10-04T23:50:00Z", expires="2026-10-05T00:05:00Z", urls=None):
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "approval_id": identity,
            "nonce": nonce, "issued_at": issued, "manifest_sha256": digest, "expires_at": expires,
            "max_requests": 4, "max_retained_records": records, "approved_urls": urls or [AMAZON_A],
            "account_budget_confirmed": True, "target_permissions_confirmed": True,
            "remote_resolution_risk_accepted": True}


def provider_record(url=AMAZON_A, record_id="R1", text="Setup fails."):
    return {"url": url, "review_id": record_id, "review_header": "Setup", "review_text": text,
            "review_posted_date": "2026-10-04T10:00:00Z"}


def pending_receipt():
    value = manifest()
    job = value["jobs"][0]
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "manifest_sha256": plan(value)["manifest_sha256"],
            "status": "pending", "provider_completeness": "unknown", "requests_made": 1, "returned_records": 0, "retained_records": 0,
            "excluded_records": 0, "jobs": [{"id": "reviews", "kind": "amazon_reviews", "state": "pending",
            "original_job": job, "requested_records": 1, "returned_records": 0, "retained_records": 0,
            "excluded_records": 0, "snapshot_id": "snap_secure", "error_code": "pending_snapshot",
            "query_metadata": None}], "warnings": [], "provider_cost_usd": None}


def _approval_consumer_process(state_home, identity, queue):
    os.environ["XDG_STATE_HOME"] = state_home
    try:
        cli._approval_state_consumer(identity)
    except ValueError:
        queue.put("blocked")
    else:
        queue.put("won")


def test_production_cli_ignores_environment_clock(monkeypatch, tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest()))
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval(manifest())))
    captured = {}
    monkeypatch.setenv("REVIEWS_INTO_FIXES_NOW", "1999-01-01T00:00:00Z")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    monkeypatch.setattr(cli, "_system_now", lambda: NOW)
    monkeypatch.setattr(cli, "collect", lambda *args, **kwargs: captured.update(kwargs) or {
        "sources": [], "receipt": {"status": "processed", "requests_made": 0,
                                    "provider_completeness": "unknown"}})
    assert cli.main(["collect", str(manifest_path), "--out", str(tmp_path / "out.json"), "--live",
                     "--accept-charges", "--approval", str(approval_path)]) == 0
    assert captured["now"] == NOW


def test_collect_approval_is_single_use_before_second_request():
    value = manifest()
    permit = approval(value, identity="collect-once", nonce="1" * 64)
    calls = []
    transport = lambda request: calls.append(request) or HttpResponse(200, {}, b"[]")
    result = collect(value, approval=permit, api_key="fake", zones={}, transport=transport, now=NOW)
    assert result["receipt"]["status"] == "empty"
    assert result["receipt"]["provider_completeness"] == "unknown"
    with pytest.raises(ValueError, match="already consumed"):
        collect(value, approval=permit, api_key="fake", zones={}, transport=transport, now=NOW)
    assert len(calls) == 1


def test_collect_request_timeout_uses_monotonic_run_deadline(monkeypatch):
    value = manifest()
    permit = approval(value, identity="deadline", nonce="d" * 64)
    ticks = iter([100.0, 110.0])
    monkeypatch.setattr(brightdata.time, "monotonic", lambda: next(ticks))
    calls = []
    collect(value, approval=permit, api_key="fake", zones={},
            transport=lambda request: calls.append(request) or HttpResponse(200, {}, b"[]"), now=NOW)
    assert calls[0].timeout_seconds == 65


def test_resume_approval_is_single_use():
    receipt = pending_receipt()
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_secure?format=json"
    permit = approval(receipt, identity="resume-once", nonce="2" * 64, records=1, urls=[url])
    calls = []
    transport = lambda request: calls.append(request) or HttpResponse(202, {}, b"")
    assert resume(receipt, approval=permit, api_key="fake", transport=transport, now=NOW)["receipt"]["status"] == "pending"
    with pytest.raises(ValueError, match="already consumed"):
        resume(receipt, approval=permit, api_key="fake", transport=transport, now=NOW)
    assert len(calls) == 1


def test_resume_accumulates_request_and_record_counts():
    receipt = pending_receipt()
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_secure?format=json"
    permit = approval(receipt, identity="resume-counts", nonce="8" * 64, records=1, urls=[url])
    result = resume(receipt, approval=permit, api_key="fake",
                    transport=lambda request: HttpResponse(200, {}, json.dumps([provider_record()]).encode()), now=NOW)
    assert result["receipt"]["requests_made"] == 2
    assert result["receipt"]["returned_records"] == 1
    assert result["receipt"]["retained_records"] == 1
    assert result["receipt"]["jobs"][0]["state"] == "processed"


def test_resume_cli_preserves_library_sources_and_reads_wrapped_receipt(monkeypatch, tmp_path):
    original = pending_receipt()
    prior_source = {"id": "prior", "kind": "page", "role": "product_instructions", "url": "https://docs.python.org/3/",
                    "title": "Prior", "text": "Setup fails.", "status": "collected",
                    "observed_at": NOW, "published_at": None, "provider_date": None,
                    "record_id": None, "record_id_origin": "none", "provenance": "bright_data"}
    prior_job = {"id": "help", "kind": "web_page", "role": "product_instructions", "source_id": "prior",
                 "url": prior_source["url"]}
    original["jobs"].insert(0, {"id": "help", "kind": "web_page", "state": "processed",
                               "original_job": prior_job, "requested_records": None,
                               "returned_records": 0, "retained_records": 1, "excluded_records": 0,
                               "snapshot_id": None, "error_code": None, "query_metadata": None})
    original["requests_made"] = 2
    library = {"schema_version": "1.0", "project": "reviews-into-fixes", "transport_contract_version": "1.0",
               "sources": [prior_source], "receipt": original}
    manifest_with_prior = {"schema_version": "1.0", "project": "reviews-into-fixes",
                           "jobs": [prior_job, original["jobs"][1]["original_job"]]}
    original["manifest_sha256"] = plan(manifest_with_prior)["manifest_sha256"]
    original["retained_records"] = 1
    receipt_path = tmp_path / "library.json"
    receipt_path.write_text(json.dumps(library))
    target = "https://api.brightdata.com/datasets/v3/snapshot/snap_secure?format=json"
    approval_path = tmp_path / "resume.approval.json"
    approval_path.write_text(json.dumps(approval(original, identity="cli-resume", nonce="9" * 64, records=2, urls=[target])))
    output = tmp_path / "resumed.json"
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_system_now", lambda: NOW)
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    errors = []
    monkeypatch.setattr(cli, "_error", lambda code, message, requests_made=0: errors.append((code, message, requests_made)))
    original_resume = cli.resume
    resume_errors = []
    def capture_resume(*args, **kwargs):
        try:
            return original_resume(*args, **kwargs)
        except Exception as exc:
            resume_errors.append(repr(exc))
            raise
    monkeypatch.setattr(cli, "resume", capture_resume)
    calls = []
    monkeypatch.setattr(cli, "_transport", lambda request: calls.append(request) or HttpResponse(
        200, {}, json.dumps([provider_record()]).encode()))

    assert cli.main(["resume", str(receipt_path), "--out", str(output), "--live", "--accept-charges",
                     "--approval", str(approval_path)]) == 0, (errors, resume_errors)
    result = json.loads(output.read_text())
    assert len(calls) == 1
    assert result["sources"][0]["id"] == "prior"
    assert len(result["sources"]) == 2
    assert result["receipt"]["requests_made"] == 3
    assert result["receipt"]["retained_records"] == 2


def test_cli_approval_marker_is_atomic_and_persistent(tmp_path):
    state_home = tmp_path / "state"
    identity = {"approval_id": "persistent-once", "nonce": "f" * 64, "approval_sha256": "a" * 64}
    cli._approval_state_consumer(identity, state_home=state_home)
    with pytest.raises(ValueError, match="already consumed"):
        cli._approval_state_consumer(identity, state_home=state_home)
    markers = list((state_home / "reviews-into-fixes" / "approval-consumption").iterdir())
    assert len(markers) == 1
    assert identity["nonce"] not in markers[0].read_text()
    assert stat.S_IMODE(markers[0].stat().st_mode) == 0o600
    assert stat.S_IMODE(markers[0].parent.stat().st_mode) == 0o700


def test_approval_nonce_cannot_be_reused_with_different_approval_content(tmp_path):
    state_home = tmp_path / "state"
    identity = {"approval_id": "digest-binding", "nonce": "a" * 64, "approval_sha256": "b" * 64}
    cli._approval_state_consumer(identity, state_home=state_home)
    changed = {**identity, "approval_sha256": "c" * 64}
    with pytest.raises(ValueError, match="unsafe approval state marker"):
        cli._approval_state_consumer(changed, state_home=state_home)
    assert len(list((state_home / "reviews-into-fixes" / "approval-consumption").iterdir())) == 1


def test_default_approval_state_uses_private_home_directory(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: home)
    identity = {"approval_id": "home-state", "nonce": "e" * 64, "approval_sha256": "f" * 64}

    cli._approval_state_consumer(identity)

    store = home / ".reviews-into-fixes-state" / "reviews-into-fixes" / "approval-consumption"
    assert len(list(store.iterdir())) == 1
    assert stat.S_IMODE(store.parent.stat().st_mode) == 0o700


def test_approval_consumer_refuses_precreated_unsafe_state_directory(tmp_path):
    state_home = tmp_path / "state"
    app_state = state_home / "reviews-into-fixes"
    app_state.mkdir(parents=True)
    app_state.chmod(0o755)
    identity = {"approval_id": "unsafe-dir", "nonce": "1" * 64, "approval_sha256": "2" * 64}
    with pytest.raises(ValueError, match="unsafe approval state"):
        cli._approval_state_consumer(identity, state_home=state_home)
    assert stat.S_IMODE(app_state.stat().st_mode) == 0o755
    assert list(app_state.iterdir()) == []


def test_approval_consumer_refuses_symlinked_state_directory(tmp_path):
    state_home = tmp_path / "state"
    state_home.mkdir()
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    (state_home / "reviews-into-fixes").symlink_to(attacker, target_is_directory=True)
    identity = {"approval_id": "symlink-dir", "nonce": "3" * 64, "approval_sha256": "4" * 64}
    with pytest.raises(ValueError, match="unsafe approval state"):
        cli._approval_state_consumer(identity, state_home=state_home)
    assert list(attacker.iterdir()) == []


def test_approval_consumer_refuses_symlinked_consumption_directory(tmp_path):
    state_home = tmp_path / "state"
    app_state = state_home / "reviews-into-fixes"
    app_state.mkdir(parents=True, mode=0o700)
    attacker = tmp_path / "attacker-markers"
    attacker.mkdir()
    (app_state / "approval-consumption").symlink_to(attacker, target_is_directory=True)
    identity = {"approval_id": "symlink-markers", "nonce": "7" * 64, "approval_sha256": "8" * 64}
    with pytest.raises(ValueError, match="unsafe approval state"):
        cli._approval_state_consumer(identity, state_home=state_home)
    assert list(attacker.iterdir()) == []


def test_approval_consumer_refuses_symlinked_marker(tmp_path):
    state_home = tmp_path / "state"
    consume_dir = state_home / "reviews-into-fixes" / "approval-consumption"
    consume_dir.mkdir(parents=True, mode=0o700)
    state_home.chmod(0o700)
    (state_home / "reviews-into-fixes").chmod(0o700)
    identity = {"approval_id": "symlink-marker", "nonce": "9" * 64, "approval_sha256": "a" * 64}
    marker_name = hashlib.sha256(
        f"{identity['approval_id']}\x00{identity['nonce']}".encode()
    ).hexdigest()
    target = tmp_path / "attacker-file"
    target.write_text("not a consumption marker")
    (consume_dir / marker_name).symlink_to(target)
    with pytest.raises(ValueError, match="unsafe approval state marker"):
        cli._approval_state_consumer(identity, state_home=state_home)
    assert target.read_text() == "not a consumption marker"


def test_approval_consumer_refuses_tampered_marker_content(tmp_path):
    state_home = tmp_path / "state"
    consume_dir = state_home / "reviews-into-fixes" / "approval-consumption"
    consume_dir.mkdir(parents=True, mode=0o700)
    state_home.chmod(0o700)
    (state_home / "reviews-into-fixes").chmod(0o700)
    identity = {"approval_id": "tampered-marker", "nonce": "b" * 64, "approval_sha256": "c" * 64}
    marker_name = hashlib.sha256(
        f"{identity['approval_id']}\x00{identity['nonce']}".encode()
    ).hexdigest()
    marker = consume_dir / marker_name
    marker.write_text("not the validated approval binding")
    marker.chmod(0o600)
    with pytest.raises(ValueError, match="unsafe approval state marker"):
        cli._approval_state_consumer(identity, state_home=state_home)


def test_approval_consumer_rejects_wrong_owner_metadata():
    metadata = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=os.getuid() + 1)
    with pytest.raises(ValueError, match="unsafe approval state"):
        cli._validate_private_state_stat(metadata)


def test_state_home_symlink_is_rejected(tmp_path):
    real_state = tmp_path / "real-state"
    real_state.mkdir(mode=0o700)
    state_link = tmp_path / "state-link"
    state_link.symlink_to(real_state, target_is_directory=True)
    identity = {"approval_id": "base-symlink", "nonce": "4" * 64, "approval_sha256": "5" * 64}
    with pytest.raises(ValueError, match="unsafe approval state"):
        cli._approval_state_consumer(identity, state_home=state_link)
    assert list(real_state.iterdir()) == []


def test_concurrent_processes_only_one_consume_same_approval(tmp_path):
    state_home = tmp_path / "shared-state"
    identity = {"approval_id": "concurrent", "nonce": "5" * 64, "approval_sha256": "6" * 64}
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    processes = [context.Process(target=_approval_consumer_process, args=(str(state_home), identity, queue)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
    assert all(process.exitcode == 0 for process in processes)
    assert sorted([queue.get(timeout=2), queue.get(timeout=2)]) == ["blocked", "won"]
    markers = list((state_home / "reviews-into-fixes" / "approval-consumption").iterdir())
    assert len(markers) == 1


def test_cli_collection_consumes_approval_once_across_invocations(monkeypatch, tmp_path):
    value = manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(value))
    approval_path = tmp_path / "private.approval.json"
    approval_path.write_text(json.dumps(approval(value, identity="cli-once", nonce="b" * 64)))
    calls = []
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    approval_dir_state = tmp_path / ".reviews-into-fixes-consumed"
    attacker = tmp_path / "approval-dir-attacker"
    attacker.mkdir()
    approval_dir_state.symlink_to(attacker, target_is_directory=True)
    monkeypatch.setattr(cli, "_system_now", lambda: NOW)
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    monkeypatch.setattr(cli, "_transport", lambda request: calls.append(request) or HttpResponse(200, {}, b"[]"))
    assert cli.main(["collect", str(manifest_path), "--out", str(tmp_path / "first.json"), "--live",
                     "--accept-charges", "--approval", str(approval_path)]) == 0
    assert cli.main(["collect", str(manifest_path), "--out", str(tmp_path / "second.json"), "--live",
                     "--accept-charges", "--approval", str(approval_path)]) == 2
    assert len(calls) == 1 and not (tmp_path / "second.json").exists()
    assert list(attacker.iterdir()) == []
    assert len(list((tmp_path / "state" / "reviews-into-fixes" / "approval-consumption").iterdir())) == 1


def test_cli_output_collision_prevents_request_and_approval_consumption(monkeypatch, tmp_path):
    value = manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(value))
    approval_path = tmp_path / "private.approval.json"
    approval_path.write_text(json.dumps(approval(value, identity="collision", nonce="c" * 64)))
    output = tmp_path / "existing.json"
    output.write_text("keep")
    calls = []
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "_system_now", lambda: NOW)
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    monkeypatch.setattr(cli, "_transport", lambda request: calls.append(request) or HttpResponse(200, {}, b"[]"))
    assert cli.main(["collect", str(manifest_path), "--out", str(output), "--live", "--accept-charges",
                     "--approval", str(approval_path)]) == 2
    assert calls == [] and output.read_text() == "keep"
    assert not (tmp_path / "state" / "reviews-into-fixes" / "approval-consumption").exists()


@pytest.mark.parametrize("mutate", [
    lambda a: a.update(approval_id=True),
    lambda a: a.update(nonce="short"),
    lambda a: a.update(issued_at="2026-10-05T00:00:00+00:00"),
    lambda a: a.update(expires_at="2026-10-05T00:20:01Z"),
    lambda a: a.update(max_requests="4"),
    lambda a: a.update(max_retained_records=True),
    lambda a: a.update(approved_urls=AMAZON_A),
    lambda a: a.update(approved_urls=[AMAZON_A, "not-a-url"]),
])
def test_approval_has_strict_types_utc_and_bounded_lifetime(mutate):
    value = manifest()
    permit = approval(value, identity="strict-approval", nonce="3" * 64)
    mutate(permit)
    calls = []
    with pytest.raises((TypeError, ValueError)):
        collect(value, approval=permit, api_key="fake", zones={}, transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


def test_retention_budget_counts_selected_web_pages_before_fail_closed():
    value = {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [
        {"id": "help", "kind": "web_page", "role": "product_instructions", "source_id": "help",
         "url": "https://docs.python.org/3/"},
        manifest(count=2)["jobs"][0],
    ]}
    permit = approval(value, identity="retention-cap", nonce="4" * 64, records=2,
                      urls=["https://docs.python.org/3/", AMAZON_A])
    calls = []
    with pytest.raises(ValueError, match="retained-record allowance"):
        collect(value, approval=permit, api_key="fake", zones={"web_unlocker": "zone"},
                transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


@pytest.mark.parametrize("query", ["access_token=do-not-forward", "campaign=tracking-value"])
def test_live_amazon_target_rejects_every_query_parameter(query):
    target = AMAZON_A + "?" + query
    value = manifest([target])
    permit = approval(value, identity="query-reject", nonce="c" * 64, records=1, urls=[target])
    calls = []
    with pytest.raises(ValueError, match="query parameters"):
        collect(value, approval=permit, api_key="fake", zones={},
                transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


def test_resume_cap_counts_prior_retained_page_sources():
    receipt = pending_receipt()
    prior_job = {"id": "help", "kind": "web_page", "role": "product_instructions", "source_id": "help",
                 "url": "https://docs.python.org/3/"}
    pending_job = receipt["jobs"][0]["original_job"]
    manifest_with_prior = {"schema_version": "1.0", "project": "reviews-into-fixes",
                           "jobs": [prior_job, pending_job]}
    receipt["manifest_sha256"] = plan(manifest_with_prior)["manifest_sha256"]
    receipt["requests_made"] = 2
    receipt["retained_records"] = 1
    receipt["jobs"].insert(0, {"id": "help", "kind": "web_page", "state": "processed",
                               "original_job": prior_job, "requested_records": None,
                               "returned_records": 0, "retained_records": 1, "excluded_records": 0,
                               "snapshot_id": None, "error_code": None, "query_metadata": None})
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_secure?format=json"
    permit = approval(receipt, identity="resume-cumulative-cap", nonce="d" * 64, records=1, urls=[url])
    calls = []
    with pytest.raises(ValueError, match="retained-record allowance"):
        resume(receipt, approval=permit, api_key="fake", transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


def test_live_web_unlocker_fails_closed_without_verified_final_target_scope():
    value = {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "help", "kind": "web_page", "role": "product_instructions", "source_id": "help",
        "url": "https://docs.python.org/3/"}]}
    permit = approval(value, identity="web-closed", nonce="5" * 64, records=1,
                      urls=["https://docs.python.org/3/"])
    calls = []
    with pytest.raises(ValueError, match="redirect scope"):
        collect(value, approval=permit, api_key="fake", zones={"web_unlocker": "zone"},
                transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


def test_single_input_provider_url_is_mapped_to_approved_target():
    value = manifest()
    permit = approval(value, identity="map-single", nonce="6" * 64)
    arbitrary = "https://www.amazon.com/gp/customer-reviews/PROFILE123?token=leak"
    result = collect(value, approval=permit, api_key="fake", zones={},
        transport=lambda request: HttpResponse(200, {}, json.dumps([provider_record(arbitrary)]).encode()), now=NOW)
    assert result["sources"][0]["url"] == AMAZON_A
    assert "token" not in result["sources"][0]["url"]


def test_multi_input_arbitrary_provider_url_is_excluded():
    value = manifest([AMAZON_A, AMAZON_B])
    permit = approval(value, identity="map-multi", nonce="7" * 64, records=2, urls=[AMAZON_A, AMAZON_B])
    result = collect(value, approval=permit, api_key="fake", zones={},
        transport=lambda request: HttpResponse(200, {}, json.dumps([
            provider_record("https://www.amazon.com/profile/not-approved")]).encode()), now=NOW)
    assert result["sources"] == []
    assert result["receipt"]["excluded_records"] == 1


@pytest.mark.parametrize("status,headers", [
    (202, {"X-Brd-Error-Code": "secret"}),
    (409, {"X-Brd-Status-Code": "429"}),
])
def test_resume_pending_status_with_error_headers_is_failure(status, headers):
    receipt = pending_receipt()
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_secure?format=json"
    permit = approval(receipt, identity=f"pending-error-{status}", nonce=f"{status:064x}", records=1, urls=[url])
    with pytest.raises(TransportError):
        resume(receipt, approval=permit, api_key="fake", transport=lambda request: HttpResponse(status, headers, b""), now=NOW)


def test_resume_pending_status_with_explicit_error_body_is_failure():
    receipt = pending_receipt()
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_secure?format=json"
    permit = approval(receipt, identity="pending-body-error", nonce="e" * 64, records=1, urls=[url])
    with pytest.raises(TransportError, match="provider_http_error"):
        resume(receipt, approval=permit, api_key="fake",
               transport=lambda request: HttpResponse(202, {}, b'{"error":"not pending"}'), now=NOW)


def test_bounded_reader_rejects_symlink_directory_and_oversize(tmp_path):
    target = tmp_path / "target.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="regular file"):
        cli._read_json(link)
    with pytest.raises(ValueError, match="regular file"):
        cli._read_json(tmp_path)
    oversized = tmp_path / "large.json"
    oversized.write_bytes(b"x" * 17)
    with pytest.raises(ValueError, match="exceeds"):
        cli._read_json(oversized, max_bytes=16)


def test_markdown_escapes_all_active_markdown_constructs():
    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text())
    payload["sources"][0]["text"] = "Setup stops at step 3. [click](javascript:alert(1)) ![x](https://evil.invalid/x) **bold** # heading <script>x</script>"
    markdown = render_markdown(analyze(payload))
    for active in ("[click]", "](javascript:", "![x]", "**bold**", "<script>"):
        assert active not in markdown
    assert "Setup stops at step 3." in markdown


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t=", "\u200b=", "\ufeff="])
def test_csv_formula_prefixes_are_inert(prefix):
    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text())
    payload["areas"][1]["next_check"] = prefix + "CMD()"
    rows = list(csv.DictReader(io.StringIO(render_csv(analyze(payload)))))
    request_row = next(row for row in rows if row["classification"] == "request")
    assert request_row["next_check"].startswith("'")


@pytest.mark.parametrize("prefix", ["\u202e=", "\u200f@", "\u061c+"])
def test_csv_bidi_prefix_cannot_hide_formula_prefix(prefix):
    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text())
    payload["areas"][1]["next_check"] = prefix + "CMD()"
    rows = list(csv.DictReader(io.StringIO(render_csv(analyze(payload)))))
    request_row = next(row for row in rows if row["classification"] == "request")
    assert "\u202e" not in request_row["next_check"]
    assert "\u200f" not in request_row["next_check"]
    assert "\u061c" not in request_row["next_check"]
    assert request_row["next_check"].startswith("'")


def test_csv_removes_embedded_unicode_bidi_controls_only_from_csv():
    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text())
    payload["areas"][1]["next_check"] = "Confirm\u202e export"
    report = analyze(payload)
    row = next(row for row in csv.DictReader(io.StringIO(render_csv(report))) if row["classification"] == "request")
    assert row["next_check"] == "Confirm export"
    assert "\u202e" in report["cards"][1]["next_check"]
