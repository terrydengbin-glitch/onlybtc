from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from onlybtc.core.paths import paths
from onlybtc.db.session import Database, database


def backup_database(db: Database = database, backup_dir: Path | None = None) -> Path:
    db.init_schema()
    target_dir = backup_dir or paths.backup_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    target = target_dir / f"onlybtc-{timestamp}.sqlite3"
    shutil.copy2(db.db_path, target)
    return target


def vacuum_database(db: Database = database) -> None:
    with db.engine.connect() as connection:
        connection.execute(text("VACUUM"))


def export_schema_sql(db: Database = database, export_dir: Path | None = None) -> Path:
    target_dir = export_dir or paths.exports_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "schema.sql"
    with db.engine.connect() as connection:
        rows = connection.execute(
            text("select sql from sqlite_master where sql is not null order by type, name")
        ).scalars()
        target.write_text("\n\n".join(rows), encoding="utf-8")
    return target


def run_mode_audit(db: Database = database) -> dict[str, object]:
    db.init_schema()
    with db.engine.connect() as connection:
        metric_counts = dict(
            connection.execute(
                text(
                    """
                    select coalesce(run_mode, 'unknown') as run_mode, count(*)
                    from metric_values
                    group by coalesce(run_mode, 'unknown')
                    """
                )
            ).all()
        )
        mixed_metrics = [
            row[0]
            for row in connection.execute(
                text(
                    """
                    select metric_id
                    from metric_values
                    group by metric_id
                    having count(distinct coalesce(run_mode, 'unknown')) > 1
                    order by metric_id
                    """
                )
            ).all()
        ]
        suspicious_rows = [
            {
                "metric_id": row[0],
                "source_id": row[1],
                "run_id": row[2],
                "run_mode": row[3],
                "ts": row[4],
                "value": row[5],
            }
            for row in connection.execute(
                text(
                    """
                    select metric_id, source_id, run_id, coalesce(run_mode, 'unknown'), ts, value
                    from metric_values
                    where coalesce(run_mode, 'unknown') != 'live'
                    order by ts desc
                    limit 50
                    """
                )
            ).all()
        ]
    return {
        "metric_value_counts": metric_counts,
        "mixed_metric_ids": mixed_metrics,
        "mixed_metric_count": len(mixed_metrics),
        "non_live_sample": suspicious_rows,
        "production_blocker": bool(
            metric_counts.get("mock", 0)
            or metric_counts.get("test", 0)
            or metric_counts.get("unknown", 0)
        ),
    }


def archive_non_live_metric_values(db: Database = database) -> dict[str, object]:
    db.init_schema()
    with db.engine.begin() as connection:
        before = dict(
            connection.execute(
                text(
                    """
                    select coalesce(run_mode, 'unknown') as run_mode, count(*)
                    from metric_values
                    group by coalesce(run_mode, 'unknown')
                    """
                )
            ).all()
        )
        connection.execute(
            text(
                """
                update source_runs
                set mode = case
                    when lower(coalesce(run_id, '')) like '%mock%' then 'mock'
                    when lower(coalesce(run_id, '')) like '%test%' then 'test'
                    when lower(coalesce(run_id, '')) like '%seed%' then 'test'
                    when coalesce(mode, 'unknown') in ('live', 'mock', 'test') then mode
                    else 'unknown'
                end
                """
            )
        )
        connection.execute(
            text(
                """
                update raw_observations
                set mode = case
                    when lower(coalesce(run_id, '')) like '%mock%' then 'mock'
                    when lower(coalesce(run_id, '')) like '%test%' then 'test'
                    when lower(coalesce(run_id, '')) like '%seed%' then 'test'
                    when coalesce(mode, 'unknown') in ('live', 'mock', 'test') then mode
                    else 'unknown'
                end
                """
            )
        )
        result = connection.execute(
            text(
                """
                update metric_values
                set run_mode = case
                    when lower(coalesce(run_id, '')) like '%mock%' then 'mock'
                    when lower(coalesce(run_id, '')) like '%test%' then 'test'
                    when lower(coalesce(run_id, '')) like '%seed%' then 'test'
                    when coalesce(run_mode, 'unknown') in ('live', 'mock', 'test') then run_mode
                    else 'unknown'
                end
                """
            )
        )
        after = dict(
            connection.execute(
                text(
                    """
                    select coalesce(run_mode, 'unknown') as run_mode, count(*)
                    from metric_values
                    group by coalesce(run_mode, 'unknown')
                    """
                )
            ).all()
        )
    return {
        "updated_rows": result.rowcount,
        "before": before,
        "after": after,
        "note": "non-live rows are tagged for filtering; rows are retained for replay/testing",
    }
