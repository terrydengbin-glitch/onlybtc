from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from onlybtc.db.repositories import TimescaleJudgeReplayRepository
from onlybtc.db.session import Database, database


def save_timescale_judge_snapshot(
    run_id: str,
    payload: dict[str, Any],
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        return TimescaleJudgeReplayRepository(session).save_snapshot(run_id=run_id, payload=payload)


def replay_timescale_judge(
    *,
    run_id: str | None = None,
    snapshot_id: str | None = None,
    asof_ts: datetime | str | None = None,
    latest: bool = False,
    db: Database = database,
) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        repository = TimescaleJudgeReplayRepository(session)
        if snapshot_id:
            return repository.by_snapshot_id(snapshot_id)
        if run_id:
            return repository.by_run_id(run_id)
        if asof_ts:
            parsed = _parse_asof(asof_ts)
            return repository.at_or_before(parsed) if parsed else None
        if latest:
            return repository.latest()
        return repository.latest()


def list_timescale_judge_replays(
    limit: int = 20,
    db: Database = database,
) -> list[dict[str, Any]]:
    db.init_schema()
    with db.session() as session:
        return TimescaleJudgeReplayRepository(session).list_recent(limit=limit)


def _parse_asof(value: datetime | str) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
