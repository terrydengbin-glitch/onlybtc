from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p6.article_pipeline import P6_AUTO_ARTICLE_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID

P6_OUTCOME_TRACKING_SCHEMA_VERSION = "p6.outcome_tracking.v1"

HORIZONS: tuple[tuple[str, int], ...] = (
    ("24h", 24),
    ("72h", 72),
    ("7d", 168),
)
PRICE_METRIC_IDS = ("btc_price", "btc_close", "btc_spot_price")


def outcome_tracking(
    *,
    article_snapshot_id: str | None = None,
    limit: int = 50,
    run_mode: str = "live",
    db: Database = database,
) -> dict[str, Any]:
    snapshots = _article_snapshots(
        article_snapshot_id=article_snapshot_id,
        limit=limit,
        db=db,
    )
    items = [
        _tracking_item(row, run_mode=run_mode, db=db)
        for row in snapshots
    ]
    return {
        "schema_version": P6_OUTCOME_TRACKING_SCHEMA_VERSION,
        "status": "ok" if items else "empty",
        "items": items,
        "count": len(items),
        "run_mode": run_mode,
        "tracking_policy": {
            "anchor": "article_snapshot_id",
            "price_metric_ids": list(PRICE_METRIC_IDS),
            "horizons": [name for name, _hours in HORIZONS],
            "read_only": True,
            "mutates_final_view": False,
            "trading_advice": False,
        },
    }


def _article_snapshots(
    *,
    article_snapshot_id: str | None,
    limit: int,
    db: Database,
) -> list[schema.ModuleJsonOutput]:
    db.init_schema()
    with db.session() as session:
        query = select(schema.ModuleJsonOutput).where(
            schema.ModuleJsonOutput.module_id == P6_AUTO_ARTICLE_MODULE_ID
        )
        if article_snapshot_id:
            query = query.where(schema.ModuleJsonOutput.run_id == article_snapshot_id)
        return list(
            session.scalars(
                query.order_by(
                    schema.ModuleJsonOutput.created_at.desc(),
                    schema.ModuleJsonOutput.id.desc(),
                ).limit(max(1, min(limit, 200)))
            ).all()
        )


def _tracking_item(
    row: schema.ModuleJsonOutput,
    *,
    run_mode: str,
    db: Database,
) -> dict[str, Any]:
    snapshot = dict(row.payload or {})
    article_snapshot_id = str(snapshot.get("article_snapshot_id") or row.run_id)
    final_run_id = str(snapshot.get("final_run_id") or "")
    final_payload = _payload_by_run(P45_FINAL_ARTICLE_MODULE_ID, final_run_id, db=db) or {}
    anchor_at = _parse_datetime(snapshot.get("created_at")) or row.created_at
    if anchor_at.tzinfo is None:
        anchor_at = anchor_at.replace(tzinfo=UTC)
    anchor_price = _price_at_or_before(anchor_at, run_mode=run_mode, db=db)
    final_view = str(final_payload.get("final_view") or snapshot.get("final_view") or "unknown")
    horizons = {
        name: _horizon_result(
            name=name,
            anchor_at=anchor_at,
            hours=hours,
            anchor_price=anchor_price,
            final_view=final_view,
            run_mode=run_mode,
            db=db,
        )
        for name, hours in HORIZONS
    }
    return {
        "article_snapshot_id": article_snapshot_id,
        "final_run_id": final_run_id or None,
        "pack_id": snapshot.get("pack_id") or final_payload.get("pack_id"),
        "created_at": anchor_at.isoformat(),
        "final_view": final_view,
        "final_view_cn": final_payload.get("final_view_cn"),
        "anchor_price": _price_payload(anchor_price),
        "horizons": horizons,
        "read_only": True,
        "trading_advice": False,
    }


