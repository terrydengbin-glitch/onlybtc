from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.core.config import Settings, get_settings
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database

SCHEMA_VERSION = "p7.c06.cost_control_cache_rate_limit.v1"
SENSITIVE_KEY_HINTS = ("api_key", "token", "authorization", "secret", "password")


def build_cost_control_report(
    db: Database = database,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    cache_dir: Path | None = None,
    recent_hours: int = 24,
) -> dict[str, Any]:
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    cache_path = cache_dir or paths.cache_dir
    db.init_schema()
    with db.session() as session:
        rate_limit_events = _recent_rate_limit_events(session, now=now, recent_hours=recent_hours)
        fallback_summary = _fallback_summary(session)
    config = _config_summary(settings)
    cache = _cache_summary(cache_path)
    alerts = _alerts(config, cache, rate_limit_events, fallback_summary)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "applied_to_production": False,
        "overall_status": _overall_status(alerts),
        "alert_count": len(alerts),
        "alerts": alerts,
        "config": config,
        "cache": cache,
        "recent_event_window_hours": recent_hours,
        "recent_rate_limit_events": rate_limit_events,
        "fallback_summary": fallback_summary,
        "downstream_policy": _downstream_policy(alerts),
        "guardrails": [
            "audit_only",
            "does_not_modify_runtime_settings",
            "does_not_call_external_providers",
            "does_not_cache_secrets",
            "does_not_modify_state_machine",
            "does_not_emit_trading_advice",
            "requires_p7_c08_before_production_apply",
        ],
    }


def _config_summary(settings: Settings) -> dict[str, Any]:
    return {
        "source_collection": {
            "timeout_seconds": settings.source_timeout_seconds,
            "http_concurrency": settings.source_http_concurrency,
            "playwright_concurrency": settings.source_playwright_concurrency,
            "official_concurrency": settings.source_official_concurrency,
            "fred_concurrency": settings.source_fred_concurrency,
            "source_max_retries": settings.source_max_retries,
            "source_retry_backoff_seconds": settings.source_retry_backoff_seconds,
            "source_failure_gate_threshold": settings.source_failure_gate_threshold,
            "source_min_current_metrics": settings.source_min_current_metrics,
        },
        "fred_throttle": {
            "batch_size": settings.source_fred_batch_size,
            "inter_batch_delay_ms": settings.source_fred_inter_batch_delay_ms,
            "per_request_jitter_ms": settings.source_fred_per_request_jitter_ms,
            "api_max_attempts": settings.source_fred_api_max_attempts,
            "api_backoff_seconds": settings.source_fred_api_backoff_seconds,
        },
        "p4_llm_budget": {
            "timeout_seconds": settings.p4_llm_timeout_seconds,
            "max_retries": settings.p4_llm_max_retries,
            "max_calls_per_run": settings.p4_llm_max_calls_per_run,
            "max_estimated_tokens_per_run": settings.p4_llm_max_estimated_tokens_per_run,
            "fallback_policy": settings.p4_llm_fallback_policy,
            "has_explicit_call_budget": settings.p4_llm_max_calls_per_run > 0,
            "has_explicit_token_budget": settings.p4_llm_max_estimated_tokens_per_run > 0,
        },
        "p45_research_budget": {
            "provider": settings.p45_research_provider,
            "timeout_seconds": settings.p45_research_timeout_seconds,
            "max_retries": settings.p45_research_max_retries,
            "has_explicit_call_budget": False,
            "has_explicit_token_budget": False,
        },
    }


def _cache_summary(cache_dir: Path) -> dict[str, Any]:
    if not cache_dir.exists():
        return {
            "path": str(cache_dir),
            "exists": False,
            "file_count": 0,
            "total_bytes": 0,
            "largest_files": [],
        }
    files = [path for path in cache_dir.rglob("*") if path.is_file()]
    sizes = [(path, path.stat().st_size) for path in files]
    largest = sorted(sizes, key=lambda item: item[1], reverse=True)[:10]
    return {
        "path": str(cache_dir),
        "exists": True,
        "file_count": len(files),
        "total_bytes": sum(size for _, size in sizes),
        "largest_files": [
            {"path": str(path.relative_to(cache_dir)), "bytes": size}
            for path, size in largest
        ],
    }


def _recent_rate_limit_events(
    session,
    *,
    now: datetime,
    recent_hours: int,
) -> list[dict[str, Any]]:
    cutoff = now - timedelta(hours=recent_hours)
    rows = session.scalars(
        select(schema.RateLimitEvent)
        .where(schema.RateLimitEvent.created_at >= cutoff)
        .order_by(schema.RateLimitEvent.created_at.desc(), schema.RateLimitEvent.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "source_id": row.source_id,
            "current": row.current,
            "limit": row.limit,
            "reset_at": row.reset_at.isoformat() if row.reset_at else None,
            "created_at": row.created_at.isoformat(),
            "utilization": round(row.current / row.limit, 6) if row.limit else None,
        }
        for row in rows
    ]


