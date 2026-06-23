from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    group_name: Mapped[str] = mapped_column(String(80), index=True)
    method: Mapped[str] = mapped_column(String(40))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(32), default="healthy", index=True)
    fallback_source_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    runs: Mapped[list[SourceRun]] = relationship(back_populates="source")


class SourceRun(Base, TimestampMixin):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"), index=True)
    mode: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="runs")


class RawObservation(Base, TimestampMixin):
    __tablename__ = "raw_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(80), index=True)


class NormalizedMetric(Base, TimestampMixin):
    __tablename__ = "normalized_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    group_name: Mapped[str] = mapped_column(String(80), index=True)
    higher_is: Mapped[str] = mapped_column(String(32), default="neutral")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MetricValue(Base, TimestampMixin):
    __tablename__ = "metric_values"
    __table_args__ = (
        UniqueConstraint(
            "metric_id",
            "ts",
            "source_id",
            "run_mode",
            name="uq_metric_value_identity",
        ),
        Index("ix_metric_values_metric_ts", "metric_id", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_id: Mapped[str] = mapped_column(String(120), index=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    run_mode: Mapped[str] = mapped_column(String(16), default="live", index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timeframe: Mapped[str] = mapped_column(String(24), default="spot", index=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    value: Mapped[float] = mapped_column(Float)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, default=1.0)


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    trigger: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    current_stage: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    stages: Mapped[list[RunStage]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunStage(Base, TimestampMixin):
    __tablename__ = "run_stages"
    __table_args__ = (UniqueConstraint("run_id", "stage_name", name="uq_run_stage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.run_id"), index=True)
    stage_name: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    run: Mapped[Run] = relationship(back_populates="stages")


class RunLog(Base, TimestampMixin):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    stage_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="INFO", index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    path: Mapped[str] = mapped_column(String(240), index=True)
    method: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    status_code: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(80), default="local_api", index=True)
    client_host: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkerHeartbeat(Base, TimestampMixin):
    __tablename__ = "worker_heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RetryRecord(Base, TimestampMixin):
    __tablename__ = "retry_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(120))
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeatureValue(Base, TimestampMixin):
    __tablename__ = "feature_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    module_id: Mapped[str] = mapped_column(String(80), index=True)
    feature_id: Mapped[str] = mapped_column(String(120), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RadarOutput(Base, TimestampMixin):
    __tablename__ = "radar_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    module_id: Mapped[str] = mapped_column(String(80), index=True)
    signal: Mapped[str] = mapped_column(String(32), index=True)
    strength: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    data_quality: Mapped[str] = mapped_column(String(32), index=True)
    evidence_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    conflicting_evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    invalidation_signals: Mapped[dict] = mapped_column(JSON, default=dict)


class ModuleJsonOutput(Base, TimestampMixin):
    __tablename__ = "module_json_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    module_id: Mapped[str] = mapped_column(String(80), index=True)
    schema_version: Mapped[str] = mapped_column(String(24), default="1.0")
    payload: Mapped[dict] = mapped_column(JSON)


class TimescaleJudgeSnapshot(Base, TimestampMixin):
    __tablename__ = "timescale_judge_snapshots"
    __table_args__ = (
        Index("idx_timescale_snapshot_id", "snapshot_id"),
        Index("idx_timescale_asof_ts", "asof_ts"),
        Index("idx_timescale_schema_version", "schema_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(120), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    asof_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    schema_version: Mapped[str] = mapped_column(String(32), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    source_window_json: Mapped[dict] = mapped_column(JSON, default=dict)
    freshness_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlgorithmAlert(Base, TimestampMixin):
    __tablename__ = "algorithm_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[str] = mapped_column(String(32), index=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertEvent(Base, TimestampMixin):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class InvalidationCondition(Base, TimestampMixin):
    __tablename__ = "invalidation_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    condition_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(40), index=True)
    module_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    threshold_json: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(32), index=True)


class InvalidationEvent(Base, TimestampMixin):
    __tablename__ = "invalidation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    condition_id: Mapped[str] = mapped_column(String(80), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidencePack(Base, TimestampMixin):
    __tablename__ = "evidence_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pack_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    data_quality_score: Mapped[float] = mapped_column(Float, default=1.0)


class EvidenceItem(Base, TimestampMixin):
    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    pack_id: Mapped[str] = mapped_column(String(80), index=True)
    module_id: Mapped[str] = mapped_column(String(80), index=True)
    claim: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(32), index=True)
    strength: Mapped[float] = mapped_column(Float)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class EvidenceMetricLink(Base, TimestampMixin):
    __tablename__ = "evidence_metric_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(80), index=True)
    metric_value_id: Mapped[int] = mapped_column(Integer, index=True)


class LlmDebate(Base, TimestampMixin):
    __tablename__ = "llm_debates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debate_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    consensus_score: Mapped[float] = mapped_column(Float)
    disagreement_level: Mapped[str] = mapped_column(String(32), index=True)
    final_state: Mapped[str] = mapped_column(String(64), index=True)
    publish_allowed: Mapped[bool] = mapped_column(Boolean, default=False)


class LlmRound(Base, TimestampMixin):
    __tablename__ = "llm_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debate_id: Mapped[str] = mapped_column(String(80), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    round_type: Mapped[str] = mapped_column(String(40), index=True)
    summary: Mapped[str] = mapped_column(Text)


class LlmModelVote(Base, TimestampMixin):
    __tablename__ = "llm_model_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debate_id: Mapped[str] = mapped_column(String(80), index=True)
    model_name: Mapped[str] = mapped_column(String(80), index=True)
    vote: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    changed: Mapped[bool] = mapped_column(Boolean, default=False)


class LlmChallenge(Base, TimestampMixin):
    __tablename__ = "llm_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debate_id: Mapped[str] = mapped_column(String(80), index=True)
    challenger: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(80))
    issue: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(32), index=True)


class LlmRevision(Base, TimestampMixin):
    __tablename__ = "llm_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debate_id: Mapped[str] = mapped_column(String(80), index=True)
    challenge_id: Mapped[str] = mapped_column(String(120), index=True)
    responding_agent: Mapped[str] = mapped_column(String(80), index=True)
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    previous_vote: Mapped[str] = mapped_column(String(64), index=True)
    revised_vote: Mapped[str] = mapped_column(String(64), index=True)
    previous_confidence: Mapped[float] = mapped_column(Float)
    revised_confidence: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class JudgeSynthesis(Base, TimestampMixin):
    __tablename__ = "judge_syntheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    debate_id: Mapped[str] = mapped_column(String(80), index=True)
    final_state: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    confidence_discount: Mapped[float] = mapped_column(Float, default=0)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AdversarialReview(Base, TimestampMixin):
    __tablename__ = "adversarial_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    debate_id: Mapped[str] = mapped_column(String(80), index=True)
    review_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    issues: Mapped[dict] = mapped_column(JSON, default=dict)
    required_changes: Mapped[dict] = mapped_column(JSON, default=dict)


class DashboardSnapshot(Base, TimestampMixin):
    __tablename__ = "dashboard_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    btc_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    bias: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(64), index=True)
    alert_level: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class SnapshotModule(Base, TimestampMixin):
    __tablename__ = "snapshot_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(80), index=True)
    module_id: Mapped[str] = mapped_column(String(80), index=True)
    signal: Mapped[str] = mapped_column(String(32), index=True)
    strength: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class SnapshotAlert(Base, TimestampMixin):
    __tablename__ = "snapshot_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(80), index=True)
    alert_id: Mapped[str] = mapped_column(String(80), index=True)


class Article(Base, TimestampMixin):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    snapshot_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    publish_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN")


class ArticleVersion(Base, TimestampMixin):
    __tablename__ = "article_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)


class ArticleEvidenceLink(Base, TimestampMixin):
    __tablename__ = "article_evidence_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[str] = mapped_column(String(80), index=True)
    evidence_id: Mapped[str] = mapped_column(String(80), index=True)


class ReplayScore(Base, TimestampMixin):
    __tablename__ = "replay_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(80), index=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)
    result_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class CalibrationNote(Base, TimestampMixin):
    __tablename__ = "calibration_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(String(120), index=True)
    note: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class DataQualitySnapshot(Base, TimestampMixin):
    __tablename__ = "data_quality_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class SourceHealthEvent(Base, TimestampMixin):
    __tablename__ = "source_health_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    quality_score: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class FallbackEvent(Base, TimestampMixin):
    __tablename__ = "fallback_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    fallback_source_id: Mapped[str] = mapped_column(String(80), index=True)
    reason: Mapped[str] = mapped_column(Text)
    discount: Mapped[float] = mapped_column(Float)


class RateLimitEvent(Base, TimestampMixin):
    __tablename__ = "rate_limit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(80), index=True)
    current: Mapped[int] = mapped_column(Integer)
    limit: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModuleDiscount(Base, TimestampMixin):
    __tablename__ = "module_discounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[str] = mapped_column(String(80), index=True)
    reason: Mapped[str] = mapped_column(Text)
    discount: Mapped[float] = mapped_column(Float)
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)


class EventWatchtowerSnapshot(Base, TimestampMixin):
    __tablename__ = "event_watchtower_snapshots"
    __table_args__ = (
        Index("ix_event_watchtower_snapshots_asof_level", "asof_ts", "emergency_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    asof_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    daemon_status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    event_window_state: Mapped[str] = mapped_column(String(80), default="event_neutral", index=True)
    emergency_level: Mapped[str] = mapped_column(String(32), default="none", index=True)
    trade_permission_modifier: Mapped[str] = mapped_column(String(64), default="none", index=True)
    ordinary_radar_trust: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    active_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload_hash: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RadarRuntimeSnapshot(Base, TimestampMixin):
    __tablename__ = "radar_runtime_snapshots"
    __table_args__ = (
        Index("ix_radar_runtime_snapshots_asof_health", "asof_ts", "health_state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    runtime_snapshot_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    asof_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    trigger_type: Mapped[str] = mapped_column(String(40), default="scheduler_tick", index=True)
    health_state: Mapped[str] = mapped_column(String(32), default="healthy", index=True)
    module_count: Mapped[int] = mapped_column(Integer, default=0)
    fresh_module_count: Mapped[int] = mapped_column(Integer, default=0)
    stale_module_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_hash: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RadarModuleSnapshot(Base, TimestampMixin):
    __tablename__ = "radar_module_snapshots"
    __table_args__ = (
        Index("ix_radar_module_snapshots_module_asof", "module_name", "asof_ts"),
        Index("ix_radar_module_snapshots_freshness", "freshness_state", "asof_ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_snapshot_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    runtime_snapshot_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    module_name: Mapped[str] = mapped_column(String(80), index=True)
    cadence_group: Mapped[str] = mapped_column(String(40), index=True)
    trigger_type: Mapped[str] = mapped_column(String(40), default="scheduler_tick", index=True)
    asof_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ttl_sec: Mapped[int] = mapped_column(Integer, default=300)
    hard_stale_sec: Mapped[int] = mapped_column(Integer, default=900)
    age_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    freshness_state: Mapped[str] = mapped_column(String(32), default="fresh", index=True)
    participation_policy: Mapped[str] = mapped_column(String(64), default="full", index=True)
    module_direction: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    module_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RadarRuntimeSchedulerState(Base, TimestampMixin):
    __tablename__ = "radar_runtime_scheduler_state"
    __table_args__ = (
        UniqueConstraint("module_name", name="uq_radar_runtime_scheduler_module"),
        Index("ix_radar_runtime_scheduler_next_due", "next_due_at", "last_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    cadence_group: Mapped[str] = mapped_column(String(40), index=True)
    interval_sec: Mapped[int] = mapped_column(Integer, default=300)
    ttl_sec: Mapped[int] = mapped_column(Integer, default=600)
    hard_stale_sec: Mapped[int] = mapped_column(Integer, default=1800)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    last_snapshot_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventCalendarItem(Base, TimestampMixin):
    __tablename__ = "event_calendar_items"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_calendar_item_event_id"),
        Index("ix_event_calendar_items_release_importance", "release_time_utc", "importance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    importance: Mapped[str] = mapped_column(String(24), default="medium", index=True)
    release_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    release_time_et: Mapped[str | None] = mapped_column(String(40), nullable=True)
    release_time_local: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_tier: Mapped[str] = mapped_column(String(24), default="official", index=True)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventExpectationSnapshot(Base, TimestampMixin):
    __tablename__ = "event_expectation_snapshots"
    __table_args__ = (Index("ix_event_expectation_snapshots_event_ts", "event_id", "snapshot_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(120), index=True)
    snapshot_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consensus: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous: Mapped[float | None] = mapped_column(Float, nullable=True)
    nowcast: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_implied: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectation_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectation_drift_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectation_drift_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_cut_prob_drift_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_direction: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventOfficialTextItem(Base, TimestampMixin):
    __tablename__ = "event_official_text_items"
    __table_args__ = (
        UniqueConstraint("text_hash", name="uq_event_official_text_hash"),
        Index("ix_event_official_text_items_source_ts", "source_tier", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    text_hash: Mapped[str] = mapped_column(String(80), index=True)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    source_tier: Mapped[str] = mapped_column(String(24), default="official", index=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    speaker: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventLlmAnalysis(Base, TimestampMixin):
    __tablename__ = "event_llm_analyses"
    __table_args__ = (Index("ix_event_llm_analyses_text_ts", "text_id", "analyzed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    text_id: Mapped[str] = mapped_column(String(120), index=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    speaker: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    speaker_weight: Mapped[float] = mapped_column(Float, default=0.0)
    tone: Mapped[str] = mapped_column(String(40), default="ambiguous", index=True)
    tone_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    policy_relevance: Mapped[str] = mapped_column(String(24), default="low", index=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventShockLaneItem(Base, TimestampMixin):
    __tablename__ = "event_shock_lane_items"
    __table_args__ = (
        Index("ix_event_shock_lane_items_ts_level", "detected_at", "emergency_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shock_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    shock_type: Mapped[str] = mapped_column(String(40), default="unknown", index=True)
    emergency_level: Mapped[str] = mapped_column(String(32), default="watch", index=True)
    confirmation_level: Mapped[str] = mapped_column(String(32), default="single_source", index=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    market_dislocation: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    btc_microstructure_confirmation: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
    )
    rumor_risk: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventMarketProbe(Base, TimestampMixin):
    __tablename__ = "event_market_probes"
    __table_args__ = (
        UniqueConstraint("market_probe_id", name="uq_event_market_probe_id"),
        Index("ix_event_market_probes_collected_symbol", "collected_at", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_probe_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    symbol: Mapped[str] = mapped_column(String(32), default="BTCUSDT", index=True)
    source: Mapped[str] = mapped_column(String(80), default="binance", index=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_15m: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_4h: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventPostReactionSnapshot(Base, TimestampMixin):
    __tablename__ = "event_post_reaction_snapshots"
    __table_args__ = (Index("ix_event_post_reaction_event_ts", "event_id", "snapshot_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reaction_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(120), index=True)
    snapshot_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    consensus: Mapped[float | None] = mapped_column(Float, nullable=True)
    surprise_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    surprise_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    btc_return_5m: Mapped[float | None] = mapped_column(Float, nullable=True)
    btc_return_30m: Mapped[float | None] = mapped_column(Float, nullable=True)
    btc_return_2h: Mapped[float | None] = mapped_column(Float, nullable=True)
    btc_absorbed_shock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    followthrough: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventAlert(Base, TimestampMixin):
    __tablename__ = "event_alerts"
    __table_args__ = (Index("ix_event_alerts_level_status", "emergency_level", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    event_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    emergency_level: Mapped[str] = mapped_column(String(32), default="watch", index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    reason_code: Mapped[str] = mapped_column(String(80), default="calendar_monitor", index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventSourceFetch(Base, TimestampMixin):
    __tablename__ = "event_source_fetches"
    __table_args__ = (
        Index("ix_event_source_fetches_source_started", "source_id", "started_at"),
        Index("ix_event_source_fetches_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fetch_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_id: Mapped[str] = mapped_column(String(120), index=True)
    source_tier: Mapped[str] = mapped_column(String(32), default="official", index=True)
    endpoint_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default="failed",
        index=True,
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    parsed_item_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class EventSchedulerState(Base, TimestampMixin):
    __tablename__ = "event_scheduler_state"
    __table_args__ = (
        UniqueConstraint("source_group", name="uq_event_scheduler_state_source_group"),
        Index("ix_event_scheduler_state_next_due", "next_due_at", "last_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_group: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    cadence_profile: Mapped[str] = mapped_column(String(32), default="balanced", index=True)
    phase: Mapped[str] = mapped_column(String(64), default="normal", index=True)
    interval_sec: Mapped[int] = mapped_column(Integer, default=300)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    last_fetch_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
