from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from onlybtc.event_window.connectors.actuals import collect_actual_snapshot
from onlybtc.event_window.connectors.expectations import collect_expectation_snapshot
from onlybtc.event_window.connectors.market_probe import collect_market_probe
from onlybtc.event_window.connectors.official_calendar import collect_official_calendar
from onlybtc.event_window.connectors.reactions import build_post_event_reaction
from onlybtc.event_window.connectors.shock_lane import collect_shock_fast_lane
from onlybtc.event_window.provider_confidence import build_provider_confidence
from onlybtc.event_window.speech_analyzer import analyze_fed_texts

EVENT_WINDOW_SCHEMA_VERSION = "p45.event_window.v3"
EVENT_WINDOW_RUNTIME_VERSION = "event_watchtower.v3.2.market-shock"

OFFICIAL_SOURCE_LINEAGE = [
    {
        "source_id": "fed-fomc-calendar",
        "source_tier": "official",
        "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "role": "FOMC calendar, statements, minutes and SEP lineage",
    },
    {
        "source_id": "fed-rss",
        "source_tier": "official",
        "url": "https://www.federalreserve.gov/feeds/feeds.htm",
        "role": "Fed speeches, testimony, press releases and statistics RSS lineage",
    },
    {
        "source_id": "bls-release-calendar",
        "source_tier": "official",
        "url": "https://www.bls.gov/schedule/",
        "role": "CPI, PPI, NFP, JOLTS and ECI official release calendar",
    },
    {
        "source_id": "fred-release-dates",
        "source_tier": "official_mirror",
        "url": "https://api.stlouisfed.org/fred/release/dates",
        "role": "BLS release-date mirror when official BLS calendar access is blocked",
    },
    {
        "source_id": "bea-api",
        "source_tier": "official",
        "url": "https://apps.bea.gov/api/",
        "role": "PCE, GDP and Personal Income and Outlays official data lineage",
    },
    {
        "source_id": "cleveland-fed-nowcast",
        "source_tier": "expectation",
        "url": "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting",
        "role": "CPI/PCE inflation nowcast expectation drift",
    },
    {
        "source_id": "cme-fedwatch",
        "source_tier": "market_implied",
        "url": "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
        "role": "Fed funds futures implied policy path",
    },
    {
        "source_id": "fxstreet-calendar",
        "source_tier": "secondary_consensus",
        "url": "https://www.fxstreet.com/economic-calendar",
        "role": "Secondary economic calendar and consensus cross-check",
    },
    {
        "source_id": "kalshi-public-markets",
        "source_tier": "prediction_market",
        "url": "https://external-api.kalshi.com/trade-api/v2/",
        "role": "Prediction market odds for policy and inflation risk repricing",
    },
    {
        "source_id": "polymarket-public-events",
        "source_tier": "prediction_market",
        "url": "https://gamma-api.polymarket.com/events",
        "role": "Prediction market cross-check for policy and inflation risk repricing",
    },
    {
        "source_id": "atlanta-fed-mpt",
        "source_tier": "fed_research_tool",
        "url": "https://www.atlantafed.org/cenfis/market-probability-tracker",
        "role": "Fed research tool for market-implied rate range probabilities",
    },
]


