from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.sources.registry import SOURCE_CONFIGS
from onlybtc.sources.service import ensure_source_registry, source_health_summary

SCHEMA_VERSION = "p7.c04.source_health_monitor.v1"
WARNING_EVENT_STATUSES = {"warning", "error", "stale"}


def build_source_health_monitor_report(
    db: Database = database,
    *,
    now: datetime | None = None,
    recent_hours: int = 24,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        snapshot = _latest_data_quality_snapshot(session)
        recent_events = _recent_source_health_events(session, now=now, recent_hours=recent_hours)
    health_summary = source_health_summary(db)
    snapshot_payload = dict(snapshot.payload if snapshot is not None else {})
    alerts = _build_alerts(snapshot, snapshot_payload, recent_events)
    overall_status = _overall_status(snapshot, alerts)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "applied_to_production": False,
        "overall_status": overall_status,
        "alert_count": len(alerts),
        "alerts": alerts,
        "latest_data_quality": _snapshot_summary(snapshot, snapshot_payload),
        "recent_event_window_hours": recent_hours,
        "recent_source_events": [_event_summary(event) for event in recent_events],
        "source_health_summary": health_summary,
        "source_registry": _source_registry_summary(),
        "downstream_policy": _downstream_policy(overall_status),
        "guardrails": [
            "monitoring_only",
            "does_not_collect_sources",
            "does_not_modify_source_registry",
            "does_not_modify_state_machine",
            "does_not_emit_trading_advice",
            "requires_p7_c08_before_production_apply",
        ],
    }


def _latest_data_quality_snapshot(session) -> schema.DataQualitySnapshot | None:
    snapshots = session.scalars(
        select(schema.DataQualitySnapshot)
        .order_by(schema.DataQualitySnapshot.created_at.desc(), schema.DataQualitySnapshot.id.desc())
        .limit(20)
    ).all()
    for snapshot in snapshots:
        if _has_scoped_run_mode_summary(snapshot):
            return snapshot
    return snapshots[0] if snapshots else None


def _has_scoped_run_mode_summary(snapshot: schema.DataQualitySnapshot) -> bool:
    payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
    run_mode_summary = payload.get("run_mode_summary")
    return isinstance(run_mode_summary, dict) and isinstance(run_mode_summary.get("current_run"), dict)


def _recent_source_health_events(
    session,
    *,
    now: datetime,
    recent_hours: int,
) -> list[schema.SourceHealthEvent]:
    cutoff = now - timedelta(hours=recent_hours)
    return session.scalars(
        select(schema.SourceHealthEvent)
        .where(schema.SourceHealthEvent.created_at >= cutoff)
        .order_by(schema.SourceHealthEvent.created_at.desc(), schema.SourceHealthEvent.id.desc())
        .limit(200)
    ).all()


