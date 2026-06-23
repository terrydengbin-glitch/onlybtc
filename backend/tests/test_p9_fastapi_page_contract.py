from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_p45_dashboard_api import _seed_p45_payloads

import onlybtc.api.app as app_module
from onlybtc.api import p45_dashboard
from onlybtc.db import schema
from onlybtc.db.session import Database


def test_p9_page_contracts_are_served_through_fastapi_with_seed_data(
    tmp_path,
    monkeypatch,
) -> None:
    db = Database(tmp_path / "p9-page-contract.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    _add_llm_internal_reference(db)
    _bind_p45_dashboard_routes(monkeypatch, db)
    client = TestClient(app_module.app)

    dashboard = client.get("/api/p45/dashboard/latest").json()
    overview = client.get("/api/p45/overview/latest").json()
    modules = client.get("/api/p45/radar-modules/latest").json()
    module = client.get("/api/p45/radar-modules/macro_radar").json()
    evidence = client.get("/api/p45/evidence?limit=200").json()
    articles = client.get("/api/p45/articles/latest").json()
    llm = client.get("/api/p45/llm/latest").json()
    invalidation = client.get("/api/p45/invalidation/latest").json()
    data_quality = client.get("/api/data-quality/latest").json()
    runs = client.get("/api/p45/runs/latest").json()

    assert dashboard["status"] == "ok"
    assert dashboard["schema_version"] == "p45.dashboard.v1"
    assert dashboard["final_view"] == overview["final_view"] == "neutral"
    assert dashboard["run_lineage"]["final_run_id"] == "final-test"
    assert dashboard["contract_validation"]["status"] == "passed"
    assert dashboard["metric_evidence_count"] == len(evidence["items"]) == 6

    assert modules["status"] == "ok"
    assert modules["count"] == len(modules["radar_modules"]) == len(modules["modules"])
    assert module["module"]["radar_module"] == "macro_radar"
    assert module["source_freshness"]["fresh_count"] == 1

    required_evidence_fields = {
        "evidence_id",
        "radar_module",
        "metric_id",
        "metric_effective_score",
        "claim",
        "data",
        "interpretation",
    }
    assert required_evidence_fields <= set(evidence["items"][0])
    assert articles["contract_validation"]["status"] == "passed"
    assert llm["llm_research"]["internal_reference"]["mode"] == "internal_reference"
    assert invalidation["invalidation_rules"][0]["rule_kind"] == "invalidation"
    assert data_quality["contract_validation"]["status"] == "passed"
    assert runs["latest"]["final_run_id"] == "final-test"
    assert runs["api_security"]["schema_version"] == "p9.c11.api_security.v1"


def test_p9_history_replay_and_realtime_contracts_are_separated(
    tmp_path,
    monkeypatch,
) -> None:
    db = Database(tmp_path / "p9-history-contract.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    _bind_p45_dashboard_routes(monkeypatch, db)
    client = TestClient(app_module.app)

    history = client.get("/api/p45/history/final-test").json()
    latest = client.get("/api/p45/dashboard/latest").json()
    with client.stream("GET", "/api/events?once=true") as response:
        event_body = "".join(response.iter_text())

    assert history["status"] == "ok"
    assert history["history_mode"]["read_only"] is True
    assert history["history_mode"]["uses_latest_runtime_state"] is False
    assert history["final"]["final_run_id"] == "final-test"
    assert "history_mode" not in latest
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: p45_run_update" in event_body


def test_p9_error_and_run_full_contracts_are_frontend_consumable(monkeypatch) -> None:
    async def fake_full_chain(**_: Any) -> dict[str, Any]:
        return {
            "status": "completed",
            "collect_run_id": "collect-api-test",
            "p2_radar_run_id": "radar-api-test",
            "p3_run_id": "p3-api-test",
            "pack_id": "pack-api-test",
            "article_run_id": "articles-api-test",
            "final_run_id": "final-api-test",
            "llm_research_run_id": "research-api-test",
            "llm_analyst_run_id": "analysts-api-test",
            "run_mode": "live",
            "runtime_mode": "deterministic",
            "llm_runtime_mode": "llm",
            "error_message": "api_key=raw-secret token=raw-token",
        }

    monkeypatch.setattr(app_module, "run_p45_full_chain_with_llm_audit", fake_full_chain)
    client = TestClient(app_module.app)

    error_response = client.get("/api/p45/evidence/not-found?api_key=raw-secret")
    run_response = client.post("/api/p45/run-full-with-llm?run_mode=live")

    assert error_response.status_code == 404
    assert "raw-secret" not in error_response.text
    error_payload = error_response.json()
    assert error_payload["status"] == "error"
    assert error_payload["error"]["recoverable"] is True

    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    assert run_payload["schema_version"] == "p45.run_full_with_llm.v1"
    assert run_payload["run_lineage"]["final_run_id"] == "final-api-test"
    assert "raw-secret" not in run_response.text
    assert "raw-token" not in run_response.text


def _bind_p45_dashboard_routes(monkeypatch, db: Database) -> None:
    bindings: dict[str, Callable[..., dict[str, Any] | None]] = {
        "latest_dashboard": p45_dashboard.latest_dashboard,
        "latest_overview": p45_dashboard.latest_overview,
        "latest_radar_modules": p45_dashboard.latest_radar_modules,
        "radar_module_detail": p45_dashboard.radar_module_detail,
        "latest_evidence": p45_dashboard.latest_evidence,
        "latest_articles": p45_dashboard.latest_articles,
        "latest_llm": p45_dashboard.latest_llm,
        "latest_invalidation": p45_dashboard.latest_invalidation,
        "latest_data_quality": p45_dashboard.latest_data_quality,
        "latest_runs": p45_dashboard.latest_runs,
        "history_list": p45_dashboard.history_list,
        "history": p45_dashboard.history,
    }

    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_dashboard",
        lambda: bindings["latest_dashboard"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_overview",
        lambda: bindings["latest_overview"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_radar_modules",
        lambda: bindings["latest_radar_modules"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "radar_module_detail",
        lambda module_id: bindings["radar_module_detail"](module_id, db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_evidence",
        lambda module_id=None, metric_id=None, limit=500: bindings["latest_evidence"](
            module_id=module_id,
            metric_id=metric_id,
            limit=limit,
            db=db,
        ),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_articles",
        lambda: bindings["latest_articles"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_llm",
        lambda: bindings["latest_llm"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_invalidation",
        lambda: bindings["latest_invalidation"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_data_quality",
        lambda: bindings["latest_data_quality"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "latest_runs",
        lambda: bindings["latest_runs"](db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "history_list",
        lambda limit=50: bindings["history_list"](limit=limit, db=db),
    )
    monkeypatch.setattr(
        app_module.p45_dashboard,
        "history",
        lambda final_run_id: bindings["history"](final_run_id, db=db),
    )


def _add_llm_internal_reference(db: Database) -> None:
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "research-test",
                schema.ModuleJsonOutput.module_id == "p45_llm_research_article",
            )
        )
        assert row is not None
        row.payload = {
            **row.payload,
            "internal_reference": {
                "mode": "internal_reference",
                "source": "seed_fixture",
            },
        }
