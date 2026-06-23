from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from onlybtc.p45.cockpit import normalize_module_signals


SCHEMA_VERSION = "p45.invalidation_workbench.v2"

BTC_RESPONSE_MODULES = {"kline_orderflow", "trade_structure_flow", "derivatives_crowding"}
FAST_CONFIRMATION_MODULES = {
    "kline_orderflow",
    "trade_structure_flow",
    "derivatives_crowding",
    "crypto_breadth",
    "options_volatility",
    "asia_risk",
}
FLOW_CAPITAL_MODULES = {"fund_flow", "dollar_liquidity", "treasury_credit"}
REGIME_MODULES = {"macro_radar", "treasury_credit", "asia_risk", "onchain_valuation", "btc_adoption"}
QUALITY_MODULES = {"btc_total_state", "event_policy", "data_quality", "contract_validation"}

RULE_STATUSES = {"not_armed", "arming", "armed", "triggered", "rejected", "blocked", "expired"}


def build_invalidation_workbench(
    *,
    btc_trend_cockpit: dict[str, Any] | None,
    modules: list[dict[str, Any]],
    invalidation_rules: list[dict[str, Any]] | None = None,
    confirmation_rules: list[dict[str, Any]] | None = None,
    contract_validation: dict[str, Any] | None = None,
    data_quality: dict[str, Any] | None = None,
    run_lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cockpit = btc_trend_cockpit or {}
    module_signals = list(cockpit.get("module_signals") or normalize_module_signals(modules))
    scores = dict(cockpit.get("scores") or {})
    evidence_matrix = _module_evidence_matrix(module_signals)
    btc_response = _btc_response(module_signals, scores)
    data_quality_penalty = _data_quality_penalty(module_signals, data_quality, scores)
    current_thesis = _current_thesis(cockpit)
    base_scores = _validation_scores(
        signals=module_signals,
        cockpit_scores=scores,
        btc_response=btc_response,
        data_quality_penalty=data_quality_penalty,
    )
    quality_blocked = _quality_blocked(contract_validation, data_quality_penalty, module_signals)
    rule_groups = _rule_groups(
        current_thesis=current_thesis,
        scores=base_scores,
        btc_response=btc_response,
        signals=module_signals,
        quality_blocked=quality_blocked,
        legacy_confirmation=confirmation_rules or [],
        legacy_invalidation=invalidation_rules or [],
    )
    all_rules = [
        rule
        for rules in rule_groups.values()
        if isinstance(rules, list)
        for rule in rules
        if isinstance(rule, dict)
    ]
    triggered_rules = [rule for rule in all_rules if rule.get("status") == "triggered"]
    armed_rules = [rule for rule in all_rules if rule.get("status") in {"arming", "armed"}]
    blocked_rules = [rule for rule in all_rules if rule.get("status") == "blocked"]
    validation_state, validation_reason = _validation_state(
        current_thesis=current_thesis,
        scores=base_scores,
        btc_response=btc_response,
        quality_blocked=quality_blocked,
        triggered_rules=triggered_rules,
    )

    lineage = dict(run_lineage or {})
    lineage.setdefault("generated_at", datetime.now(UTC).isoformat())
    lineage["source_payload_version"] = str(cockpit.get("schema_version") or "")
    lineage["cockpit_payload_hash"] = _stable_hash(cockpit)

    return {
        "schema_version": SCHEMA_VERSION,
        "run_lineage": lineage,
        "current_thesis": current_thesis,
        "validation_state": validation_state,
        "validation_reason": validation_reason,
        "scores": base_scores,
        "btc_response": btc_response,
        "module_evidence_matrix": evidence_matrix,
        "rule_groups": rule_groups,
        "triggered_rules": triggered_rules,
        "armed_rules": armed_rules,
        "blocked_rules": blocked_rules,
        "timeline": _timeline(all_rules),
        "legacy": {
            "invalidation_rules": invalidation_rules or [],
            "confirmation_rules": confirmation_rules or [],
        },
    }


def _current_thesis(cockpit: dict[str, Any]) -> dict[str, Any]:
    return {
        "headline_state": str(cockpit.get("headline_state") or "neutral"),
        "btc_direction": str(cockpit.get("btc_direction") or "neutral"),
        "trend_quality": str(cockpit.get("trend_quality") or "mixed"),
        "trade_permission": str(cockpit.get("trade_permission") or "watch_only"),
        "confidence_score": _round(_num(cockpit.get("confidence_score")), 2),
        "horizons": cockpit.get("horizon") or {},
    }


def _module_evidence_matrix(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for signal in signals:
        direction = str(signal.get("effective_direction") or "neutral")
        accepted = str(signal.get("accepted_status") or "unknown")
        quality = str(signal.get("quality_status") or "partial")
        state = _evidence_state(direction, accepted, quality, signal)
        weight_status = _evidence_weight_status(direction, accepted, quality, signal)
        trigger_eligible = _trigger_eligible(direction, accepted, quality, signal)
        strength = min(100.0, abs(_num(signal.get("contribution"))) * 100.0)
        matrix.append(
            {
                "module_id": signal.get("module_name"),
                "layer": _evidence_layer(str(signal.get("module_name") or ""), str(signal.get("layer") or "")),
                "module_direction": signal.get("raw_direction") or "neutral",
                "module_effective_direction": direction,
                "btc_implication": signal.get("btc_implication") or "",
                "evidence_state": state,
                "evidence_weight_status": weight_status,
                "trigger_eligible": trigger_eligible,
                "strength": _round(strength, 2),
                "freshness_sec": None,
                "horizon": signal.get("horizon") or "",
                "signal_stage": signal.get("signal_stage") or "none",
                "support_drivers": signal.get("support_drivers") or [],
                "pressure_drivers": signal.get("pressure_drivers") or [],
                "conflict_drivers": signal.get("conflict_drivers") or [],
                "rejection_reason": _rejection_reason(signal),
                "data_quality_flags": signal.get("data_quality_flags") or [],
                "evidence_ids": _evidence_ids(signal),
            }
        )
    return matrix


def _evidence_layer(module_name: str, default_layer: str) -> str:
    if module_name in BTC_RESPONSE_MODULES:
        return "btc_response"
    if module_name in FAST_CONFIRMATION_MODULES:
        return "fast_confirmation"
    if module_name in FLOW_CAPITAL_MODULES:
        return "flow_capital"
    if module_name in REGIME_MODULES:
        return "regime"
    if module_name in QUALITY_MODULES or default_layer == "controller":
        return "quality_controller"
    return default_layer or "regime"


def _evidence_state(
    direction: str,
    accepted: str,
    quality: str,
    signal: dict[str, Any],
) -> str:
    if quality == "failed":
        return "blocked"
    if quality == "stale":
        return "stale"
    if not direction or direction == "neutral":
        return "missing" if accepted == "unknown" else "conflict"
    if accepted == "accepted":
        if _data_quality_flags(signal):
            return "quality_discounted"
        if _is_context_accepted(direction, signal):
            return "accepted_context"
        return "accepted"
    if accepted == "rejected":
        return "rejected"
    if direction == "conflict" or str(signal.get("signal_stage")) == "conflict":
        return "conflict"
    return "conflict" if accepted == "fragile" else "missing"


def _evidence_weight_status(
    direction: str,
    accepted: str,
    quality: str,
    signal: dict[str, Any],
) -> str:
    if quality == "failed":
        return "blocked"
    if quality == "stale":
        return "stale"
    if accepted == "rejected":
        return "rejected"
    if accepted != "accepted" or direction not in {"bullish", "bearish"}:
        return "missing"
    if _data_quality_flags(signal):
        return "discounted"
    if _is_context_accepted(direction, signal):
        return "context"
    return "full"


def _trigger_eligible(
    direction: str,
    accepted: str,
    quality: str,
    signal: dict[str, Any],
) -> bool:
    if quality in {"failed", "stale"}:
        return False
    if accepted != "accepted" or direction not in {"bullish", "bearish"}:
        return False
    if _data_quality_flags(signal):
        return False
    return not _is_context_accepted(direction, signal)


def _is_context_accepted(direction: str, signal: dict[str, Any]) -> bool:
    stage = str(signal.get("signal_stage") or "none").lower()
    implication = str(signal.get("btc_implication") or "").lower()
    if direction not in {"bullish", "bearish"}:
        return True
    if stage in {"fast_signal", "confirmed_signal", "conflict"}:
        return False
    if _directional_implication(implication):
        return False
    if signal.get("module_name") in BTC_RESPONSE_MODULES and abs(_num(signal.get("btc_response_score"))) >= 35:
        return False
    return True


def _directional_implication(implication: str) -> bool:
    directional_terms = (
        "confirmed",
        "rejected",
        "rejecting",
        "drag",
        "pressure",
        "absorbed",
        "failed",
        "weakness",
        "strength",
        "fragile",
        "risk_off",
        "squeeze",
        "breakdown",
        "reclaim",
        "tailwind",
        "headwind",
    )
    return any(term in implication for term in directional_terms)


def _data_quality_flags(signal: dict[str, Any]) -> list[Any]:
    return list(signal.get("data_quality_flags") or [])


def _btc_response(signals: list[dict[str, Any]], scores: dict[str, Any]) -> dict[str, Any]:
    response_signals = [
        item
        for item in signals
        if item.get("module_name") in BTC_RESPONSE_MODULES
        or item.get("btc_response_score") is not None
        or item.get("residual") is not None
    ]
    score_values = [_num(item.get("btc_response_score")) for item in response_signals if item.get("btc_response_score") is not None]
    residual_values = [_num(item.get("residual")) for item in response_signals if item.get("residual") is not None]
    price_score = _avg(score_values)
    residual_score = _avg(residual_values)
    if price_score is None:
        price_score = _num(scores.get("trend_acceptance_score")) - 50.0 if scores.get("trend_acceptance_score") is not None else None
    residual_direction = "flat"
    if residual_score is not None and residual_score > 0.15:
        residual_direction = "positive"
    elif residual_score is not None and residual_score < -0.15:
        residual_direction = "negative"
    direction = "neutral"
    if price_score is not None and price_score > 15:
        direction = "bullish"
    elif price_score is not None and price_score < -15:
        direction = "bearish"
    micro_items = [
        item
        for item in signals
        if item.get("module_name") in {"kline_orderflow", "trade_structure_flow"}
    ]
    micro_score = _avg([_num(item.get("contribution")) * 100.0 for item in micro_items])
    return {
        "price_acceptance": {
            "direction": direction,
            "score": _round(price_score, 2) if price_score is not None else None,
            "accepted_level": _accepted_level(direction, price_score),
            "anchor_price": None,
            "current_price": None,
            "acceptance_window_sec": None,
            "hold_duration_sec": None,
            "failed_attempts": sum(1 for item in response_signals if item.get("accepted_status") == "rejected"),
        },
        "residual": {
            "direction": residual_direction,
            "score": _round((residual_score or 0.0) * 33.0, 2) if residual_score is not None else None,
            "expected_return_bps": None,
            "actual_return_bps": None,
            "residual_bps": None,
            "zscore": _round(residual_score, 3) if residual_score is not None else None,
        },
        "micro_response": {
            "ofi_z": None,
            "cvd_z": None,
            "depth_imbalance_z": None,
            "taker_delta_z": None,
            "spread_bps": None,
            "liquidity_survival": _liquidity_survival(micro_items),
            "score": _round(micro_score, 2) if micro_score is not None else None,
        },
        "missing_btc_response": not response_signals,
        "missing_residual": residual_score is None,
    }


def _validation_scores(
    *,
    signals: list[dict[str, Any]],
    cockpit_scores: dict[str, Any],
    btc_response: dict[str, Any],
    data_quality_penalty: float,
) -> dict[str, float]:
    accepted = [
        item
        for item in signals
        if _trigger_eligible(
            str(item.get("effective_direction") or "neutral"),
            str(item.get("accepted_status") or "unknown"),
            str(item.get("quality_status") or "partial"),
            item,
        )
    ]
    rejected = [item for item in signals if item.get("accepted_status") == "rejected"]
    fast_aligned = sum(1 for item in accepted if item.get("layer") == "fast")
    confirmation_aligned = sum(1 for item in accepted if item.get("layer") == "confirmation")
    rejection_fast = sum(1 for item in rejected if item.get("layer") == "fast")
    support = _num(cockpit_scores.get("support_score")) * 100.0
    pressure = _num(cockpit_scores.get("pressure_score")) * 100.0
    conflict = _num(cockpit_scores.get("conflict_score")) * 100.0
    acceptance = _num(cockpit_scores.get("trend_acceptance_score"))
    response_score = _btc_response_score(btc_response)
    residual_rejection = _residual_rejection_score(btc_response, signals)
    confirmation_score = min(
        100.0,
        0.35 * acceptance
        + 0.25 * abs(response_score)
        + 0.20 * max(support, pressure)
        + 10.0 * min(2, fast_aligned)
        + 5.0 * min(2, confirmation_aligned),
    )
    invalidation_score = min(
        100.0,
        0.35 * residual_rejection
        + 0.25 * abs(response_score)
        + 0.20 * conflict
        + 10.0 * min(2, rejection_fast)
        + 5.0 * len(rejected),
    )
    return {
        "confirmation_score": _round(confirmation_score, 2),
        "invalidation_score": _round(invalidation_score, 2),
        "conflict_score": _round(conflict, 2),
        "trend_acceptance_score": _round(acceptance, 2),
        "btc_response_score": _round(response_score, 2),
        "residual_rejection_score": _round(residual_rejection, 2),
        "data_quality_penalty": _round(data_quality_penalty, 2),
    }


def _rule_groups(
    *,
    current_thesis: dict[str, Any],
    scores: dict[str, float],
    btc_response: dict[str, Any],
    signals: list[dict[str, Any]],
    quality_blocked: bool,
    legacy_confirmation: list[dict[str, Any]],
    legacy_invalidation: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    direction = str(current_thesis.get("btc_direction") or "neutral")
    headline = str(current_thesis.get("headline_state") or "neutral")
    groups = {
        "confirm_current_view": [],
        "refute_current_view": [],
        "break_neutral_scenarios": [],
        "upgrade_scenarios": [],
        "downgrade_scenarios": [],
        "data_quality_blocks": [],
    }
    if quality_blocked:
        groups["data_quality_blocks"].append(
            _rule(
                rule_id="quality_block_data_or_contract",
                rule_type="quality_block",
                target_view=direction,
                horizon="latest",
                status="blocked",
                progress=100,
                severity="critical",
                reason="Data quality or contract validation blocks Workbench validation.",
                required_layers=["quality_controller"],
                observed_modules=_modules_with_quality_issue(signals),
                btc_response=btc_response,
            )
        )
        return groups

    if direction == "neutral" or headline in {"neutral", "conflict", "blocked"}:
        groups["break_neutral_scenarios"].append(
            _directional_rule(
                rule_id="break_neutral_bullish_confirmation",
                target_view="bullish",
                required_direction="bullish",
                scores=scores,
                btc_response=btc_response,
                signals=signals,
                rule_type="confirmation",
                horizon="4h",
            )
        )
        groups["break_neutral_scenarios"].append(
            _directional_rule(
                rule_id="break_neutral_bearish_confirmation",
                target_view="bearish",
                required_direction="bearish",
                scores=scores,
                btc_response=btc_response,
                signals=signals,
                rule_type="confirmation",
                horizon="4h",
            )
        )
        groups["downgrade_scenarios"].append(
            _rule(
                rule_id="neutral_kept_by_conflict_or_low_response",
                rule_type="downgrade",
                target_view="neutral",
                horizon="4h",
                status="armed" if scores["conflict_score"] >= 35 or scores["btc_response_score"] < 60 else "not_armed",
                progress=max(scores["conflict_score"], 100.0 - scores["btc_response_score"]),
                severity="medium",
                reason="Neutral remains valid until one side is accepted by BTC response and residual.",
                required_layers=["btc_response", "fast_confirmation"],
                observed_modules=_observed_modules(signals),
                btc_response=btc_response,
            )
        )
    else:
        groups["confirm_current_view"].append(
            _directional_rule(
                rule_id=f"confirm_current_{direction}_view",
                target_view=direction,
                required_direction=direction,
                scores=scores,
                btc_response=btc_response,
                signals=signals,
                rule_type="confirmation",
                horizon="4h",
            )
        )
        opposite = "bearish" if direction == "bullish" else "bullish"
        groups["refute_current_view"].append(
            _directional_rule(
                rule_id=f"refute_current_{direction}_view",
                target_view=opposite,
                required_direction=opposite,
                scores=scores,
                btc_response=btc_response,
                signals=signals,
                rule_type="invalidation",
                horizon="4h",
            )
        )
        groups["upgrade_scenarios"].append(
            _rule_from_legacy(
                "upgrade_current_view_with_legacy_confirmation",
                "upgrade",
                direction,
                legacy_confirmation,
                scores,
                btc_response,
                signals,
            )
        )
        groups["downgrade_scenarios"].append(
            _rule_from_legacy(
                "downgrade_current_view_with_legacy_invalidation",
                "downgrade",
                opposite,
                legacy_invalidation,
                scores,
                btc_response,
                signals,
            )
        )

    return groups


def _directional_rule(
    *,
    rule_id: str,
    target_view: str,
    required_direction: str,
    scores: dict[str, float],
    btc_response: dict[str, Any],
    signals: list[dict[str, Any]],
    rule_type: str,
    horizon: str,
) -> dict[str, Any]:
    fast = _signals_by_direction(signals, required_direction, layers={"fast"})
    confirming = _signals_by_direction(signals, required_direction, layers={"confirmation", "regime"})
    response_passed = _response_passed(required_direction, btc_response)
    residual_passed = _residual_passed(required_direction, btc_response)
    enough_modules = len(fast) >= 1 and (len(fast) + len(confirming)) >= 2
    score_key = "confirmation_score" if rule_type == "confirmation" else "invalidation_score"
    progress = min(100.0, 0.45 * scores[score_key] + 0.30 * scores["btc_response_score"] + 0.25 * scores["trend_acceptance_score"])
    if btc_response.get("missing_btc_response") or btc_response.get("missing_residual"):
        status = "armed" if progress >= 70 else "arming"
    elif response_passed and residual_passed and enough_modules and scores[score_key] >= 65:
        status = "triggered"
    elif not response_passed or not residual_passed:
        status = "rejected" if progress >= 45 else "arming"
    else:
        status = "armed" if progress >= 70 else "arming" if progress >= 35 else "not_armed"
    return _rule(
        rule_id=rule_id,
        rule_type=rule_type,
        target_view=target_view,
        horizon=horizon,
        status=status,
        progress=progress,
        severity="high" if status == "triggered" else "medium",
        reason=_rule_reason(required_direction, status, btc_response, enough_modules),
        required_layers=["btc_response", "fast_confirmation", "flow_capital"],
        required_modules=[item.get("module_name") for item in fast[:3] + confirming[:3]],
        observed_modules=[item.get("module_name") for item in fast + confirming],
        missing_evidence=_missing_evidence(response_passed, residual_passed, enough_modules, btc_response),
        btc_response=btc_response,
        trigger_conditions=[
            f"fast layer has {required_direction} evidence",
            "BTC price acceptance passes",
            "residual gate passes",
            "at least two modules align",
        ],
        current_observations=_current_observations(fast, confirming, btc_response),
    )


def _rule_from_legacy(
    rule_id: str,
    rule_type: str,
    target_view: str,
    legacy_rules: list[dict[str, Any]],
    scores: dict[str, float],
    btc_response: dict[str, Any],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    progress = min(85.0, 30.0 + len(legacy_rules) * 10.0 + scores["trend_acceptance_score"] * 0.25)
    status = "armed" if progress >= 70 else "arming"
    if btc_response.get("missing_btc_response") or btc_response.get("missing_residual"):
        status = "armed" if progress >= 70 else "arming"
    return _rule(
        rule_id=rule_id,
        rule_type=rule_type,
        target_view=target_view,
        horizon="24h",
        status=status,
        progress=progress,
        severity="medium",
        reason="Legacy P4.5 rule is kept as context and waits for BTC response gate.",
        required_layers=["btc_response", "legacy_p45_rules"],
        observed_modules=_observed_modules(signals),
        btc_response=btc_response,
        trigger_conditions=[str(item.get("condition") or item.get("applies_when") or item.get("rule") or "") for item in legacy_rules[:5]],
        current_observations=[f"legacy_rule_count={len(legacy_rules)}"],
    )


def _rule(
    *,
    rule_id: str,
    rule_type: str,
    target_view: str,
    horizon: str,
    status: str,
    progress: float,
    severity: str,
    reason: str,
    required_layers: list[str],
    observed_modules: list[Any],
    btc_response: dict[str, Any],
    required_modules: list[Any] | None = None,
    missing_evidence: list[str] | None = None,
    trigger_conditions: list[str] | None = None,
    current_observations: list[str] | None = None,
) -> dict[str, Any]:
    if status not in RULE_STATUSES:
        status = "not_armed"
    valid_until = datetime.now(UTC) + timedelta(hours=4 if horizon in {"4h", "1h"} else 24)
    return {
        "rule_id": rule_id,
        "rule_type": rule_type,
        "target_view": target_view,
        "horizon": horizon,
        "status": status,
        "progress": _round(progress, 2),
        "severity": severity,
        "required_layers": required_layers,
        "required_modules": [item for item in (required_modules or []) if item],
        "observed_modules": [item for item in observed_modules if item],
        "missing_evidence": missing_evidence or [],
        "trigger_conditions": trigger_conditions or [],
        "current_observations": current_observations or [reason],
        "btc_response_gate": {
            "required": True,
            "passed": not btc_response.get("missing_btc_response"),
            "reason": "BTC response is available." if not btc_response.get("missing_btc_response") else "BTC response is missing; rule cannot trigger.",
        },
        "residual_gate": {
            "required": True,
            "passed": not btc_response.get("missing_residual"),
            "direction": str((btc_response.get("residual") or {}).get("direction") or "unknown"),
        },
        "evidence_ids": _rule_evidence_ids(observed_modules),
        "data_quality_flags": [],
        "valid_until": valid_until.isoformat(),
        "reason": reason,
    }


def _validation_state(
    *,
    current_thesis: dict[str, Any],
    scores: dict[str, float],
    btc_response: dict[str, Any],
    quality_blocked: bool,
    triggered_rules: list[dict[str, Any]],
) -> tuple[str, str]:
    if quality_blocked:
        return "blocked", "Data quality or contract validation blocks trend validation."
    if btc_response.get("missing_btc_response") or btc_response.get("missing_residual"):
        return "watching", "BTC response or residual is missing, so rules may arm but cannot trigger."
    if scores["confirmation_score"] >= 65 and scores["btc_response_score"] >= 60 and scores["conflict_score"] <= 35:
        if any(rule.get("rule_type") == "confirmation" for rule in triggered_rules):
            return "confirmed", "Current thesis is confirmed by module evidence plus BTC response and residual gates."
    if scores["invalidation_score"] >= 65 and scores["residual_rejection_score"] >= 60:
        if any(rule.get("rule_type") == "invalidation" for rule in triggered_rules):
            return "refuted", "Current thesis is refuted by BTC response mismatch and residual rejection."
    if scores["confirmation_score"] >= 45 and scores["invalidation_score"] >= 45 or scores["conflict_score"] >= 45:
        return "conflict", "Confirmation and invalidation evidence coexist; Workbench will not force a direction."
    headline = str(current_thesis.get("headline_state") or "neutral")
    return "watching", f"Current thesis {headline} is not fully confirmed or refuted."


def _timeline(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {name: index for index, name in enumerate(["not_armed", "arming", "armed", "triggered", "rejected", "blocked", "expired"])}
    items = sorted(rules, key=lambda item: order.get(str(item.get("status")), 99))
    return [
        {
            "rule_id": item.get("rule_id"),
            "status": item.get("status"),
            "rule_type": item.get("rule_type"),
            "target_view": item.get("target_view"),
            "progress": item.get("progress"),
            "valid_until": item.get("valid_until"),
        }
        for item in items
    ]


def _quality_blocked(
    contract_validation: dict[str, Any] | None,
    data_quality_penalty: float,
    signals: list[dict[str, Any]],
) -> bool:
    if str((contract_validation or {}).get("status") or "passed") not in {"passed", "ok"}:
        return True
    if data_quality_penalty >= 50:
        return True
    return bool(signals) and not any(item.get("quality_status") != "failed" for item in signals)


def _data_quality_penalty(
    signals: list[dict[str, Any]],
    data_quality: dict[str, Any] | None,
    scores: dict[str, Any],
) -> float:
    explicit = scores.get("data_quality_penalty")
    if explicit is not None:
        return _num(explicit)
    failed = sum(1 for item in signals if item.get("quality_status") == "failed")
    stale = sum(1 for item in signals if item.get("quality_status") == "stale")
    unavailable = _num((data_quality or {}).get("unavailable_metric_count"))
    return min(60.0, failed * 12.0 + stale * 6.0 + min(12.0, unavailable))


def _btc_response_score(btc_response: dict[str, Any]) -> float:
    price = (btc_response.get("price_acceptance") or {}).get("score")
    if price is None:
        return 0.0
    return min(100.0, abs(_num(price)))


def _residual_rejection_score(btc_response: dict[str, Any], signals: list[dict[str, Any]]) -> float:
    rejected = sum(1 for item in signals if item.get("accepted_status") == "rejected")
    residual = _num((btc_response.get("residual") or {}).get("score"))
    return min(100.0, abs(residual) + rejected * 15.0)


def _response_passed(required_direction: str, btc_response: dict[str, Any]) -> bool:
    direction = str((btc_response.get("price_acceptance") or {}).get("direction") or "neutral")
    score = _num((btc_response.get("price_acceptance") or {}).get("score"))
    if required_direction == "bullish":
        return direction == "bullish" and score >= 15
    if required_direction == "bearish":
        return direction == "bearish" and score <= -15
    return False


def _residual_passed(required_direction: str, btc_response: dict[str, Any]) -> bool:
    direction = str((btc_response.get("residual") or {}).get("direction") or "flat")
    if required_direction == "bullish":
        return direction == "positive"
    if required_direction == "bearish":
        return direction == "negative"
    return False


def _signals_by_direction(
    signals: list[dict[str, Any]],
    direction: str,
    *,
    layers: set[str],
) -> list[dict[str, Any]]:
    return [
        item
        for item in signals
        if item.get("effective_direction") == direction
        and _trigger_eligible(
            str(item.get("effective_direction") or "neutral"),
            str(item.get("accepted_status") or "unknown"),
            str(item.get("quality_status") or "partial"),
            item,
        )
        and item.get("layer") in layers
    ]


def _observed_modules(signals: list[dict[str, Any]]) -> list[Any]:
    return [item.get("module_name") for item in signals if item.get("module_name")]


def _modules_with_quality_issue(signals: list[dict[str, Any]]) -> list[Any]:
    return [
        item.get("module_name")
        for item in signals
        if item.get("quality_status") in {"failed", "stale"}
    ]


def _missing_evidence(
    response_passed: bool,
    residual_passed: bool,
    enough_modules: bool,
    btc_response: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    if btc_response.get("missing_btc_response"):
        missing.append("btc_response")
    elif not response_passed:
        missing.append("btc_price_acceptance")
    if btc_response.get("missing_residual"):
        missing.append("residual")
    elif not residual_passed:
        missing.append("residual_alignment")
    if not enough_modules:
        missing.append("two_aligned_modules")
    return missing


def _current_observations(
    fast: list[dict[str, Any]],
    confirming: list[dict[str, Any]],
    btc_response: dict[str, Any],
) -> list[str]:
    return [
        f"fast_modules={','.join(str(item.get('module_name')) for item in fast[:3]) or 'none'}",
        f"confirmation_modules={','.join(str(item.get('module_name')) for item in confirming[:3]) or 'none'}",
        f"price_acceptance={(btc_response.get('price_acceptance') or {}).get('direction')}",
        f"residual={(btc_response.get('residual') or {}).get('direction')}",
    ]


def _rule_reason(
    required_direction: str,
    status: str,
    btc_response: dict[str, Any],
    enough_modules: bool,
) -> str:
    if status == "triggered":
        return f"{required_direction} thesis passed module, BTC response and residual gates."
    if btc_response.get("missing_btc_response") or btc_response.get("missing_residual"):
        return "Rule is armed but cannot trigger without BTC response and residual."
    if not enough_modules:
        return "Rule lacks at least two aligned modules."
    if status == "rejected":
        return "Module evidence is not accepted by BTC response or residual."
    return "Rule is waiting for stronger alignment."


def _accepted_level(direction: str, score: float | None) -> str:
    if score is None:
        return "unknown"
    if direction == "bullish":
        return "upside_acceptance"
    if direction == "bearish":
        return "downside_acceptance"
    return "neutral_acceptance"


def _liquidity_survival(items: list[dict[str, Any]]) -> str:
    if any(item.get("accepted_status") == "accepted" for item in items):
        return "accepted"
    if any(item.get("accepted_status") == "rejected" for item in items):
        return "absorbed"
    if not items:
        return "unknown"
    return "thin" if any(item.get("quality_status") == "stale" for item in items) else "unknown"


def _rejection_reason(signal: dict[str, Any]) -> str:
    if signal.get("accepted_status") == "rejected":
        return "BTC response or residual rejects module direction."
    if signal.get("quality_status") in {"failed", "stale"}:
        return "Data quality prevents full validation."
    if signal.get("effective_direction") == "conflict":
        return "Module reports conflict."
    return ""


def _evidence_ids(signal: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("evidence_id", "evidence_ids"):
        value = signal.get(key)
        if isinstance(value, str):
            ids.append(value)
        elif isinstance(value, list):
            ids.extend(str(item) for item in value[:5])
    return ids


def _rule_evidence_ids(observed_modules: list[Any]) -> list[str]:
    return [f"module:{item}" for item in observed_modules if item][:12]


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload or {}, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _num(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _round(value: float | None, digits: int = 2) -> float:
    return round(float(value or 0.0), digits)
