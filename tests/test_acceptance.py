"""Acceptance regression tests for the Reviews Into Fixes contract."""

from copy import deepcopy

import pytest

from reviews_into_fixes.core import analyze


AS_OF = "2026-10-04T12:00:00Z"
OBSERVED = "2026-10-04T10:00:00Z"


def source(source_id, kind, role, text, *, record_id=None, status="collected"):
    url = (
        f"https://example.com/reviews/{source_id}"
        if kind == "review"
        else "https://example.com/help"
        if kind == "page"
        else None
    )
    return {
        "id": source_id,
        "kind": kind,
        "role": role,
        "url": url,
        "title": source_id,
        "text": text if status == "collected" else "",
        "status": status,
        "observed_at": OBSERVED,
        "published_at": None,
        "provider_date": None,
        "record_id": record_id,
        "record_id_origin": "operator" if record_id else "none",
        "provenance": "synthetic_fixture",
    }


def fixture():
    return {
        "schema_version": "1.0",
        "project": "reviews-into-fixes",
        "as_of": AS_OF,
        "product": "Harbor",
        "areas": [
            {
                "id": "setup",
                "label": "Setup",
                "aliases": ["setup"],
                "next_check": "Repeat setup from a fresh test account and record step 3.",
            },
            {
                "id": "export",
                "label": "Export",
                "aliases": ["CSV export"],
                "next_check": "Confirm export requirements with the product owner.",
            },
        ],
        "known_issues": [
            {
                "id": "setup_3",
                "area_id": "setup",
                "title": "Setup stops at step 3",
                "status": "open",
                "symptom_phrases": ["stops at step 3"],
            }
        ],
        "sources": [
            source("r1", "review", "review", "Setup stops at step 3.", record_id="R1"),
            source("r2", "review", "review", "Please add CSV export.", record_id="R2"),
            source(
                "r3",
                "review",
                "review",
                "The setup instructions are unclear how to activate it.",
                record_id="R3",
            ),
            source("r4", "review", "review", "Setup works fine.", record_id="R4"),
            source(
                "help",
                "page",
                "product_instructions",
                "## Setup\n\nComplete setup by selecting Activate at step 3.",
            ),
        ],
    }


def cards(report):
    return report["cards"]


def citation_pairs(card, key):
    return {
        (ref["source_id"], ref["block_id"], ref["quote"])
        for ref in card[key]
    }


def test_RF01_fixture_builds_three_joined_investigation_cards_with_citations():
    report = analyze(fixture())

    assert report["decision"] == "investigation_candidates"
    assert report["analysis_method"] == "deterministic_rules_v1"
    assert [card["classification"] for card in cards(report)] == [
        "possible_defect",
        "request",
        "documentation",
    ]
    defect, request, documentation = cards(report)
    assert defect["area_id"] == "setup"
    assert defect["known_state"] == "similar_to_open_issue"
    assert defect["matched_issue_ids"] == ["setup_3"]
    assert defect["interpretation"] == "investigation_candidate_not_verified_defect"
    assert defect["next_check"] == (
        "Verify this report before treating it as a defect. "
        "Repeat setup from a fresh test account and record step 3."
    )
    assert defect["reported_problem"] == "Setup stops at step 3."
    assert ("r1", "b0001", "Setup stops at step 3.") in citation_pairs(
        defect, "report_refs"
    )
    assert defect["documentation_state"] == "related_passage_found"
    assert any(ref["source_id"] == "help" for ref in defect["instruction_refs"])
    assert request["area_id"] == "export"
    assert request["known_state"] == "not_matched_to_known_issue"
    assert request["next_check"] == "Confirm export requirements with the product owner."
    assert documentation["classification"] == "documentation"
    assert all(card["classification"] != "verified_defect" for card in cards(report))
    assert report["counterevidence"]
    assert all(ref["source_id"] == "r4" for ref in report["counterevidence"])


def test_RF02_resolved_known_issue_changes_candidate_state_without_claiming_recurrence():
    payload = fixture()
    payload["known_issues"][0]["status"] = "resolved"

    card = cards(analyze(payload))[0]

    assert card["known_state"] == "similar_to_resolved_issue"
    assert card["matched_issue_ids"] == ["setup_3"]
    assert card["interpretation"] == "investigation_candidate_not_verified_defect"
    assert "recurrence" not in str(card).casefold()


