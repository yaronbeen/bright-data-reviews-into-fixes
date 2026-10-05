"""Pure validation and deterministic analysis for Reviews Into Fixes."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

PROJECT = "reviews-into-fixes"
SCHEMA_VERSION = "1.0"
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
BLOCK_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")

PAYLOAD_KEYS = {"schema_version", "project", "sources", "as_of", "product", "areas", "known_issues"}
SOURCE_KEYS = {
    "id", "kind", "role", "url", "title", "text", "status", "observed_at",
    "published_at", "provider_date", "record_id", "record_id_origin", "provenance",
}
AREA_KEYS = {"id", "label", "aliases", "next_check"}
ISSUE_KEYS = {"id", "area_id", "title", "status", "symptom_phrases"}

CUES = {
    "possible_defect": ["stops", "fails", "error", "does not work", "broken"],
    "request": ["wish it had", "please add", "would like", "missing feature"],
    "documentation": ["instructions", "documentation", "manual", "unclear how"],
}
POSITIVE_CUES = ["works fine", "no longer fails", "not broken", "never fails"]


def _error(message: str) -> ValueError:
    return ValueError(message)


def _object(value: object, name: str, keys: set[str]) -> dict:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    unknown = set(value) - keys
    if unknown:
        raise _error(f"{name} has unknown fields: {', '.join(sorted(unknown))}")
    return value


def _string(value: object, name: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not (minimum <= len(value) <= maximum) or (minimum and not value.strip()):
        raise _error(f"{name} must contain {minimum}..{maximum} characters")
    if "\x00" in value or any(ord(c) < 32 and c not in "\t\n\r" for c in value):
        raise _error(f"{name} contains unsupported control characters")
    return value


def _id(value: object, name: str) -> str:
    value = _string(value, name, 1, 64)
    if not ID_RE.fullmatch(value):
        raise _error(f"{name} is not a valid ID")
    return value


def _utc(value: object, name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    value = _string(value, name, 1, 40)
    if not UTC_RE.fullmatch(value):
        raise _error(f"{name} must be an RFC3339 UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise _error(f"{name} is not a valid timestamp") from exc
    return value


def canonical_url(value: object, name: str = "url", *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    value = _string(value, name, 1, 2048)
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise _error(f"{name} is invalid") from exc
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise _error(f"{name} must be a credential-free absolute HTTPS URL without a fragment")
    host = parts.hostname.lower().rstrip(".")
    netloc = host if port in (None, 443) else f"{host}:{port}"
    return urlunsplit(("https", netloc, parts.path or "", parts.query, ""))


def normalize_text(text: str) -> tuple[str, list[dict]]:
    _string(text, "source.text", 0, 50_000)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.lstrip().casefold().startswith(("<!doctype html", "<html", "<body")):
        raise _error("unsupported_content_format")
    raw_blocks = re.split(r"\n[\t ]*\n+", text)
    blocks = []
    canonical_parts = []
    for raw in raw_blocks:
        cleaned = " ".join(raw.split())
        if not cleaned:
            continue
        heading = BLOCK_RE.fullmatch(raw.strip())
        kind = "heading" if heading else "body"
        if heading:
            cleaned = " ".join(heading.group(2).split())
        block_id = f"b{len(blocks) + 1:04d}"
        blocks.append({"id": block_id, "kind": kind, "text": cleaned})
        canonical_parts.append(cleaned)
    return "\n\n".join(canonical_parts), blocks


def _phrase_match(text: str, phrase: str) -> bool:
    folded = " ".join(text.casefold().split())
    needle = " ".join(phrase.casefold().split())
    return re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", folded) is not None


def _sentences(block_text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.?!])(?:\s+|$)", block_text) if part.strip()]


def _excerpt(text: str, phrases: list[str]) -> str:
    """Return an exact <=240-character excerpt centered near the first rule hit."""
    if len(text) <= 240:
        return text
    folded = text.casefold()
    hits = [folded.find(phrase.casefold()) for phrase in phrases]
    hits = [hit for hit in hits if hit >= 0]
    hit = min(hits) if hits else 0
    start = min(max(0, hit - 80), len(text) - 240)
    return text[start:start + 240]


def _citation(source_id: str, block_id: str, quote: str, phrases: list[str] | None = None) -> dict:
    return {"source_id": source_id, "block_id": block_id, "quote": _excerpt(quote, phrases or [])}


def _validate(payload: dict) -> tuple[dict, list[dict], list[dict], list[dict], str | None]:
    payload = _object(payload, "payload", PAYLOAD_KEYS)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise _error("payload exceeds 2 MiB")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("project") != PROJECT:
        raise _error("unsupported schema_version or project")
    product = _string(payload.get("product"), "product", 1, 120)

    raw_areas = payload.get("areas")
    if not isinstance(raw_areas, list) or not (1 <= len(raw_areas) <= 12):
        raise _error("areas must contain 1..12 entries")
    areas = []
    area_ids = set()
    for index, raw in enumerate(raw_areas):
        area = _object(raw, f"areas[{index}]", AREA_KEYS)
        if set(area) != AREA_KEYS:
            raise _error(f"areas[{index}] has missing fields")
        area_id = _id(area["id"], f"areas[{index}].id")
        if area_id in area_ids:
            raise _error("area IDs must be unique")
        area_ids.add(area_id)
        aliases = area["aliases"]
        if not isinstance(aliases, list) or not (1 <= len(aliases) <= 8):
            raise _error("area aliases must contain 1..8 entries")
        aliases = [_string(v, "alias", 1, 80) for v in aliases]
        areas.append({"id": area_id, "label": _string(area["label"], "area label", 1, 80), "aliases": aliases,
                      "next_check": _string(area["next_check"], "next_check", 1, 300)})

    raw_issues = payload.get("known_issues")
    if not isinstance(raw_issues, list) or len(raw_issues) > 20:
        raise _error("known_issues must contain 0..20 entries")
    issues = []
    issue_ids = set()
    for index, raw in enumerate(raw_issues):
        issue = _object(raw, f"known_issues[{index}]", ISSUE_KEYS)
        if set(issue) != ISSUE_KEYS:
            raise _error(f"known_issues[{index}] has missing fields")
        issue_id = _id(issue["id"], "issue id")
        area_id = _id(issue["area_id"], "issue area_id")
        if issue_id in issue_ids or area_id not in area_ids:
            raise _error("known issue ID is duplicate or references an unknown area")
        issue_ids.add(issue_id)
        if issue["status"] not in {"open", "resolved"}:
            raise _error("known issue status must be open or resolved")
        phrases = issue["symptom_phrases"]
        if not isinstance(phrases, list) or not (1 <= len(phrases) <= 8):
            raise _error("symptom_phrases must contain 1..8 entries")
        issues.append({"id": issue_id, "area_id": area_id, "title": _string(issue["title"], "issue title", 1, 160),
                       "status": issue["status"], "symptom_phrases": [_string(v, "symptom phrase", 1, 120) for v in phrases]})

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or len(raw_sources) > 100:
        raise _error("sources must contain 0..100 entries")
    sources = []
    source_ids = set()
    role_counts = {"review": 0, "product_instructions": 0, "context_note": 0}
    for index, raw in enumerate(raw_sources):
        src = _object(raw, f"sources[{index}]", SOURCE_KEYS)
        if set(src) != SOURCE_KEYS:
            raise _error(f"sources[{index}] has missing fields")
        source_id = _id(src["id"], "source id")
        if source_id in source_ids:
            raise _error("source IDs must be unique")
        source_ids.add(source_id)
        role, kind = src["role"], src["kind"]
        allowed = {"review": "review", "product_instructions": "page", "context_note": "operator_note"}
        if role not in allowed or kind != allowed[role]:
            raise _error("unsupported source kind/role pair")
        role_counts[role] += 1
        limits = {"review": 50, "product_instructions": 3, "context_note": 5}
        if role_counts[role] > limits[role]:
            raise _error(f"too many {role} sources")
        status = src["status"]
        if status not in {"collected", "empty", "unavailable", "pending"}:
            raise _error("invalid source status")
        text_limit = 5000 if kind == "review" else 50_000 if kind == "page" else 2000
        raw_text = _string(src["text"], "source.text", 0, text_limit)
        if (status == "collected") != bool(raw_text.strip()):
            raise _error("collected sources require text and other statuses require empty text")
        url = canonical_url(src["url"], nullable=kind == "operator_note")
        if kind != "operator_note" and url is None:
            raise _error("review/page sources require a URL")
        title = _string(src["title"], "source.title", 1, 200)
        observed = _utc(src["observed_at"], "observed_at")
        published = _utc(src["published_at"], "published_at", nullable=True)
        provider_date = src["provider_date"]
        if provider_date is not None:
            provider_date = _string(provider_date, "provider_date", 1, 100)
        record_id = src["record_id"]
        origin = src["record_id_origin"]
        if origin not in {"provider", "operator", "content_hash", "none"}:
            raise _error("invalid record_id_origin")
        if origin == "none":
            if record_id is not None:
                raise _error("record_id_origin none requires null record_id")
        else:
            record_id = _string(record_id, "record_id", 1, 200)
        provenance = src["provenance"]
        if provenance not in {"synthetic_fixture", "operator_supplied", "bright_data"}:
            raise _error("invalid provenance")
        canonical, blocks = normalize_text(raw_text) if status == "collected" else ("", [])
        sources.append({**src, "url": url, "title": title, "observed_at": observed, "published_at": published,
                        "provider_date": provider_date, "record_id": record_id, "canonical_text": canonical,
                        "blocks": blocks, "content_sha256": hashlib.sha256(canonical.encode()).hexdigest()})

    as_of = payload.get("as_of")
    if as_of is not None:
        as_of = _utc(as_of, "as_of")
    elif sources:
        as_of = max(src["observed_at"] for src in sources)
    return {"product": product}, areas, issues, sources, as_of


def analyze(payload: dict) -> dict:
    """Validate and analyze a payload without filesystem, environment, or network access."""
    info, areas, issues, sources, as_of = _validate(payload)
    area_by_id = {area["id"]: area for area in areas}
    warnings = []

    # Deduplicate review records before any sentence can support a conclusion.
    review_groups: dict[tuple, list[dict]] = {}
    for src in sources:
        if src["role"] != "review" or src["status"] != "collected":
            continue
        local_id = src["record_id"] or src["content_sha256"]
        identity = (src["kind"], src["url"], local_id)
        review_groups.setdefault(identity, []).append(src)
    excluded_ids = set()
    duplicate_ids = set()
    for group in review_groups.values():
        texts = {src["canonical_text"] for src in group}
        if len(texts) > 1:
            ids = [src["id"] for src in group]
            excluded_ids.update(ids)
            warnings.append({"code": "conflicting_record", "source_ids": ids, "note": "Records with the same identity have conflicting text and were excluded."})
        elif len(group) > 1:
            duplicate_ids.update(src["id"] for src in group[1:])
            warnings.append({"code": "duplicate_record", "source_ids": [src["id"] for src in group], "note": "Identical duplicate records were counted once."})

    instructions = [src for src in sources if src["role"] == "product_instructions"]
    collected_instructions = [src for src in instructions if src["status"] == "collected"]
    instruction_unavailable = any(src["status"] != "collected" for src in instructions)
    groups: dict[tuple, dict] = {}
    counterevidence = []
    positive_by_area: dict[str, list[dict]] = {}
    sentence_count = 0

    for src in sources:
        if src["role"] != "review" or src["status"] != "collected" or src["id"] in excluded_ids | duplicate_ids:
            continue
        for block in src["blocks"]:
            if block["kind"] != "body":
                continue
            for sentence in _sentences(block["text"]):
                sentence_count += 1
                matched_areas = [area for area in areas if any(_phrase_match(sentence, alias) for alias in area["aliases"])]
                positive = any(_phrase_match(sentence, cue) for cue in POSITIVE_CUES)
                evidence_phrases = POSITIVE_CUES + [cue for cues in CUES.values() for cue in cues]
                evidence_phrases += [alias for area in areas for alias in area["aliases"]]
                citation = _citation(src["id"], block["id"], sentence, evidence_phrases)
                if positive:
                    counterevidence.append(citation)
                    if len(matched_areas) == 1:
                        positive_by_area.setdefault(matched_areas[0]["id"], []).append(citation)
                candidates = [category for category, cues in CUES.items() if any(_phrase_match(sentence, cue) for cue in cues)]
                if positive and "possible_defect" in candidates:
                    candidates.remove("possible_defect")
                if positive and not candidates:
                    continue
                area = matched_areas[0] if len(matched_areas) == 1 else None
                classification = candidates[0] if len(candidates) == 1 else "unclear"
                if area is None:
                    classification = "unclear"
                matched_issues = []
                if area is not None:
                    matched_issues = [issue for issue in issues if issue["area_id"] == area["id"] and
                                      any(_phrase_match(sentence, phrase) for phrase in issue["symptom_phrases"])]
                if not matched_issues:
                    known_state = "not_matched_to_known_issue"
                elif len(matched_issues) > 1:
                    known_state = "ambiguous_issue_match"
                else:
                    known_state = f"similar_to_{matched_issues[0]['status']}_issue"
                issue_ids = [issue["id"] for issue in matched_issues]
                key = (area["id"] if area else None, classification, known_state, tuple(sorted(issue_ids)))
                if key not in groups:
                    groups[key] = {"area": area, "classification": classification, "classification_candidates": candidates,
                                   "known_state": known_state, "matched_issue_ids": issue_ids, "reported_problem": citation["quote"],
                                   "report_refs": []}
                if len(groups[key]["report_refs"]) < 3:
                    groups[key]["report_refs"].append(citation)

    all_cards = []
    for index, group in enumerate(groups.values(), 1):
        area = group.pop("area")
        instruction_refs = []
        if area:
            for src in collected_instructions:
                for block in src["blocks"]:
                    if block["kind"] == "body" and any(_phrase_match(block["text"], alias) for alias in area["aliases"]):
                        instruction_refs.append(_citation(src["id"], block["id"], block["text"], area["aliases"]))
                        if len(instruction_refs) == 2:
                            break
                if len(instruction_refs) == 2:
                    break
        if instruction_refs:
            documentation_state = "related_passage_found"
        elif instruction_unavailable:
            documentation_state = "instructions_unavailable"
        elif instructions:
            documentation_state = "no_related_passage_found_in_supplied_text"
        else:
            documentation_state = "no_instructions_supplied"
        if area is None:
            next_check = "Clarify the product area and obtain reproduction steps."
        else:
            next_check = area["next_check"]
            if group["classification"] == "possible_defect":
                next_check = "Verify this report before treating it as a defect. " + next_check
        all_cards.append({"id": f"card-{index:03d}", "area_id": area["id"] if area else None, **group,
                          "documentation_state": documentation_state, "instruction_refs": instruction_refs,
                          "counterevidence_refs": positive_by_area.get(area["id"], [])[:2] if area else [],
                          "next_check": next_check, "interpretation": "investigation_candidate_not_verified_defect"})

    cards, overflow = all_cards[:5], all_cards[5:]
    if overflow:
        warnings.append({"code": "card_overflow", "source_ids": [], "note": "Additional candidate groups are retained in JSON overflow."})
    if as_of:
        cutoff = datetime.fromisoformat(as_of[:-1] + "+00:00").astimezone(timezone.utc)
        stale = [src["id"] for src in sources if (cutoff - datetime.fromisoformat(src["observed_at"][:-1] + "+00:00")).days > 30]
        if stale:
            warnings.append({"code": "stale_source", "source_ids": stale, "note": "Source observation is more than 30 days before as_of."})
    intended_unavailable = any(src["status"] != "collected" for src in sources)
    has_conflicts = bool(excluded_ids)
    collected_review_count = sum(
        src["role"] == "review" and src["status"] == "collected"
        and src["id"] not in excluded_ids | duplicate_ids for src in sources
    )
    review_source_count = sum(src["role"] == "review" for src in sources)
    if review_source_count == 0:
        decision = "no_reports"
    elif not cards:
        decision = "no_actionable_cues"
    else:
        decision = "investigation_candidates"
    status = "needs_review" if intended_unavailable or has_conflicts else "no_data" if review_source_count == 0 else "ok"
    source_index = [{key: src[key] for key in ("id", "kind", "role", "url", "status", "observed_at", "published_at",
                                                 "provider_date", "record_id", "record_id_origin", "provenance", "content_sha256")}
                    for src in sources]
    provenance_by_id = {source["id"]: source["provenance"] for source in source_index}
    for card in all_cards:
        evidence_ids = {
            ref["source_id"]
            for key in ("report_refs", "instruction_refs", "counterevidence_refs")
            for ref in card[key]
        }
        card["provenance"] = list(dict.fromkeys(
            provenance_by_id[source["id"]] for source in source_index if source["id"] in evidence_ids
        ))
        card["contains_synthetic_data"] = "synthetic_fixture" in card["provenance"]
    return {
        "schema_version": SCHEMA_VERSION, "project": PROJECT, "analysis_method": "deterministic_rules_v1",
        "status": status, "decision": decision,
        "scope": {"product": info["product"], "source_ids": [src["id"] for src in sources],
                  "source_roles": [src["role"] for src in sources], "as_of": as_of},
        "summary": {"review_count": collected_review_count, "sentence_count": sentence_count,
                    "excluded_source_count": len(excluded_ids | duplicate_ids), "card_count": len(cards),
                    "overflow_count": len(overflow)},
        "warnings": warnings, "source_index": source_index, "cards": cards, "overflow": overflow,
        "counterevidence": counterevidence,
        "contains_synthetic_data": any(source["provenance"] == "synthetic_fixture" for source in source_index),
    }
