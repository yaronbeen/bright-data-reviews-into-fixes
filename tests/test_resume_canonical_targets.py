"""Collect-to-resume regression for accepted noncanonical target spellings."""

import hashlib
import json

from reviews_into_fixes.brightdata import AMAZON_DATASET, HttpResponse, collect, plan, resume


NOW = "2026-10-05T00:00:00Z"
AMAZON_A = "https://www.amazon.com/dp/B012345678"
AMAZON_B_RAW = "https://www.amazon.com:443/dp/B098765432"
AMAZON_B = "https://www.amazon.com/dp/B098765432"
SNAPSHOT_ID = "snap_canonical_targets"
SNAPSHOT_URL = f"https://api.brightdata.com/datasets/v3/snapshot/{SNAPSHOT_ID}?format=json"


def test_collect_pending_resume_preserves_raw_job_and_maps_canonical_second_target():
    job = {
        "id": "reviews", "kind": "amazon_reviews", "role": "review",
        "source_prefix": "canonical", "urls": [AMAZON_A, AMAZON_B_RAW], "max_reviews": 1,
    }
    manifest = {"schema_version": "1.0", "project": "reviews-into-fixes", "jobs": [job]}
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    planned = plan(manifest)
    assert planned["manifest_sha256"] == manifest_hash
    assert planned["jobs"][0]["urls"] == [AMAZON_A, AMAZON_B]

    collect_approval = {
        "schema_version": "1.0", "project": "reviews-into-fixes",
        "approval_id": "canonical-targets-collect",
        "nonce": hashlib.sha256(b"canonical-targets-collect").hexdigest(),
        "manifest_sha256": manifest_hash,
        "issued_at": "2026-10-04T23:50:00Z", "expires_at": "2026-10-05T00:05:00Z",
        "max_requests": 1, "max_retained_records": 2,
        "approved_urls": [AMAZON_A, AMAZON_B], "account_budget_confirmed": True,
        "target_permissions_confirmed": True, "remote_resolution_risk_accepted": True,
    }
    calls = []
    pending = collect(
        manifest, approval=collect_approval, api_key="fake-canonical-token", zones={}, now=NOW,
        transport=lambda request: calls.append(request) or HttpResponse(
            202, {}, json.dumps({"snapshot_id": SNAPSHOT_ID}).encode()
        ),
    )

    assert len(calls) == 1 and calls[0].method == "POST"
    assert calls[0].url == (
        "https://api.brightdata.com/datasets/v3/scrape?"
        f"dataset_id={AMAZON_DATASET}&format=json&include_errors=true"
    )
    assert json.loads(calls[0].body)["input"] == [
        {"url": AMAZON_A, "max_reviews": 1}, {"url": AMAZON_B, "max_reviews": 1},
    ]
    receipt = pending["receipt"]
    assert pending["sources"] == []
    assert receipt["status"] == "pending" and receipt["requests_made"] == 1
    assert receipt["manifest_sha256"] == manifest_hash
    assert receipt["jobs"][0]["original_job"] == json.loads(manifest_bytes)["jobs"][0]
    assert receipt["jobs"][0]["original_job"]["urls"] == [AMAZON_A, AMAZON_B_RAW]
    assert receipt["jobs"][0]["snapshot_id"] == SNAPSHOT_ID
    assert receipt["jobs"][0]["requested_records"] == 2

    resume_approval = {
        **collect_approval, "approval_id": "canonical-targets-resume",
        "nonce": hashlib.sha256(b"canonical-targets-resume").hexdigest(),
        "manifest_sha256": hashlib.sha256(json.dumps(
            receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "approved_urls": [SNAPSHOT_URL],
    }
    record = {
        "url": AMAZON_B, "review_id": "invented-canonical-second",
        "review_header": "Invented second-target report", "review_text": "Setup fails.",
        "review_posted_date": NOW,
    }
    result = resume(
        receipt, approval=resume_approval, api_key="fake-canonical-token", now=NOW,
        transport=lambda request: calls.append(request) or HttpResponse(200, {}, json.dumps([record]).encode()),
    )

    assert [request.method for request in calls] == ["POST", "GET"]
    assert calls[1].url == SNAPSHOT_URL
    assert result["receipt"]["requests_made"] == 2
    assert result["receipt"]["manifest_sha256"] == manifest_hash
    assert result["receipt"]["jobs"][0]["original_job"] == json.loads(manifest_bytes)["jobs"][0]
    assert json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() == manifest_bytes
    assert [source["url"] for source in result["sources"]] == [AMAZON_B], {
        "status": result["receipt"]["status"],
        "returned_records": result["receipt"]["returned_records"],
        "retained_records": result["receipt"]["retained_records"],
        "excluded_records": result["receipt"]["excluded_records"],
        "warnings": result["receipt"]["warnings"],
    }
    assert result["sources"][0]["record_id"] == record["review_id"]
    assert result["receipt"]["status"] == "processed"
    assert (result["receipt"]["returned_records"], result["receipt"]["retained_records"],
            result["receipt"]["excluded_records"]) == (1, 1, 0)
    assert result["receipt"]["provider_completeness"] == "unknown"