def test_RF03_unrelated_instructions_report_scoped_no_passage_not_missing_docs():
    payload = fixture()
    payload["sources"][-1]["text"] = "## Billing\n\nUpdate your payment method."

    card = cards(analyze(payload))[0]

    assert card["documentation_state"] == "no_related_passage_found_in_supplied_text"
    assert "missing" not in card["documentation_state"]


def test_RF04_zero_reviews_is_no_reports_with_empty_artifacts():
    payload = fixture()
    payload["sources"] = [payload["sources"][-1]]

    report = analyze(payload)

    assert report["decision"] == "no_reports"
    assert report["cards"] == []
    assert report["overflow"] == []
    assert report["counterevidence"] == []


def test_RF05_identical_duplicate_record_counts_once_and_conflict_supports_no_card():
    payload = fixture()
    duplicate = deepcopy(payload["sources"][0])
    duplicate["id"] = "r1_copy"
    payload["sources"].insert(1, duplicate)
    conflict = source("r1_conflict", "review", "review", "Setup fails at step 3.", record_id="R1")
    conflict["url"] = payload["sources"][0]["url"]
    payload["sources"].append(conflict)

    report = analyze(payload)

    assert sum(ref["source_id"] in {"r1", "r1_copy"} for card in cards(report) for ref in card["report_refs"]) <= 1
    assert any(warning["code"] == "conflicting_record" for warning in report["warnings"])
    assert report["status"] == "needs_review"
    assert all(
        ref["source_id"] not in {"r1", "r1_conflict"}
        for card in cards(report)
        for ref in card["report_refs"]
    )


def test_RF06_positive_phrase_suppresses_only_its_sentence_not_separate_defect_sentence():
    payload = fixture()
    payload["sources"][0]["text"] = "Setup no longer fails. Setup fails."

    report = analyze(payload)

    # Contract section 5 scopes positive suppression to one sentence; it must
    # not erase actionable sentences from this or any unrelated review source.
    assert len(cards(report)) == 3
    assert cards(report)[0]["classification"] == "possible_defect"
    assert cards(report)[0]["reported_problem"] == "Setup fails."
    assert [card["classification"] for card in cards(report)[1:]] == ["request", "documentation"]
    assert any(ref["source_id"] == "r1" for ref in report["counterevidence"])


def test_same_record_id_at_different_canonical_urls_is_independent():
    payload = fixture()
    other = source("other", "review", "review", "Setup fails at launch.", record_id="R1")
    payload["sources"] = [payload["sources"][0], other]

    report = analyze(payload)

    assert report["status"] == "ok"
    assert not any(warning["code"] == "conflicting_record" for warning in report["warnings"])
    assert {ref["source_id"] for card in report["cards"] for ref in card["report_refs"]} == {"r1", "other"}


@pytest.mark.parametrize(
    "text,area_id",
    [
        ("It fails.", None),
        ("Setup CSV export fails.", None),
    ],
)
def test_RF07_missing_or_multiple_area_matches_are_preserved_as_unclear(text, area_id):
    payload = fixture()
    payload["sources"] = [source("r1", "review", "review", text, record_id="R1")]

    card = cards(analyze(payload))[0]

    assert card["area_id"] == area_id
    assert card["classification"] == "unclear"
    assert card["reported_problem"] == text
    assert card["next_check"] == "Clarify the product area and obtain reproduction steps."


def test_RF08_sentence_matching_two_categories_is_unclear_with_both_candidates():
    payload = fixture()
    payload["sources"] = [
        source("r1", "review", "review", "Setup fails; please add a retry button.", record_id="R1")
    ]

    card = cards(analyze(payload))[0]

    assert card["classification"] == "unclear"
    assert set(card["classification_candidates"]) == {"possible_defect", "request"}


def test_RF09_six_groups_keep_five_cards_and_preserve_overflow():
    payload = fixture()
    payload["areas"] = [
        {"id": f"area{i}", "label": f"Area {i}", "aliases": [f"feature{i}"], "next_check": f"Check feature{i}."}
        for i in range(6)
    ]
    payload["known_issues"] = []
    payload["sources"] = [
        source(f"r{i}", "review", "review", f"Feature{i} fails.", record_id=f"R{i}")
        for i in range(6)
    ]

    report = analyze(payload)

    assert len(report["cards"]) == 5
    assert len(report["overflow"]) == 1
    assert report["summary"]["overflow_count"] == 1
    assert any(warning.get("code") == "card_overflow" for warning in report["warnings"])
    assert report["overflow"][0]["area_id"] == "area5"


