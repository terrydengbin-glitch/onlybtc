from __future__ import annotations

from typing import Any

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p6.outcome_tracking import outcome_tracking
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID

P6_MODULE_EFFECTIVENESS_SCHEMA_VERSION = "p6.module_effectiveness.v1"


def module_effectiveness(
    *,
    article_snapshot_id: str | None = None,
    limit: int = 50,
    run_mode: str = "live",
    db: Database = database,
) -> dict[str, Any]:
    outcomes = outcome_tracking(
        article_snapshot_id=article_snapshot_id,
        limit=limit,
        run_mode=run_mode,
        db=db,
    )
    module_stats: dict[str, dict[str, Any]] = {}
    sample_count = 0
    gap_count = 0
    for item in outcomes.get("items") or []:
        if not isinstance(item, dict):
            continue
        final_payload = _payload_by_run(
            P45_FINAL_ARTICLE_MODULE_ID,
            str(item.get("final_run_id") or ""),
            db=db,
        )
        if not final_payload:
            gap_count += 1
            continue
        modules = _radar_modules(final_payload)
        observed = _observed_horizons(item)
        if not observed:
            gap_count += 1
        sample_count += 1
        for module in modules:
            module_id = _module_id(module)
            if not module_id:
                continue
            stats = module_stats.setdefault(module_id, _empty_stats(module_id))
            _accumulate_module(stats, module, observed)

    modules = [_finalize_stats(stats) for stats in sorted(module_stats.values(), key=lambda x: x["module_id"])]
    return {
        "schema_version": P6_MODULE_EFFECTIVENESS_SCHEMA_VERSION,
        "status": _overall_status(modules, sample_count),
        "summary": {
            "sample_count": sample_count,
            "module_count": len(modules),
            "observed_module_count": sum(1 for item in modules if item["observed_count"] > 0),
            "gap_count": gap_count,
            "scoring_policy": "historical_observability_only_no_weight_mutation",
        },
        "modules": modules,
        "count": len(modules),
        "run_mode": run_mode,
        "read_only": True,
        "mutates_module_weights": False,
        "trading_advice": False,
    }


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


def _radar_modules(final_payload: dict[str, Any]) -> list[dict[str, Any]]:
    modules = final_payload.get("radar_module_scores")
    if not isinstance(modules, list):
        return []
    return [dict(item) for item in modules if isinstance(item, dict)]


def _observed_horizons(item: dict[str, Any]) -> list[dict[str, Any]]:
    horizons = item.get("horizons") or {}
    if not isinstance(horizons, dict):
        return []
    return [
        {**value, "horizon": key}
        for key, value in horizons.items()
        if isinstance(value, dict) and value.get("status") == "observed"
    ]


def _module_id(module: dict[str, Any]) -> str:
    return str(
        module.get("radar_module")
        or module.get("module_id")
        or module.get("id")
        or ""
    )


def _empty_stats(module_id: str) -> dict[str, Any]:
    return {
        "module_id": module_id,
        "observed_count": 0,
        "aligned_count": 0,
        "miss_count": 0,
        "neutral_count": 0,
        "unknown_direction_count": 0,
        "horizon_results": [],
    }


def _accumulate_module(
    stats: dict[str, Any],
    module: dict[str, Any],
    observed: list[dict[str, Any]],
) -> None:
    module_direction = _module_direction(module)
    for horizon in observed:
        return_pct = horizon.get("return_pct")
        outcome_direction = _return_direction(return_pct)
        alignment = _module_alignment(module_direction, outcome_direction)
        stats["observed_count"] += 1
        if alignment == "aligned":
            stats["aligned_count"] += 1
        elif alignment == "neutral":
            stats["neutral_count"] += 1
        elif alignment == "unknown":
            stats["unknown_direction_count"] += 1
        else:
            stats["miss_count"] += 1
        stats["horizon_results"].append(
            {
                "horizon": horizon.get("horizon"),
                "return_pct": return_pct,
                "module_direction": module_direction,
                "outcome_direction": outcome_direction,
                "alignment": alignment,
            }
        )


def _finalize_stats(stats: dict[str, Any]) -> dict[str, Any]:
    observed_count = int(stats["observed_count"])
    aligned_count = int(stats["aligned_count"])
    scored_count = observed_count - int(stats["unknown_direction_count"])
    effectiveness_score = round(aligned_count / scored_count, 4) if scored_count > 0 else None
    noise_score = round(1.0 - effectiveness_score, 4) if effectiveness_score is not None else None
    status = _module_status(effectiveness_score, observed_count)
    return {
        **stats,
        "scored_count": scored_count,
        "effectiveness_score": effectiveness_score,
        "noise_score": noise_score,
        "status": status,
    }


def _module_direction(module: dict[str, Any]) -> str:
    raw = str(
        module.get("module_direction")
        or module.get("module_effective_direction")
        or module.get("direction")
        or ""
    ).lower()
    if any(token in raw for token in ("bull", "support", "positive", "up")):
        return "bullish"
    if any(token in raw for token in ("bear", "pressure", "negative", "down")):
        return "bearish"
    score = _float_or_none(
        module.get("module_effective_score")
        if module.get("module_effective_score") is not None
        else module.get("module_score")
    )
    if score is None:
        return "unknown"
    if score > 0.05:
        return "bullish"
    if score < -0.05:
        return "bearish"
    return "neutral"


def _return_direction(value: Any) -> str:
    return_pct = _float_or_none(value)
    if return_pct is None:
        return "unknown"
    if return_pct > 0.02:
        return "bullish"
    if return_pct < -0.02:
        return "bearish"
    return "neutral"


def _module_alignment(module_direction: str, outcome_direction: str) -> str:
    if "unknown" in {module_direction, outcome_direction}:
        return "unknown"
    if module_direction == "neutral" or outcome_direction == "neutral":
        return "neutral" if module_direction == outcome_direction else "not_aligned"
    return "aligned" if module_direction == outcome_direction else "not_aligned"


def _module_status(effectiveness_score: float | None, observed_count: int) -> str:
    if observed_count <= 0 or effectiveness_score is None:
        return "insufficient"
    if effectiveness_score >= 0.6:
        return "effective"
    if effectiveness_score >= 0.4:
        return "mixed"
    return "noisy"


def _overall_status(modules: list[dict[str, Any]], sample_count: int) -> str:
    if sample_count <= 0 or not modules:
        return "empty"
    statuses = {str(item.get("status") or "") for item in modules}
    if statuses == {"insufficient"}:
        return "insufficient"
    if "noisy" in statuses:
        return "warning"
    return "ok"


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
