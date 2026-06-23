from __future__ import annotations

from onlybtc.audit import p45_full_chain
from onlybtc.audit.p45_full_chain import run_p45_full_chain_with_llm_audit
from onlybtc.db import schema
from onlybtc.db.session import Database


async def test_p45_full_chain_with_llm_uses_same_lineage(tmp_path, monkeypatch) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    monkeypatch.setattr(p45_full_chain, "run_p45_full_chain_audit", _fake_full_chain)
    monkeypatch.setattr(p45_full_chain, "run_p45_llm_research_writer", _fake_research)
    monkeypatch.setattr(p45_full_chain, "run_p45_llm_analyst_writers", _fake_analysts)
    monkeypatch.setattr(p45_full_chain, "run_p45_html_report", _fake_html)

    result = await run_p45_full_chain_with_llm_audit(
        collect_live=False,
        run_mode="mock",
        runtime_mode="deterministic",
        llm_runtime_mode="mock",
        db=db,
    )

    assert result["status"] == "completed"
    assert result["collect_run_id"] == "collect-test"
    assert result["p2_radar_run_id"] == "radar-test"
    assert result["p3_run_id"] == "p3-test"
    assert result["pack_id"] == "pack-test"
    assert result["final_run_id"] == "final-test"
    assert result["llm_research_run_id"] == "research-test"
    assert result["llm_analyst_run_id"] == "analysts-test"
    assert result["llm_provider"] == "deepseek"
    assert result["llm_model"] == "deepseek-reasoner"
    assert result["reports"]["p45"].endswith("p45-research-report.html")
    assert result["contract_validation"]["status"] == "passed"
    assert result["llm_summary"]["llm_provider"] == "deepseek"
    assert result["llm_summary"]["llm_model"] == "deepseek-reasoner"
    assert result["llm_summary"]["research_status"] == "completed"
    assert result["llm_summary"]["llm_research_latency_ms"] == 100
    assert result["llm_summary"]["llm_analyst_total_latency_ms"] == 100
    assert result["llm_summary"]["llm_total_latency_ms"] == 200
    assert result["llm_summary"]["analyst_completed_count"] == 4
    assert result["llm_summary"]["analyst_failed_count"] == 0
    assert result["llm_summary"]["analyst_statuses"]["macro_event_analyst"][
        "status"
    ] == "completed"
    assert result["llm_summary"]["radar_modules_covered"] == 14
    assert result["lineage_check"]["research_final_run_id_matches"] is True
    assert result["lineage_check"]["analyst_pack_id_matches"] is True
    assert result["lineage_check"]["html_refreshed"] is True
    assert result["llm_errors"] == []


