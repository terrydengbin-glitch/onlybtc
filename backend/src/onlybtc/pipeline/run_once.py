from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from onlybtc.db.repositories import RunRepository
from onlybtc.db.session import Database, database
from onlybtc.domain.models import RunStageName, RunStageStatus, RunState, empty_run_state


class RunOnceStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}

    def save(self, run: RunState) -> RunState:
        run.updated_at = datetime.now(UTC)
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def latest(self) -> RunState | None:
        if not self._runs:
            return None
        return max(self._runs.values(), key=lambda run: run.created_at)


run_once_store = RunOnceStore()


async def run_once_mock(delay_seconds: float = 0.01, persist: bool = True) -> RunState:
    run = empty_run_state()
    run.status = RunStageStatus.RUNNING
    run_once_store.save(run)
    if persist:
        persist_run_state(run)

    for stage in run.stages:
        run.current_stage = stage.name
        stage.status = RunStageStatus.RUNNING
        stage.started_at = datetime.now(UTC)
        stage.detail = _stage_detail(stage.name)
        run_once_store.save(run)
        if persist:
            persist_run_state(run)
        await asyncio.sleep(delay_seconds)
        stage.status = RunStageStatus.COMPLETED
        stage.completed_at = datetime.now(UTC)
        run_once_store.save(run)
        if persist:
            persist_run_state(run)

    run.status = RunStageStatus.COMPLETED
    run.current_stage = RunStageName.COMPLETED
    run_once_store.save(run)
    if persist:
        persist_run_state(run)
    return run


def persist_run_state(run: RunState, db: Database = database) -> RunState:
    db.init_schema()
    with db.session() as session:
        return RunRepository(session).save_run_state(run)


def latest_persisted_run(db: Database = database) -> RunState | None:
    db.init_schema()
    with db.session() as session:
        return RunRepository(session).latest()


def get_persisted_run(run_id: str, db: Database = database) -> RunState | None:
    db.init_schema()
    with db.session() as session:
        return RunRepository(session).get(run_id)


def _stage_detail(stage: RunStageName) -> str:
    details = {
        RunStageName.QUEUED: "Task entered mock queue.",
        RunStageName.FETCHING: "Mock source data prepared.",
        RunStageName.CLEANING: "Mock data normalized.",
        RunStageName.FEATURE_CALCULATION: "Mock feature values calculated.",
        RunStageName.RADAR_ANALYSIS: "Mock radar states generated.",
        RunStageName.MODULE_LLM: "Mock module reasoning completed.",
        RunStageName.FUSION: "Mock fusion result prepared.",
        RunStageName.MULTI_LLM_DEBATE: "Mock debate transcript prepared.",
        RunStageName.REVIEW: "Mock adversarial review passed.",
        RunStageName.ALERT_POLICY: "Mock alert policy checked.",
        RunStageName.PUBLISH: "Mock publish skipped in P0.",
        RunStageName.COMPLETED: "Mock run completed without trading advice.",
    }
    return details[stage]
