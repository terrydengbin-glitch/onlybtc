from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from onlybtc.core.paths import paths
from onlybtc.db.schema import Base

SQLITE_BUSY_TIMEOUT_MS = 30_000
_SQLITE_WRITE_LOCK = threading.RLock()


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or paths.sqlite_db_path
        self.engine = self._create_engine(self.db_path)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def _create_engine(self, db_path: Path) -> Engine:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            f"sqlite:///{db_path}",
            future=True,
            connect_args={"timeout": SQLITE_BUSY_TIMEOUT_MS / 1000},
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection: sqlite3.Connection, _: object) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        return engine

    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        self._ensure_runtime_columns()

    def drop_schema(self) -> None:
        Base.metadata.drop_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with _SQLITE_WRITE_LOCK:
            session = self.session_factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    def pragma(self, name: str) -> str | int | None:
        with self.engine.connect() as connection:
            return connection.execute(text(f"PRAGMA {name}")).scalar()

    def _ensure_runtime_columns(self) -> None:
        migrations = {
            "source_runs": {
                "mode": "ALTER TABLE source_runs ADD COLUMN mode VARCHAR(16) DEFAULT 'unknown'",
            },
            "raw_observations": {
                "mode": (
                    "ALTER TABLE raw_observations "
                    "ADD COLUMN mode VARCHAR(16) DEFAULT 'unknown'"
                ),
            },
            "metric_values": {
                "run_mode": (
                    "ALTER TABLE metric_values "
                    "ADD COLUMN run_mode VARCHAR(16) DEFAULT 'unknown'"
                ),
            },
        }
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_source_runs_run_id_mode ON source_runs (run_id, mode)",
            (
                "CREATE INDEX IF NOT EXISTS ix_raw_observations_source_run_mode "
                "ON raw_observations (source_id, run_id, mode)"
            ),
            (
                "CREATE INDEX IF NOT EXISTS ix_metric_values_metric_source_mode_ts "
                "ON metric_values (metric_id, source_id, run_mode, ts)"
            ),
            (
                "CREATE INDEX IF NOT EXISTS ix_radar_module_snapshots_module_asof "
                "ON radar_module_snapshots (module_name, asof_ts)"
            ),
            (
                "CREATE INDEX IF NOT EXISTS ix_radar_runtime_snapshots_asof "
                "ON radar_runtime_snapshots (asof_ts)"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_timescale_snapshot_id "
                "ON timescale_judge_snapshots (snapshot_id)"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_timescale_asof_ts "
                "ON timescale_judge_snapshots (asof_ts)"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_timescale_schema_version "
                "ON timescale_judge_snapshots (schema_version)"
            ),
        ]
        with self.engine.begin() as connection:
            for table, columns in migrations.items():
                existing = {
                    row[1]
                    for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")
                }
                for column, statement in columns.items():
                    if column not in existing:
                        connection.execute(text(statement))
            self._ensure_metric_values_run_mode_identity(connection)
            self._ensure_timescale_snapshot_run_identity(connection)
            for statement in indexes:
                connection.execute(text(statement))

    def _ensure_metric_values_run_mode_identity(self, connection: Connection) -> None:
        table_sql = connection.execute(
            text(
                """
                select sql
                from sqlite_master
                where type = 'table' and name = 'metric_values'
                """
            )
        ).scalar()
        if not table_sql:
            return
        normalized = str(table_sql).lower().replace("\n", " ")
        has_old_identity = "unique (metric_id, ts, source_id)" in normalized
        has_new_identity = "unique (metric_id, ts, source_id, run_mode)" in normalized
        if not has_old_identity or has_new_identity:
            return

        backup_table = "metric_values_before_run_mode_identity"
        connection.exec_driver_sql(f"DROP TABLE IF EXISTS {backup_table}")
        connection.exec_driver_sql(f"ALTER TABLE metric_values RENAME TO {backup_table}")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_metric_values_metric_ts")
        Base.metadata.tables["metric_values"].create(connection, checkfirst=False)
        columns = [
            "id",
            "metric_id",
            "source_id",
            "run_id",
            "run_mode",
            "ts",
            "timeframe",
            "is_fallback",
            "value",
            "previous_value",
            "change_24h",
            "change_7d",
            "ma_30d",
            "quality_score",
            "created_at",
            "updated_at",
        ]
        column_sql = ", ".join(columns)
        connection.execute(
            text(
                f"""
                INSERT INTO metric_values ({column_sql})
                SELECT
                    id,
                    metric_id,
                    source_id,
                    run_id,
                    coalesce(run_mode, 'unknown'),
                    ts,
                    timeframe,
                    is_fallback,
                    value,
                    previous_value,
                    change_24h,
                    change_7d,
                    ma_30d,
                    quality_score,
                    created_at,
                    updated_at
                FROM {backup_table}
                """
            )
        )
        connection.exec_driver_sql(f"DROP TABLE {backup_table}")

    def _ensure_timescale_snapshot_run_identity(self, connection: Connection) -> None:
        table_sql = connection.execute(
            text(
                """
                select sql
                from sqlite_master
                where type = 'table' and name = 'timescale_judge_snapshots'
                """
            )
        ).scalar()
        if not table_sql:
            return
        normalized = str(table_sql).lower().replace("\n", " ")
        has_inline_unique = "unique (snapshot_id)" in normalized
        has_unique_snapshot_index = False
        for index_row in connection.exec_driver_sql(
            "PRAGMA index_list(timescale_judge_snapshots)"
        ):
            index_name = str(index_row[1])
            is_unique = bool(index_row[2])
            if not is_unique:
                continue
            columns = [
                str(info_row[2])
                for info_row in connection.exec_driver_sql(f"PRAGMA index_info({index_name})")
            ]
            if columns == ["snapshot_id"]:
                has_unique_snapshot_index = True
                break
        if not has_inline_unique and not has_unique_snapshot_index:
            return

        backup_table = "timescale_judge_snapshots_before_run_identity"
        connection.exec_driver_sql(f"DROP TABLE IF EXISTS {backup_table}")
        connection.exec_driver_sql(
            f"ALTER TABLE timescale_judge_snapshots RENAME TO {backup_table}"
        )
        connection.exec_driver_sql("DROP INDEX IF EXISTS idx_timescale_snapshot_id")
        connection.exec_driver_sql("DROP INDEX IF EXISTS idx_timescale_asof_ts")
        connection.exec_driver_sql("DROP INDEX IF EXISTS idx_timescale_schema_version")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_timescale_judge_snapshots_snapshot_id")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_timescale_judge_snapshots_run_id")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_timescale_judge_snapshots_asof_ts")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_timescale_judge_snapshots_schema_version")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_timescale_judge_snapshots_fallback_used")
        Base.metadata.tables["timescale_judge_snapshots"].create(connection, checkfirst=False)
        columns = [
            "id",
            "snapshot_id",
            "run_id",
            "asof_ts",
            "schema_version",
            "payload_json",
            "source_window_json",
            "freshness_summary_json",
            "fallback_used",
            "fallback_reason",
            "created_at",
            "updated_at",
        ]
        column_sql = ", ".join(columns)
        connection.execute(
            text(
                f"""
                INSERT INTO timescale_judge_snapshots ({column_sql})
                SELECT {column_sql}
                FROM {backup_table}
                """
            )
        )
        connection.exec_driver_sql(f"DROP TABLE {backup_table}")


database = Database()
