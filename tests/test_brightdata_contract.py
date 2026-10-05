import hashlib
import itertools
import json
from copy import deepcopy

import pytest

from reviews_into_fixes.brightdata import (
    AMAZON_DATASET, HttpResponse, TransportError, collect, normalize_export, plan, resume,
)


NOW = "2026-10-05T00:00:00Z"
APPROVAL_SEQUENCE = itertools.count(1)


def amazon_manifest(urls=None, count=2):
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [{
        "id": "reviews", "kind": "amazon_reviews", "role": "review", "source_prefix": "amz",
        "urls": urls or ["https://www.amazon.com/dp/B012345678"], "max_reviews": count,
    }]}


def approval(value, urls, records=50):
    sequence = next(APPROVAL_SEQUENCE)
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "approval_id": f"approval-{sequence}",
            "nonce": f"{sequence:064x}", "issued_at": "2026-10-04T23:50:00Z", "manifest_sha256": digest,
            "expires_at": "2026-10-05T00:05:00Z", "max_requests": 1, "max_retained_records": records,
            "approved_urls": urls, "account_budget_confirmed": True, "target_permissions_confirmed": True,
            "remote_resolution_risk_accepted": True}


def record(text="Setup fails.", **extra):
    return {"url": "https://www.amazon.com/dp/B012345678", "review_id": "R1",
            "review_header": "Setup", "review_text": text, "review_posted_date": "2026-10-04T10:00:00Z", **extra}


def pending_receipt():
    manifest = amazon_manifest()
    job = manifest["jobs"][0]
    return {"schema_version": "1.0", "project": "reviews-into-fixes", "manifest_sha256": plan(manifest)["manifest_sha256"],
            "status": "pending", "provider_completeness": "unknown", "requests_made": 1, "returned_records": 0, "retained_records": 0,
            "excluded_records": 0, "jobs": [{"id": "reviews", "kind": "amazon_reviews", "state": "pending",
            "original_job": job, "requested_records": 2, "returned_records": 0, "retained_records": 0,
            "excluded_records": 0, "snapshot_id": "snap_1", "error_code": "pending_snapshot",
            "query_metadata": None}], "warnings": [], "provider_cost_usd": None}


def test_timeout_is_completion_unknown_after_exactly_one_request():
    manifest = amazon_manifest()
    calls = []
    def timeout(request):
        calls.append(request)
        raise TimeoutError("secret provider detail")
    result = collect(manifest, approval=approval(manifest, manifest["jobs"][0]["urls"], 2), api_key="secret",
                     zones={}, transport=timeout, now=NOW)
    assert len(calls) == 1
    assert result["receipt"]["status"] == "completion_unknown"
    assert result["receipt"]["provider_completeness"] == "unknown"
    assert result["receipt"]["requests_made"] == 1
    assert result["receipt"]["jobs"][0]["state"] == "completion_unknown"
    assert "secret" not in json.dumps(result)


def test_normalizer_does_not_truncate_oversize_record_fields():
    records = [record(review_id="x" * 201), record(review_header="x" * 201, review_id="R2"),
               record(review_posted_date="x" * 101, review_id="R3")]
    library = normalize_export("amazon_reviews", records, role="review",
        source_url="https://www.amazon.com/dp/B012345678", observed_at=NOW, source_prefix="amz")
    assert library["sources"] == []
    assert library["receipt"]["returned_records"] == 3
    assert library["receipt"]["excluded_records"] == 3
    assert library["receipt"]["status"] == "processed_with_exclusions"
    assert library["receipt"]["provider_completeness"] == "unknown"


def test_normalizer_drops_person_metadata_and_preserves_valid_record():
    library = normalize_export("amazon_reviews", [record(username="person", profile_url="https://bad.invalid")],
        role="review", source_url="https://www.amazon.com/dp/B012345678", observed_at=NOW, source_prefix="amz")
    assert len(library["sources"]) == 1
    assert "username" not in library["sources"][0]
    assert library["receipt"]["excluded_records"] == 0


def test_empty_imported_web_page_has_empty_local_receipt_state():
    library = normalize_export("web_page", "  \n\n", role="product_instructions",
        source_url="https://docs.python.org/3/", observed_at=NOW, source_prefix="help")
    assert library["sources"][0]["status"] == "empty"
    assert library["receipt"]["status"] == "empty"
    assert library["receipt"]["provider_completeness"] == "unknown"


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(schema_version="2.0"),
    lambda r: r.update(extra=True),
    lambda r: r["jobs"][0].update(kind="web_page"),
    lambda r: r["jobs"][0]["original_job"].update(kind="web_page"),
    lambda r: r["jobs"][0].update(requested_records=0),
    lambda r: r["jobs"][0].update(snapshot_id="../bad"),
    lambda r: r["jobs"][0].update(state="mystery"),
    lambda r: r.update(returned_records=1),
    lambda r: r.update(requests_made=0),
])
def test_resume_rejects_malformed_receipt_before_request(mutation):
    receipt = pending_receipt()
    mutation(receipt)
    calls = []
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_1?format=json"
    with pytest.raises(ValueError):
        resume(receipt, approval=approval(receipt, [url], 2), api_key="secret",
               transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


def test_resume_validates_provider_array_after_one_request():
    receipt = pending_receipt()
    url = "https://api.brightdata.com/datasets/v3/snapshot/snap_1?format=json"
    calls = []
    def transport(request):
        calls.append(request)
        return HttpResponse(200, {}, b'{"not":"an array"}')
    with pytest.raises(TransportError, match="invalid_response"):
        resume(receipt, approval=approval(receipt, [url], 2), api_key="secret", transport=transport, now=NOW)
    assert len(calls) == 1


def test_scraper_request_is_pinned_bounded_and_metadata_minimized():
    manifest = amazon_manifest()
    calls = []
    def transport(request):
        calls.append(request)
        return HttpResponse(200, {}, json.dumps([record(username="drop")]).encode())
    result = collect(manifest, approval=approval(manifest, manifest["jobs"][0]["urls"], 2), api_key="secret",
                     zones={}, transport=transport, now=NOW)
    assert len(calls) == 1
    assert f"dataset_id={AMAZON_DATASET}" in calls[0].url
    assert json.loads(calls[0].body)["input"] == [{"url": manifest["jobs"][0]["urls"][0], "max_reviews": 2}]
    assert "username" not in result["sources"][0]


def test_plan_rejects_boolean_count_and_cross_project_kind():
    bad = amazon_manifest(count=True)
    with pytest.raises(ValueError):
        plan(bad)
    bad = amazon_manifest()
    bad["jobs"][0]["kind"] = "youtube_comments"
    with pytest.raises(ValueError):
        plan(bad)