async def test_p45_full_chain_with_llm_keeps_deterministic_result_on_llm_errors(
    tmp_path,
    monkeypatch,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    monkeypatch.setattr(p45_full_chain, "run_p45_full_chain_audit", _fake_full_chain)
    monkeypatch.setattr(p45_full_chain, "run_p45_llm_research_writer", _fake_failed_research)
    monkeypatch.setattr(p45_full_chain, "run_p45_llm_analyst_writers", _fake_failed_analysts)
    monkeypatch.setattr(p45_full_chain, "run_p45_html_report", _fake_html)

    result = await run_p45_full_chain_with_llm_audit(
        collect_live=False,
        run_mode="mock",
        runtime_mode="deterministic",
        llm_runtime_mode="bad-mode",
        db=db,
    )

    assert result["status"] == "completed_with_llm_errors"
    assert result["final_run_id"] == "final-test"
    assert result["contract_validation"]["status"] == "passed"
    assert result["llm_summary"]["research_status"] == "failed"
    assert result["llm_summary"]["analyst_failed_count"] == 1
    assert result["llm_summary"]["llm_provider"] == "deepseek"
    assert {item["stage"] for item in result["llm_errors"]} == {
        "llm_research",
        "llm_analysts",
    }


async def test_p45_full_chain_with_llm_can_skip_llm(tmp_path, monkeypatch) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    monkeypatch.setattr(p45_full_chain, "run_p45_full_chain_audit", _fake_full_chain)
    monkeypatch.setattr(p45_full_chain, "run_p45_html_report", _fake_html)

    result = await run_p45_full_chain_with_llm_audit(
        collect_live=False,
        run_mode="mock",
        runtime_mode="deterministic",
        skip_llm=True,
        db=db,
    )

    assert result["status"] == "completed"
    assert result["skip_llm"] is True
    assert result["llm_research_run_id"] is None
    assert result["llm_analyst_run_id"] is None
    assert result["llm_summary"]["research_status"] == "skipped"
    assert result["lineage_check"]["research_final_run_id_matches"] is True
    assert result["lineage_check"]["analyst_pack_id_matches"] is True


async def _fake_full_chain(
    collect_live: bool,
    run_mode: str,
    runtime_mode: str,
    db: Database,
) -> dict:
    _seed_final_payload(db)
    return {
        "status": "completed",
        "run_mode": run_mode,
        "runtime_mode": runtime_mode,
        "p1_c22_html_path": "reports/p1.html",
        "p2_html_path": "reports/p2.html",
        "p3_html_path": "reports/p3.html",
        "p45_html_path": "reports/p45-research-report.html",
        "collect_run_id": "collect-test",
        "p2_radar_run_id": "radar-test",
        "p3_run_id": "p3-test",
        "pack_id": "pack-test",
        "article_run_id": "articles-test",
        "final_run_id": "final-test",
        "core_view": "mixed",
        "summary": {"final": {"schema_version": "p45.research_report.v2"}},
    }


def _fake_research(
    final_run_id: str,
    runtime_mode: str,
    db: Database,
) -> dict:
    assert final_run_id == "final-test"
    return {
        "status": "completed",
        "llm_research_run_id": "research-test",
        "final_run_id": final_run_id,
        "pack_id": "pack-test",
        "provider": "deepseek",
        "model": "deepseek-reasoner",
        "latency_ms": 100,
    }


def _fake_analysts(
    pack_id: str,
    runtime_mode: str,
    db: Database,
) -> dict:
    assert pack_id == "pack-test"
    return {
        "llm_analyst_run_id": "analysts-test",
        "pack_id": pack_id,
        "provider": "deepseek",
        "analyst_articles": [
            {
                "analyst_id": "macro_event_analyst",
                "status": "completed",
                "latency_ms": 25,
                "provider": "deepseek",
                "model": "deepseek-reasoner",
                "error": None,
            },
            {
                "analyst_id": "liquidity_flow_analyst",
                "status": "completed",
                "latency_ms": 25,
                "provider": "deepseek",
                "model": "deepseek-reasoner",
                "error": None,
            },
            {
                "analyst_id": "microstructure_analyst",
                "status": "completed",
                "latency_ms": 25,
                "provider": "deepseek",
                "model": "deepseek-reasoner",
                "error": None,
            },
            {
                "analyst_id": "onchain_structure_analyst",
                "status": "completed",
                "latency_ms": 25,
                "provider": "deepseek",
                "model": "deepseek-reasoner",
                "error": None,
            },
        ],
        "summary": {
            "completed_count": 4,
            "failed_count": 0,
            "radar_modules_covered": [f"module-{index}" for index in range(14)],
        },
    }


def _fake_failed_research(
    final_run_id: str,
    runtime_mode: str,
    db: Database,
) -> dict:
    return {
        "status": "failed",
        "llm_research_run_id": "research-failed",
        "final_run_id": final_run_id,
        "provider": "deepseek",
        "model": "deepseek-reasoner",
        "latency_ms": 100,
        "error": "boom",
    }


def _fake_failed_analysts(
    pack_id: str,
    runtime_mode: str,
    db: Database,
) -> dict:
    return {
        "llm_analyst_run_id": "analysts-failed",
        "pack_id": pack_id,
        "provider": "deepseek",
        "analyst_articles": [
            {
                "analyst_id": "macro_event_analyst",
                "status": "failed",
                "latency_ms": 50,
                "provider": "deepseek",
                "model": "deepseek-reasoner",
                "error": "boom",
            }
        ],
        "summary": {
            "completed_count": 3,
            "failed_count": 1,
            "radar_modules_covered": [f"module-{index}" for index in range(10)],
        },
    }


def _fake_html(final_run_id: str, db: Database) -> dict:
    assert final_run_id == "final-test"
    return {"status": "completed", "html_path": "reports/p45-research-report.html"}


def _seed_final_payload(db: Database) -> None:
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="final-test",
                module_id="p45_final_article",
                schema_version="p45.research_report.v2",
                payload={
                    "schema_version": "p45.research_report.v2",
                    "final_run_id": "final-test",
                    "pack_id": "pack-test",
                    "contract_validation": {
                        "status": "passed",
                        "errors": [],
                        "warnings": [],
                    },
                },
            )
        )