def build_event_window_payload(
    *,
    now: datetime | None = None,
    daemon_status: str = "running",
    daemon_enabled: bool = True,
    shock_items: list[dict[str, Any]] | None = None,
    official_text_items: list[dict[str, Any]] | None = None,
    llm_analyses: list[dict[str, Any]] | None = None,
    due_source_groups: list[str] | None = None,
    previous_payload: dict[str, Any] | None = None,
    trigger: str = "manual_collect_once",
) -> dict[str, Any]:
    asof = _ensure_utc(now or datetime.now(UTC))
    previous = deepcopy(previous_payload or {})
    full_sweep = due_source_groups is None
    due_groups = set(due_source_groups or [])
    source_fetches: list[dict[str, Any]] = []
    if full_sweep or "official_calendar" in due_groups:
        official_result = collect_official_calendar(asof)
        source_fetches.extend(official_result.get("source_fetches") or [])
        calendar = list(official_result.get("calendar_items") or [])
        texts = official_text_items or list(official_result.get("official_text_items") or [])
    else:
        calendar = deepcopy(previous.get("calendar_items") or [])
        texts = official_text_items or deepcopy(previous.get("official_text_items") or [])
        source_fetches.append(_scheduler_skip_fetch("official_calendar", asof, previous, "calendar_items"))
        source_fetches.append(_scheduler_skip_fetch("fed_rss_official_text", asof, previous, "official_text_items"))
    expectation_snapshot: dict[str, Any] = {}
    if not calendar:
        calendar = _fallback_calendar(asof)
        source_fetches.append(_fallback_fetch("embedded-official-calendar", asof, len(calendar)))
    active_event = _select_active_event(calendar, asof)
    expectations = []
    if active_event:
        if full_sweep or due_groups & {"expectation_nowcast", "consensus_proxy", "rate_probability"}:
            expectation_result = collect_expectation_snapshot(active_event, asof)
            expectation_snapshot = expectation_result.get("snapshot") or {}
            source_fetches.extend(expectation_result.get("source_fetches") or [])
        else:
            expectation_snapshot = deepcopy(previous.get("expectation_monitor") or {})
            source_fetches.append(
                _scheduler_skip_fetch("expectation_nowcast", asof, previous, "expectation_monitor")
            )
            source_fetches.append(
                _scheduler_skip_fetch("consensus_proxy", asof, previous, "expectation_monitor")
            )
            source_fetches.append(
                _scheduler_skip_fetch("rate_probability", asof, previous, "expectation_monitor")
            )
        active_event["expectation"] = expectation_snapshot
        expectations = [expectation_snapshot]
    if not texts:
        texts = _default_official_text_items(asof)
        source_fetches.append(_fallback_fetch("embedded-fed-rss-placeholder", asof, len(texts)))
    if full_sweep or due_groups & {"btc_reaction", "shock_fast_lane"}:
        market_probe = collect_market_probe(asof)
        source_fetches.extend(_source_fetches_from_market_probe(market_probe))
    else:
        market_probe = deepcopy(previous.get("market_probe") or {})
        source_fetches.append(_scheduler_skip_fetch("btc_reaction", asof, previous, "market_probe"))
    market_probes = [market_probe] if market_probe else []
    if shock_items is not None:
        shocks = shock_items
    elif full_sweep or "shock_fast_lane" in due_groups:
        shock_result = collect_shock_fast_lane(
            asof,
            official_text_items=texts,
            market_probe=market_probe,
        )
        shocks = list(shock_result.get("shock_items") or [])
        source_fetches.extend(shock_result.get("source_fetches") or [])
    else:
        shocks = deepcopy(previous.get("shock_lane_items") or [])
        source_fetches.append(_scheduler_skip_fetch("shock_fast_lane", asof, previous, "shock_lane_items"))
    if llm_analyses is not None:
        analyses = llm_analyses
    elif full_sweep or "llm_speech_analyzer" in due_groups:
        analyses = analyze_fed_texts(texts, asof, use_deepseek=False)
    else:
        analyses = deepcopy(previous.get("llm_analyses") or [])
        source_fetches.append(_scheduler_skip_fetch("llm_speech_analyzer", asof, previous, "llm_analyses"))
    data_quality = _data_quality(calendar, active_event, daemon_enabled, source_fetches)
    state = _state_from_inputs(
        asof,
        active_event,
        shocks,
        daemon_enabled,
        daemon_status,
        data_quality,
    )
    overlay = _overlay_from_state(state)
    actual_snapshot = None
    if active_event and _parse_ts(active_event["release_time"]) <= asof:
        if full_sweep or "actual_polling" in due_groups:
            actual_result = collect_actual_snapshot(active_event, asof)
            actual_snapshot = actual_result.get("actual_snapshot") or {}
            active_event["actual_snapshot"] = actual_snapshot
            source_fetches.extend(actual_result.get("source_fetches") or [])
        else:
            actual_snapshot = deepcopy(previous.get("actual_monitor") or {})
            if actual_snapshot:
                active_event["actual_snapshot"] = actual_snapshot
            source_fetches.append(_scheduler_skip_fetch("actual_polling", asof, previous, "actual_monitor"))
    provider_confidence = build_provider_confidence(
        active_event,
        source_fetches,
        expectation_snapshot,
    )
    data_quality["provider_confidence"] = provider_confidence
    data_quality["disabled_capabilities"] = sorted(
        set(data_quality.get("disabled_capabilities") or [])
        | set(provider_confidence.get("disabled_capabilities") or [])
    )
    if not active_event:
        reaction = None
    elif full_sweep or due_groups & {"btc_reaction", "actual_polling"}:
        reaction = build_post_event_reaction(active_event, asof)
    else:
        reaction = deepcopy(previous.get("post_event_reaction") or {}) or None
        source_fetches.append(
            _scheduler_skip_fetch("post_event_reaction", asof, previous, "post_event_reaction")
        )
    alert = _alert_from_state(state, active_event, asof)
    payload = {
        "schema_version": EVENT_WINDOW_SCHEMA_VERSION,
        "asof_ts": asof.isoformat(),
        "module_name": "event_window_policy_shock_watchtower",
        "direct_score_impact": False,
        "daemon": {
            "status": daemon_status,
            "enabled": daemon_enabled,
            "collection_mode": "standalone_daemon",
            "runtime_code_version": EVENT_WINDOW_RUNTIME_VERSION,
            "status_schema_version": "p9.event_watchtower.status.v2",
            "last_market_probe_at": market_probe.get("collected_at"),
            "trigger": trigger,
            "due_source_groups": sorted(due_groups),
            "scheduler_due_gate": {
                "mode": "full_sweep" if full_sweep else "due_only",
                "due_source_groups": sorted(due_groups),
                "skipped_source_groups": _skipped_groups(due_groups) if not full_sweep else [],
            },
            "cadence": {
                "official_calendar_sec": 3600,
                "expectation_normal_sec": 3600,
                "expectation_hot_window_sec": 600,
                "official_rss_sec": 60,
                "shock_fast_lane_sec": 15,
                "btc_reaction_sec": 5,
            },
        },
        "state": state,
        "overlay": overlay,
        "active_event": active_event or {},
        "expectation_monitor": expectations[0] if expectations else _empty_expectation(),
        "actual_monitor": actual_snapshot or {},
        "fed_speech_monitor": _speech_monitor(analyses),
        "market_probe": market_probe,
        "market_probes": market_probes,
        "shock_fast_lane": _shock_fast_lane(shocks),
        "post_event_reaction": reaction or _empty_reaction(),
        "data_quality": data_quality,
        "calendar_items": calendar,
        "expectation_snapshots": expectations,
        "official_text_items": texts,
        "llm_analyses": analyses,
        "shock_lane_items": shocks,
        "post_event_reactions": [reaction] if reaction else [],
        "alerts": [alert] if alert else [],
        "source_lineage": OFFICIAL_SOURCE_LINEAGE,
        "source_fetches": source_fetches,
    }
    return payload


