from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import onlybtc.api.app as app_module
from onlybtc.api import p45_jobs
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p6.article_pipeline import (
    P6_AUTO_ARTICLE_MODULE_ID,
    article_history,
    build_auto_article_snapshot,
    generate_auto_article_snapshot,
    get_manual_article,
    latest_auto_article_snapshot,
    latest_manual_article,
    manual_generate_article,
    replay_article_snapshot,
)
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID


def test_build_auto_article_snapshot_blocks_publish_and_keeps_traceable_evidence() -> None:
    final_payload = _final_payload()

    snapshot = build_auto_article_snapshot(final_payload)

    assert snapshot["schema_version"] == "p6.auto_article.v1"
    assert snapshot["article_snapshot_id"] == "p6article-final-p6-test"
    assert snapshot["draft_status"] == "ready"
    assert snapshot["publish_boundary"]["auto_publish_allowed"] is False
    assert snapshot["quality_gate"]["status"] == "passed"
    assert snapshot["quality_gate"]["checks"]["citations_traceable"] is True
    assert {item["evidence_id"] for item in snapshot["evidence_citations"]} == {
        "ev-p6-1",
        "ev-p6-2",
    }
    assert "position_size" in snapshot["publish_boundary"]["forbidden_outputs"]


def test_generate_auto_article_snapshot_is_idempotent_and_persists(tmp_path) -> None:
    db = Database(tmp_path / "p6-auto-article.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="final-p6-test",
                module_id="p45_final_article",
                schema_version="p45.research_report.v2",
                payload=_final_payload(),
            )
        )

    first = generate_auto_article_snapshot(final_run_id="final-p6-test", db=db)
    second = generate_auto_article_snapshot(final_run_id="final-p6-test", db=db)
    latest = latest_auto_article_snapshot(db=db)

    assert first["article_snapshot_id"] == second["article_snapshot_id"]
    assert latest is not None
    assert latest["article_snapshot_id"] == "p6article-final-p6-test"
    with db.session() as session:
        rows = session.query(schema.ModuleJsonOutput).filter_by(
            module_id=P6_AUTO_ARTICLE_MODULE_ID,
            run_id="p6article-final-p6-test",
        ).all()
    assert len(rows) == 1


def test_manual_article_envelope_keeps_draft_only_publication_strategy(tmp_path) -> None:
    db = Database(tmp_path / "p6-manual.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="final-p6-test",
                module_id="p45_final_article",
                schema_version="p45.research_report.v2",
                payload=_final_payload(),
            )
        )

    generated = manual_generate_article(final_run_id="final-p6-test", db=db)
    latest = latest_manual_article(db=db)
    detail = get_manual_article("p6article-final-p6-test", db=db)

    assert generated["schema_version"] == "p6.manual_article.v1"
    assert generated["publication_status"] == "draft_only"
    assert generated["run_once_publication_strategy"]["auto_publish_allowed"] is False
    assert generated["run_once_publication_strategy"]["run_once_auto_generates_draft"] is True
    assert generated["article"]["publish_boundary"]["manual_review_required"] is True
    assert latest is not None
    assert latest["article_snapshot_id"] == generated["article_snapshot_id"]
    assert detail is not None
    assert detail["article"]["final_run_id"] == "final-p6-test"


def test_p6_article_api_endpoints_are_frontend_consumable(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "p6-api.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="final-p6-test",
                module_id="p45_final_article",
                schema_version="p45.research_report.v2",
                payload=_final_payload(),
            )
        )

    monkeypatch.setattr(
        app_module,
        "manual_generate_article",
        lambda final_run_id=None: manual_generate_article(final_run_id=final_run_id, db=db),
    )
    monkeypatch.setattr(app_module, "latest_manual_article", lambda: latest_manual_article(db=db))
    monkeypatch.setattr(
        app_module,
        "get_manual_article",
        lambda article_snapshot_id: get_manual_article(article_snapshot_id, db=db),
    )
    client = TestClient(app_module.app)

    generated = client.post("/api/p6/articles/generate?final_run_id=final-p6-test")
    latest = client.get("/api/p6/articles/latest")
    detail = client.get("/api/p6/articles/p6article-final-p6-test")
    missing = client.get("/api/p6/articles/not-found")

    assert generated.status_code == 200
    assert generated.json()["article_snapshot_id"] == "p6article-final-p6-test"
    assert generated.json()["publication_status"] == "draft_only"
    assert latest.status_code == 200
    assert latest.json()["article"]["quality_gate"]["status"] == "passed"
    assert detail.status_code == 200
    assert detail.json()["run_once_publication_strategy"]["manual_review_required"] is True
    assert missing.status_code == 404
    assert missing.json()["status"] == "error"


