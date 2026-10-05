import csv
import io
import json
from copy import deepcopy
from pathlib import Path

import pytest

from reviews_into_fixes.core import analyze
from reviews_into_fixes.export import render_csv, render_json, render_markdown


ROOT = Path(__file__).parents[1]


def demo():
    return json.loads((ROOT / "fixtures" / "demo.json").read_text())


def review(source_id, url, text, record_id=None):
    return {
        "id": source_id, "kind": "review", "role": "review", "url": url, "title": source_id,
        "text": text, "status": "collected", "observed_at": "2026-10-04T10:00:00Z",
        "published_at": None, "provider_date": None, "record_id": record_id,
        "record_id_origin": "operator" if record_id else "none", "provenance": "synthetic_fixture",
    }


def test_identity_uses_kind_canonical_url_and_record_id():
    payload = demo()
    payload["sources"] = [
        review("a", "https://EXAMPLE.com.:443/reviews/x", "Setup fails.", "R1"),
        review("b", "https://example.com/reviews/x", "Setup broken.", "R1"),
        review("c", "https://example.com/reviews/y", "Setup error.", "R1"),
    ]
    report = analyze(payload)
    assert report["status"] == "needs_review"
    assert report["summary"]["review_count"] == 1
    assert report["summary"]["excluded_source_count"] == 2
    assert {ref["source_id"] for card in report["cards"] for ref in card["report_refs"]} == {"c"}


def test_idless_identity_uses_url_and_canonical_content_hash():
    payload = demo()
    payload["sources"] = [
        review("a", "https://example.com/reviews/x", "Setup fails."),
        review("b", "https://EXAMPLE.com:443/reviews/x", "Setup   fails."),
        review("c", "https://example.com/reviews/x", "Setup broken."),
    ]
    report = analyze(payload)
    assert report["status"] == "ok"
    assert report["summary"]["review_count"] == 2
    assert any(w["code"] == "duplicate_record" for w in report["warnings"])
    assert not any(w["code"] == "conflicting_record" for w in report["warnings"])


def test_conflict_retains_unaffected_cards_and_counts_exclusions():
    payload = demo()
    conflict = deepcopy(payload["sources"][0])
    conflict["id"] = "r1_conflict"
    conflict["text"] = "Setup broken."
    payload["sources"].append(conflict)
    report = analyze(payload)
    assert report["status"] == "needs_review"
    assert report["summary"]["review_count"] == 3
    assert report["summary"]["excluded_source_count"] == 2
    assert [card["classification"] for card in report["cards"]] == ["request", "documentation"]


def test_hit_centered_excerpt_contains_late_cue_and_is_exact():
    payload = demo()
    long_prefix = "x" * 300
    payload["sources"] = [review("late", "https://example.com/reviews/late", f"{long_prefix} setup fails.", "L1")]
    report = analyze(payload)
    quote = report["cards"][0]["report_refs"][0]["quote"]
    assert len(quote) <= 240
    assert "setup fails" in quote
    assert quote in (long_prefix + " setup fails.")
    assert report["cards"][0]["reported_problem"] == quote


def test_markdown_lists_matched_issue_ids_and_escapes_evidence():
    payload = demo()
    payload["sources"][0]["text"] = "Setup stops at step 3. <script>alert(1)</script>"
    markdown = render_markdown(analyze(payload))
    assert "Matched known issue IDs: `setup_3`" in markdown
    assert "<script>" not in markdown
    assert "&lt;script&gt;" in markdown


def test_csv_formula_protection_and_json_exact_evidence():
    payload = demo()
    payload["areas"][0]["next_check"] = "=RUN()"
    report = analyze(payload)
    assert "'=RUN()" in render_csv(report)
    assert "=RUN()" in render_json(report)


def test_checked_expected_artifacts_are_byte_exact():
    report = analyze(demo())
    assert render_json(report).encode() == (ROOT / "fixtures" / "expected" / "report.json").read_bytes()
    assert render_markdown(report).encode() == (ROOT / "fixtures" / "expected" / "fixes.md").read_bytes()
    assert render_csv(report).encode() == (ROOT / "fixtures" / "expected" / "fixes.csv").read_bytes()


def test_cards_and_csv_carry_provenance_and_synthetic_flag():
    report = analyze(demo())
    assert all(card["provenance"] == ["synthetic_fixture"] for card in report["cards"])
    assert all(card["contains_synthetic_data"] is True for card in report["cards"])
    rows = list(csv.DictReader(io.StringIO(render_csv(report))))
    assert all(row["provenance"] == "synthetic_fixture" for row in rows)
    assert all(row["contains_synthetic_data"] == "true" for row in rows)


def test_mixed_markdown_disclosure_lists_only_synthetic_source_ids():
    payload = demo()
    payload["sources"][1]["provenance"] = "operator_supplied"
    markdown = render_markdown(analyze(payload))
    assert "Mixed provenance" in markdown
    disclosure = next(line for line in markdown.splitlines() if "Synthetic source IDs" in line)
    assert all(source_id in disclosure for source_id in ("r1", "r3", "r4", "help"))
    assert "r2" not in disclosure


@pytest.mark.parametrize("field,value", [("title", "x" * 201), ("record_id", "x" * 201)])
def test_source_fields_are_rejected_not_truncated(field, value):
    payload = demo()
    payload["sources"][0][field] = value
    with pytest.raises(ValueError):
        analyze(payload)
