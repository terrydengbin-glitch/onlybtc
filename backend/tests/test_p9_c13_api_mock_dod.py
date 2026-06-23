from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from scripts.generate_p9_c13_api_mock_dod_report import generate

from onlybtc.api.app import app
from onlybtc.api.mock_fixtures import p9_c13_mock_scenarios


def test_p9_c13_mock_scenarios_cover_required_contract_states() -> None:
    scenarios = p9_c13_mock_scenarios()
    scenario_ids = {item["scenario_id"] for item in scenarios}

    assert {
        "normal_run",
        "contract_warning_run",
        "llm_completed_run",
        "llm_completed_with_llm_errors_run",
        "data_quality_degraded_run",
        "historical_replay_run",
        "legacy_p4_reference_run",
    } <= scenario_ids
    assert all(item["payload"]["schema_version"] == "p45.research_report.v2" for item in scenarios)
    assert "raw-secret" not in str(scenarios)
    assert "raw-token" not in str(scenarios)


def test_p9_c13_mock_endpoint_serves_contract_fixture() -> None:
    client = TestClient(app)

    response = client.get("/api/mock/p9-c13/scenarios")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "p9.c13.api_mock.v1"
    assert payload["mock_server"]["source_contract"] == "p45.research_report.v2"
    assert payload["scenario_count"] == 7


def test_p9_c13_report_generator_writes_dod_outputs() -> None:
    report = generate()

    assert report["schema_version"] == "p9.c13.api_mock_dod_report.v1"
    assert report["overall_status"] == "passed"
    assert report["mock_server"]["endpoint"] == "/api/mock/p9-c13/scenarios"
    for path_key in ("json_path", "md_path", "html_path", "openapi_snapshot_path", "frontend_dto_snapshot_path"):
        assert Path(report[path_key]).exists()
    assert all(item["status"] == "PASS" for item in report["p9_dod_checklist"])
