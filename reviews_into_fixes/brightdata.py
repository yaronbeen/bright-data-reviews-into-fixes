"""Optional bounded Bright Data ingestion with explicit local approval gates."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit

from .core import PROJECT, SCHEMA_VERSION, _utc, canonical_url, normalize_text

TRANSPORT_VERSION = "1.0"
API_HOST = "api.brightdata.com"
AMAZON_DATASET = "gd_le8e811kzy4ggddlq"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_APPROVAL_LIFETIME_SECONDS = 15 * 60
SENSITIVE_QUERY_KEYS = {"token", "password", "secret", "api_key", "auth", "session", "signature"}
SAFE_SNAPSHOT_RE = re.compile(r"^[A-Za-z0-9_]{1,128}$")
_CONSUMED_APPROVALS: set[tuple[str, str]] = set()
_CONSUMED_APPROVALS_LOCK = threading.Lock()


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_seconds: int = 75


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class TransportError(RuntimeError):
    def __init__(self, code: str = "transport_error", *, receipt: dict | None = None):
        self.code = code
        self.receipt = receipt
        super().__init__(code)


def _hash(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _live_url(value: object) -> str:
    value = canonical_url(value)
    parts = urlsplit(value)
    if parts.port not in (None, 443):
        raise ValueError("live target may only use port 443")
    host = parts.hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal live targets are not allowed")
    labels = host.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label) for label in labels):
        raise ValueError("live target hostname is invalid")
    if labels[-1].isdigit() or host == "localhost" or any(host.endswith(suffix) for suffix in (".localhost", ".local", ".internal", ".invalid", ".example", ".test")):
        raise ValueError("reserved/private live target is not allowed")
    if host in {"example.com", "example.org", "example.net"} or any(host.endswith("." + domain) for domain in ("example.com", "example.org", "example.net")):
        raise ValueError("fixture host is not allowed in live mode")
    if any(key.casefold() in SENSITIVE_QUERY_KEYS for key, _ in parse_qsl(parts.query, keep_blank_values=True)):
        raise ValueError("sensitive query parameter is not allowed")
    return value


def _manifest(manifest: dict, *, live_urls: bool = False) -> tuple[list[dict], list[dict]]:
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "project", "jobs"}:
        raise ValueError("manifest has invalid fields")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["project"] != PROJECT:
        raise ValueError("manifest schema/project mismatch")
    jobs = manifest["jobs"]
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 4:
        raise ValueError("manifest jobs must contain 1..4 entries")
    ids = set()
    planned = []
    review_batches = 0
    page_count = 0
    for job in jobs:
        if not isinstance(job, dict) or "id" not in job or "kind" not in job:
            raise ValueError("invalid job")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", str(job["id"])) or job["id"] in ids:
            raise ValueError("job IDs must be valid and unique")
        ids.add(job["id"])
        kind = job["kind"]
        if kind == "web_page":
            allowed = {"id", "kind", "role", "source_id", "url", "country"}
            if set(job) - allowed or not {"id", "kind", "role", "source_id", "url"} <= set(job):
                raise ValueError("invalid web_page job fields")
            if job["role"] != "product_instructions" or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", str(job["source_id"])):
                raise ValueError("invalid web_page role/source_id")
            url = _live_url(job["url"]) if live_urls else canonical_url(job["url"])
            country = job.get("country")
            if country is not None and not re.fullmatch(r"[a-z]{2}", str(country)):
                raise ValueError("country must be two lowercase ASCII letters")
            page_count += 1
            if page_count > 3:
                raise ValueError("at most three help pages are allowed")
            planned.append({"id": job["id"], "kind": kind, "role": job["role"], "urls": [url], "requested_records": None})
        elif kind == "amazon_reviews":
            allowed = {"id", "kind", "role", "source_prefix", "urls", "max_reviews"}
            if set(job) != allowed or job["role"] != "review" or not re.fullmatch(r"[a-z][a-z0-9_-]{0,46}", str(job["source_prefix"])):
                raise ValueError("invalid amazon_reviews job")
            urls = job["urls"]
            count = job["max_reviews"]
            if not isinstance(urls, list) or not 1 <= len(urls) <= 2 or isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 25:
                raise ValueError("invalid Amazon review bounds")
            normalized = []
            for raw_url in urls:
                url = _live_url(raw_url) if live_urls else canonical_url(raw_url)
                parts = urlsplit(url)
                if live_urls and parts.query:
                    raise ValueError("Amazon live target query parameters are not allowed")
                amazon_path = re.fullmatch(r"/(?:dp|gp/product|product-reviews)/[A-Z0-9]{10}/?", parts.path)
                review_path = re.fullmatch(r"/gp/customer-reviews/[A-Za-z0-9]{1,100}/?", parts.path)
                if parts.hostname not in {"amazon.com", "www.amazon.com"} or not (amazon_path or review_path):
                    raise ValueError("unsupported Amazon review URL")
                normalized.append(url)
            review_batches += 1
            if review_batches > 1 or count * len(urls) > 50:
                raise ValueError("only one bounded review batch is allowed")
            planned.append({"id": job["id"], "kind": kind, "role": "review", "urls": normalized, "requested_records": count * len(urls)})
        else:
            raise ValueError("unsupported job kind")
    return jobs, planned


def plan(manifest: dict) -> dict:
    """Validate a collection manifest and make zero requests."""
    _, planned = _manifest(manifest)
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "manifest_sha256": _hash(manifest),
            "request_count": len(planned), "requests_made": 0, "jobs": planned}


def validate_live_manifest(manifest: dict) -> dict:
    """Apply live-target restrictions while still making zero requests."""
    _, planned = _manifest(manifest, live_urls=True)
    if any(job["kind"] == "web_page" for job in planned):
        raise ValueError("live Web Unlocker redirect scope cannot be verified")
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "manifest_sha256": _hash(manifest),
            "request_count": len(planned), "requests_made": 0, "jobs": planned}


def _parse_date(value: object) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    raw = value[:100]
    if raw.endswith("Z") or re.search(r"[+-]\d\d:\d\d$", raw):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo:
                return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), raw
        except ValueError:
            pass
    return None, raw


def _normalize_records(kind: str, records: list, *, role: str, source_url: str, observed_at: str,
                       source_prefix: str, provenance: str, limit: int = 50,
                       use_record_url: bool = False) -> tuple[list[dict], list[dict], int]:
    if kind not in {"amazon_reviews", "google_maps_reviews"} or role != "review":
        raise ValueError("unsupported export kind/role")
    if not isinstance(records, list):
        raise ValueError("review export must be a JSON array")
    canonical_url(source_url)
    _utc(observed_at, "observed_at")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,46}", source_prefix):
        raise ValueError("invalid source_prefix")
    sources, warnings = [], []
    seen: dict[tuple[str, str], dict] = {}
    conflicted: set[tuple[str, str]] = set()
    excluded = 0
    for record in records[:limit]:
        if not isinstance(record, dict):
            excluded += 1
            continue
        if kind == "amazon_reviews":
            text, raw_title, record_id, date = record.get("review_text"), record.get("review_header"), record.get("review_id"), record.get("review_posted_date")
            title = raw_title if raw_title is not None and raw_title != "" else "Review"
        else:
            text, title, record_id, date = record.get("review"), "Public review", record.get("review_id"), record.get("review_date")
        invalid_field = (
            not isinstance(text, str) or not text.strip() or len(text) > 5000
            or not isinstance(title, str) or not title.strip() or len(title) > 200
            or (record_id is not None and (not isinstance(record_id, str) or len(record_id) > 200))
            or (date is not None and (not isinstance(date, str) or not date.strip() or len(date) > 100))
        )
        if invalid_field:
            excluded += 1
            warnings.append({"code": "text_too_long" if isinstance(text, str) and len(text) > 5000 else "invalid_record", "source_ids": [], "note": "A provider record was excluded."})
            continue
        try:
            canonical, _ = normalize_text(text)
            url = canonical_url(record.get("url") or source_url) if use_record_url else canonical_url(source_url)
        except (TypeError, ValueError):
            excluded += 1
            warnings.append({"code": "invalid_record", "source_ids": [], "note": "A provider record was excluded."})
            continue
        if record_id is None or not record_id.strip():
            record_id = "content-" + hashlib.sha256(canonical.encode()).hexdigest()[:16]
            origin = "content_hash"
        else:
            record_id, origin = record_id, "provider"
        seed = json.dumps(["review", url, record_id], ensure_ascii=False, separators=(",", ":")).encode()
        source_id = source_prefix + "-" + hashlib.sha256(seed).hexdigest()[:16]
        published, provider_date = _parse_date(date)
        source = {"id": source_id, "kind": "review", "role": role, "url": url,
                  "title": title, "text": canonical, "status": "collected",
                  "observed_at": observed_at, "published_at": published, "provider_date": provider_date,
                  "record_id": record_id, "record_id_origin": origin, "provenance": provenance}
        identity = (url, record_id)
        if identity in conflicted:
            excluded += 1
            continue
        if identity in seen:
            previous = seen[identity]
            if previous["text"] == canonical:
                excluded += 1
                warnings.append({"code": "duplicate_record", "source_ids": [previous["id"], source_id],
                                 "note": "An identical duplicate provider record was excluded."})
                continue
            seen.pop(identity)
            sources.remove(previous)
            conflicted.add(identity)
            excluded += 2
            warnings.append({"code": "conflicting_record", "source_ids": [previous["id"], source_id],
                             "note": "Conflicting records with the same identity were excluded."})
            continue
        seen[identity] = source
        sources.append(source)
    if len(records) > limit:
        excluded += len(records) - limit
        warnings.append({"code": "provider_limit_exceeded", "source_ids": [], "note": "Records beyond the local retention limit were excluded."})
    return sources, warnings, excluded


def _normalize_amazon_response(records: list, *, urls: list[str], observed_at: str,
                               source_prefix: str, limit: int) -> tuple[list[dict], list[dict], int]:
    usable_records, warnings = [], []
    excluded = 0
    for record in records:
        if record.get("error_code") is not None:
            code = str(record.get("error_code", "")).casefold()
            safe_code = code if code in {"dead_page", "bucket_rate_limit", "global_rate_limit"} else "record_error"
            warnings.append({"code": safe_code, "source_ids": [], "note": "A provider error record was excluded."})
            excluded += 1
        elif len(urls) == 1:
            usable_records.append({**record, "url": urls[0]})
        else:
            try:
                returned_url = canonical_url(record.get("url"))
            except (TypeError, ValueError):
                returned_url = None
            if returned_url not in urls:
                warnings.append({"code": "invalid_record", "source_ids": [], "note": "A record outside approved targets was excluded."})
                excluded += 1
            else:
                usable_records.append({**record, "url": returned_url})
    sources, record_warnings, record_excluded = _normalize_records(
        "amazon_reviews", usable_records, role="review", source_url=urls[0], observed_at=observed_at,
        source_prefix=source_prefix, provenance="bright_data", limit=limit, use_record_url=True,
    )
    return sources, warnings + record_warnings, excluded + record_excluded


def normalize_export(kind, records, *, role, source_url, observed_at, source_prefix) -> dict:
    """Normalize an already-authorized local provider export without HTTP."""
    if kind == "web_page":
        if role != "product_instructions" or not isinstance(records, str):
            raise ValueError("unsupported export kind/role")
        url = canonical_url(source_url)
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,46}", source_prefix):
            raise ValueError("invalid source_prefix")
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        canonical, blocks = normalize_text(records)
        source_id = source_prefix + "-" + hashlib.sha256(url.encode()).hexdigest()[:16]
        heading = next((block["text"] for block in blocks if block["kind"] == "heading"), "Selected public page")
        sources = [{"id": source_id, "kind": "page", "role": role, "url": url, "title": heading[:200],
                    "text": canonical, "status": "collected" if canonical else "empty", "observed_at": observed_at,
                    "published_at": None, "provider_date": None, "record_id": None, "record_id_origin": "none",
                    "provenance": "operator_supplied"}]
        warnings, excluded, returned_count = [], 0, 1
    else:
        sources, warnings, excluded = _normalize_records(kind, records, role=role, source_url=source_url,
                                                           observed_at=observed_at, source_prefix=source_prefix,
                                                           provenance="operator_supplied")
        returned_count = len(records)
    status = (
        "processed_with_exclusions" if excluded
        else "processed" if any(source["status"] == "collected" for source in sources)
        else "empty"
    )
    receipt = {"schema_version": SCHEMA_VERSION, "project": PROJECT, "manifest_sha256": None,
               "status": status, "provider_completeness": "unknown", "requests_made": 0,
               "returned_records": returned_count, "retained_records": len(sources), "excluded_records": excluded,
               "jobs": [], "warnings": warnings, "provider_cost_usd": None}
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "transport_contract_version": TRANSPORT_VERSION,
            "sources": sources, "receipt": receipt}


def _approval(manifest: dict, approval: dict, planned: list[dict], now: str) -> tuple[str, str]:
    required = {"schema_version", "project", "approval_id", "nonce", "issued_at", "manifest_sha256",
                "expires_at", "max_requests", "max_retained_records",
                "approved_urls", "account_budget_confirmed", "target_permissions_confirmed", "remote_resolution_risk_accepted"}
    if not isinstance(approval, dict) or set(approval) != required:
        raise ValueError("invalid approval")
    approval_id = approval["approval_id"]
    nonce = approval["nonce"]
    if not isinstance(approval_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", approval_id):
        raise ValueError("invalid approval")
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{64}", nonce):
        raise ValueError("invalid approval")
    if approval["schema_version"] != SCHEMA_VERSION or approval["project"] != PROJECT or approval["manifest_sha256"] != _hash(manifest):
        raise ValueError("approval does not match manifest")
    issued_at = _utc(approval["issued_at"], "issued_at")
    expires_at = _utc(approval["expires_at"], "expires_at")
    current = _utc(now, "now")
    issued = datetime.fromisoformat(issued_at[:-1] + "+00:00")
    expires = datetime.fromisoformat(expires_at[:-1] + "+00:00")
    current_time = datetime.fromisoformat(current[:-1] + "+00:00")
    if not issued <= current_time < expires:
        raise ValueError("approval has expired")
    lifetime = (expires - issued).total_seconds()
    if lifetime <= 0 or lifetime > MAX_APPROVAL_LIFETIME_SECONDS:
        raise ValueError("approval lifetime exceeds local limit")
    if any(approval[key] is not True for key in ("account_budget_confirmed", "target_permissions_confirmed", "remote_resolution_risk_accepted")):
        raise ValueError("approval attestations are required")
    if (isinstance(approval["max_requests"], bool) or not isinstance(approval["max_requests"], int)
            or not 1 <= approval["max_requests"] <= 4 or approval["max_requests"] < len(planned)):
        raise ValueError("approval request allowance is insufficient")
    requested = sum(job["requested_records"] if job["requested_records"] is not None else 1 for job in planned)
    if (isinstance(approval["max_retained_records"], bool) or not isinstance(approval["max_retained_records"], int)
            or not 1 <= approval["max_retained_records"] <= 50 or requested > approval["max_retained_records"]):
        raise ValueError("approval retained-record allowance is insufficient")
    if not isinstance(approval["approved_urls"], list) or not approval["approved_urls"]:
        raise ValueError("invalid approval")
    if any(not isinstance(url, str) for url in approval["approved_urls"]):
        raise ValueError("invalid approval")
    try:
        if any(canonical_url(url) != url for url in approval["approved_urls"]):
            raise ValueError("invalid approval")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid approval") from exc
    approved_urls = set(approval["approved_urls"])
    if len(approved_urls) != len(approval["approved_urls"]):
        raise ValueError("invalid approval")
    if any(url not in approved_urls for job in planned for url in job["urls"]):
        raise ValueError("approval does not include every target URL")
    return approval_id, nonce, _hash(approval)


def _consume_approval(approval_id: str, nonce: str, approval_digest: str, consumer=None) -> None:
    if consumer is not None:
        consumer({"approval_id": approval_id, "nonce": nonce, "approval_sha256": approval_digest})
        return
    key = (approval_id, nonce)
    with _CONSUMED_APPROVALS_LOCK:
        if key in _CONSUMED_APPROVALS:
            raise ValueError("approval already consumed")
        _CONSUMED_APPROVALS.add(key)


def _response_ok(response: HttpResponse) -> None:
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise TransportError("response_too_large")
    headers = {key.casefold(): value for key, value in response.headers.items()}
    error_headers = {"x-brd-error-code", "x-brd-err-code", "x-luminati-error-code", "x-brd-error", "x-brd-err-msg", "x-luminati-error"}
    embedded_status = headers.get("x-brd-status-code") or headers.get("x-luminati-status-code")
    if embedded_status is not None:
        if not embedded_status.isdigit():
            raise TransportError("invalid_response")
        if not 200 <= int(embedded_status) < 300:
            raise TransportError("provider_target_error")
    if any(key in headers for key in error_headers) or not 200 <= response.status < 300:
        raise TransportError("provider_http_error")


def _pending_response_ok(response: HttpResponse) -> None:
    if len(response.body) > MAX_RESPONSE_BYTES:
        raise TransportError("response_too_large")
    headers = {key.casefold(): value for key, value in response.headers.items()}
    error_headers = {"x-brd-error-code", "x-brd-err-code", "x-luminati-error-code", "x-brd-error", "x-brd-err-msg", "x-luminati-error"}
    if any(key in headers for key in error_headers):
        raise TransportError("provider_http_error")
    embedded_status = headers.get("x-brd-status-code") or headers.get("x-luminati-status-code")
    if embedded_status is not None:
        if not embedded_status.isdigit():
            raise TransportError("invalid_response")
        if not 200 <= int(embedded_status) < 300:
            raise TransportError("provider_target_error")
    if response.status not in {202, 409}:
        raise TransportError("provider_http_error")
    if response.body:
        try:
            payload = json.loads(response.body)
        except RecursionError as exc:
            raise TransportError("invalid_response") from exc
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and (
            "error" in payload or "error_code" in payload or str(payload.get("status", "")).casefold() in {"error", "failed"}
        ):
            raise TransportError("provider_http_error")


def _parse_web_markdown(body: bytes) -> tuple[str, list[dict]]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TransportError("invalid_response") from exc
    if text.lstrip().startswith("{"):
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError:
            envelope = None
        if envelope is not None:
            if not isinstance(envelope, dict) or not {"status_code", "headers", "body"} <= set(envelope):
                raise TransportError("response_contract_mismatch")
            status = envelope["status_code"]
            headers = envelope["headers"]
            envelope_body = envelope["body"]
            if (isinstance(status, bool) or not isinstance(status, int) or not isinstance(headers, dict)
                    or any(not isinstance(key, str) or not isinstance(value, str) for key, value in headers.items())
                    or not isinstance(envelope_body, str)):
                raise TransportError("invalid_response")
            encoded_body = envelope_body.encode("utf-8")
            response = HttpResponse(status, headers, encoded_body)
            _response_ok(response)
            text = envelope_body
    return normalize_text(text)


def collect(manifest, *, approval, api_key, zones, transport, now, approval_consumer=None) -> dict:
    """Execute an explicitly approved manifest sequentially, with no retries."""
    jobs, planned = _manifest(manifest, live_urls=True)
    approval_id, nonce, approval_digest = _approval(manifest, approval, planned, now)
    if not isinstance(api_key, str) or not api_key or not callable(transport):
        raise ValueError("api_key and transport are required")
    if not isinstance(zones, dict) or any(job["kind"] == "web_page" for job in planned) and not zones.get("web_unlocker"):
        raise ValueError("required Bright Data zone is missing")
    if any(job["kind"] == "web_page" for job in planned):
        raise ValueError("live Web Unlocker redirect scope cannot be verified")
    _consume_approval(approval_id, nonce, approval_digest, approval_consumer)
    sources, job_receipts, warnings = [], [], []
    requests_made = returned = excluded = 0
    status = "processed"
    deadline = time.monotonic() + 75
    for index, (job, item) in enumerate(zip(jobs, planned)):
        try:
            if job["kind"] == "web_page":
                data = {"zone": zones["web_unlocker"], "url": item["urls"][0], "format": "raw", "data_format": "markdown"}
                if job.get("country"):
                    data["country"] = job["country"]
                url = "https://api.brightdata.com/request"
            else:
                data = {"input": [{"url": url, "max_reviews": job["max_reviews"]} for url in item["urls"]],
                        "custom_output_fields": "url|review_id|review_text|review_header|review_posted_date"}
                url = f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={AMAZON_DATASET}&format=json&include_errors=true"
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError("transport_error")
            request = HttpRequest("POST", url, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                                  json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(),
                                  min(75, max(1, math.ceil(remaining))))
            requests_made += 1
            response = transport(request)
            _response_ok(response)
            if response.status == 202:
                try:
                    pending = json.loads(response.body)
                    snapshot_id = pending.get("snapshot_id") or pending.get("id")
                except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, RecursionError):
                    snapshot_id = None
                if job["kind"] != "amazon_reviews" or not isinstance(snapshot_id, str) or not SAFE_SNAPSHOT_RE.fullmatch(snapshot_id):
                    raise TransportError("invalid_response")
                job_receipts.append(_job_receipt(job, "pending", item["requested_records"], snapshot_id=snapshot_id,
                                                 error_code="pending_snapshot"))
                status = "pending"
                break
            if job["kind"] == "web_page":
                canonical, blocks = _parse_web_markdown(response.body)
                if canonical:
                    heading = next((block["text"] for block in blocks if block["kind"] == "heading"), "Selected public page")
                    sources.append({"id": job["source_id"], "kind": "page", "role": job["role"], "url": item["urls"][0],
                                    "title": heading[:200], "text": canonical, "status": "collected", "observed_at": now,
                                    "published_at": None, "provider_date": None, "record_id": None,
                                    "record_id_origin": "none", "provenance": "bright_data"})
                    state = "processed"
                else:
                    sources.append({"id": job["source_id"], "kind": "page", "role": job["role"], "url": item["urls"][0],
                                    "title": "Selected public page", "text": "", "status": "empty", "observed_at": now,
                                    "published_at": None, "provider_date": None, "record_id": None,
                                    "record_id_origin": "none", "provenance": "bright_data"})
                    state = "empty"
                job_receipts.append(_job_receipt(job, state, None, retained=1 if canonical else 0))
            else:
                try:
                    records = json.loads(response.body)
                except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
                    raise TransportError("invalid_response") from exc
                if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
                    raise TransportError("invalid_response")
                returned += len(records)
                normalized, local_warnings, local_excluded = _normalize_amazon_response(
                    records, urls=item["urls"], observed_at=now, source_prefix=job["source_prefix"],
                    limit=min(item["requested_records"], approval["max_retained_records"]),
                )
                sources.extend(normalized)
                warnings.extend(local_warnings)
                excluded += local_excluded
                if local_excluded:
                    state = "processed_with_exclusions"
                elif normalized:
                    state = "processed"
                else:
                    state = "empty"
                job_receipts.append(_job_receipt(job, state, item["requested_records"], returned=len(records),
                                                 retained=len(normalized), excluded=local_excluded,
                                                 error_code="provider_limit_exceeded" if len(records) > item["requested_records"] else None))
                if local_excluded:
                    status = "processed_with_exclusions"
                    break
                if not normalized:
                    status = "empty"
        except TransportError as exc:
            if exc.code == "completion_unknown":
                status = "completion_unknown"
                job_receipts.append(_job_receipt(job, "completion_unknown", item["requested_records"], error_code="transport_error"))
                break
            status = "transport_failed"
            job_receipts.append(_job_receipt(job, "transport_failed", item["requested_records"], error_code=exc.code))
            break
        except TimeoutError:
            status = "completion_unknown"
            job_receipts.append(_job_receipt(job, "completion_unknown", item["requested_records"], error_code="transport_error"))
            break
        except (OSError, ValueError):
            status = "transport_failed"
            job_receipts.append(_job_receipt(job, "transport_failed", item["requested_records"], error_code="invalid_response"))
            break
    attempted = len(job_receipts)
    for job, item in zip(jobs[attempted:], planned[attempted:]):
        job_receipts.append(_job_receipt(job, "not_attempted", item["requested_records"]))
    receipt = {"schema_version": SCHEMA_VERSION, "project": PROJECT, "manifest_sha256": _hash(manifest), "status": status,
               "provider_completeness": "unknown",
               "requests_made": requests_made, "returned_records": returned, "retained_records": len(sources),
               "excluded_records": excluded, "jobs": job_receipts, "warnings": warnings, "provider_cost_usd": None}
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "transport_contract_version": TRANSPORT_VERSION,
            "sources": sources, "receipt": receipt}


def _job_receipt(job, state, requested, *, returned=0, retained=0, excluded=0, snapshot_id=None, error_code=None):
    return {"id": job["id"], "kind": job["kind"], "state": state, "original_job": job,
            "requested_records": requested, "returned_records": returned, "retained_records": retained,
            "excluded_records": excluded, "snapshot_id": snapshot_id, "error_code": error_code, "query_metadata": None}


def resume(receipt, *, approval, api_key, transport, now, approval_consumer=None) -> dict:
    """Fetch one approved pending Amazon snapshot exactly once."""
    receipt_keys = {"schema_version", "project", "manifest_sha256", "status", "provider_completeness", "requests_made",
                    "returned_records", "retained_records", "excluded_records", "jobs", "warnings",
                    "provider_cost_usd"}
    job_keys = {"id", "kind", "state", "original_job", "requested_records", "returned_records",
                "retained_records", "excluded_records", "snapshot_id", "error_code", "query_metadata"}
    if not isinstance(receipt, dict) or set(receipt) != receipt_keys:
        raise ValueError("invalid receipt")
    if (receipt["schema_version"] != SCHEMA_VERSION or receipt["project"] != PROJECT
            or receipt["status"] not in {"pending", "transport_failed", "completion_unknown"}):
        raise ValueError("invalid receipt")
    if receipt["provider_completeness"] != "unknown":
        raise ValueError("invalid receipt")
    if not isinstance(receipt["manifest_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", receipt["manifest_sha256"]):
        raise ValueError("invalid receipt")
    for name in ("requests_made", "returned_records", "retained_records", "excluded_records"):
        if isinstance(receipt[name], bool) or not isinstance(receipt[name], int) or receipt[name] < 0:
            raise ValueError("invalid receipt")
    if not isinstance(receipt["warnings"], list) or receipt["provider_cost_usd"] is not None:
        raise ValueError("invalid receipt")
    if not isinstance(receipt["jobs"], list) or not 1 <= len(receipt["jobs"]) <= 4:
        raise ValueError("invalid receipt")
    allowed_states = {"processed", "processed_with_exclusions", "empty", "pending", "transport_failed", "completion_unknown", "not_attempted"}
    for job_receipt in receipt["jobs"]:
        if not isinstance(job_receipt, dict) or set(job_receipt) != job_keys:
            raise ValueError("invalid receipt")
        if job_receipt["state"] not in allowed_states:
            raise ValueError("invalid receipt")
        for name in ("returned_records", "retained_records", "excluded_records"):
            if isinstance(job_receipt[name], bool) or not isinstance(job_receipt[name], int) or job_receipt[name] < 0:
                raise ValueError("invalid receipt")
    attempted_jobs = sum(job["state"] != "not_attempted" for job in receipt["jobs"])
    if receipt["requests_made"] < attempted_jobs or receipt["requests_made"] > 12:
        raise ValueError("invalid receipt")
    for name in ("returned_records", "retained_records", "excluded_records"):
        if receipt[name] != sum(job[name] for job in receipt["jobs"]):
            raise ValueError("invalid receipt")
    reconstructed = {"schema_version": SCHEMA_VERSION, "project": PROJECT,
                     "jobs": [job["original_job"] for job in receipt["jobs"]]}
    jobs, planned_jobs = _manifest(reconstructed, live_urls=True)
    if _hash(reconstructed) != receipt["manifest_sha256"]:
        raise ValueError("invalid receipt")
    for job_receipt, original, planned_job in zip(receipt["jobs"], jobs, planned_jobs):
        if job_receipt["id"] != original["id"] or job_receipt["kind"] != original["kind"]:
            raise ValueError("invalid receipt")
        requested = planned_job["requested_records"]
        if job_receipt["requested_records"] != requested:
            raise ValueError("invalid receipt")
    pending = [job for job in receipt.get("jobs", []) if job.get("state") == "pending"]
    if (len(pending) != 1 or pending[0]["kind"] != "amazon_reviews"
            or not SAFE_SNAPSHOT_RE.fullmatch(str(pending[0].get("snapshot_id", "")))
            or pending[0]["returned_records"] != 0 or pending[0]["retained_records"] != 0
            or pending[0]["excluded_records"] != 0 or pending[0]["error_code"] != "pending_snapshot"
            or pending[0]["query_metadata"] is not None):
        raise ValueError("receipt does not contain one valid pending snapshot")
    pseudo = receipt
    planned = [{"urls": [f"https://api.brightdata.com/datasets/v3/snapshot/{pending[0]['snapshot_id']}?format=json"],
                "requested_records": pending[0]["requested_records"]}]
    approval_id, nonce, approval_digest = _approval(pseudo, approval, planned, now)
    if receipt["retained_records"] + pending[0]["requested_records"] > approval["max_retained_records"]:
        raise ValueError("approval retained-record allowance is insufficient for resumed records")
    if not api_key or not callable(transport):
        raise ValueError("api_key and transport are required")
    _consume_approval(approval_id, nonce, approval_digest, approval_consumer)
    url = planned[0]["urls"][0]
    deadline = time.monotonic() + 75
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TransportError("transport_error")
    try:
        response = transport(HttpRequest("GET", url, {"Authorization": f"Bearer {api_key}"}, b"",
                                         min(75, max(1, math.ceil(remaining)))))
        if response.status in {202, 409}:
            _pending_response_ok(response)
            return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "transport_contract_version": TRANSPORT_VERSION,
                    "sources": [], "receipt": {**receipt, "status": "pending", "provider_completeness": "unknown",
                                               "requests_made": receipt["requests_made"] + 1}}
        _response_ok(response)
        try:
            records = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise TransportError("invalid_response") from exc
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise TransportError("invalid_response")
        job = pending[0]["original_job"]
        job_plan = planned_jobs[receipt["jobs"].index(pending[0])]
        sources, warnings, excluded = _normalize_amazon_response(
            records, urls=job_plan["urls"], observed_at=now, source_prefix=job["source_prefix"],
            limit=pending[0]["requested_records"],
        )
    except (TransportError, OSError, ValueError) as exc:
        timed_out = isinstance(exc, TimeoutError) or isinstance(exc, TransportError) and exc.code == "completion_unknown"
        code = exc.code if isinstance(exc, TransportError) else "transport_error" if isinstance(exc, OSError) else "invalid_response"
        if timed_out:
            code = "transport_error"
        # Keep the pending snapshot resumable; a failed download never retriggers collection.
        failed_receipt = {**receipt, "status": "completion_unknown" if timed_out else "transport_failed",
                          "requests_made": receipt["requests_made"] + 1,
                          "warnings": receipt["warnings"] + [{"code": code, "source_ids": [],
                              "note": "One snapshot download was attempted without a usable result. No retry was made."}]}
        raise TransportError(code, receipt=failed_receipt) from exc
    resumed_state = "processed_with_exclusions" if excluded else "processed" if sources else "empty"
    updated_jobs = []
    for job_receipt in receipt["jobs"]:
        if job_receipt is pending[0]:
            updated_jobs.append({**job_receipt, "state": resumed_state, "returned_records": len(records),
                                 "retained_records": len(sources), "excluded_records": excluded,
                                 "snapshot_id": None, "error_code": None})
        else:
            updated_jobs.append(job_receipt)
    new_receipt = {**receipt, "status": resumed_state, "provider_completeness": "unknown",
                   "requests_made": receipt["requests_made"] + 1,
                   "returned_records": receipt["returned_records"] + len(records),
                   "retained_records": receipt["retained_records"] + len(sources),
                   "excluded_records": receipt["excluded_records"] + excluded,
                   "jobs": updated_jobs, "warnings": warnings}
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, "transport_contract_version": TRANSPORT_VERSION,
            "sources": sources, "receipt": new_receipt}
