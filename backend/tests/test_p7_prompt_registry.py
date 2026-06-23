from __future__ import annotations

from scripts.generate_p7_c03_prompt_version_report import generate

from onlybtc.governance.prompt_registry import (
    REQUIRED_GUARDRAILS,
    build_prompt_registry_report,
    prompt_content_hash,
    prompt_registry_entries,
    validate_prompt_registry,
)


def test_prompt_registry_entries_have_stable_hashes_and_required_fields() -> None:
    entries = prompt_registry_entries()
    assert entries
    for entry in entries:
        assert entry.prompt_id
        assert entry.prompt_version
        assert len(entry.content_hash) == 64
        assert entry.surface == "system+user"
        assert set(REQUIRED_GUARDRAILS).issubset(entry.guardrails)


def test_prompt_registry_covers_p45_mainline_and_marks_p4_legacy() -> None:
    entries = prompt_registry_entries()
    by_id = {entry.prompt_id: entry for entry in entries}
    assert by_id["p45.llm_research_writer.article"].runtime_scope == "p45_mainline"
    assert by_id["p45.llm_analyst_writer.article"].runtime_scope == "p45_mainline"
    assert by_id["p4.analyst_agent.independent_review"].runtime_scope == "legacy_compat"
    assert by_id["p4.judge.synthesis"].status == "legacy_compat"


def test_prompt_hash_changes_when_prompt_text_changes() -> None:
    base = prompt_content_hash(
        prompt_id="sample",
        prompt_version="v1",
        system_prompt="system",
        user_prompt="user",
        output_schema="schema",
    )
    changed = prompt_content_hash(
        prompt_id="sample",
        prompt_version="v1",
        system_prompt="system changed",
        user_prompt="user",
        output_schema="schema",
    )
    assert base != changed


def test_prompt_registry_report_validates_and_is_not_applied_to_production() -> None:
    report = build_prompt_registry_report()
    assert report["applied_to_production"] is False
    assert report["coverage"]["validation_passed"] is True
    assert validate_prompt_registry()["passed"] is True


def test_prompt_version_report_generator_writes_json_and_md() -> None:
    report = generate()
    assert report["entry_count"] >= 2
    assert report["json_path"].endswith("p7-c03-prompt-version-management-report.json")
    assert report["md_path"].endswith("p7-c03-prompt-version-management-report.md")
