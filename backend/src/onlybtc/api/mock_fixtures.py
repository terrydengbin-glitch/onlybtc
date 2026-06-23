from __future__ import annotations

from copy import deepcopy
from typing import Any

P9_C13_MOCK_SCHEMA_VERSION = "p9.c13.api_mock.v1"


def p9_c13_mock_scenarios() -> list[dict[str, Any]]:
    base = _base_report_v2_payload()
    scenarios = [
        {
            "scenario_id": "normal_run",
            "description": "P4.5 Report v2 deterministic normal run.",
            "payload": base,
        },
        {
            "scenario_id": "contract_warning_run",
            "description": "Contract warning remains frontend-consumable.",
            "payload": _with(base, contract_validation={"status": "warning", "warnings": ["score_gap"]}),
        },
        {
            "scenario_id": "llm_completed_run",
            "description": "LLM appendix completed with internal_reference only.",
            "payload": _with(base, llm={"status": "completed", "internal_reference": True, "errors": []}),
        },
        {
            "scenario_id": "llm_completed_with_llm_errors_run",
            "description": "Deterministic final is completed while LLM errors are surfaced.",
            "payload": _with(
                base,
                llm={"status": "completed_with_llm_errors", "internal_reference": True, "errors": ["timeout"]},
            ),
        },
        {
            "scenario_id": "data_quality_degraded_run",
            "description": "Data quality degraded without leaking source secrets.",
            "payload": _with(
                base,
                data_quality={"status": "degraded", "source_health": "partial", "rate_limit_event_count": 1},
            ),
        },
        {
            "scenario_id": "historical_replay_run",
            "description": "Historical replay is read-only and frozen by final_run_id.",
            "payload": _with(
                base,
                history_mode={
                    "anchor": "final_run_id",
                    "read_only": True,
                    "uses_latest_runtime_state": False,
                },
            ),
        },
        {
            "scenario_id": "legacy_p4_reference_run",
            "description": "Legacy P4 data is explicitly marked as reference-only.",
            "payload": _with(
                base,
                legacy_p4_reference={
                    "enabled": True,
                    "usable_as_current_final": False,
                    "label": "legacy_p4_reference",
                },
            ),
        },
    ]
    return [
        {
            "schema_version": P9_C13_MOCK_SCHEMA_VERSION,
            "scenario_id": item["scenario_id"],
            "description": item["description"],
            "payload": item["payload"],
        }
        for item in scenarios
    ]


def p9_c13_mock_server_manifest() -> dict[str, Any]:
    return {
        "schema_version": P9_C13_MOCK_SCHEMA_VERSION,
        "status": "ok",
        "mock_server": {
            "mode": "contract_fixture",
            "endpoint": "/api/mock/p9-c13/scenarios",
            "source_contract": "p45.research_report.v2",
        },
        "scenario_count": len(p9_c13_mock_scenarios()),
        "scenarios": p9_c13_mock_scenarios(),
    }


def _base_report_v2_payload() -> dict[str, Any]:
    return {
        "schema_version": "p45.research_report.v2",
        "final_run_id": "mock-final-normal",
        "pack_id": "mock-pack-normal",
        "final_view": "neutral",
        "decision_card": {"direction": "neutral", "confidence": "medium"},
        "run_lineage": {
            "collect_run_id": "mock-collect",
            "p2_radar_run_id": "mock-radar",
            "p3_run_id": "mock-p3",
            "pack_id": "mock-pack-normal",
            "final_run_id": "mock-final-normal",
            "run_mode": "mock",
            "runtime_mode": "deterministic",
            "llm_runtime_mode": "llm",
        },
        "contract_validation": {"status": "passed", "warnings": []},
        "radar_modules": [
            {"radar_module": "macro_radar", "module_effective_direction": "neutral"},
            {"radar_module": "kline_orderflow", "module_effective_direction": "neutral"},
        ],
        "metric_evidence": [
            {
                "evidence_id": "mock-ev-1",
                "radar_module": "macro_radar",
                "metric_id": "ofr_fsi",
                "metric_effective_score": 0.0,
                "claim": {"brief": "mock evidence"},
                "data": {"source_id": "mock-source", "payload_redacted": True},
                "interpretation": {"direction": "neutral"},
            }
        ],
        "llm": {"status": "completed", "internal_reference": True, "errors": []},
        "data_quality": {"status": "ok", "source_health": "healthy"},
        "errors": [],
        "warnings": [],
    }


def _with(payload: dict[str, Any], **updates: Any) -> dict[str, Any]:
    result = deepcopy(payload)
    result.update(updates)
    return result
