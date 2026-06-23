from __future__ import annotations

from pathlib import Path

from scripts.generate_p7_c07_provider_permission_report import generate

from onlybtc.core.config import Settings
from onlybtc.governance.provider_permissions import (
    build_provider_permission_report,
    _sensitive_paths,
)


def test_provider_matrix_reports_configured_without_secret_values(tmp_path) -> None:
    report = build_provider_permission_report(
        settings=Settings(fred_api_key="fred-secret", deepseek_api_key="deepseek-secret"),
        gitignore_path=_gitignore(tmp_path),
        env_example_path=_env_example(tmp_path),
    )
    by_provider = {row["provider_id"]: row for row in report["provider_matrix"]}

    assert by_provider["fred"]["configured"] is True
    assert by_provider["deepseek"]["configured"] is True
    assert by_provider["fred"]["secret_value_exposed"] is False
    assert "fred-secret" not in str(report)
    assert "deepseek-secret" not in str(report)


def test_glassnode_manual_login_provider_is_visible_and_sanitized(tmp_path) -> None:
    report = build_provider_permission_report(
        settings=Settings(),
        gitignore_path=_gitignore(tmp_path),
        env_example_path=_env_example(tmp_path),
    )
    glassnode = next(row for row in report["provider_matrix"] if row["provider_id"] == "glassnode")

    assert glassnode["auth_method"] == "manual_login_playwright"
    assert glassnode["permission_level"] == "session_cookie_page_access"
    assert glassnode["secret_value_exposed"] is False
    assert isinstance(glassnode["allowed_metrics"], list)


def test_sensitive_metadata_paths_are_detected() -> None:
    paths = _sensitive_paths({"nested": {"api_key": "secret"}, "headers": {"Authorization": "x"}})

    assert "metadata.nested.api_key" in paths
    assert "metadata.headers.Authorization" in paths


def test_source_onboarding_checklist_and_provider_locked_policy(tmp_path) -> None:
    report = build_provider_permission_report(
        settings=Settings(),
        gitignore_path=_gitignore(tmp_path),
        env_example_path=_env_example(tmp_path),
    )

    assert report["source_onboarding"]["source_count"] > 0
    assert "declare_auth_method_and_provider_id_if_needed" in report["source_onboarding"]["new_source_checklist"]
    assert report["provider_locked_policy"]["missing_reason"] == "provider_locked"
    assert report["provider_locked_policy"]["forbidden_behavior"] == "do_not_fabricate_default_metric_values"


def test_provider_permission_report_generator_writes_json_and_md() -> None:
    report = generate()
    assert report["schema_version"] == "p7.c07.provider_permission_source_onboarding.v1"
    assert report["json_path"].endswith("p7-c07-provider-permission-source-onboarding-report.json")
    assert report["md_path"].endswith("p7-c07-provider-permission-source-onboarding-report.md")


def _gitignore(tmp_path: Path) -> Path:
    path = tmp_path / ".gitignore"
    path.write_text(".env\n.env.*\nplaywright-artifacts/*\n", encoding="utf-8")
    return path


def _env_example(tmp_path: Path) -> Path:
    path = tmp_path / ".env.example"
    path.write_text("ONLYBTC_FRED_API_KEY=your_fred_api_key_here\n", encoding="utf-8")
    return path
