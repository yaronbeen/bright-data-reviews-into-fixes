import json
import socket
import tomllib
from pathlib import Path

import pytest

from reviews_into_fixes import cli
from reviews_into_fixes.brightdata import HttpResponse, TransportError, plan


ROOT = Path(__file__).parents[1]


def test_offline_cli_and_module_entry_need_no_network(monkeypatch, tmp_path):
    monkeypatch.delenv("BRIGHT_DATA_API_KEY", raising=False)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network attempted")))
    assert cli.main(["analyze", str(ROOT / "fixtures" / "demo.json"), "--out-dir", str(tmp_path)]) == 0
    assert {path.name for path in tmp_path.iterdir()} == {"report.json", "fixes.md", "fixes.csv"}


def test_live_dry_run_validates_live_targets_and_writes_nothing(tmp_path, capsys):
    output = tmp_path / "never.json"
    code = cli.main(["collect", str(ROOT / "fixtures" / "manifest.json"), "--out", str(output), "--live", "--dry-run"])
    error = json.loads(capsys.readouterr().err)
    assert code == 2
    assert error == {"code": "invalid_input", "message": "live target is not allowed", "requests_made": 0}
    assert not output.exists()


def test_analysis_three_file_write_rolls_back_on_replace_failure(monkeypatch, tmp_path):
    outputs = {tmp_path / "report.json": "new-json", tmp_path / "fixes.md": "new-md", tmp_path / "fixes.csv": "new-csv"}
    for path in outputs:
        path.write_text("old-" + path.name)
    original = cli.os.replace
    calls = []
    def fail_second(source, destination):
        calls.append(Path(destination).name)
        if len(calls) == 2:
            raise OSError("private filesystem detail")
        return original(source, destination)
    monkeypatch.setattr(cli.os, "replace", fail_second)
    with pytest.raises(OSError):
        cli._write_many(outputs, overwrite=True)
    assert {path.name: path.read_text() for path in outputs} == {path.name: "old-" + path.name for path in outputs}
    assert not list(tmp_path.glob(".*.tmp-*"))


def test_collision_changes_no_file(tmp_path):
    existing = tmp_path / "report.json"
    existing.write_text("keep")
    with pytest.raises(ValueError):
        cli._write_many({existing: "replace", tmp_path / "fixes.md": "new", tmp_path / "fixes.csv": "new"}, False)
    assert existing.read_text() == "keep"
    assert not (tmp_path / "fixes.md").exists()


def test_public_error_is_fixed_and_does_not_echo_exception(monkeypatch, tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "amz",
        "urls": ["https://www.amazon.com/dp/B012345678"], "max_reviews": 1}]}))
    approval = tmp_path / "approval.json"
    approval.write_text("{}")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "secret-token")
    monkeypatch.setenv("BRIGHT_DATA_WEB_UNLOCKER_ZONE", "zone")
    monkeypatch.setenv("REVIEWS_INTO_FIXES_NOW", "2026-10-05T00:00:00Z")
    monkeypatch.setattr(cli, "collect", lambda *a, **k: (_ for _ in ()).throw(TransportError("provider_http_error")))
    code = cli.main(["collect", str(manifest), "--out", str(tmp_path / "out.json"), "--live",
                     "--accept-charges", "--approval", str(approval)])
    error = json.loads(capsys.readouterr().err)
    assert code == 3
    assert error == {"code": "provider_http_error", "message": "Collection failed safely.", "requests_made": 0}
    assert "secret-token" not in json.dumps(error)


def test_completion_unknown_cli_returns_four(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "amz",
        "urls": ["https://www.amazon.com/dp/B012345678"], "max_reviews": 1}]}))
    approval = tmp_path / "approval.json"
    approval.write_text("{}")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "secret")
    monkeypatch.setenv("REVIEWS_INTO_FIXES_NOW", "2026-10-05T00:00:00Z")
    monkeypatch.setattr(cli, "collect", lambda *a, **k: {"sources": [], "receipt": {"status": "completion_unknown", "requests_made": 1}})
    assert cli.main(["collect", str(manifest), "--out", str(tmp_path / "out.json"), "--live",
                     "--accept-charges", "--approval", str(approval)]) == 4


