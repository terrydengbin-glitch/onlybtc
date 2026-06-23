from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceKind(StrEnum):
    FRED = "fred"
    EXCHANGE = "exchange"
    BITCOIN = "bitcoin"
    OFFICIAL = "official"
    PLAYWRIGHT = "playwright"


class SourceMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"
    TEST = "test"


class SourceStatus(StrEnum):
    HEALTHY = "healthy"
    STALE = "stale"
    WARNING = "warning"
    ERROR = "error"


class SourceConfig(BaseModel):
    source_id: str
    name: str
    kind: SourceKind
    group_name: str
    method: str
    priority: int = 100
    url: str | None = None
    fallback_source_id: str | None = None
    metrics: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricDefinition(BaseModel):
    metric_id: str
    name: str
    source_id: str
    group_name: str
    unit: str | None = None
    higher_is: str = "neutral"


class RawObservationData(BaseModel):
    source_id: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any]
    status: SourceStatus = SourceStatus.HEALTHY
    latency_ms: int | None = None
    error_message: str | None = None


class MetricSample(BaseModel):
    metric_id: str
    source_id: str
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    collected_at: datetime | None = None
    observed_at_source: str = "source"
    value: float
    timeframe: str = "spot"
    is_fallback: bool = False
    quality_score: float = 1.0
    previous_value: float | None = None
    change_24h: float | None = None
    change_7d: float | None = None
    ma_30d: float | None = None


class CollectionResult(BaseModel):
    source: SourceConfig
    raw: RawObservationData
    metrics: list[MetricSample] = Field(default_factory=list)


class HistoricalWindow(BaseModel):
    metric_id: str
    source_id: str | None
    current: float | None
    previous: float | None
    change_24h: float | None
    change_7d: float | None
    ma_30d: float | None
    quality_score: float
    is_fallback: bool
    run_mode: str = "unknown"
    sample_count: int
    observed_at: datetime | None = None
    collected_at: datetime | None = None
    source_ts: str | None = None
    freshness_minutes: float | None = None
    stale_after_minutes: float | None = None
    is_stale: bool | None = None
    source_run_id: str | None = None
    age_seconds: float | None = None
    expected_refresh_seconds: float | None = None
    freshness_status: str = "unknown"
    freshness_discount: float = 0.0
    collection_age_seconds: float | None = None
    collection_freshness_status: str = "unknown"
    collection_freshness_discount: float = 0.0
    business_age_seconds: float | None = None
    business_recency_status: str = "unknown"
    business_recency_discount: float = 0.0
    freshness_policy: dict[str, Any] = Field(default_factory=dict)
    effective_quality_score: float | None = None
    selected_reason: str | None = None
    feature_run_scope: str = "unspecified_history"
    current_run_has_value: bool = False
    fallback_age_seconds: float | None = None
    fallback_reason: str | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    conflict: dict[str, Any] | None = None