def _fallback_calendar(now: datetime) -> list[dict[str, Any]]:
    base = now.replace(hour=12, minute=30, second=0, microsecond=0)
    return [
        _event(
            "PCE",
            "Personal Income and Outlays",
            "critical",
            _next_after(base + timedelta(hours=19), now),
            "https://www.bea.gov/news/schedule",
        ),
        _event(
            "NFP",
            "Employment Situation",
            "critical",
            _next_after(base + timedelta(days=8), now),
            "https://www.bls.gov/schedule/",
        ),
        _event(
            "CPI",
            "Consumer Price Index",
            "critical",
            _next_after(base + timedelta(days=13), now),
            "https://www.bls.gov/schedule/",
        ),
        _event(
            "FOMC",
            "FOMC meeting",
            "critical",
            _next_after(base + timedelta(days=21), now),
            "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        ),
    ]


def _event(
    event_type: str, title: str, importance: str, release_time: datetime, source_url: str
) -> dict[str, Any]:
    event_id = f"{event_type.lower()}-{release_time.strftime('%Y%m%d%H%M')}"
    return {
        "event_id": event_id,
        "event_type": event_type,
        "title": title,
        "importance": importance,
        "release_time": release_time.isoformat(),
        "release_time_utc": release_time.isoformat(),
        "release_time_et": "08:30 ET" if event_type in {"PCE", "NFP", "CPI"} else "14:00 ET",
        "release_time_local": "",
        "source_url": source_url,
        "source_tier": "fallback",
        "status": "scheduled",
        "source_name": "Embedded fallback calendar",
        "data_quality_flags": ["embedded_official_calendar_fallback"],
    }


def _next_after(candidate: datetime, now: datetime) -> datetime:
    while candidate <= now - timedelta(hours=2):
        candidate += timedelta(days=28)
    return _ensure_utc(candidate)


def _select_active_event(calendar: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    upcoming = sorted(
        (item for item in calendar if _parse_ts(item["release_time"]) >= now - timedelta(hours=2)),
        key=lambda item: (
            _parse_ts(item["release_time"]),
            _event_priority(str(item.get("event_type") or "")),
        ),
    )
    if not upcoming:
        return None
    item = dict(upcoming[0])
    release_time = _parse_ts(item["release_time"])
    time_to_event = int((release_time - now).total_seconds())
    item["time_to_event_sec"] = time_to_event
    item["phase"] = _phase(time_to_event)
    return item


def _event_priority(event_type: str) -> int:
    return {
        "FOMC": 0,
        "PCE": 1,
        "CPI": 2,
        "NFP": 3,
        "PPI": 4,
        "JOLTS": 5,
        "ECI": 6,
        "GDP": 7,
    }.get(event_type.upper(), 20)


def _phase(time_to_event_sec: int) -> str:
    if -7200 <= time_to_event_sec <= 7200:
        return "event_lock"
    if 0 < time_to_event_sec <= 86400:
        return "high_alert"
    if 0 < time_to_event_sec <= 7 * 86400:
        return "expectation_build"
    if time_to_event_sec < -7200:
        return "post_event"
    return "calendar_awareness"


def _expectation_snapshot(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    event_type = str(event.get("event_type") or "unknown")
    consensus = {"PCE": 0.2, "CPI": 0.3, "NFP": 165.0, "FOMC": None}.get(event_type)
    previous = {"PCE": 0.3, "CPI": 0.2, "NFP": 175.0, "FOMC": None}.get(event_type)
    nowcast = {"PCE": 0.25, "CPI": 0.35}.get(event_type)
    gap = None if consensus is None or nowcast is None else round(nowcast - consensus, 4)
    risk_direction = "hawkish" if gap is not None and gap > 0 else "neutral"
    return {
        "snapshot_id": f"exp-{event['event_id']}-{now.strftime('%Y%m%d%H%M')}",
        "event_id": event["event_id"],
        "snapshot_ts": now.isoformat(),
        "consensus": consensus,
        "previous": previous,
        "nowcast": nowcast,
        "market_implied": None,
        "expectation_gap": gap,
        "expectation_drift_1d": None,
        "expectation_drift_3d": None,
        "rate_cut_prob_drift_1d": None,
        "risk_direction": risk_direction,
        "source_quality": "embedded_fallback_until_live_connector",
    }


def _state_from_inputs(
    now: datetime,
    active_event: dict[str, Any] | None,
    shocks: list[dict[str, Any]],
    daemon_enabled: bool,
    daemon_status: str,
    data_quality: dict[str, Any],
) -> dict[str, Any]:
    flags = set(data_quality.get("data_quality_flags") or [])
    if not daemon_enabled or daemon_status == "paused_by_user":
        return {
            "event_window_state": "data_quality_blocked",
            "state_priority": 100,
            "emergency_level": "watch",
            "reason_codes": ["daemon_paused_by_user"],
            "valid_until": (now + timedelta(minutes=15)).isoformat(),
        }
    critical_shock = next(
        (item for item in shocks if item.get("emergency_level") == "critical"), None
    )
    if critical_shock:
        return {
            "event_window_state": "unscheduled_shock_confirmed",
            "state_priority": 95,
            "emergency_level": "critical",
            "reason_codes": [str(critical_shock.get("shock_type") or "unscheduled_shock")],
            "valid_until": (now + timedelta(hours=2)).isoformat(),
        }
    high_shock = next(
        (item for item in shocks if item.get("emergency_level") == "high"), None
    )
    if high_shock:
        shock_reason = _shock_reason(high_shock)
        return {
            "event_window_state": shock_reason.get("state", "unscheduled_shock_watch"),
            "state_priority": 75,
            "emergency_level": "high",
            "reason_codes": shock_reason.get("reason_codes")
            or [str(high_shock.get("shock_type") or "unscheduled_shock")],
            "valid_until": (now + timedelta(hours=1)).isoformat(),
        }
    watch_shock = next(
        (item for item in shocks if item.get("emergency_level") == "watch"), None
    )
    if watch_shock:
        shock_reason = _shock_reason(watch_shock)
        return {
            "event_window_state": shock_reason.get("state", "unscheduled_shock_watch"),
            "state_priority": 55,
            "emergency_level": "watch",
            "reason_codes": shock_reason.get("reason_codes")
            or [str(watch_shock.get("shock_type") or "unscheduled_shock")],
            "valid_until": (now + timedelta(minutes=45)).isoformat(),
        }
    phase = str((active_event or {}).get("phase") or "calendar_awareness")
    source_mode = str(data_quality.get("overall_source_mode") or "fallback")
    level_by_phase = {
        "event_lock": ("event_lock", 90, "critical", "scheduled_event_lock"),
        "high_alert": ("pre_event_high_alert", 70, "high", "scheduled_high_impact_event_near"),
        "expectation_build": ("expectation_build", 40, "watch", "expectation_monitoring"),
        "post_event": ("post_event_reaction_check", 50, "watch", "post_event_reaction_pending"),
    }
    state_name, priority, level, reason = level_by_phase.get(
        phase, ("calendar_monitor", 20, "none", "calendar_monitor")
    )
    if source_mode == "fallback":
        if level in {"critical", "high"}:
            level = "watch"
            priority = min(priority, 45)
            reason = "fallback_event_window_monitor"
        flags.add("event_window_fallback_only")
    return {
        "event_window_state": state_name,
        "state_priority": priority,
        "emergency_level": level,
        "reason_codes": [reason],
        "valid_until": (now + timedelta(hours=1)).isoformat(),
    }


def _overlay_from_state(state: dict[str, Any]) -> dict[str, Any]:
    level = str(state.get("emergency_level") or "none")
    mapping = {
        "critical": ("event_lock", 45, True, "blocked"),
        "high": ("watch_only", 55, True, "low"),
        "watch": ("reduce_size", 70, True, "reduced"),
        "none": ("none", None, False, "normal"),
    }
    modifier, cap, vol_warning, trust = mapping.get(level, mapping["none"])
    return {
        "trade_permission_modifier": modifier,
        "confidence_cap": cap,
        "volatility_warning": vol_warning,
        "ordinary_radar_trust": trust,
    }


def _default_official_text_items(now: datetime) -> list[dict[str, Any]]:
    text_id = f"fed-rss-placeholder-{now.strftime('%Y%m%d')}"
    return [
        {
            "text_id": text_id,
            "text_hash": text_id,
            "source_name": "Federal Reserve RSS",
            "source_tier": "official",
            "published_at": now.isoformat(),
            "speaker": "",
            "title": "Fed RSS monitor active",
            "url": "https://www.federalreserve.gov/feeds/feeds.htm",
            "raw_text": "No material policy text change detected in embedded fallback mode.",
        }
    ]


def _speech_monitor(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    latest = analyses[0] if analyses else {}
    return {
        "latest_item_ts": latest.get("analyzed_at", ""),
        "speaker": latest.get("speaker", ""),
        "speaker_weight": latest.get("speaker_weight", 0),
        "tone": latest.get("tone", "not_policy_relevant"),
        "tone_confidence": latest.get("tone_confidence", 0),
        "policy_relevance": latest.get("policy_relevance", "low"),
        "tone_shift_vs_baseline": bool(latest.get("tone_shift_vs_baseline")),
        "requires_human_review": bool(latest.get("requires_human_review")),
        "policy_topics": latest.get("policy_topics", []),
        "source_url": latest.get("source_url", ""),
        "llm_provider": latest.get("llm_provider", "deterministic"),
        "llm_model": latest.get("llm_model", ""),
        "llm_status": latest.get("llm_status", "not_requested"),
        "llm_error": latest.get("llm_error", ""),
        "analysis_hash": latest.get("analysis_hash", ""),
        "summary": latest.get("summary", ""),
        "btc_direction_boundary_pass": bool(
            latest.get("btc_direction_boundary_pass", True)
        ),
    }


def _shock_fast_lane(shocks: list[dict[str, Any]]) -> dict[str, Any]:
    latest = shocks[0] if shocks else {}
    summary = _shock_summary(latest)
    return {
        "shock_detected": bool(shocks),
        "shock_type": latest.get("shock_type", "unknown"),
        "emergency_level": latest.get("emergency_level", "none"),
        "confirmation_level": latest.get("confirmation_level", "none"),
        "source_count": latest.get("source_count", 0),
        "market_dislocation": bool(latest.get("market_dislocation")),
        "btc_microstructure_confirmation": bool(latest.get("btc_microstructure_confirmation")),
        "rumor_risk": bool(latest.get("rumor_risk")),
        "reason_codes": latest.get("reason_codes", []),
        "evidence": latest.get("evidence", {}),
        "summary": summary,
        "llm_analysis": _shock_llm_analysis_v2(latest, summary),
    }


def _shock_summary(shock: dict[str, Any]) -> str:
    if not shock:
        return (
            "No official unscheduled policy shock. Market dislocation checks are normal "
            "or unavailable."
        )
    evidence = shock.get("evidence") or {}
    primary = evidence.get("primary_window") or "market"
    ret = evidence.get("primary_return")
    try:
        ret_text = f"{float(ret) * 100:+.2f}%"
    except (TypeError, ValueError):
        ret_text = "n/a"
    return (
        f"{shock.get('emergency_level', 'watch')} {shock.get('shock_type', 'shock')} "
        f"via {primary} move {ret_text}; ordinary radar trust is controlled by overlay."
    )


def _shock_llm_analysis_v2(shock: dict[str, Any], summary: str) -> dict[str, Any]:
    if not shock:
        return {
            "provider": "deterministic",
            "status": "pending",
            "summary_zh": "当前没有确认的突发冲击，Shock Fast Lane 维持监控状态。",
            "risk_reason_zh": "官方突发、可信来源数量和 BTC 市场错位证据尚未达到触发阈值。",
            "action_boundary_zh": "该区块只解释事件窗口覆盖层，不改变 BTC score、radar score 或趋势方向。",
            "boundary_pass": True,
            "analysis_source": "business_payload_fallback",
        }
    evidence = shock.get("evidence") or {}
    primary = str(evidence.get("primary_window") or "market")
    try:
        primary_return = float(evidence.get("primary_return") or 0.0)
    except (TypeError, ValueError):
        primary_return = 0.0
    direction_word = "下跌" if primary_return < 0 else "上涨"
    level = str(shock.get("emergency_level") or "watch")
    shock_type = str(shock.get("shock_type") or "unknown")
    confirmation = str(shock.get("confirmation_level") or "none")
    missing = [str(item) for item in list(shock.get("data_quality_flags") or [])]
    missing_text = "，但" + "、".join(missing[:2]) + "。" if missing else "。"
    return {
        "provider": str(shock.get("llm_provider") or "deterministic"),
        "status": str(shock.get("llm_status") or "success"),
        "summary_zh": (
            f"检测到 BTC {primary} 市场错位冲击，事件级别为 {level}，"
            "Event Window 将普通雷达信任交给 overlay 管理。"
        ),
        "risk_reason_zh": (
            f"冲击类型为 {shock_type}，确认方式为 {confirmation}，"
            f"价格窗口显示 {direction_word} 压力/波动已进入事件监控范围{missing_text}"
        ),
        "action_boundary_zh": (
            "该解释只说明 Shock Fast Lane 如何影响 Event Window 的交易权限、"
            "置信上限和雷达信任，不直接输出 BTC 多空，也不修改任何 radar 分数。"
        ),
        "boundary_pass": True,
        "analysis_source": "business_payload_fallback",
        "source_summary": summary,
    }


def _shock_llm_analysis(shock: dict[str, Any], summary: str) -> dict[str, Any]:
    if not shock:
        return {
            "provider": "deterministic",
            "status": "pending",
            "summary_zh": "当前没有确认的突发冲击，Shock Fast Lane 维持监控状态。",
            "risk_reason_zh": "官方突发、可信来源数量和 BTC 市场错位证据尚未达到触发阈值。",
            "action_boundary_zh": "该区块只解释事件窗口覆盖层，不改变 BTC score、radar score 或趋势方向。",
            "boundary_pass": True,
        }
    evidence = shock.get("evidence") or {}
    primary = str(evidence.get("primary_window") or "market")
    try:
        primary_return = float(evidence.get("primary_return") or 0.0)
    except (TypeError, ValueError):
        primary_return = 0.0
    direction_word = "下跌" if primary_return < 0 else "上涨"
    level = str(shock.get("emergency_level") or "watch")
    shock_type = str(shock.get("shock_type") or "unknown")
    confirmation = str(shock.get("confirmation_level") or "none")
    missing = list(shock.get("data_quality_flags") or [])
    missing_text = "，但" + "、".join(missing[:2]) + "。" if missing else "。"
    return {
        "provider": str(shock.get("llm_provider") or "deterministic"),
        "status": str(shock.get("llm_status") or "success"),
        "summary_zh": (
            f"检测到 BTC {primary} 市场错位冲击，事件级别为 {level}，"
            f"Event Window 将普通雷达信任交给 overlay 管理。"
        ),
        "risk_reason_zh": (
            f"冲击类型为 {shock_type}，确认方式为 {confirmation}；"
            f"价格窗口显示 {direction_word} 压力/波动已进入事件监控范围{missing_text}"
        ),
        "action_boundary_zh": (
            "该解释只说明 Shock Fast Lane 如何影响 Event Window 的交易权限、"
            "置信上限和雷达信任，不直接输出 BTC 多空，也不修改任何 radar 分数。"
        ),
        "boundary_pass": True,
        "source_summary": summary,
    }


def _shock_reason(shock: dict[str, Any]) -> dict[str, Any]:
    reason_codes = list(shock.get("reason_codes") or [])
    if shock.get("market_dislocation"):
        evidence = shock.get("evidence") or {}
        primary = str(evidence.get("primary_window") or "")
        state = "market_dislocation_high_alert"
        if primary in {"1h", "4h", "24h"}:
            try:
                primary_return = float(evidence.get("primary_return"))
            except (TypeError, ValueError):
                primary_return = 0.0
            state = (
                "sustained_drawdown_high_alert"
                if primary_return < 0
                else "sustained_rally_high_alert"
            )
        return {"state": state, "reason_codes": reason_codes or ["market_dislocation"]}
    return {"state": "unscheduled_shock_watch", "reason_codes": reason_codes}


def _source_fetches_from_market_probe(probe: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for item in probe.get("source_lineage") or []:
        source_id = str(item.get("source_id") or "market_probe")
        started = item.get("started_at") or probe.get("started_at") or probe.get("collected_at")
        fetch_id = f"fetch-{source_id}-{str(started).replace(':', '').replace('-', '')}"
        items.append(
            {
                "fetch_id": fetch_id,
                "source_id": source_id,
                "source_tier": item.get("source_tier", "market_live"),
                "endpoint_url": item.get("endpoint_url"),
                "started_at": started,
                "finished_at": item.get("finished_at") or probe.get("finished_at"),
                "status": item.get("status", "failed"),
                "http_status": item.get("http_status"),
                "error_code": item.get("error_code"),
                "error_message": item.get("error_message"),
                "payload_hash": probe.get("payload_hash"),
                "parsed_item_count": item.get("parsed_item_count", 0),
                "fallback_used": item.get("fallback_used", False),
                "payload_json": item,
            }
        )
    return items


def _reaction_placeholder(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "reaction_id": f"rxn-{event['event_id']}-{now.strftime('%Y%m%d%H%M')}",
        "event_id": event["event_id"],
        "snapshot_ts": now.isoformat(),
        "actual": None,
        "consensus": None,
        "surprise_raw": None,
        "surprise_z": None,
        "btc_return_5m": None,
        "btc_return_30m": None,
        "btc_return_2h": None,
        "btc_absorbed_shock": None,
        "followthrough": "pending",
    }


def _empty_expectation() -> dict[str, Any]:
    return {
        "consensus": None,
        "previous": None,
        "nowcast": None,
        "market_implied": None,
        "expectation_gap": None,
        "expectation_drift_1d": None,
        "expectation_drift_3d": None,
        "rate_cut_prob_drift_1d": None,
        "risk_direction": "unknown",
    }


def _empty_reaction() -> dict[str, Any]:
    return {
        "actual": None,
        "consensus": None,
        "surprise_raw": None,
        "surprise_z": None,
        "btc_return_5m": None,
        "btc_return_30m": None,
        "btc_return_2h": None,
        "btc_absorbed_shock": None,
        "followthrough": None,
    }


def _data_quality(
    calendar: list[dict[str, Any]],
    active_event: dict[str, Any] | None,
    daemon_enabled: bool,
    source_fetches: list[dict[str, Any]],
) -> dict[str, Any]:
    flags: list[str] = []
    if not daemon_enabled:
        flags.append("daemon_paused")
    live_count = sum(
        1
        for item in source_fetches
        if item.get("status") == "success" and not item.get("fallback_used")
    )
    fallback_count = sum(1 for item in source_fetches if item.get("fallback_used"))
    failed_count = sum(1 for item in source_fetches if item.get("status") == "failed")
    partial_count = sum(1 for item in source_fetches if item.get("status") == "partial")
    expectation_attempted = any(
        item.get("source_id") in {"cleveland-fed-nowcast", "cme-fedwatch"}
        for item in source_fetches
    )
    if fallback_count:
        fallback_ids = {
            str(item.get("source_id") or "")
            for item in source_fetches
            if item.get("fallback_used")
        }
        if any(source_id.startswith("embedded-") for source_id in fallback_ids):
            flags.append("embedded_official_calendar_fallback")
        else:
            flags.append("event_source_provider_fallback_used")
    if failed_count:
        flags.append("event_source_fetch_failed")
    if not expectation_attempted:
        flags.append("live_expectation_connectors_pending")
    if live_count:
        overall_source_mode = (
            "live" if not partial_count and not fallback_count and not failed_count else "partial"
        )
    elif fallback_count:
        overall_source_mode = "fallback"
    elif partial_count:
        overall_source_mode = "partial"
    else:
        overall_source_mode = "failed"
    if overall_source_mode == "fallback":
        flags.append("event_window_fallback_only")
    source_quality = _source_quality_breakdown(
        active_event,
        source_fetches,
        overall_source_mode,
        flags,
    )
    return {
        "calendar_fresh": bool(calendar),
        "consensus_fresh": False,
        "official_actual_confirmed": False,
        "source_conflict": False,
        "blocked_reason": source_quality.get("blocked_reason")
        or (None if active_event else "no_active_event"),
        "overall_source_mode": overall_source_mode,
        "functional_live": bool(source_quality.get("functional_live")),
        "blocked": bool(source_quality.get("blocked")),
        "confidence_note": source_quality.get("confidence_note"),
        "source_quality": source_quality,
        "disabled_capabilities": source_quality.get("disabled_capabilities", []),
        "live_source_count": live_count,
        "partial_source_count": partial_count,
        "fallback_source_count": fallback_count,
        "failed_source_count": failed_count,
        "data_quality_flags": flags,
    }


def _source_quality_breakdown(
    active_event: dict[str, Any] | None,
    source_fetches: list[dict[str, Any]],
    overall_source_mode: str,
    flags: list[str],
) -> dict[str, Any]:
    fetch_by_id = {str(item.get("source_id")): item for item in source_fetches}
    calendar_quality = "ok" if any(
        item.get("source_tier") == "official" and item.get("status") == "success"
        for item in source_fetches
    ) else "missing"
    if any(
        item.get("source_tier") in {
            "manual_override",
            "official_mirror",
            "secondary_calendar",
            "secondary_calendar_free_export",
        }
        for item in source_fetches
    ):
        calendar_quality = "fallback" if calendar_quality == "missing" else "partial"
    if not active_event:
        calendar_quality = "blocked"

    event_type = str((active_event or {}).get("event_type") or "")
    expectation = (active_event or {}).get("expectation") or {}
    actual_snapshot = (active_event or {}).get("actual_snapshot") or {}
    nowcast_quality = "ok" if expectation.get("nowcast_payload") else "missing"
    if fetch_by_id.get("cleveland-fed-nowcast", {}).get("status") == "partial":
        nowcast_quality = "partial"
    if event_type not in {"PCE", "CPI"}:
        nowcast_quality = "missing"

    consensus_quality = str(expectation.get("consensus_status") or "missing")
    fedwatch_quality = "missing"
    market_implied = expectation.get("market_implied")
    if isinstance(market_implied, dict) and market_implied.get("fedwatch_proxy_used"):
        fedwatch_quality = "proxy"
    elif market_implied is not None:
        fedwatch_quality = "ok"

    actual_status = str(actual_snapshot.get("actual_status") or "pending")
    actual_quality = {
        "available": "ok",
        "not_released": "pending",
        "provider_failed": "blocked",
    }.get(actual_status, "pending")

    speech_quality = (
        "ok" if fetch_by_id.get("fed-rss", {}).get("status") == "success" else "missing"
    )
    disabled = []
    if consensus_quality != "ok":
        disabled.append("release_surprise_disabled")
    if event_type == "FOMC" and fedwatch_quality in {"proxy", "missing"}:
        disabled.append("official_fedwatch_unavailable")
    if actual_quality == "pending":
        disabled.append("actual_pending")
    blocked_reason = None
    if calendar_quality == "blocked":
        blocked_reason = "critical_event_time_unavailable"
    elif actual_quality == "blocked":
        blocked_reason = "actual_provider_failed_after_release"
    source_mode = "partial_live" if overall_source_mode == "partial" else overall_source_mode
    if blocked_reason:
        source_mode = "blocked"
        flags.append(blocked_reason)
    blocked = bool(blocked_reason)
    functional_live = source_mode in {"live", "partial_live"} and not blocked
    return {
        "calendar_quality": calendar_quality,
        "actual_quality": actual_quality,
        "nowcast_quality": nowcast_quality,
        "consensus_quality": consensus_quality,
        "fedwatch_quality": fedwatch_quality,
        "speech_quality": speech_quality,
        "overall_source_mode": source_mode,
        "functional_live": functional_live,
        "blocked": blocked,
        "confidence_note": _source_mode_confidence_note(source_mode, blocked_reason),
        "disabled_capabilities": disabled,
        "blocked_reason": blocked_reason,
    }


def _source_mode_confidence_note(source_mode: str, blocked_reason: str | None) -> str:
    if blocked_reason:
        return (
            f"blocked by {blocked_reason}; Event Window must not promote alerts "
            "until the blocking condition clears."
        )
    if source_mode == "partial_live":
        return (
            "partial_live is fully functional for monitoring; missing fields are "
            "capability-scoped, not system-blocking."
        )
    if source_mode == "live":
        return "live sources are available and Event Window monitoring is fully active."
    if source_mode == "fallback":
        return (
            "fallback sources can keep calendar monitoring alive, but high-confidence "
            "surprise calculations remain disabled."
        )
    return "source mode requires review before high-confidence event conclusions."


def _fallback_fetch(source_id: str, now: datetime, parsed_item_count: int) -> dict[str, Any]:
    return {
        "fetch_id": f"fetch-{source_id}-{now.strftime('%Y%m%d%H%M%S')}",
        "source_id": source_id,
        "source_tier": "fallback",
        "endpoint_url": "embedded://event-window/fallback",
        "started_at": now.isoformat(),
        "finished_at": now.isoformat(),
        "status": "fallback_used",
        "http_status": None,
        "error_code": "live_source_unavailable",
        "error_message": (
            "Embedded fallback used because live connector did not return usable data."
        ),
        "payload_hash": None,
        "parsed_item_count": parsed_item_count,
        "fallback_used": True,
    }


SCHEDULER_SOURCE_GROUPS = {
    "official_calendar",
    "expectation_nowcast",
    "consensus_proxy",
    "rate_probability",
    "fed_rss_official_text",
    "shock_fast_lane",
    "btc_reaction",
    "actual_polling",
    "llm_speech_analyzer",
    "post_event_reaction",
}


def _skipped_groups(due_groups: set[str]) -> list[str]:
    return sorted(SCHEDULER_SOURCE_GROUPS - due_groups)


def _scheduler_skip_fetch(
    source_group: str,
    now: datetime,
    previous_payload: dict[str, Any],
    previous_field: str,
) -> dict[str, Any]:
    previous_value = previous_payload.get(previous_field)
    if isinstance(previous_value, list):
        parsed_count = len(previous_value)
    elif previous_value:
        parsed_count = 1
    else:
        parsed_count = 0
    return {
        "fetch_id": f"fetch-{source_group}-skipped-{now.strftime('%Y%m%d%H%M%S')}",
        "source_id": f"{source_group}-scheduler",
        "source_group": source_group,
        "source_tier": "scheduler",
        "endpoint_url": f"scheduler://event-window/{source_group}",
        "started_at": now.isoformat(),
        "finished_at": now.isoformat(),
        "status": "skipped_not_due",
        "http_status": None,
        "error_code": "skipped_not_due",
        "error_message": (
            f"{source_group} skipped by scheduler due gate; reused previous {previous_field}."
        ),
        "payload_hash": None,
        "parsed_item_count": parsed_count,
        "fallback_used": False,
        "skip_reason": "next_due_at_in_future",
        "cache_status": "reused_previous_snapshot" if parsed_count else "previous_snapshot_missing",
    }


def _alert_from_state(
    state: dict[str, Any], event: dict[str, Any] | None, now: datetime
) -> dict[str, Any] | None:
    level = str(state.get("emergency_level") or "none")
    if level == "none":
        return None
    event_id = str((event or {}).get("event_id") or "watchtower")
    reason = str((state.get("reason_codes") or ["event_window"])[0])
    return {
        "alert_id": f"ew-{event_id}-{level}-{now.strftime('%Y%m%d%H%M')}",
        "event_id": event_id,
        "created_ts": now.isoformat(),
        "emergency_level": level,
        "title": _alert_title(level, event),
        "summary": _alert_summary(state, event),
        "reason_code": reason,
        "status": "open",
    }


def _alert_title(level: str, event: dict[str, Any] | None) -> str:
    title = str((event or {}).get("title") or "Policy shock watch")
    return f"{level.upper()} - {title}"


def _alert_summary(state: dict[str, Any], event: dict[str, Any] | None) -> str:
    phase = str((event or {}).get("phase") or state.get("event_window_state") or "")
    return (
        "Event Watchtower overlay is active; ordinary radar trust is reduced until "
        f"the {phase} window is resolved."
    )


def _ensure_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _ensure_utc(value)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return _ensure_utc(parsed)