def _horizon_result(
    *,
    name: str,
    anchor_at: datetime,
    hours: int,
    anchor_price: schema.MetricValue | None,
    final_view: str,
    run_mode: str,
    db: Database,
) -> dict[str, Any]:
    target_at = anchor_at + timedelta(hours=hours)
    if anchor_price is None:
        return {
            "horizon": name,
            "status": "missing_anchor",
            "target_at": target_at.isoformat(),
            "target_price": None,
            "return_pct": None,
            "directional_alignment": "unknown",
        }
    if datetime.now(UTC) < target_at:
        return {
            "horizon": name,
            "status": "pending",
            "target_at": target_at.isoformat(),
            "target_price": None,
            "return_pct": None,
            "directional_alignment": "pending",
        }
    target_price = _price_at_or_after(target_at, run_mode=run_mode, db=db)
    if target_price is None:
        return {
            "horizon": name,
            "status": "missing_target",
            "target_at": target_at.isoformat(),
            "target_price": None,
            "return_pct": None,
            "directional_alignment": "unknown",
        }
    return_pct = _return_pct(anchor_price.value, target_price.value)
    return {
        "horizon": name,
        "status": "observed",
        "target_at": target_at.isoformat(),
        "target_price": _price_payload(target_price),
        "return_pct": return_pct,
        "directional_alignment": _directional_alignment(final_view, return_pct),
    }


def _price_at_or_before(
    ts: datetime,
    *,
    run_mode: str,
    db: Database,
) -> schema.MetricValue | None:
    return _price_row(ts=ts, before=True, run_mode=run_mode, db=db)


def _price_at_or_after(
    ts: datetime,
    *,
    run_mode: str,
    db: Database,
) -> schema.MetricValue | None:
    return _price_row(ts=ts, before=False, run_mode=run_mode, db=db)


def _price_row(
    *,
    ts: datetime,
    before: bool,
    run_mode: str,
    db: Database,
) -> schema.MetricValue | None:
    db.init_schema()
    with db.session() as session:
        query = select(schema.MetricValue).where(
            schema.MetricValue.metric_id.in_(PRICE_METRIC_IDS)
        )
        if before:
            query = query.where(schema.MetricValue.ts <= ts).order_by(
                schema.MetricValue.ts.desc(),
                schema.MetricValue.id.desc(),
            )
        else:
            query = query.where(schema.MetricValue.ts >= ts).order_by(
                schema.MetricValue.ts.asc(),
                schema.MetricValue.id.asc(),
            )
        if run_mode != "all":
            query = query.where(schema.MetricValue.run_mode == run_mode)
        return session.scalar(query.limit(1))


def _payload_by_run(module_id: str, run_id: str, db: Database) -> dict[str, Any] | None:
    if not run_id:
        return None
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(
                schema.ModuleJsonOutput.module_id == module_id,
                schema.ModuleJsonOutput.run_id == run_id,
            )
            .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
            .limit(1)
        )
        return dict(row.payload or {}) if row else None


def _price_payload(row: schema.MetricValue | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "metric_id": row.metric_id,
        "source_id": row.source_id,
        "run_id": row.run_id,
        "run_mode": row.run_mode,
        "ts": row.ts.isoformat() if row.ts else None,
        "value": row.value,
        "quality_score": row.quality_score,
    }


def _return_pct(anchor_value: float, target_value: float) -> float | None:
    if not anchor_value:
        return None
    return round((target_value - anchor_value) / abs(anchor_value), 6)


def _directional_alignment(final_view: str, return_pct: float | None) -> str:
    if return_pct is None:
        return "unknown"
    view = final_view.lower()
    neutral_band = 0.02
    if "bull" in view or "support" in view:
        return "aligned" if return_pct > 0 else "not_aligned"
    if "bear" in view or "pressure" in view:
        return "aligned" if return_pct < 0 else "not_aligned"
    if abs(return_pct) <= neutral_band:
        return "neutral_observed"
    return "moved_after_neutral_view"


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