def _build_alerts(
    snapshot: schema.DataQualitySnapshot | None,
    payload: dict[str, Any],
    events: list[schema.SourceHealthEvent],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if snapshot is None:
        alerts.append(
            {
                "alert_id": "data_quality_snapshot_missing",
                "level": "warning",
                "scope": "data_quality",
                "reason": "no_data_quality_snapshot_found",
                "recommended_action": "run_source_collection_or_write_snapshot_before_p7_c08",
            }
        )
        return alerts

    if snapshot.status in {"warning", "critical"}:
        alerts.append(
            {
                "alert_id": f"data_quality_{snapshot.status}",
                "level": snapshot.status,
                "scope": "data_quality",
                "reason": f"latest_data_quality_status_{snapshot.status}_score_{snapshot.score:.4f}",
                "recommended_action": "keep_publish_or_confirmed_signal_gates_conservative",
            }
        )

    freshness_counts = payload.get("freshness_counts") or {}
    missing = int(freshness_counts.get("missing") or 0)
    expired = int(freshness_counts.get("expired") or 0)
    stale = int(freshness_counts.get("stale") or 0)
    if missing or expired:
        alerts.append(
            {
                "alert_id": "source_freshness_gap",
                "level": "critical" if missing else "warning",
                "scope": "freshness",
                "reason": f"missing={missing}; expired={expired}; stale={stale}",
                "recommended_action": "block_confirmed_signal_for_affected_modules",
            }
        )
    elif stale:
        alerts.append(
            {
                "alert_id": "source_freshness_stale",
                "level": "watch",
                "scope": "freshness",
                "reason": f"stale={stale}",
                "recommended_action": "lower_sensitivity_for_affected_modules",
            }
        )

    lagging_count = len(payload.get("business_lagging_sources") or [])
    if lagging_count:
        alerts.append(
            {
                "alert_id": "business_recency_lagging",
                "level": "warning",
                "scope": "business_recency",
                "reason": f"business_lagging_source_count={lagging_count}",
                "recommended_action": "treat_as_context_only_until_source_recency_recovers",
            }
        )

    fallback = payload.get("fallback_summary") or {}
    if int(fallback.get("fallback_event_count") or 0):
        alerts.append(
            {
                "alert_id": "fallback_sources_active",
                "level": "watch",
                "scope": "fallback",
                "reason": f"fallback_event_count={fallback.get('fallback_event_count')}",
                "recommended_action": "surface_fallback_reason_in_dashboard_and_audit",
            }
        )
    if fallback.get("http_403_sources"):
        alerts.append(
            {
                "alert_id": "source_auth_or_permission_403",
                "level": "warning",
                "scope": "provider_auth",
                "reason": "http_403_sources=" + ",".join(fallback["http_403_sources"]),
                "recommended_action": "route_to_p7_c07_permissions_and_source_access_audit",
            }
        )

    run_mode = payload.get("run_mode_summary") or {}
    if run_mode.get("production_blocker"):
        alerts.append(
            {
                "alert_id": "run_mode_mixing_production_blocker",
                "level": "critical",
                "scope": "run_mode",
                "reason": "mock_test_or_unknown_metric_values_present",
                "recommended_action": "block_production_publish_until_lineage_is_live_only",
            }
        )

    if int(payload.get("registry_drift_count") or 0):
        alerts.append(
            {
                "alert_id": "source_registry_drift",
                "level": "watch",
                "scope": "registry",
                "reason": f"archived_source_count={payload.get('registry_drift_count')}",
                "recommended_action": "review_removed_sources_before_new_provider_rollout",
            }
        )

    warning_events = [event for event in events if event.status in WARNING_EVENT_STATUSES]
    if warning_events:
        level = _recent_source_event_level(warning_events)
        alerts.append(
            {
                "alert_id": "recent_source_health_events",
                "level": level,
                "scope": "source_health_events",
                "reason": "sources="
                + ",".join(sorted({event.source_id for event in warning_events})[:20]),
                "recommended_action": "inspect_recent_source_health_events",
            }
        )

    return alerts


def _recent_source_event_level(events: list[schema.SourceHealthEvent]) -> str:
    if any(event.status == "error" for event in events):
        return "critical"
    if any(_source_event_needs_warning(event) for event in events):
        return "warning"
    return "watch"


def _source_event_needs_warning(event: schema.SourceHealthEvent) -> bool:
    message = (event.message or "").lower()
    if event.status in {"stale", "expired", "missing"}:
        return True
    if any(
        token in message
        for token in (
            "collection_freshness=stale",
            "collection_freshness=expired",
            "collection_freshness=missing",
            "freshness_status=stale",
            "freshness_status=expired",
            "freshness_status=missing",
            "business_recency=lagging",
            "business_recency=outdated",
            "business_recency=provider_stale_suspect",
            "403",
            "forbidden",
            "unauthorized",
            "provider_locked",
        )
    ):
        return True
    return False


def _overall_status(
    snapshot: schema.DataQualitySnapshot | None,
    alerts: list[dict[str, Any]],
) -> str:
    levels = {str(alert.get("level")) for alert in alerts}
    if "critical" in levels:
        return "critical"
    if "warning" in levels:
        return "warning"
    if "watch" in levels:
        return "watch"
    if snapshot is None:
        return "warning"
    return "healthy" if snapshot.status == "healthy" else snapshot.status


def _snapshot_summary(
    snapshot: schema.DataQualitySnapshot | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if snapshot is None:
        return {
            "run_id": None,
            "score": None,
            "status": "missing",
            "source_count": 0,
            "freshness_counts": {},
            "business_recency_counts": {},
            "stale_sources": [],
            "business_lagging_sources": [],
            "missing_sources": [],
            "fallback_summary": {},
            "run_mode_summary": {},
        }
    return {
        "run_id": snapshot.run_id,
        "score": snapshot.score,
        "status": snapshot.status,
        "source_count": payload.get("source_count", 0),
        "freshness_counts": payload.get("freshness_counts") or {},
        "business_recency_counts": payload.get("business_recency_counts") or {},
        "stale_sources": payload.get("stale_sources") or [],
        "business_lagging_sources": payload.get("business_lagging_sources") or [],
        "missing_sources": payload.get("missing_sources") or [],
        "fallback_summary": payload.get("fallback_summary") or {},
        "run_mode_summary": payload.get("run_mode_summary") or {},
        "registry_drift_count": payload.get("registry_drift_count", 0),
    }


def _event_summary(event: schema.SourceHealthEvent) -> dict[str, Any]:
    return {
        "source_id": event.source_id,
        "status": event.status,
        "quality_score": event.quality_score,
        "latency_ms": event.latency_ms,
        "message": event.message,
        "created_at": event.created_at.isoformat(),
    }


def _source_registry_summary() -> dict[str, Any]:
    by_group: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    critical_sources: list[str] = []
    for source in SOURCE_CONFIGS:
        by_group[source.group_name] = by_group.get(source.group_name, 0) + 1
        by_kind[str(source.kind)] = by_kind.get(str(source.kind), 0) + 1
        if source.metadata.get("critical_source"):
            critical_sources.append(source.source_id)
    return {
        "configured_source_count": len(SOURCE_CONFIGS),
        "by_group": dict(sorted(by_group.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "metadata_critical_sources": sorted(critical_sources),
    }


def _downstream_policy(status: str) -> dict[str, Any]:
    if status == "critical":
        return {
            "dashboard_badge": "data_quality_critical",
            "participation_policy": "block_confirmed_signal",
            "publish_gate_recommendation": "block_production_publish",
        }
    if status == "warning":
        return {
            "dashboard_badge": "data_quality_warning",
            "participation_policy": "lower_sensitivity",
            "publish_gate_recommendation": "manual_review_before_publish",
        }
    if status == "watch":
        return {
            "dashboard_badge": "data_quality_watch",
            "participation_policy": "context_only_for_affected_sources",
            "publish_gate_recommendation": "surface_warning_without_auto_block",
        }
    return {
        "dashboard_badge": "data_quality_healthy",
        "participation_policy": "full",
        "publish_gate_recommendation": "no_additional_gate_from_source_health",
    }
