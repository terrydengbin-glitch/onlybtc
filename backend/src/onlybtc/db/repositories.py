from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from onlybtc.db import schema
from onlybtc.domain.models import RunStage as DomainRunStage
from onlybtc.domain.models import RunState


def _stable_payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _nullable_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _nullable_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_run_state(self, run_state: RunState) -> RunState:
        db_run = self.session.scalar(
            select(schema.Run).where(schema.Run.run_id == run_state.run_id)
        )
        now = datetime.now(UTC)
        completed_at = now if run_state.status == "completed" else None

        if db_run is None:
            db_run = schema.Run(
                run_id=run_state.run_id,
                trigger=run_state.trigger,
                status=run_state.status,
                current_stage=run_state.current_stage,
                started_at=run_state.created_at,
                completed_at=completed_at,
            )
            self.session.add(db_run)
        else:
            db_run.status = run_state.status
            db_run.current_stage = run_state.current_stage
            db_run.completed_at = completed_at

        existing_stages = {
            item.stage_name: item
            for item in self.session.scalars(
                select(schema.RunStage).where(schema.RunStage.run_id == run_state.run_id)
            )
        }
        for stage in run_state.stages:
            db_stage = existing_stages.get(stage.name)
            if db_stage is None:
                db_stage = schema.RunStage(
                    run_id=run_state.run_id,
                    stage_name=stage.name,
                    status=stage.status,
                    started_at=stage.started_at,
                    completed_at=stage.completed_at,
                    detail=stage.detail,
                )
                self.session.add(db_stage)
            else:
                db_stage.status = stage.status
                db_stage.started_at = stage.started_at
                db_stage.completed_at = stage.completed_at
                db_stage.detail = stage.detail

        self.session.add(
            schema.RunLog(
                run_id=run_state.run_id,
                stage_name=run_state.current_stage,
                level="INFO",
                message=f"Run stage updated: {run_state.current_stage}",
            )
        )
        return run_state

    def get(self, run_id: str) -> RunState | None:
        db_run = self.session.scalar(self._run_query().where(schema.Run.run_id == run_id))
        return self._to_domain(db_run) if db_run else None

    def latest(self) -> RunState | None:
        db_run = self.session.scalar(
            self._run_query().order_by(schema.Run.created_at.desc()).limit(1)
        )
        return self._to_domain(db_run) if db_run else None

    def list_recent(self, limit: int = 20) -> list[RunState]:
        db_runs = self.session.scalars(
            self._run_query().order_by(schema.Run.created_at.desc()).limit(limit)
        ).all()
        return [self._to_domain(db_run) for db_run in db_runs]

    def _run_query(self) -> Select[tuple[schema.Run]]:
        return select(schema.Run).options(selectinload(schema.Run.stages))

    def _to_domain(self, db_run: schema.Run) -> RunState:
        stages = [
            DomainRunStage(
                name=stage.stage_name,
                status=stage.status,
                started_at=stage.started_at,
                completed_at=stage.completed_at,
                detail=stage.detail,
            )
            for stage in sorted(db_run.stages, key=lambda item: item.id)
        ]
        return RunState(
            run_id=db_run.run_id,
            trigger=db_run.trigger,
            status=db_run.status,
            created_at=db_run.created_at,
            updated_at=db_run.updated_at,
            current_stage=db_run.current_stage,
            stages=stages,
        )


class EventWatchtowerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = payload.get("state") or {}
        overlay = payload.get("overlay") or {}
        active_event = payload.get("active_event") or {}
        daemon = payload.get("daemon") or {}
        asof_ts = _parse_datetime(payload.get("asof_ts")) or datetime.now(UTC)
        snapshot_id = str(
            payload.get("snapshot_id")
            or f"evt-{asof_ts.strftime('%Y%m%d%H%M%S')}-{_stable_payload_hash(payload)[:8]}"
        )
        payload["snapshot_id"] = snapshot_id
        payload["asof_ts"] = asof_ts.isoformat()
        payload_hash = _stable_payload_hash(payload)
        existing = self.session.scalar(
            select(schema.EventWatchtowerSnapshot).where(
                schema.EventWatchtowerSnapshot.snapshot_id == snapshot_id
            )
        )
        row = existing or schema.EventWatchtowerSnapshot(
            snapshot_id=snapshot_id,
            asof_ts=asof_ts,
            payload_hash=payload_hash,
        )
        row.asof_ts = asof_ts
        row.daemon_status = str(daemon.get("status") or "running")
        row.event_window_state = str(state.get("event_window_state") or "event_neutral")
        row.emergency_level = str(state.get("emergency_level") or "none")
        row.trade_permission_modifier = str(overlay.get("trade_permission_modifier") or "none")
        row.ordinary_radar_trust = str(overlay.get("ordinary_radar_trust") or "normal")
        row.active_event_id = str(active_event.get("event_id") or "") or None
        row.payload_hash = payload_hash
        row.payload_json = payload
        self.session.add(row)
        self._upsert_calendar_items(payload.get("calendar_items") or [])
        self._upsert_expectations(payload.get("expectation_snapshots") or [])
        self._upsert_official_texts(payload.get("official_text_items") or [])
        self._upsert_llm_analyses(payload.get("llm_analyses") or [])
        self._upsert_market_probes(payload.get("market_probes") or [], snapshot_id=snapshot_id)
        self._upsert_shocks(payload.get("shock_lane_items") or [])
        self._upsert_reactions(payload.get("post_event_reactions") or [])
        self._upsert_alerts(payload.get("alerts") or [], snapshot_id=snapshot_id)
        self._upsert_source_fetches(payload.get("source_fetches") or [])
        return payload

    def latest_snapshot(self) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.EventWatchtowerSnapshot)
            .order_by(schema.EventWatchtowerSnapshot.asof_ts.desc())
            .limit(1)
        )
        return dict(row.payload_json) if row else None

    def snapshot_by_id(self, snapshot_id: str) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.EventWatchtowerSnapshot).where(
                schema.EventWatchtowerSnapshot.snapshot_id == snapshot_id
            )
        )
        return dict(row.payload_json) if row else None

    def list_snapshots(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventWatchtowerSnapshot)
            .order_by(schema.EventWatchtowerSnapshot.asof_ts.desc())
            .limit(limit)
        ).all()
        return [dict(row.payload_json) for row in rows]

    def list_calendar(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventCalendarItem)
            .order_by(schema.EventCalendarItem.release_time_utc.asc())
            .limit(limit)
        ).all()
        return [self._calendar_payload(row) for row in rows]

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.EventCalendarItem).where(schema.EventCalendarItem.event_id == event_id)
        )
        return self._calendar_payload(row) if row else None

    def event_expectations(self, event_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventExpectationSnapshot)
            .where(schema.EventExpectationSnapshot.event_id == event_id)
            .order_by(schema.EventExpectationSnapshot.snapshot_ts.desc())
            .limit(limit)
        ).all()
        return [dict(row.payload_json) for row in rows]

    def event_reactions(self, event_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventPostReactionSnapshot)
            .where(schema.EventPostReactionSnapshot.event_id == event_id)
            .order_by(schema.EventPostReactionSnapshot.snapshot_ts.desc())
            .limit(limit)
        ).all()
        return [dict(row.payload_json) for row in rows]

    def list_speeches(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventOfficialTextItem)
            .order_by(schema.EventOfficialTextItem.published_at.desc())
            .limit(limit)
        ).all()
        return [dict(row.payload_json) for row in rows]

    def get_speech(self, text_id: str) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.EventOfficialTextItem).where(
                schema.EventOfficialTextItem.text_id == text_id
            )
        )
        return dict(row.payload_json) if row else None

    def list_shocks(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventShockLaneItem)
            .order_by(schema.EventShockLaneItem.detected_at.desc())
            .limit(limit)
        ).all()
        return [dict(row.payload_json) for row in rows]

    def latest_shock(self) -> dict[str, Any] | None:
        rows = self.list_shocks(limit=1)
        return rows[0] if rows else None

    def list_market_probes(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventMarketProbe)
            .order_by(schema.EventMarketProbe.collected_at.desc())
            .limit(limit)
        ).all()
        return [dict(row.payload_json) for row in rows]

    def latest_market_probe(self) -> dict[str, Any] | None:
        rows = self.list_market_probes(limit=1)
        return rows[0] if rows else None

    def list_alerts(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = select(schema.EventAlert).order_by(schema.EventAlert.created_ts.desc()).limit(limit)
        if status:
            query = query.where(schema.EventAlert.status == status)
        rows = self.session.scalars(query).all()
        return [dict(row.payload_json, status=row.status) for row in rows]

    def ack_alert(self, alert_id: str) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.EventAlert).where(schema.EventAlert.alert_id == alert_id)
        )
        if row is None:
            return None
        row.status = "acked"
        row.acked_at = datetime.now(UTC)
        payload = dict(row.payload_json)
        payload["status"] = row.status
        payload["acked_at"] = row.acked_at.isoformat()
        row.payload_json = payload
        self.session.add(row)
        return payload

    def mute_alert(self, alert_id: str, muted_until: datetime) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.EventAlert).where(schema.EventAlert.alert_id == alert_id)
        )
        if row is None:
            return None
        row.status = "muted"
        row.muted_until = muted_until
        payload = dict(row.payload_json)
        payload["status"] = row.status
        payload["muted_until"] = muted_until.isoformat()
        row.payload_json = payload
        self.session.add(row)
        return payload

    def timeline(self, limit: int = 200) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        latest = self.latest_snapshot()
        if latest:
            items.append(
                {
                    "ts": latest.get("asof_ts"),
                    "type": "snapshot",
                    "level": (latest.get("state") or {}).get("emergency_level", "none"),
                    "title": "Watchtower snapshot",
                    "payload": latest,
                }
            )
        for alert in self.list_alerts(limit=limit):
            items.append(
                {
                    "ts": alert.get("created_ts"),
                    "type": "alert",
                    "level": alert.get("emergency_level"),
                    "title": alert.get("title"),
                    "payload": alert,
                }
            )
        for shock in self.list_shocks(limit=limit):
            items.append(
                {
                    "ts": shock.get("detected_at"),
                    "type": "shock",
                    "level": shock.get("emergency_level"),
                    "title": shock.get("shock_type", "shock"),
                    "payload": shock,
                }
            )
        for probe in self.list_market_probes(limit=limit):
            items.append(
                {
                    "ts": probe.get("collected_at"),
                    "type": "market_probe",
                    "level": "info",
                    "title": "BTC market probe",
                    "payload": probe,
                }
            )
        items.sort(key=lambda item: str(item.get("ts") or ""), reverse=True)
        return items[:limit]

    def list_source_fetches(
        self,
        source_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = select(schema.EventSourceFetch).order_by(schema.EventSourceFetch.started_at.desc())
        if source_id:
            query = query.where(schema.EventSourceFetch.source_id == source_id)
        rows = self.session.scalars(query.limit(limit)).all()
        return [dict(row.payload_json) for row in rows]

    def source_diagnostics(self) -> dict[str, Any]:
        rows = self.session.scalars(
            select(schema.EventSourceFetch).order_by(schema.EventSourceFetch.started_at.desc())
        ).all()
        latest_by_source: dict[str, schema.EventSourceFetch] = {}
        last_success: dict[str, str] = {}
        for row in rows:
            if row.source_id not in latest_by_source:
                latest_by_source[row.source_id] = row
            if row.status == "success" and row.source_id not in last_success:
                last_success[row.source_id] = row.finished_at.isoformat() if row.finished_at else ""
        sources = []
        counts = {"live": 0, "partial": 0, "fallback": 0, "failed": 0}
        for _source_id, row in sorted(latest_by_source.items()):
            if row.status == "success" and not row.fallback_used:
                mode = "live"
            elif row.status in {"partial", "throttled", "backoff", "skipped_not_due"}:
                mode = "partial"
            elif row.fallback_used or row.status == "fallback_used":
                mode = "fallback"
            else:
                mode = "failed"
            counts[mode] += 1
            sources.append(
                {
                    "source_id": row.source_id,
                    "source_tier": row.source_tier,
                    "status": row.status,
                    "source_mode": mode,
                    "endpoint_url": row.endpoint_url,
                    "last_success_at": last_success.get(row.source_id, ""),
                    "last_attempt_at": row.started_at.isoformat() if row.started_at else "",
                    "last_error": row.error_message or row.error_code or "",
                    "parsed_item_count": row.parsed_item_count,
                    "fallback_used": row.fallback_used,
                    "throttle_status": (row.payload_json or {}).get("throttle_status"),
                    "cache_status": (row.payload_json or {}).get("cache_status"),
                    "next_allowed_at": (row.payload_json or {}).get("next_allowed_at"),
                    "last_http_status": (row.payload_json or {}).get("last_http_status") or row.http_status,
                    "blocked_reason": (row.payload_json or {}).get("blocked_reason"),
                    "skip_reason": (row.payload_json or {}).get("skip_reason"),
                    "source_group": (row.payload_json or {}).get("source_group"),
                }
            )
        if counts["live"] and (counts["partial"] or counts["fallback"] or counts["failed"]):
            overall = "partial"
        elif counts["live"]:
            overall = "live"
        elif counts["partial"]:
            overall = "partial"
        elif counts["fallback"]:
            overall = "fallback"
        elif counts["failed"]:
            overall = "failed"
        else:
            overall = "unknown"
        return {
            "schema_version": "p45.event_window.source_diagnostics.v1",
            "summary": {
                "live_source_count": counts["live"],
                "partial_source_count": counts["partial"],
                "fallback_source_count": counts["fallback"],
                "failed_source_count": counts["failed"],
                "overall_source_mode": overall,
            },
            "sources": sources,
        }

    def upsert_scheduler_state(
        self,
        states: dict[str, dict[str, Any]],
        *,
        cadence_profile: str = "balanced",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for source_group, item in sorted(states.items()):
            row = self.session.scalar(
                select(schema.EventSchedulerState).where(
                    schema.EventSchedulerState.source_group == source_group
                )
            )
            row = row or schema.EventSchedulerState(source_group=source_group)
            row.cadence_profile = str(item.get("cadence_profile") or cadence_profile)
            row.phase = str(item.get("phase") or "normal")
            row.interval_sec = int(item.get("interval_sec") or 300)
            row.next_due_at = _parse_datetime(item.get("next_due_at"))
            row.last_attempt_at = _parse_datetime(item.get("last_attempt_at"))
            row.last_success_at = _parse_datetime(item.get("last_success_at"))
            row.last_status = str(item.get("last_status") or "pending")
            row.last_fetch_id = _nullable_str(item.get("last_fetch_id"))
            row.payload_json = dict(item, source_group=source_group)
            self.session.add(row)
            rows.append(dict(row.payload_json))
        return rows

    def scheduler_state(self) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.EventSchedulerState).order_by(schema.EventSchedulerState.source_group.asc())
        ).all()
        return [dict(row.payload_json) for row in rows]

    def _upsert_calendar_items(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            event_id = str(item.get("event_id") or "")
            release_time = _parse_datetime(item.get("release_time") or item.get("release_time_utc"))
            if not event_id or release_time is None:
                continue
            row = self.session.scalar(
                select(schema.EventCalendarItem).where(
                    schema.EventCalendarItem.event_id == event_id
                )
            )
            if row is None:
                row = schema.EventCalendarItem(
                    event_id=event_id,
                    release_time_utc=release_time,
                    title="",
                )
            row.event_type = str(item.get("event_type") or "unknown")
            row.title = str(item.get("title") or event_id)
            row.importance = str(item.get("importance") or "medium")
            row.release_time_utc = release_time
            row.release_time_et = _nullable_str(item.get("release_time_et"))
            row.release_time_local = _nullable_str(item.get("release_time_local"))
            row.source_url = _nullable_str(item.get("source_url"))
            row.source_tier = str(item.get("source_tier") or "official")
            row.status = str(item.get("status") or "scheduled")
            row.payload_json = item
            self.session.add(row)

    def _upsert_expectations(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            snapshot_id = str(item.get("snapshot_id") or "")
            event_id = str(item.get("event_id") or "")
            snapshot_ts = _parse_datetime(item.get("snapshot_ts"))
            if not snapshot_id or not event_id or snapshot_ts is None:
                continue
            row = self.session.scalar(
                select(schema.EventExpectationSnapshot).where(
                    schema.EventExpectationSnapshot.snapshot_id == snapshot_id
                )
            )
            row = row or schema.EventExpectationSnapshot(
                snapshot_id=snapshot_id,
                event_id=event_id,
                snapshot_ts=snapshot_ts,
            )
            row.event_id = event_id
            row.snapshot_ts = snapshot_ts
            for key in (
                "consensus",
                "previous",
                "nowcast",
                "market_implied",
                "expectation_gap",
                "expectation_drift_1d",
                "expectation_drift_3d",
                "rate_cut_prob_drift_1d",
            ):
                setattr(row, key, _nullable_float(item.get(key)))
            row.risk_direction = str(item.get("risk_direction") or "unknown")
            row.payload_json = item
            self.session.add(row)

    def _upsert_official_texts(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            text_id = str(item.get("text_id") or "")
            if not text_id:
                continue
            text_hash = str(item.get("text_hash") or _stable_payload_hash(item))
            row = self.session.scalar(
                select(schema.EventOfficialTextItem).where(
                    schema.EventOfficialTextItem.text_id == text_id
                )
            )
            row = row or schema.EventOfficialTextItem(
                text_id=text_id,
                text_hash=text_hash,
                source_name="unknown",
                title=text_id,
            )
            row.text_hash = text_hash
            row.source_name = str(item.get("source_name") or "unknown")
            row.source_tier = str(item.get("source_tier") or "official")
            row.published_at = _parse_datetime(item.get("published_at"))
            row.speaker = _nullable_str(item.get("speaker"))
            row.title = str(item.get("title") or text_id)
            row.url = _nullable_str(item.get("url"))
            row.raw_text = _nullable_str(item.get("raw_text"))
            row.payload_json = item
            self.session.add(row)

    def _upsert_llm_analyses(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            analysis_id = str(item.get("analysis_id") or "")
            text_id = str(item.get("text_id") or "")
            analyzed_at = _parse_datetime(item.get("analyzed_at"))
            if not analysis_id or not text_id or analyzed_at is None:
                continue
            row = self.session.scalar(
                select(schema.EventLlmAnalysis).where(
                    schema.EventLlmAnalysis.analysis_id == analysis_id
                )
            )
            row = row or schema.EventLlmAnalysis(
                analysis_id=analysis_id,
                text_id=text_id,
                analyzed_at=analyzed_at,
            )
            row.text_id = text_id
            row.analyzed_at = analyzed_at
            row.speaker = _nullable_str(item.get("speaker"))
            row.speaker_weight = float(item.get("speaker_weight") or 0.0)
            row.tone = str(item.get("tone") or "ambiguous")
            row.tone_confidence = float(item.get("tone_confidence") or 0.0)
            row.policy_relevance = str(item.get("policy_relevance") or "low")
            row.requires_human_review = bool(item.get("requires_human_review"))
            row.payload_json = item
            self.session.add(row)

    def _upsert_market_probes(self, items: list[dict[str, Any]], snapshot_id: str) -> None:
        for item in items:
            probe_id = str(item.get("market_probe_id") or "")
            collected_at = _parse_datetime(item.get("collected_at"))
            if not probe_id or collected_at is None:
                continue
            row = self.session.scalar(
                select(schema.EventMarketProbe).where(
                    schema.EventMarketProbe.market_probe_id == probe_id
                )
            )
            row = row or schema.EventMarketProbe(
                market_probe_id=probe_id,
                collected_at=collected_at,
            )
            returns = item.get("returns") or {}
            row.snapshot_id = snapshot_id
            row.collected_at = collected_at
            row.symbol = str(item.get("symbol") or "BTCUSDT")
            row.source = str(item.get("source") or "binance")
            row.price = _nullable_float(item.get("price"))
            row.return_5m = _nullable_float(returns.get("5m"))
            row.return_15m = _nullable_float(returns.get("15m"))
            row.return_1h = _nullable_float(returns.get("1h"))
            row.return_4h = _nullable_float(returns.get("4h"))
            row.return_24h = _nullable_float(returns.get("24h"))
            row.payload_hash = _nullable_str(item.get("payload_hash"))
            row.payload_json = item
            self.session.add(row)

    def _upsert_shocks(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            shock_id = str(item.get("shock_id") or "")
            detected_at = _parse_datetime(item.get("detected_at"))
            if not shock_id or detected_at is None:
                continue
            row = self.session.scalar(
                select(schema.EventShockLaneItem).where(
                    schema.EventShockLaneItem.shock_id == shock_id
                )
            )
            row = row or schema.EventShockLaneItem(shock_id=shock_id, detected_at=detected_at)
            row.detected_at = detected_at
            row.shock_type = str(item.get("shock_type") or "unknown")
            row.emergency_level = str(item.get("emergency_level") or "watch")
            row.confirmation_level = str(item.get("confirmation_level") or "single_source")
            row.source_count = int(item.get("source_count") or 0)
            row.market_dislocation = bool(item.get("market_dislocation"))
            row.btc_microstructure_confirmation = bool(item.get("btc_microstructure_confirmation"))
            row.rumor_risk = bool(item.get("rumor_risk"))
            row.payload_json = item
            self.session.add(row)

    def _upsert_reactions(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            reaction_id = str(item.get("reaction_id") or "")
            event_id = str(item.get("event_id") or "")
            snapshot_ts = _parse_datetime(item.get("snapshot_ts"))
            if not reaction_id or not event_id or snapshot_ts is None:
                continue
            row = self.session.scalar(
                select(schema.EventPostReactionSnapshot).where(
                    schema.EventPostReactionSnapshot.reaction_id == reaction_id
                )
            )
            row = row or schema.EventPostReactionSnapshot(
                reaction_id=reaction_id,
                event_id=event_id,
                snapshot_ts=snapshot_ts,
            )
            row.event_id = event_id
            row.snapshot_ts = snapshot_ts
            for key in (
                "actual",
                "consensus",
                "surprise_raw",
                "surprise_z",
                "btc_return_5m",
                "btc_return_30m",
                "btc_return_2h",
            ):
                setattr(row, key, _nullable_float(item.get(key)))
            absorbed = item.get("btc_absorbed_shock")
            row.btc_absorbed_shock = None if absorbed is None else bool(absorbed)
            row.followthrough = str(item.get("followthrough") or "unknown")
            row.payload_json = item
            self.session.add(row)

    def _upsert_alerts(self, items: list[dict[str, Any]], snapshot_id: str) -> None:
        for item in items:
            alert_id = str(item.get("alert_id") or "")
            created_ts = _parse_datetime(item.get("created_ts"))
            if not alert_id or created_ts is None:
                continue
            row = self.session.scalar(
                select(schema.EventAlert).where(schema.EventAlert.alert_id == alert_id)
            )
            row = row or schema.EventAlert(
                alert_id=alert_id,
                created_ts=created_ts,
                title="",
                summary="",
            )
            row.snapshot_id = snapshot_id
            row.event_id = _nullable_str(item.get("event_id"))
            row.created_ts = created_ts
            row.emergency_level = str(item.get("emergency_level") or "watch")
            row.title = str(item.get("title") or alert_id)
            row.summary = str(item.get("summary") or "")
            row.reason_code = str(item.get("reason_code") or "calendar_monitor")
            row.status = str(item.get("status") or row.status or "open")
            row.payload_json = item
            self.session.add(row)

    def _upsert_source_fetches(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            fetch_id = str(item.get("fetch_id") or "")
            source_id = str(item.get("source_id") or "")
            started_at = _parse_datetime(item.get("started_at"))
            if not fetch_id or not source_id or started_at is None:
                continue
            row = self.session.scalar(
                select(schema.EventSourceFetch).where(schema.EventSourceFetch.fetch_id == fetch_id)
            )
            row = row or schema.EventSourceFetch(
                fetch_id=fetch_id,
                source_id=source_id,
                started_at=started_at,
            )
            row.source_id = source_id
            row.source_tier = str(item.get("source_tier") or "official")
            row.endpoint_url = _nullable_str(item.get("endpoint_url"))
            row.started_at = started_at
            row.finished_at = _parse_datetime(item.get("finished_at"))
            row.status = str(item.get("status") or "failed")
            row.http_status = (
                int(item["http_status"]) if item.get("http_status") is not None else None
            )
            row.error_code = _nullable_str(item.get("error_code"))
            row.error_message = _nullable_str(item.get("error_message"))
            row.payload_hash = _nullable_str(item.get("payload_hash"))
            row.parsed_item_count = int(item.get("parsed_item_count") or 0)
            row.fallback_used = bool(item.get("fallback_used"))
            row.payload_json = item
            self.session.add(row)

    @staticmethod
    def _calendar_payload(row: schema.EventCalendarItem) -> dict[str, Any]:
        payload = dict(row.payload_json)
        payload.setdefault("event_id", row.event_id)
        payload.setdefault("release_time", row.release_time_utc.isoformat())
        return payload


class TimescaleJudgeReplayRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_snapshot(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        asof_ts = _parse_datetime(payload.get("asof_ts")) or datetime.now(UTC)
        snapshot_id = str(
            payload.get("snapshot_id")
            or f"timescale-{asof_ts.strftime('%Y%m%d%H%M%S')}-{_stable_payload_hash(payload)[:8]}"
        )
        source_window = _timescale_source_window(payload)
        freshness_summary = dict(payload.get("freshness_summary") or {})
        row = self.session.scalar(
            select(schema.TimescaleJudgeSnapshot).where(
                schema.TimescaleJudgeSnapshot.run_id == run_id
            )
        )
        if row is None:
            row = schema.TimescaleJudgeSnapshot(
                snapshot_id=snapshot_id,
                run_id=run_id,
                asof_ts=asof_ts,
                schema_version=str(payload.get("schema_version") or "unknown"),
                payload_json=payload,
            )
            self.session.add(row)
        row.run_id = run_id
        row.asof_ts = asof_ts
        row.schema_version = str(payload.get("schema_version") or "unknown")
        row.payload_json = payload
        row.source_window_json = source_window
        row.freshness_summary_json = freshness_summary
        row.fallback_used = bool(payload.get("fallback_used"))
        row.fallback_reason = _nullable_str(payload.get("fallback_reason"))
        return self._to_payload(row)

    def latest(self) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.TimescaleJudgeSnapshot)
            .order_by(
                schema.TimescaleJudgeSnapshot.asof_ts.desc(),
                schema.TimescaleJudgeSnapshot.id.desc(),
            )
            .limit(1)
        )
        return self._to_payload(row) if row else None

    def by_snapshot_id(self, snapshot_id: str) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.TimescaleJudgeSnapshot)
            .where(
                schema.TimescaleJudgeSnapshot.snapshot_id == snapshot_id
            )
            .order_by(
                schema.TimescaleJudgeSnapshot.asof_ts.desc(),
                schema.TimescaleJudgeSnapshot.id.desc(),
            )
            .limit(1)
        )
        return self._to_payload(row) if row else None

    def by_run_id(self, run_id: str) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.TimescaleJudgeSnapshot)
            .where(schema.TimescaleJudgeSnapshot.run_id == run_id)
            .order_by(
                schema.TimescaleJudgeSnapshot.asof_ts.desc(),
                schema.TimescaleJudgeSnapshot.id.desc(),
            )
            .limit(1)
        )
        return self._to_payload(row) if row else None

    def at_or_before(self, asof_ts: datetime) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.TimescaleJudgeSnapshot)
            .where(schema.TimescaleJudgeSnapshot.asof_ts <= asof_ts)
            .order_by(
                schema.TimescaleJudgeSnapshot.asof_ts.desc(),
                schema.TimescaleJudgeSnapshot.id.desc(),
            )
            .limit(1)
        )
        return self._to_payload(row) if row else None

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.TimescaleJudgeSnapshot)
            .order_by(
                schema.TimescaleJudgeSnapshot.asof_ts.desc(),
                schema.TimescaleJudgeSnapshot.id.desc(),
            )
            .limit(limit)
        ).all()
        return [self._to_payload(row) for row in rows]

    def _to_payload(self, row: schema.TimescaleJudgeSnapshot) -> dict[str, Any]:
        return {
            "snapshot_id": row.snapshot_id,
            "run_id": row.run_id,
            "asof_ts": row.asof_ts.isoformat(),
            "schema_version": row.schema_version,
            "payload": row.payload_json,
            "source_window": row.source_window_json or {},
            "freshness_summary": row.freshness_summary_json or {},
            "fallback_used": row.fallback_used,
            "fallback_reason": row.fallback_reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def _timescale_source_window(payload: dict[str, Any]) -> dict[str, Any]:
    horizons = payload.get("horizons") or {}
    windows = [
        horizon.get("source_window") or {}
        for horizon in horizons.values()
        if isinstance(horizon, dict)
    ]
    min_values = [
        _parse_datetime(window.get("min_source_asof_ts"))
        for window in windows
        if window.get("min_source_asof_ts")
    ]
    max_values = [
        _parse_datetime(window.get("max_source_asof_ts"))
        for window in windows
        if window.get("max_source_asof_ts")
    ]
    lag_values = [
        _nullable_float(window.get("max_source_lag_sec"))
        for window in windows
        if window.get("max_source_lag_sec") is not None
    ]
    min_values = [item for item in min_values if item is not None]
    max_values = [item for item in max_values if item is not None]
    lag_values = [item for item in lag_values if item is not None]
    return {
        "min_source_asof_ts": min(min_values).isoformat() if min_values else None,
        "max_source_asof_ts": max(max_values).isoformat() if max_values else None,
        "max_source_lag_sec": max(lag_values) if lag_values else None,
        "horizons": {
            horizon_id: horizon.get("source_window") or {}
            for horizon_id, horizon in horizons.items()
            if isinstance(horizon, dict)
        },
    }


class RadarRuntimeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_module_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        asof_ts = _parse_datetime(payload.get("asof_ts")) or datetime.now(UTC)
        module_name = str(payload.get("module_name") or payload.get("module_id") or "")
        if not module_name:
            raise ValueError("module_name is required")
        snapshot_id = str(
            payload.get("module_snapshot_id")
            or f"radar-module-{module_name}-{asof_ts.strftime('%Y%m%d%H%M%S')}-{_stable_payload_hash(payload)[:8]}"
        )
        payload["module_snapshot_id"] = snapshot_id
        payload["asof_ts"] = asof_ts.isoformat()
        payload_hash = _stable_payload_hash(payload)
        row = self.session.scalar(
            select(schema.RadarModuleSnapshot).where(
                schema.RadarModuleSnapshot.module_snapshot_id == snapshot_id
            )
        )
        row = row or schema.RadarModuleSnapshot(
            module_snapshot_id=snapshot_id,
            module_name=module_name,
            asof_ts=asof_ts,
            payload_hash=payload_hash,
        )
        row.runtime_snapshot_id = _nullable_str(payload.get("runtime_snapshot_id"))
        row.module_name = module_name
        row.cadence_group = str(payload.get("cadence_group") or "confirmation")
        row.trigger_type = str(payload.get("trigger_type") or "scheduler_tick")
        row.asof_ts = asof_ts
        row.collected_at = _parse_datetime(payload.get("collected_at"))
        row.last_success_at = _parse_datetime(payload.get("last_success_at"))
        row.ttl_sec = int(payload.get("ttl_sec") or 300)
        row.hard_stale_sec = int(payload.get("hard_stale_sec") or 900)
        row.age_sec = int(payload["age_sec"]) if payload.get("age_sec") is not None else None
        row.freshness_state = str(payload.get("freshness_state") or "fresh")
        row.participation_policy = str(payload.get("participation_policy") or "full")
        row.module_direction = _nullable_str(payload.get("module_direction"))
        row.module_score = _nullable_float(payload.get("module_score"))
        row.payload_hash = payload_hash
        row.payload_json = payload
        row.error_json = dict(payload.get("error_json") or {})
        self.session.add(row)
        return payload

    def save_runtime_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        asof_ts = _parse_datetime(payload.get("asof_ts")) or datetime.now(UTC)
        snapshot_id = str(
            payload.get("runtime_snapshot_id")
            or f"radar-runtime-{asof_ts.strftime('%Y%m%d%H%M%S')}-{_stable_payload_hash(payload)[:8]}"
        )
        payload["runtime_snapshot_id"] = snapshot_id
        payload["asof_ts"] = asof_ts.isoformat()
        payload_hash = _stable_payload_hash(payload)
        row = self.session.scalar(
            select(schema.RadarRuntimeSnapshot).where(
                schema.RadarRuntimeSnapshot.runtime_snapshot_id == snapshot_id
            )
        )
        row = row or schema.RadarRuntimeSnapshot(
            runtime_snapshot_id=snapshot_id,
            asof_ts=asof_ts,
            payload_hash=payload_hash,
        )
        health = payload.get("health") or {}
        row.asof_ts = asof_ts
        row.trigger_type = str(payload.get("trigger_type") or "scheduler_tick")
        row.health_state = str(health.get("health_state") or payload.get("health_state") or "healthy")
        row.module_count = int(health.get("module_count") or len(payload.get("modules") or []))
        row.fresh_module_count = int(health.get("fresh_module_count") or 0)
        row.stale_module_count = int(health.get("stale_module_count") or 0)
        row.payload_hash = payload_hash
        row.payload_json = payload
        self.session.add(row)
        return payload

    def latest_runtime_snapshot(self) -> dict[str, Any] | None:
        row = self.session.scalar(
            select(schema.RadarRuntimeSnapshot)
            .order_by(schema.RadarRuntimeSnapshot.asof_ts.desc())
            .limit(1)
        )
        return dict(row.payload_json) if row else None

    def list_runtime_snapshots(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.RadarRuntimeSnapshot)
            .order_by(schema.RadarRuntimeSnapshot.asof_ts.desc())
            .limit(limit)
        ).all()
        return [dict(row.payload_json) for row in rows]

    def latest_module_snapshots(self) -> list[dict[str, Any]]:
        module_names = self.session.scalars(
            select(schema.RadarModuleSnapshot.module_name)
            .group_by(schema.RadarModuleSnapshot.module_name)
            .order_by(schema.RadarModuleSnapshot.module_name.asc())
        ).all()
        latest: list[dict[str, Any]] = []
        for module_name in module_names:
            row = self.session.scalar(
                select(schema.RadarModuleSnapshot)
                .where(schema.RadarModuleSnapshot.module_name == module_name)
                .order_by(schema.RadarModuleSnapshot.asof_ts.desc(), schema.RadarModuleSnapshot.id.desc())
                .limit(1)
            )
            if row:
                latest.append(dict(row.payload_json))
        return latest

    def upsert_scheduler_state(self, states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        for module_name, item in sorted(states.items()):
            row = self.session.scalar(
                select(schema.RadarRuntimeSchedulerState).where(
                    schema.RadarRuntimeSchedulerState.module_name == module_name
                )
            )
            row = row or schema.RadarRuntimeSchedulerState(module_name=module_name)
            row.module_name = module_name
            row.cadence_group = str(item.get("cadence_group") or "confirmation")
            row.interval_sec = int(item.get("interval_sec") or 300)
            row.ttl_sec = int(item.get("ttl_sec") or 600)
            row.hard_stale_sec = int(item.get("hard_stale_sec") or 1800)
            row.next_due_at = _parse_datetime(item.get("next_due_at"))
            row.last_attempt_at = _parse_datetime(item.get("last_attempt_at"))
            row.last_success_at = _parse_datetime(item.get("last_success_at"))
            row.last_status = str(item.get("last_status") or "pending")
            row.last_snapshot_id = _nullable_str(item.get("last_snapshot_id"))
            row.payload_json = dict(item, module_name=module_name)
            self.session.add(row)
            saved.append(dict(row.payload_json))
        return saved

    def scheduler_state(self) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(schema.RadarRuntimeSchedulerState)
            .order_by(schema.RadarRuntimeSchedulerState.module_name.asc())
        ).all()
        return [dict(row.payload_json) for row in rows]


class SeedRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def seed_demo(self) -> dict[str, Any]:
        if self.session.scalar(select(func.count()).select_from(schema.Source)):
            return {"seeded": False, "reason": "demo data already exists"}

        run_id = "seed-run-001"
        snapshot_id = "snap-seed-001"
        debate_id = "debate-seed-001"
        pack_id = "pack-seed-001"
        alert_id = "alert-seed-001"

        self.session.add_all(
            [
                schema.Source(
                    source_id="fred-dxy",
                    name="FRED DXY",
                    group_name="macro",
                    method="fred",
                    status="healthy",
                    metadata_json={"priority": "primary"},
                ),
                schema.Source(
                    source_id="binance-btcusdt",
                    name="Binance BTCUSDT",
                    group_name="exchange",
                    method="rest_ws",
                    status="healthy",
                ),
                schema.Source(
                    source_id="glassnode-mvrv",
                    name="Glassnode MVRV",
                    group_name="onchain",
                    method="api",
                    status="stale",
                    fallback_source_id="coinmetrics-mvrv",
                ),
            ]
        )
        self.session.flush()
        self.session.add_all(
            [
                schema.NormalizedMetric(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    name="BTC Price",
                    unit="USD",
                    group_name="btc",
                ),
                schema.NormalizedMetric(
                    metric_id="dxy",
                    source_id="fred-dxy",
                    name="Dollar Index",
                    unit="index",
                    group_name="macro",
                    higher_is="bearish_for_btc",
                ),
            ]
        )
        now = datetime.now(UTC)
        self.session.add_all(
            [
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    run_id=run_id,
                    ts=now,
                    value=108420.5,
                    previous_value=106140.0,
                    change_24h=0.0214,
                    change_7d=0.048,
                    ma_30d=101220.0,
                    quality_score=0.96,
                ),
                schema.MetricValue(
                    metric_id="dxy",
                    source_id="fred-dxy",
                    run_id=run_id,
                    ts=now,
                    value=104.12,
                    previous_value=104.35,
                    change_24h=-0.0023,
                    change_7d=-0.011,
                    ma_30d=105.02,
                    quality_score=0.93,
                ),
            ]
        )
        self.session.add(
            schema.Run(
                run_id=run_id,
                trigger="seed",
                status="completed",
                current_stage="completed",
                started_at=now,
                completed_at=now,
            )
        )
        self.session.add_all(
            [
                schema.RadarOutput(
                    run_id=run_id,
                    module_id="etf_flow",
                    signal="bullish",
                    strength=0.72,
                    confidence=0.76,
                    data_quality="high",
                    evidence_summary={"summary": "ETF inflow remains supportive."},
                    conflicting_evidence={},
                    risk_flags={"crowding": "medium"},
                    invalidation_signals={"outflow_2d": "not_triggered"},
                ),
                schema.RadarOutput(
                    run_id=run_id,
                    module_id="derivatives_crowding",
                    signal="bearish",
                    strength=0.79,
                    confidence=0.71,
                    data_quality="medium",
                    evidence_summary={"summary": "Funding and OI are elevated."},
                    conflicting_evidence={"spot_absorption": "present"},
                    risk_flags={"leverage": "high"},
                    invalidation_signals={"funding_reset": "near_trigger"},
                ),
            ]
        )
        self.session.add(
            schema.AlgorithmAlert(
                alert_id=alert_id,
                run_id=run_id,
                level="warning",
                state="leverage_squeeze",
                title="杠杆拥挤风险上升",
                summary="Funding 与 OI 同步升高，现货成交尚未同步放大。",
                evidence_count=6,
            )
        )
        self.session.add(
            schema.EvidencePack(
                pack_id=pack_id,
                run_id=run_id,
                summary="资金流偏强，但衍生品拥挤度上升。",
                data_quality_score=0.91,
            )
        )
        self.session.add_all(
            [
                schema.EvidenceItem(
                    evidence_id="E-1001",
                    pack_id=pack_id,
                    module_id="etf_flow",
                    claim="ETF 连续净流入支撑现货需求。",
                    direction="bullish",
                    strength=0.72,
                    data={"flow_7d": "+2.1B"},
                ),
                schema.EvidenceItem(
                    evidence_id="E-1002",
                    pack_id=pack_id,
                    module_id="derivatives_crowding",
                    claim="永续资金费率与 OI 同时升高。",
                    direction="bearish",
                    strength=0.79,
                    data={"funding": "elevated"},
                ),
            ]
        )
        self.session.add(
            schema.LlmDebate(
                debate_id=debate_id,
                run_id=run_id,
                consensus_score=0.71,
                disagreement_level="medium",
                final_state="leverage_squeeze",
                publish_allowed=True,
            )
        )
        self.session.add_all(
            [
                schema.LlmModelVote(
                    debate_id=debate_id,
                    model_name="DeepSeek",
                    vote="leverage_squeeze",
                    confidence=0.74,
                    evidence_ids=["E-1001", "E-1002"],
                ),
                schema.LlmModelVote(
                    debate_id=debate_id,
                    model_name="Qwen",
                    vote="leverage_squeeze",
                    confidence=0.66,
                    evidence_ids=["E-1001"],
                    changed=True,
                ),
            ]
        )
        self.session.add(
            schema.JudgeSynthesis(
                run_id=run_id,
                debate_id=debate_id,
                final_state="leverage_squeeze",
                confidence=0.58,
                confidence_discount=-0.12,
                summary="多头趋势仍在，但杠杆拥挤风险升高。",
                payload={"minority_objection": "downside_risk"},
            )
        )
        self.session.add(
            schema.DashboardSnapshot(
                snapshot_id=snapshot_id,
                run_id=run_id,
                btc_price=108420.5,
                state="leverage_squeeze",
                bias="volatile_up",
                confidence=0.58,
                risk_level="medium_high",
                alert_level="warning",
                payload={"watch_next": ["funding reset", "4h support"]},
            )
        )
        self.session.add_all(
            [
                schema.SnapshotModule(
                    snapshot_id=snapshot_id,
                    module_id="etf_flow",
                    signal="bullish",
                    strength=0.72,
                    payload={},
                ),
                schema.SnapshotModule(
                    snapshot_id=snapshot_id,
                    module_id="derivatives_crowding",
                    signal="bearish",
                    strength=0.79,
                    payload={},
                ),
                schema.SnapshotAlert(snapshot_id=snapshot_id, alert_id=alert_id),
            ]
        )
        self.session.add(
            schema.Article(
                article_id="article-seed-001",
                snapshot_id=snapshot_id,
                title="BTC 多头趋势延续，但杠杆拥挤风险上升",
                body="BTC 当前状态为 leverage_squeeze。结论仅供观察，不构成交易建议。",
                publish_allowed=True,
            )
        )
        self.session.add(
            schema.DataQualitySnapshot(
                run_id=run_id,
                score=0.91,
                status="healthy",
                payload={"freshness": "high", "consistency": "medium"},
            )
        )
        self.session.add_all(
            [
                schema.SourceHealthEvent(
                    source_id="fred-dxy",
                    status="healthy",
                    quality_score=0.93,
                    latency_ms=200,
                ),
                schema.SourceHealthEvent(
                    source_id="glassnode-mvrv",
                    status="stale",
                    quality_score=0.64,
                    latency_ms=3600000,
                    message="stale demo source",
                ),
            ]
        )
        return {"seeded": True, "run_id": run_id, "snapshot_id": snapshot_id}


class PageQueryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def dashboard_current(self) -> dict[str, Any] | None:
        snapshot = self.session.scalar(
            select(schema.DashboardSnapshot).order_by(schema.DashboardSnapshot.created_at.desc()).limit(1)
        )
        if snapshot is None:
            return None

        modules = self.session.scalars(
            select(schema.SnapshotModule).where(
                schema.SnapshotModule.snapshot_id == snapshot.snapshot_id
            )
        ).all()
        alerts = self.session.scalars(
            select(schema.AlgorithmAlert)
            .join(
                schema.SnapshotAlert,
                schema.SnapshotAlert.alert_id == schema.AlgorithmAlert.alert_id,
            )
            .where(schema.SnapshotAlert.snapshot_id == snapshot.snapshot_id)
        ).all()
        debate = self.session.scalar(
            select(schema.LlmDebate).where(schema.LlmDebate.run_id == snapshot.run_id)
        )
        data_quality = self.session.scalar(
            select(schema.DataQualitySnapshot)
            .where(schema.DataQualitySnapshot.run_id == snapshot.run_id)
            .order_by(schema.DataQualitySnapshot.created_at.desc())
            .limit(1)
        )

        return {
            "snapshot": _model_dict(snapshot),
            "modules": [_model_dict(item) for item in modules],
            "alerts": [_model_dict(item) for item in alerts],
            "debate": _model_dict(debate) if debate else None,
            "data_quality": _model_dict(data_quality) if data_quality else None,
        }

    def table_counts(self) -> dict[str, int]:
        return {
            table.name: self.session.scalar(select(func.count()).select_from(table)) or 0
            for table in schema.Base.metadata.sorted_tables
        }


def _model_dict(item: Any) -> dict[str, Any]:
    return {
        column.name: getattr(item, column.name)
        for column in item.__table__.columns
        if column.name not in {"id"}
    }
