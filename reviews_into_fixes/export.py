"""Deterministic, injection-safe report renderers."""

from __future__ import annotations

import csv
import io
import json
import unicodedata


CSV_FIELDS = [
    "card_id", "area", "classification", "known_state", "known_issue_ids", "provenance", "contains_synthetic_data",
    "reported_problem", "documentation_state", "instruction_excerpt",
    "counterevidence_excerpt", "next_check", "evidence_source_ids", "evidence_urls",
]
BIDI_FORMAT_CONTROLS = {0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def _md(value: object) -> str:
    entities = {
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        "\\": "&#92;", "`": "&#96;", "*": "&#42;", "_": "&#95;", "{": "&#123;",
        "}": "&#125;", "[": "&#91;", "]": "&#93;", "(": "&#40;", ")": "&#41;",
        "#": "&#35;", "+": "&#43;", "-": "&#45;", "!": "&#33;", "|": "&#124;",
    }
    return "".join(entities.get(character, character) for character in str(value))


def _formula_safe(value: object) -> str:
    text = "".join(character for character in str(value) if ord(character) not in BIDI_FORMAT_CONTROLS)
    index = 0
    while index < len(text) and (
        text[index].isspace() or ord(text[index]) < 32 or unicodedata.category(text[index]) == "Cf"
    ):
        index += 1
    stripped = text[index:]
    return "'" + text if stripped.startswith(("=", "+", "-", "@")) else text


def _citation_text(ref: dict, source_by_id: dict[str, dict]) -> str:
    source = source_by_id[ref["source_id"]]
    location = source.get("url") or "local operator note"
    record = f", record {source['record_id']}" if source.get("record_id") else ""
    return (
        f'[{ref["source_id"]}/{ref["block_id"]}] "{_md(ref["quote"])}" '
        f"({_md(location)}{_md(record)}; observed {source['observed_at']}; sha256 {source['content_sha256']})"
    )


def render_markdown(report: dict) -> str:
    """Render a report as stable Markdown without trusting evidence as markup."""
    source_by_id = {source["id"]: source for source in report["source_index"]}
    synthetic_ids = [source["id"] for source in report["source_index"] if source["provenance"] == "synthetic_fixture"]
    lines = ["# Reviews Into Fixes", ""]
    if synthetic_ids:
        synthetic_list = ", ".join(f"`{_md(source_id)}`" for source_id in synthetic_ids)
        if len(synthetic_ids) == len(report["source_index"]):
            disclosure = "**Synthetic demonstration data:** all supplied sources are invented and are not customer findings."
        else:
            disclosure = "**Mixed provenance:** synthetic sources are invented; other sources retain their declared provenance."
        lines += [f"> {disclosure} Synthetic source IDs: {synthetic_list}.", ""]
    lines += [
        f"**Decision:** `{report['decision']}`  ",
        f"**Status:** `{report['status']}`  ",
        f"**Method:** `{report['analysis_method']}`", "",
        "This report contains suggested investigation checks. It does not validate defects, causes, severity, frequency, priority, or whether a check is runnable in your environment.", "",
        "## Scope", "",
        f"Product: {_md(report['scope']['product'])}  ",
        f"As of: {_md(report['scope']['as_of'] or 'not supplied')}  ",
        f"Sources inspected: {len(report['scope']['source_ids'])}", "",
        "## Investigation Candidates", "",
    ]
    if not report["cards"]:
        lines += ["No investigation cards were produced by the supported exact-phrase rules.", ""]
    for card in report["cards"]:
        lines += [
            f"### {card['id']}: {_md(card['reported_problem'])}", "",
            f"- Area: `{_md(card['area_id'] or 'unclear')}`",
            f"- Classification: `{card['classification']}`",
            f"- Known-issue state: `{card['known_state']}`",
            f"- Matched known issue IDs: `{';'.join(card['matched_issue_ids']) or 'none'}`",
            f"- Documentation state: `{card['documentation_state']}`",
            f"- Suggested next check: {_md(card['next_check'])}",
            f"- Interpretation: `{card['interpretation']}`", "",
        ]
        for ref in card["report_refs"] + card["instruction_refs"] + card["counterevidence_refs"]:
            lines.append(f"- Evidence: {_citation_text(ref, source_by_id)}")
        lines.append("")
    if report["counterevidence"]:
        lines += ["## Counterevidence", ""]
        lines.extend(f"- {_citation_text(ref, source_by_id)}" for ref in report["counterevidence"])
        lines.append("")
    lines += ["## Warnings And Unknowns", ""]
    if report["warnings"]:
        lines.extend(f"- `{warning['code']}`: {_md(warning['note'])}" for warning in report["warnings"])
    else:
        lines.append("- No structured warnings. Exact-phrase matching can still miss paraphrases or context.")
    lines += ["", "## Evidence Appendix", ""]
    for source in report["source_index"]:
        lines.append(
            f"- `{source['id']}`: {_md(source.get('url') or 'local operator note')}; "
            f"status `{source['status']}`; observed {source['observed_at']}; "
            f"provenance `{source['provenance']}`; sha256 `{source['content_sha256']}`"
        )
    lines += ["", "Generated locally with deterministic rules. Source free text may contain personal or sensitive information; inspect it before sharing.", ""]
    return "\n".join(lines)


def render_csv(report: dict) -> str:
    """Render primary card rows with spreadsheet-formula protection."""
    source_by_id = {source["id"]: source for source in report["source_index"]}
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for card in report["cards"]:
        refs = card["report_refs"] + card["instruction_refs"] + card["counterevidence_refs"]
        source_ids = list(dict.fromkeys(ref["source_id"] for ref in refs))
        urls = list(dict.fromkeys(source_by_id[source_id].get("url") or "" for source_id in source_ids))
        row = {
            "card_id": card["id"], "area": card["area_id"] or "", "classification": card["classification"],
            "known_state": card["known_state"], "known_issue_ids": ";".join(card["matched_issue_ids"]),
            "provenance": ";".join(card["provenance"]),
            "contains_synthetic_data": "true" if card["contains_synthetic_data"] else "false",
            "reported_problem": card["reported_problem"], "documentation_state": card["documentation_state"],
            "instruction_excerpt": ";".join(ref["quote"] for ref in card["instruction_refs"]),
            "counterevidence_excerpt": ";".join(ref["quote"] for ref in card["counterevidence_refs"]),
            "next_check": card["next_check"], "evidence_source_ids": ";".join(source_ids),
            "evidence_urls": ";".join(urls),
        }
        writer.writerow({key: _formula_safe(value) for key, value in row.items()})
    return output.getvalue()


def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