def test_p6_article_replay_is_frozen_by_article_snapshot_and_pack(tmp_path) -> None:
    db = Database(tmp_path / "p6-replay.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="final-p6-test",
                    module_id="p45_final_article",
                    schema_version="p45.research_report.v2",
                    payload=_final_payload(),
                ),
                schema.ModuleJsonOutput(
                    run_id="pack-p6",
                    module_id=P45_EVIDENCE_PACK_MODULE_ID,
                    schema_version="p45.evidence_pack.v1",
                    payload=_pack_payload(),
                ),
            ]
        )
    generated = generate_auto_article_snapshot(final_run_id="final-p6-test", db=db)
    with db.session() as session:
        newer = _final_payload(final_run_id="final-p6-newer", pack_id="pack-newer")
        newer["final_view"] = "bullish"
        newer["final_view_cn"] = "偏多观察"
        session.add(
            schema.ModuleJsonOutput(
                run_id="final-p6-newer",
                module_id="p45_final_article",
                schema_version="p45.research_report.v2",
                payload=newer,
            )
        )

    replay = replay_article_snapshot(generated["article_snapshot_id"], db=db)
    history = article_history(db=db)

    assert replay is not None
    assert replay["schema_version"] == "p6.article_replay.v1"
    assert replay["history_mode"]["uses_latest_runtime_state"] is False
    assert replay["final"]["final_run_id"] == "final-p6-test"
    assert replay["final"]["final_view"] == "neutral"
    assert replay["pack"]["pack_id"] == "pack-p6"
    assert replay["evidence_pack_replay"]["pack_evidence_count"] == 3
    assert replay["evidence_pack_replay"]["citation_count"] == 2
    assert replay["evidence_pack_replay"]["missing_citation_count"] == 0
    assert replay["evidence_pack_replay"]["uncited_evidence_count"] == 1
    assert history["schema_version"] == "p6.article_history.v1"
    assert history["items"][0]["article_snapshot_id"] == "p6article-final-p6-test"


def test_p6_article_history_and_replay_api_are_frontend_consumable(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "p6-replay-api.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="final-p6-test",
                    module_id="p45_final_article",
                    schema_version="p45.research_report.v2",
                    payload=_final_payload(),
                ),
                schema.ModuleJsonOutput(
                    run_id="pack-p6",
                    module_id=P45_EVIDENCE_PACK_MODULE_ID,
                    schema_version="p45.evidence_pack.v1",
                    payload=_pack_payload(),
                ),
            ]
        )
    generate_auto_article_snapshot(final_run_id="final-p6-test", db=db)
    monkeypatch.setattr(
        app_module,
        "p6_article_history_payload",
        lambda limit=50: article_history(limit=limit, db=db),
    )
    monkeypatch.setattr(
        app_module,
        "replay_article_snapshot",
        lambda article_snapshot_id: replay_article_snapshot(article_snapshot_id, db=db),
    )
    client = TestClient(app_module.app)

    history_response = client.get("/api/p6/articles/history")
    replay_response = client.get("/api/p6/articles/replay/p6article-final-p6-test")
    missing_response = client.get("/api/p6/articles/replay/not-found")

    assert history_response.status_code == 200
    assert history_response.json()["history_mode"]["anchor"] == "article_snapshot_id"
    assert history_response.json()["items"][0]["history_url"].endswith(
        "/p6article-final-p6-test"
    )
    assert replay_response.status_code == 200
    assert replay_response.json()["evidence_pack_replay"]["traceability_status"] == "passed"
    assert replay_response.json()["replay_boundary"]["auto_publish_allowed"] is False
    assert missing_response.status_code == 404
    assert missing_response.json()["status"] == "error"