def test_collect_output_write_failure_persists_recovery_receipt_and_actual_count(monkeypatch, tmp_path, capsys):
    manifest_data = {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "amz",
        "urls": ["https://www.amazon.com/dp/B012345678"], "max_reviews": 1}]}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(manifest_data))
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "schema_version": "1.0", "project": "reviews-into-fixes", "approval_id": "persist_failure",
        "nonce": "a" * 64, "issued_at": "2026-10-04T23:50:00Z",
        "manifest_sha256": plan(manifest_data)["manifest_sha256"], "expires_at": "2026-10-05T00:05:00Z",
        "max_requests": 1, "max_retained_records": 1,
        "approved_urls": ["https://www.amazon.com/dp/B012345678"],
        "account_budget_confirmed": True, "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    monkeypatch.setenv("REVIEWS_INTO_FIXES_NOW", "ignored")
    monkeypatch.setattr(cli, "_system_now", lambda: "2026-10-05T00:00:00Z")
    calls = []
    records = json.dumps([{"url": "https://www.amazon.com/dp/B012345678", "review_id": "R1",
                           "review_header": "Setup", "review_text": "Setup fails.",
                           "review_posted_date": "2026-10-04T10:00:00Z"}]).encode()
    monkeypatch.setattr(cli, "_transport", lambda request: calls.append(request) or HttpResponse(200, {}, records))
    monkeypatch.setattr(cli, "_atomic_write", lambda *a, **k: (_ for _ in ()).throw(OSError("disk detail")))

    code = cli.main(["collect", str(manifest), "--out", str(tmp_path / "target.library.json"), "--live",
                     "--accept-charges", "--approval", str(approval)])

    error = json.loads(capsys.readouterr().err)
    recovery_path = Path(error["recovery_path"])
    recovered = json.loads(recovery_path.read_text())
    assert code == 2
    assert len(calls) == 1
    assert error["code"] == "output_persist_failed"
    assert error["requests_made"] == 1
    assert error["receipt_id"] == recovered["recovery_id"]
    assert error["source_ids"] == [recovered["sources"][0]["id"]]
    assert error["job_ids"] == ["reviews"]
    assert recovered["sources"][0]["record_id"] == "R1"
    assert recovered["receipt"]["jobs"][0]["id"] == "reviews"
    assert recovery_path.stat().st_mode & 0o077 == 0
    assert not (tmp_path / "target.library.json").exists()


def test_collect_reports_actual_count_and_identifiers_if_recovery_write_also_fails(monkeypatch, tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "amz",
        "urls": ["https://www.amazon.com/dp/B012345678"], "max_reviews": 1}]}))
    approval = tmp_path / "approval.json"
    approval.write_text("{}")
    library = {"schema_version": "1.0", "project": "reviews-into-fixes", "transport_contract_version": "1.0",
               "sources": [{"id": "source_1"}], "receipt": {"requests_made": 1, "jobs": [{"id": "job_1"}]}}
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    monkeypatch.setattr(cli, "collect", lambda *a, **k: library)
    monkeypatch.setattr(cli, "_atomic_write", lambda *a, **k: (_ for _ in ()).throw(OSError("target failure")))
    monkeypatch.setattr(cli, "_write_recovery_library", lambda value: (_ for _ in ()).throw(OSError("recovery failure")))

    code = cli.main(["collect", str(manifest), "--out", str(tmp_path / "target.library.json"), "--live",
                     "--accept-charges", "--approval", str(approval)])

    error = json.loads(capsys.readouterr().err)
    assert code == 2
    assert error["code"] == "output_persist_failed"
    assert error["requests_made"] == 1
    assert error["recovery_saved"] is False
    assert error["source_ids"] == ["source_1"]
    assert error["job_ids"] == ["job_1"]


def test_help_and_version_entry_points(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "0.1.0" in capsys.readouterr().out


def test_distribution_and_cli_are_brand_neutral(capsys):
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert metadata["project"]["name"] == "reviews-into-fixes"
    assert metadata["project"]["scripts"] == {"reviews-into-fixes": "reviews_into_fixes.cli:main"}
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "reviews-into-fixes" in capsys.readouterr().out
    guide = (ROOT / "docs" / "technical-guide.md").read_text()
    assert "https://docs.brightdata.com/api-reference/scrapers/e-commerce-apis/amazon-reviews-collect-by-url" in guide