def _fallback_summary(session) -> dict[str, Any]:
    count = session.scalar(select(func.count()).select_from(schema.FallbackEvent)) or 0
    rows = session.scalars(
        select(schema.FallbackEvent)
        .order_by(schema.FallbackEvent.created_at.desc(), schema.FallbackEvent.id.desc())
        .limit(50)
    ).all()
    return {
        "fallback_event_count": int(count),
        "recent_events": [
            {
                "source_id": row.source_id,
                "fallback_source_id": row.fallback_source_id,
                "reason": row.reason,
                "discount": row.discount,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


def _alerts(
    config: dict[str, Any],
    cache: dict[str, Any],
    rate_limit_events: list[dict[str, Any]],
    fallback_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    source = config["source_collection"]
    fred = config["fred_throttle"]
    p4 = config["p4_llm_budget"]
    p45 = config["p45_research_budget"]

    if source["source_max_retries"] < 1 or source["source_retry_backoff_seconds"] <= 0:
        alerts.append(
            {
                "alert_id": "source_retry_policy_weak",
                "level": "warning",
                "scope": "source_collection",
                "reason": "source retry or backoff disabled",
                "recommended_action": "keep_retry_backoff_enabled_for_transient_provider_failures",
            }
        )
    if source["playwright_concurrency"] > 1:
        alerts.append(
            {
                "alert_id": "playwright_concurrency_above_singleton",
                "level": "watch",
                "scope": "source_collection",
                "reason": f"playwright_concurrency={source['playwright_concurrency']}",
                "recommended_action": "verify_provider_limits_before_parallel_browser_runs",
            }
        )
    if fred["inter_batch_delay_ms"] <= 0 or fred["per_request_jitter_ms"] <= 0:
        alerts.append(
            {
                "alert_id": "fred_throttle_jitter_missing",
                "level": "watch",
                "scope": "fred_throttle",
                "reason": "FRED inter-batch delay or per-request jitter is zero",
                "recommended_action": "keep_jitter_for_polite_provider_usage",
            }
        )
    if not p4["has_explicit_call_budget"] or not p4["has_explicit_token_budget"]:
        alerts.append(
            {
                "alert_id": "p4_llm_budget_missing",
                "level": "critical",
                "scope": "llm_budget",
                "reason": "P4 LLM call/token budget missing",
                "recommended_action": "restore_p4_llm_budget_before_real_llm_runtime",
            }
        )
    if not p45["has_explicit_call_budget"] or not p45["has_explicit_token_budget"]:
        alerts.append(
            {
                "alert_id": "p45_research_budget_gap",
                "level": "warning",
                "scope": "llm_budget",
                "reason": "P4.5 research writer has timeout/retry but no explicit call/token budget",
                "recommended_action": "add_p45_call_and_token_budget_before_production_llm_expansion",
            }
        )
    if not cache["exists"]:
        alerts.append(
            {
                "alert_id": "cache_dir_missing",
                "level": "watch",
                "scope": "cache",
                "reason": cache["path"],
                "recommended_action": "create_cache_dir_or_call_paths_ensure_directories",
            }
        )
    if cache["total_bytes"] > 512 * 1024 * 1024:
        alerts.append(
            {
                "alert_id": "cache_size_high",
                "level": "watch",
                "scope": "cache",
                "reason": f"cache_total_bytes={cache['total_bytes']}",
                "recommended_action": "review_cache_ttl_and_cleanup_policy",
            }
        )
    over_limit = [event for event in rate_limit_events if event["limit"] and event["current"] >= event["limit"]]
    if over_limit:
        alerts.append(
            {
                "alert_id": "recent_rate_limit_saturation",
                "level": "warning",
                "scope": "rate_limit",
                "reason": ",".join(sorted({event["source_id"] for event in over_limit})[:20]),
                "recommended_action": "respect_reset_at_and_backoff_before_retrying",
            }
        )
    if fallback_summary["fallback_event_count"]:
        alerts.append(
            {
                "alert_id": "fallback_events_present",
                "level": "watch",
                "scope": "fallback",
                "reason": f"fallback_event_count={fallback_summary['fallback_event_count']}",
                "recommended_action": "audit_fallback_cost_and_quality_discount",
            }
        )
    return alerts


def _overall_status(alerts: list[dict[str, Any]]) -> str:
    levels = {alert["level"] for alert in alerts}
    if "critical" in levels:
        return "critical"
    if "warning" in levels:
        return "warning"
    if "watch" in levels:
        return "watch"
    return "healthy"


def _downstream_policy(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    alert_ids = {alert["alert_id"] for alert in alerts}
    return {
        "llm_runtime_policy": (
            "block_p4_real_llm" if "p4_llm_budget_missing" in alert_ids else "budget_guarded"
        ),
        "p45_research_policy": (
            "manual_review_before_expansion"
            if "p45_research_budget_gap" in alert_ids
            else "budget_guarded"
        ),
        "source_retry_policy": (
            "backoff_required"
            if "recent_rate_limit_saturation" in alert_ids
            else "normal_retry_policy"
        ),
        "cache_policy": "review_ttl" if "cache_size_high" in alert_ids else "normal",
    }