@pytest.mark.asyncio
async def test_p45_full_chain_job_records_p6_article_snapshot(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "p6-job.sqlite3")
    db.init_schema()

    async def fake_p3_full_chain(**_kwargs):
        return {
            "collect_run_id": "collect-p6",
            "p2_radar_run_id": "radar-p6",
            "p3_run_id": "p3-p6",
            "p1_c22_html_path": "reports/p1.html",
            "p2_html_path": "reports/p2.html",
            "p3_html_path": "reports/p3.html",
        }

    monkeypatch.setattr(p45_jobs, "run_p3_full_chain_audit", fake_p3_full_chain)
    monkeypatch.setattr(
        p45_jobs,
        "build_p45_scored_evidence_pack",
        lambda **_kwargs: {"pack_id": "pack-p6"},
    )
    monkeypatch.setattr(
        p45_jobs,
        "run_p45_analyst_writers",
        lambda **_kwargs: {"article_run_id": "articles-p6", "pack_id": "pack-p6"},
    )
    monkeypatch.setattr(
        p45_jobs,
        "run_p45_final_writer",
        lambda **_kwargs: {"final_run_id": "final-p6-test"},
    )
    monkeypatch.setattr(
        p45_jobs,
        "run_p45_html_report",
        lambda **_kwargs: {"html_path": "reports/p45.html"},
    )
    monkeypatch.setattr(
        p45_jobs,
        "generate_auto_article_snapshot",
        lambda **_kwargs: {"article_snapshot_id": "p6article-final-p6-test"},
    )

    p45_jobs._init_job(  # noqa: SLF001
        "p45job-p6",
        {
            "execution_profile": "fast_deterministic",
            "skip_llm": True,
            "skip_research_llm": True,
            "skip_analyst_llm": True,
        },
        db=db,
    )
    await p45_jobs._run_full_chain_job(  # noqa: SLF001
        job_run_id="p45job-p6",
        run_mode="live",
        runtime_mode="deterministic",
        llm_runtime_mode="llm",
        execution_profile="fast_deterministic",
        skip_llm=True,
        skip_research_llm=True,
        skip_analyst_llm=True,
        refresh_html=False,
        db=db,
    )

    status = p45_jobs.job_status("p45job-p6", db=db)

    assert status is not None
    assert status["result"]["p6_article_snapshot_id"] == "p6article-final-p6-test"
    assert status["result"]["final_run_id"] == "final-p6-test"


def _final_payload(
    final_run_id: str = "final-p6-test",
    pack_id: str = "pack-p6",
) -> dict:
    return {
        "schema_version": "p45.research_report.v2",
        "final_run_id": final_run_id,
        "article_run_id": "articles-p6",
        "pack_id": pack_id,
        "p3_run_id": "p3-p6",
        "p2_radar_run_id": "radar-p6",
        "collect_run_id": "collect-p6",
        "final_view": "neutral",
        "final_view_cn": "中性观察",
        "research_article": {
            "title": "BTC 自动文章草稿",
            "body": "本轮 BTC 维持中性观察，宏观与微观结构证据互相抵消，需要等待后续确认。",
            "executive_summary": "BTC 中性观察，等待确认。",
        },
        "publish_article": {
            "title": "BTC 中性观察",
            "body": "BTC 当前维持观察状态。",
            "safe_to_publish": True,
        },
        "metric_evidence": [
            {
                "evidence_id": "ev-p6-1",
                "radar_module": "macro_radar",
                "metric_id": "ofr_fsi",
                "source_id": "ofr-source",
                "metric_effective_score": 0.08,
                "direction": "bullish",
                "p45_metric_brief": "OFR stress is contained.",
            },
            {
                "evidence_id": "ev-p6-2",
                "radar_module": "kline_orderflow",
                "metric_id": "btc_close_position_1h",
                "source_id": "binance-btcusdt-kline-1h",
                "metric_effective_score": -0.05,
                "direction": "bearish",
                "score_reason": "Close position still waits for confirmation.",
            },
        ],
        "contract_validation": {"status": "passed"},
        "data_quality": {"data_quality_level": "high"},
    }


def _pack_payload() -> dict:
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-p6",
        "p3_run_id": "p3-p6",
        "p2_radar_run_id": "radar-p6",
        "collect_run_id": "collect-p6",
        "analysts": [
            {
                "analyst_id": "macro",
                "modules": [
                    {
                        "radar_module": "macro_radar",
                        "metrics": [
                            {
                                "evidence_id": "ev-p6-1",
                                "radar_module": "macro_radar",
                                "metric_id": "ofr_fsi",
                            },
                            {
                                "evidence_id": "ev-p6-3",
                                "radar_module": "macro_radar",
                                "metric_id": "dxy_change",
                            },
                        ],
                    }
                ],
            },
            {
                "analyst_id": "micro",
                "modules": [
                    {
                        "radar_module": "kline_orderflow",
                        "metrics": [
                            {
                                "evidence_id": "ev-p6-2",
                                "radar_module": "kline_orderflow",
                                "metric_id": "btc_close_position_1h",
                            }
                        ],
                    }
                ],
            },
        ],
    }
