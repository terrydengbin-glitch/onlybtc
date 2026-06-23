from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceStatus(StrEnum):
    HEALTHY = "healthy"
    STALE = "stale"
    WARNING = "warning"
    ERROR = "error"


class RunStageName(StrEnum):
    QUEUED = "queued"
    FETCHING = "fetching"
    CLEANING = "cleaning"
    FEATURE_CALCULATION = "feature_calculation"
    RADAR_ANALYSIS = "radar_analysis"
    MODULE_LLM = "module_llm"
    FUSION = "fusion"
    MULTI_LLM_DEBATE = "multi_llm_debate"
    REVIEW = "review"
    ALERT_POLICY = "alert_policy"
    PUBLISH = "publish"
    COMPLETED = "completed"


class RunStageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SystemHealth(BaseModel):
    app: str = "onlyBTC"
    status: Literal["healthy"] = "healthy"
    environment: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunStage(BaseModel):
    name: str
    status: str = RunStageStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    detail: str | None = None


class RunState(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    trigger: str = "manual_run_once"
    status: str = RunStageStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    current_stage: str = RunStageName.QUEUED
    stages: list[RunStage]


def empty_run_state() -> RunState:
    return RunState(stages=[RunStage(name=stage) for stage in RunStageName])
