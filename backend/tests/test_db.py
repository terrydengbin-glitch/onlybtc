from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.maintenance import (
    archive_non_live_metric_values,
    backup_database,
    export_schema_sql,
    run_mode_audit,
)
from onlybtc.db.repositories import PageQueryRepository, RunRepository
from onlybtc.db.seed import seed_demo_data
from onlybtc.db.session import Database
from onlybtc.domain.models import RunStageStatus, empty_run_state
from onlybtc.pipeline.run_once import run_once_mock


def test_database_pragmas_and_schema(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    db.init_schema()

    assert db.db_path.exists()
    assert str(db.pragma("journal_mode")).lower() == "wal"
    assert db.pragma("foreign_keys") == 1


def test_run_repository_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run = empty_run_state()
    run.status = RunStageStatus.COMPLETED

    with db.session() as session:
        repository = RunRepository(session)
        repository.save_run_state(run)

    with db.session() as session:
        loaded = RunRepository(session).get(run.run_id)

    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert len(loaded.stages) == 12


async def test_run_once_can_persist_to_sqlite(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    run = await run_once_mock(delay_seconds=0, persist=False)

    db.init_schema()
    with db.session() as session:
        RunRepository(session).save_run_state(run)

    with db.session() as session:
        loaded = RunRepository(session).latest()

    assert loaded is not None
    assert loaded.status == RunStageStatus.COMPLETED


def test_seed_demo_supports_dashboard_query(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    result = seed_demo_data(db)

    assert result["seeded"] is True
    with db.session() as session:
        current = PageQueryRepository(session).dashboard_current()
        counts = PageQueryRepository(session).table_counts()

    assert current is not None
    assert current["snapshot"]["state"] == "leverage_squeeze"
    assert counts["dashboard_snapshots"] == 1
    assert counts["evidence_items"] == 2


def test_backup_and_schema_export(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    backup_dir = tmp_path / "backups"
    export_dir = tmp_path / "exports"

    backup_path = backup_database(db, backup_dir=backup_dir)
    schema_path = export_schema_sql(db, export_dir=export_dir)

    assert backup_path.exists()
    assert schema_path.exists()
    assert "CREATE TABLE" in schema_path.read_text(encoding="utf-8")


def test_run_mode_audit_and_archive_tags_old_rows(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime.now(UTC)
    with db.session() as session:
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    run_id="collect-mock-btc-price",
                    ts=now,
                    value=100.0,
                ),
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    run_id="collect-live-btc-price",
                    run_mode="live",
                    ts=now + timedelta(minutes=1),
                    value=101.0,
                ),
            ]
        )

    archive = archive_non_live_metric_values(db)
    audit = run_mode_audit(db)

    assert archive["updated_rows"] == 2
    assert audit["production_blocker"] is True
    assert audit["metric_value_counts"]["mock"] == 1
    assert "btc_price" in audit["mixed_metric_ids"]

    with db.session() as session:
        mock_row = session.scalar(
            select(schema.MetricValue).where(
                schema.MetricValue.run_id == "collect-mock-btc-price"
            )
        )

    assert mock_row is not None
    assert mock_row.run_mode == "mock"
