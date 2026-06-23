from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from onlybtc.db import schema
from onlybtc.db.session import Database, database

P6_ALERT_HISTORY_SCHEMA_VERSION = "p6.alert_history.v1"
P6_ALERT_QUALITY_SCHEMA_VERSION = "p6.alert_quality.v1"


def alert_history(
    limit: int = 100,
    alert_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    alerts, event_counts = _alert_rows(limit=limit, alert_id=alert_id, db=db)
    items = [_history_item(row, event_counts.get(row.alert_id, 0)) for row in alerts]
    return {
        "schema_version": P6_ALERT_HISTORY_SCHEMA_VERSION,
        "status": "ok" if items else "empty",
        "items": items,
        "count": len(items),
        "history_mode": {
            "anchor": "alert_id",
            "read_only": True,
            "historical_payload_frozen": True,
            "uses_latest_runtime_state": False,
        },
    }


def alert_quality(
    limit: int = 100,
    alert_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    alerts, event_counts = _alert_rows(limit=limit, alert_id=alert_id, db=db)
    items = [
        _quality_item(row, event_counts.get(row.alert_id, 0))
        for row in alerts
    ]
    scores = [float(item["quality_score"]) for item in items]
    average_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    issue_count = sum(int(item["issue_count"]) for item in items)
    return {
        "schema_version": P6_ALERT_QUALITY_SCHEMA_VERSION,
        "status": _overall_status(items),
        "summary": {
            "alert_count": len(items),
            "alert_id": alert_id,
            "average_quality_score": average_score,
            "issue_count": issue_count,
            "scoring_policy": "observability_only_no_alert_mutation",
        },
        "items": items,
        "count": len(items),
        "read_only": True,
        "mutates_alert_state": False,
    }


def _alert_rows(
    *,
    limit: int,
    alert_id: str | None,
    db: Database,
) -> tuple[list[schema.AlgorithmAlert], dict[str, int]]:
    db.init_schema()
    bounded_limit = max(1, min(limit, 500))
    with db.session() as session:
        query = select(schema.AlgorithmAlert)
        if alert_id:
            query = query.where(schema.AlgorithmAlert.alert_id == alert_id)
        alerts = session.scalars(
            query.order_by(
                schema.AlgorithmAlert.updated_at.desc(),
                schema.AlgorithmAlert.id.desc(),
            ).limit(bounded_limit)
        ).all()
        alert_ids = [row.alert_id for row in alerts]
        event_counts: dict[str, int] = {}
        if alert_ids:
            rows = session.execute(
                select(schema.AlertEvent.alert_id, func.count())
                .where(schema.AlertEvent.alert_id.in_(alert_ids))
                .group_by(schema.AlertEvent.alert_id)
            ).all()
            event_counts = {str(alert_id): int(count or 0) for alert_id, count in rows}
    return list(alerts), event_counts


def _history_item(row: schema.AlgorithmAlert, event_count: int) -> dict[str, Any]:
    return {
        "alert_id": row.alert_id,
        "run_id": row.run_id,
        "level": row.level,
        "state": row.state,
        "title": row.title,
        "summary": row.summary,
        "evidence_count": int(row.evidence_count or 0),
        "event_count": int(event_count),
        "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "quality_url": f"/api/p6/alerts/quality?alert_id={row.alert_id}",
    }


def _quality_item(row: schema.AlgorithmAlert, event_count: int) -> dict[str, Any]:
    checks = {
        "has_level": bool(row.level),
        "has_state": bool(row.state),
        "has_title": bool(str(row.title or "").strip()),
        "has_summary": bool(str(row.summary or "").strip()),
        "has_evidence": int(row.evidence_count or 0) > 0,
        "has_lifecycle_event": event_count > 0,
    }
    passed = sum(1 for value in checks.values() if value)
    quality_score = round(passed / len(checks), 4)
    issues = [name for name, value in checks.items() if not value]
    return {
        "alert_id": row.alert_id,
        "run_id": row.run_id,
        "level": row.level,
        "state": row.state,
        "quality_score": quality_score,
        "status": _item_status(quality_score),
        "checks": checks,
        "issue_count": len(issues),
        "issues": issues,
        "event_count": int(event_count),
        "evidence_count": int(row.evidence_count or 0),
    }


def _item_status(score: float) -> str:
    if score >= 0.999:
        return "passed"
    if score >= 0.66:
        return "warning"
    return "failed"


def _overall_status(items: list[dict[str, Any]]) -> str:
    if not items:
        return "empty"
    statuses = {str(item.get("status") or "") for item in items}
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    return "passed"
