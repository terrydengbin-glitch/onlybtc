from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.direct_trend.evidence import BTC_DIRECT_TREND_EVIDENCE_MODULE_ID

BTC_DIRECT_EVIDENCE_REGISTRY_MODULE_ID = "btc_direct_evidence_registry"
BTC_DIRECT_EVIDENCE_REGISTRY_SCHEMA_VERSION = "p2.c43.direct_evidence_registry.v1"


@dataclass(frozen=True)
class DirectEvidenceRegistryEntry:
    feature_id: str
    role: str
    horizons: tuple[str, ...]
    freshness_tier: str
    direction_semantics: str
    source_cadence: str
    expected_update_sec: int
    stale_after_sec: int
    blocking_level: str
    fallback_policy: str
    required_for: tuple[str, ...]
    affects_direction: bool
    affects_confidence: bool
    notes: str
    event_phase_roles: dict[str, str] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["horizons"] = list(self.horizons)
        payload["required_for"] = list(self.required_for)
        return payload


def direct_evidence_registry() -> dict[str, DirectEvidenceRegistryEntry]:
    entries = [
        _entry(
            "btc_direct_trend.price_structure.btc_return_4h",
            "trigger_eligible",
            ("4h",),
            "fast",
            "positive_bullish_negative_bearish",
            "fast",
            60 * 60,
            75 * 60,
            "block_confirmed",
            "drop_metric",
            ("4h_direction",),
            True,
            True,
            "Direct 4h price structure input.",
        ),
        _entry(
            "btc_direct_trend.price_structure.btc_return_24h",
            "trigger_eligible",
            ("1d",),
            "fast",
            "positive_bullish_negative_bearish",
            "fast",
            60 * 60,
            75 * 60,
            "block_confirmed",
            "drop_metric",
            ("1d_direction",),
            True,
            True,
            "Direct 1d persistence price input.",
        ),
        _entry(
            "btc_direct_trend.orderflow_acceptance.taker_buy_sell_ratio",
            "acceptance_gate",
            ("4h",),
            "fast",
            "above_one_buy_dominant_below_one_sell_dominant",
            "confirmation",
            5 * 60,
            30 * 60,
            "block_confirmed",
            "use_previous_with_stale_flag",
            ("4h_acceptance",),
            False,
            True,
            "Market acceptance input; not a standalone direction trigger.",
        ),
        _entry(
            "btc_direct_trend.orderflow_acceptance.taker_delta_quote",
            "acceptance_gate",
            ("4h",),
            "fast",
            "positive_buy_pressure_negative_sell_pressure",
            "confirmation",
            5 * 60,
            30 * 60,
            "block_confirmed",
            "use_proxy",
            ("4h_acceptance",),
            False,
            True,
            "Proxy from taker ratio and quote volume; not full OFI/MLOFI.",
        ),
        _entry(
            "btc_direct_trend.orderflow_acceptance.cvd_slope_z",
            "acceptance_gate",
            ("4h",),
            "fast",
            "positive_accumulation_negative_distribution",
            "confirmation",
            5 * 60,
            30 * 60,
            "block_confirmed",
            "use_proxy",
            ("4h_acceptance",),
            False,
            True,
            "CVD slope proxy; requires explicit proxy labeling.",
        ),
        *_single_point_context_entries(),
        _entry(
            "btc_direct_trend.derivatives_positioning.price_oi_interaction_state",
            "trigger_eligible",
            ("4h",),
            "fast",
            "composite_price_oi_taker_semantic",
            "derived",
            60 * 60,
            75 * 60,
            "block_confirmed",
            "drop_metric",
            ("4h_direction", "4h_acceptance"),
            True,
            True,
            "Composite semantic allowed to trigger; raw OI/funding remain context only.",
        ),
        _entry(
            "btc_direct_trend.btc_residual_cross_asset.expected_return_24h",
            "radar_context",
            ("1d",),
            "regime",
            "cross_asset_expected_return_context",
            "regime",
            24 * 60 * 60,
            36 * 60 * 60,
            "degrade",
            "use_previous_with_stale_flag",
            ("1d_direction",),
            False,
            True,
            "Context for residual semantic; not direct direction alone.",
        ),
        _entry(
            "btc_direct_trend.btc_residual_cross_asset.residual_24h",
            "radar_context",
            ("1d",),
            "regime",
            "positive_resilience_negative_underperformance",
            "regime",
            24 * 60 * 60,
            36 * 60 * 60,
            "degrade",
            "use_previous_with_stale_flag",
            ("1d_direction",),
            False,
            True,
            "Residual value must feed composite residual_semantic before direction use.",
        ),
        _entry(
            "btc_direct_trend.btc_residual_cross_asset.residual_z",
            "radar_context",
            ("1d",),
            "regime",
            "positive_resilience_negative_underperformance",
            "regime",
            24 * 60 * 60,
            36 * 60 * 60,
            "degrade",
            "use_previous_with_stale_flag",
            ("1d_direction",),
            False,
            True,
            "Z-scored residual context; not standalone trigger.",
        ),
        _entry(
            "btc_direct_trend.btc_residual_cross_asset.residual_semantic",
            "trigger_eligible",
            ("1d",),
            "regime",
            "composite_external_pressure_vs_btc_response",
            "derived",
            24 * 60 * 60,
            36 * 60 * 60,
            "degrade",
            "use_previous_with_stale_flag",
            ("1d_direction", "1d_acceptance"),
            True,
            True,
            "Composite semantic allowed for 1d direction/persistence.",
        ),
        *_event_overlay_entries(),
    ]
    return {entry.feature_id: entry for entry in entries}


