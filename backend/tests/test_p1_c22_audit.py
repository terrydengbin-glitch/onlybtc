from datetime import UTC, datetime, timedelta
from pathlib import Path

from onlybtc.audit import p1_c22
from onlybtc.audit.p1_c22 import run_p1_c22_audit
from onlybtc.core.paths import PathResolver
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.sources.registry import SOURCE_CONFIGS


async def test_p1_c22_always_outputs_chinese_html(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    db = Database(data_root / "onlybtc-test.sqlite3")
    monkeypatch.setattr(
        p1_c22,
        "paths",
        PathResolver(project_root=project_root, data_root=data_root),
    )

    result = await run_p1_c22_audit(collect_live=False, db=db)

    html_path = Path(result["HTML报告路径"])
    summary_path = Path(result["报告路径"]["summary"])
    metrics_path = Path(result["报告路径"]["metrics"])
    issues_path = Path(result["报告路径"]["issues"])

    assert result["报告语言"] == "中文"
    assert result["HTML输出"] == "已生成"
    assert html_path.name == "p1-c22-真实数据全链路验收报告.html"
    assert html_path.exists()
    assert summary_path.exists()
    assert metrics_path.exists()
    assert issues_path.exists()

    html = html_path.read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in html
    assert "P1-C22 真实数据全链路验收报告" in html
    assert "指标参数清单" in html
    assert "失败/缺失数据" in html


def test_p1_c22_latest_collect_run_skips_partial_live_runs(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime(2026, 5, 21, tzinfo=UTC)
    full_sources = SOURCE_CONFIGS[:60]
    partial_source = SOURCE_CONFIGS[60]
    db.init_schema()
    with db.session() as session:
        session.add_all(
            [
                schema.Source(
                    source_id=source.source_id,
                    name=source.name,
                    group_name=source.group_name,
                    method=source.method,
                    status="healthy",
                    metadata_json={},
                )
                for source in [*full_sources, partial_source]
            ]
        )
        session.flush()
        session.add_all(
            [
                schema.SourceRun(
                    run_id="collect-full",
                    source_id=source.source_id,
                    mode="live",
                    status="healthy",
                    started_at=now,
                    completed_at=now,
                )
                for source in full_sources
            ]
        )
        session.add(
            schema.SourceRun(
                run_id="collect-single",
                source_id=partial_source.source_id,
                mode="live",
                status="healthy",
                started_at=now + timedelta(minutes=5),
                completed_at=now + timedelta(minutes=5),
            )
        )

    selected = p1_c22._latest_collect_run_id(db, min_source_count=50)

    assert selected == "collect-full"


def test_p1_c22_run_mode_summary_separates_current_run_from_history(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime(2026, 5, 21, tzinfo=UTC)
    db.init_schema()
    with db.session() as session:
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="live-source",
                    run_id="collect-current",
                    run_mode="live",
                    ts=now,
                    timeframe="latest",
                    is_fallback=False,
                    value=100.0,
                    quality_score=1.0,
                ),
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="mock-source",
                    run_id="collect-old",
                    run_mode="mock",
                    ts=now - timedelta(days=1),
                    timeframe="latest",
                    is_fallback=False,
                    value=99.0,
                    quality_score=1.0,
                ),
            ]
        )

    summary = p1_c22._audit_run_mode_summary(db, current_run_id="collect-current")

    assert summary["current_run_live_only"] is True
    assert summary["production_blocker"] is False
    assert summary["history"]["status"] == "warning"
    assert summary["default_query_scope"] == "live_only"


def test_p1_c22_business_recency_summary_counts_provider_stale_suspect() -> None:
    rows = [
        {"business_recency_status": "current"},
        {"business_recency_status": "expected_lag"},
        {"business_recency_status": "provider_stale_suspect"},
        {"business_recency_status": "provider_stale_suspect"},
        {"business_recency_status": "lagging"},
        {"business_recency_status": "unexpected_new_status"},
    ]

    counts = p1_c22._business_recency_counts_from_metric_rows(rows)

    assert counts["current"] == 1
    assert counts["expected_lag"] == 1
    assert counts["provider_stale_suspect"] == 2
    assert counts["lagging"] == 1
    assert counts["unknown"] == 1