def test_RF10_unavailable_instruction_source_is_unknown_not_missing_documentation():
    payload = fixture()
    payload["sources"][-1]["status"] = "unavailable"
    payload["sources"][-1]["text"] = ""

    card = cards(analyze(payload))[0]

    assert card["documentation_state"] == "instructions_unavailable"
    assert card["instruction_refs"] == []


def test_only_exact_supported_cues_classify_and_unmatched_sentence_is_retained_unclear():
    payload = fixture()
    payload["sources"] = [
        source("r1", "review", "review", "Setup is frustrating.", record_id="R1")
    ]

    card = cards(analyze(payload))[0]

    assert card["classification"] == "unclear"
    assert card["classification_candidates"] == []
    assert card["reported_problem"] == "Setup is frustrating."


def test_positive_only_review_is_counterevidence_and_not_a_fix_card():
    payload = fixture()
    payload["sources"] = [
        source("r1", "review", "review", "Setup works fine.", record_id="R1")
    ]

    report = analyze(payload)

    assert report["cards"] == []
    assert len(report["counterevidence"]) == 1
    assert report["counterevidence"][0]["source_id"] == "r1"


def test_non_collected_review_never_becomes_positive_evidence():
    payload = fixture()
    payload["sources"] = [source("r1", "review", "review", "", status="unavailable")]

    report = analyze(payload)

    assert report["status"] == "needs_review"
    assert report["decision"] == "no_actionable_cues"
    assert report["cards"] == []
    assert report["counterevidence"] == []


def test_unavailable_instructions_without_reviews_do_not_prove_documentation_absent():
    payload = fixture()
    payload["sources"] = [source("help", "page", "product_instructions", "", status="unavailable")]

    report = analyze(payload)

    assert report["status"] == "needs_review"
    assert report["decision"] == "no_reports"
    assert report["cards"] == []


def test_unknown_known_issue_match_does_not_invent_an_issue_or_verified_cause():
    payload = fixture()
    payload["sources"] = [
        source("r1", "review", "review", "Setup fails at launch.", record_id="R1")
    ]

    card = cards(analyze(payload))[0]

    assert card["known_state"] == "not_matched_to_known_issue"
    assert card["matched_issue_ids"] == []
    assert card["interpretation"] == "investigation_candidate_not_verified_defect"


def test_multiple_known_issue_phrase_matches_remain_ambiguous():
    payload = fixture()
    payload["known_issues"].append(
        {
            "id": "setup_retry",
            "area_id": "setup",
            "title": "Setup retry issue",
            "status": "open",
            "symptom_phrases": ["stops at step 3"],
        }
    )

    card = cards(analyze(payload))[0]

    assert card["known_state"] == "ambiguous_issue_match"
    assert card["matched_issue_ids"] == ["setup_3", "setup_retry"]


def test_analysis_does_not_claim_cause_severity_frequency_or_priority_ranking():
    report = analyze(fixture())

    assert "severity" not in report
    assert "priority" not in report
    assert "cause" not in report
    assert report["summary"]["review_count"] == 4
    assert report["summary"].get("prevalence") is None


def test_repeated_analysis_is_deterministic():
    payload = fixture()

    assert analyze(payload) == analyze(payload)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(schema_version="2.0"),
        lambda payload: payload.update(unrecognized=True),
        lambda payload: payload["sources"][0].update(unknown_source_field="x"),
        lambda payload: payload["sources"][0].update(text="Setup stops at step 3.\x00"),
        lambda payload: payload["sources"][0].update(observed_at="yesterday"),
        lambda payload: payload["known_issues"][0].update(area_id="missing_area"),
    ],
)
def test_invalid_or_dangling_input_is_rejected(mutate):
    payload = fixture()
    mutate(payload)

    with pytest.raises((ValueError, TypeError)):
        analyze(payload)


def test_non_collected_source_with_text_is_rejected_not_used_as_evidence():
    payload = fixture()
    payload["sources"][0]["status"] = "unavailable"

    with pytest.raises((ValueError, TypeError)):
        analyze(payload)


def test_report_source_index_does_not_leak_full_source_text():
    report = analyze(fixture())

    assert "Setup stops at step 3." not in str(report["source_index"])
    assert report["source_index"][0]["id"] == "r1"