def registry_entry_for_feature(feature_id: str) -> DirectEvidenceRegistryEntry | None:
    return direct_evidence_registry().get(feature_id)


def build_direct_evidence_registry(
    evidence_run_id: str | None = None,
    registry_run_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    registry_run_id = registry_run_id or _generate_registry_run_id()
    registry = direct_evidence_registry()
    with db.session() as session:
        evidence_run_id = evidence_run_id or _latest_direct_evidence_run_id(session)
        evidence_rows = _evidence_rows(session, evidence_run_id) if evidence_run_id else []
        audit_rows = [_audit_row(row, registry) for row in evidence_rows]
        missing_in_latest = sorted(set(registry) - {row.feature_id for row in evidence_rows})
        unregistered_latest = sorted(
            row.feature_id for row in evidence_rows if row.feature_id not in registry
        )
        payload = {
            "schema_version": BTC_DIRECT_EVIDENCE_REGISTRY_SCHEMA_VERSION,
            "registry_run_id": registry_run_id,
            "evidence_run_id": evidence_run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "source_layer": "p2_direct_evidence_registry",
            "entries": [entry.to_payload() for entry in registry.values()],
            "latest_evidence_audit": audit_rows,
            "summary": {
                "registry_count": len(registry),
                "latest_evidence_count": len(evidence_rows),
                "missing_in_latest": missing_in_latest,
                "unregistered_latest": unregistered_latest,
                "role_counts": _role_counts(registry.values()),
                "trigger_eligible_count": sum(
                    1 for entry in registry.values() if entry.role == "trigger_eligible"
                ),
                "event_overlay_direction_default": "disabled",
            },
        }
        session.add(
            schema.ModuleJsonOutput(
                run_id=registry_run_id,
                module_id=BTC_DIRECT_EVIDENCE_REGISTRY_MODULE_ID,
                schema_version=BTC_DIRECT_EVIDENCE_REGISTRY_SCHEMA_VERSION,
                payload=payload,
            )
        )
    return payload


def _single_point_context_entries() -> tuple[DirectEvidenceRegistryEntry, ...]:
    specs = (
        ("oi_impulse_z_15m", "confirmation", 15 * 60, 30 * 60),
        ("oi_impulse_z_1h", "confirmation", 60 * 60, 75 * 60),
        ("oi_impulse_z_4h", "confirmation", 60 * 60, 75 * 60),
        ("funding_rate_8h_equiv_z", "regime", 8 * 60 * 60, 10 * 60 * 60),
        ("funding_acceleration_z_24h", "regime", 8 * 60 * 60, 10 * 60 * 60),
        ("liquidation_followthrough_score", "confirmation", 15 * 60, 30 * 60),
        ("liquidation_absorption_score", "confirmation", 15 * 60, 30 * 60),
    )
    return tuple(
        _entry(
            f"btc_direct_trend.derivatives_positioning.{name}",
            "radar_context" if name.startswith(("oi_", "funding_")) else "acceptance_gate",
            ("4h",),
            "fast" if cadence == "confirmation" else "regime",
            "single_point_derivatives_context",
            cadence,
            expected,
            stale,
            "degrade" if name.startswith(("oi_", "funding_")) else "block_confirmed",
            "use_previous_with_stale_flag",
            ("4h_acceptance",),
            False,
            True,
            "Single-point derivatives metric cannot trigger direction by itself.",
        )
        for name, cadence, expected, stale in specs
    )


def _event_overlay_entries() -> tuple[DirectEvidenceRegistryEntry, ...]:
    common_phase_roles = {
        "pre_event": "trust_cap",
        "post_event_unconfirmed": "trust_cap",
        "post_event_accepted": "acceptance_gate",
    }
    specs = (
        ("emergency_level", "quality_gate", "event_risk_blocks_or_degrades_horizon"),
        ("ordinary_radar_trust", "trust_cap", "caps_radar_context_trust"),
        ("trade_permission_modifier", "trust_cap", "caps_trade_permission"),
        ("event_trust_cap", "trust_cap", "caps_direct_evidence_confidence"),
        ("post_event_reaction_state", "trust_cap", "reaction_context_requires_btc_validation"),
    )
    return tuple(
        _entry(
            f"btc_direct_trend.event_overlay_context.{name}",
            role,
            ("4h", "1d"),
            "event",
            semantics,
            "event",
            60 * 60,
            6 * 60 * 60,
            "block_confirmed" if role == "quality_gate" else "degrade",
            "use_previous_with_stale_flag",
            ("4h_direction", "1d_direction"),
            False,
            True,
            "Event overlay does not affect direction by default.",
            event_phase_roles=common_phase_roles,
        )
        for name, role, semantics in specs
    )


def _entry(
    feature_id: str,
    role: str,
    horizons: tuple[str, ...],
    freshness_tier: str,
    direction_semantics: str,
    source_cadence: str,
    expected_update_sec: int,
    stale_after_sec: int,
    blocking_level: str,
    fallback_policy: str,
    required_for: tuple[str, ...],
    affects_direction: bool,
    affects_confidence: bool,
    notes: str,
    event_phase_roles: dict[str, str] | None = None,
) -> DirectEvidenceRegistryEntry:
    return DirectEvidenceRegistryEntry(
        feature_id=feature_id,
        role=role,
        horizons=horizons,
        freshness_tier=freshness_tier,
        direction_semantics=direction_semantics,
        source_cadence=source_cadence,
        expected_update_sec=expected_update_sec,
        stale_after_sec=stale_after_sec,
        blocking_level=blocking_level,
        fallback_policy=fallback_policy,
        required_for=required_for,
        affects_direction=affects_direction,
        affects_confidence=affects_confidence,
        notes=notes,
        event_phase_roles=event_phase_roles or {},
    )


def _latest_direct_evidence_run_id(session) -> str | None:
    return session.scalar(
        select(schema.FeatureValue.run_id)
        .where(schema.FeatureValue.module_id == BTC_DIRECT_TREND_EVIDENCE_MODULE_ID)
        .group_by(schema.FeatureValue.run_id)
        .having(func.count(schema.FeatureValue.id) > 0)
        .order_by(func.max(schema.FeatureValue.created_at).desc())
        .limit(1)
    )


def _evidence_rows(session, evidence_run_id: str) -> list[schema.FeatureValue]:
    return session.scalars(
        select(schema.FeatureValue)
        .where(
            schema.FeatureValue.run_id == evidence_run_id,
            schema.FeatureValue.module_id == BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
        )
        .order_by(schema.FeatureValue.feature_id)
    ).all()


def _audit_row(
    row: schema.FeatureValue,
    registry: dict[str, DirectEvidenceRegistryEntry],
) -> dict[str, Any]:
    metadata = row.metadata_json or {}
    entry = registry.get(row.feature_id)
    if entry is None:
        return {
            "feature_id": row.feature_id,
            "registered": False,
            "used_by_default": False,
            "ignore_reason": "not_registered",
            "freshness_state": metadata.get("freshness_state"),
        }
    freshness_state = metadata.get("freshness_state")
    blocked = _is_blocked(entry, freshness_state)
    return {
        "feature_id": row.feature_id,
        "registered": True,
        "role": entry.role,
        "horizons": list(entry.horizons),
        "required_for": list(entry.required_for),
        "freshness_state": freshness_state,
        "blocking_level": entry.blocking_level,
        "used_by_default": entry.affects_direction and not blocked,
        "ignore_reason": _ignore_reason(entry, freshness_state, blocked),
        "source_cadence": entry.source_cadence,
        "direction_semantics": entry.direction_semantics,
        "source_asof_ts": metadata.get("source_asof_ts"),
        "valid_until": metadata.get("valid_until"),
    }


def _is_blocked(entry: DirectEvidenceRegistryEntry, freshness_state: Any) -> bool:
    if freshness_state in {"missing", "stale", "blocked"}:
        return entry.blocking_level in {"block_confirmed", "block_all"}
    return False


def _ignore_reason(
    entry: DirectEvidenceRegistryEntry,
    freshness_state: Any,
    blocked: bool,
) -> str | None:
    if blocked:
        return f"{freshness_state}_{entry.blocking_level}"
    if entry.role in {"radar_context", "context_only", "trust_cap", "quality_gate"}:
        return f"role_{entry.role}_not_direction_trigger"
    if not entry.affects_direction:
        return "acceptance_or_confidence_only"
    return None


def _role_counts(entries) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.role] = counts.get(entry.role, 0) + 1
    return counts


def _generate_registry_run_id() -> str:
    return f"p2c43-registry-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
