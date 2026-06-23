from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "onlybtc.sqlite3"
REPORT_PATH = ROOT / "reports" / "p3-trend-state-calibration-report.md"


def main() -> None:
    runs = _load_recent_runs(limit=10)
    lines: list[str] = [
        "# P3-C25 Trend State Calibration Audit",
        "",
        f"- generated_at: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- db: `{DB_PATH}`",
        f"- covered_runs: {len(runs)}",
        "",
        "## Summary",
        "",
    ]
    if not runs:
        lines.append("No P3 scored module runs found.")
        REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {REPORT_PATH}")
        return

    old_total: Counter[str] = Counter()
    new_total: Counter[str] = Counter()
    module_state_total: Counter[str] = Counter()
    module_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for run_id, rows in runs:
        for row in rows:
            old_state = _legacy_state(row)
            new_state = _calibrated_state(row)
            old_total[old_state] += 1
            new_total[new_state] += 1
            module_state_total[str(row.get("module_state") or "unknown")] += 1
            module_rows[str(row.get("radar_module") or "unknown")].append(
                {
                    "run_id": run_id,
                    "old": old_state,
                    "new": new_state,
                    "direction_score": row.get("direction_score"),
                    "risk_score": row.get("risk_score"),
                    "confidence_score": row.get("confidence_score"),
                    "module_state": row.get("module_state"),
                    "conflict_score": row.get("conflict_score"),
                }
            )

    lines.extend(
        [
            "### Previous rule distribution",
            "",
            _counter_table(old_total),
            "",
            "### Calibrated rule distribution",
            "",
            _counter_table(new_total),
            "",
            "### Module state distribution",
            "",
            _counter_table(module_state_total),
            "",
            "## Per-module Latest Rows",
            "",
            "| module | latest_run | old_state | calibrated_state | module_state | direction_score | risk_score | confidence_score | conflict_score |",
            "|---|---|---|---|---|---:|---:|---:|---:|",
        ]
    )

    for module in sorted(module_rows):
        latest = module_rows[module][0]
        lines.append(
            "| {module} | {run_id} | {old} | {new} | {module_state} | {direction_score} | {risk_score} | {confidence_score} | {conflict_score} |".format(
                module=module,
                **latest,
            )
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print("old", dict(old_total))
    print("new", dict(new_total))


def _load_recent_runs(limit: int) -> list[tuple[str, list[dict[str, Any]]]]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    run_rows = cur.execute(
        """
        select run_id, max(created_at) as latest_created_at
        from feature_values
        where module_id = 'p3_scored_radar_module'
        group by run_id
        order by latest_created_at desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    runs: list[tuple[str, list[dict[str, Any]]]] = []
    for run_id, _ in run_rows:
        rows = [
            json.loads(row[0] or "{}")
            for row in cur.execute(
                """
                select metadata_json
                from feature_values
                where run_id = ? and module_id = 'p3_scored_radar_module'
                order by feature_id
                """,
                (run_id,),
            ).fetchall()
        ]
        runs.append((run_id, rows))
    return runs


def _legacy_state(row: dict[str, Any]) -> str:
    module_id = str(row.get("radar_module") or "")
    direction_score = float(row.get("direction_score") or 0.0)
    risk_score = float(row.get("risk_score") or 0.0)
    conflict_score = float(row.get("conflict_score") or 0.0)
    module_state = str(row.get("module_state") or "")
    if module_id == "event_policy" and risk_score >= 60:
        return "event_risk_locked"
    if row.get("raw_effective_conflict") or conflict_score >= 0.65:
        return "conflict_no_trade"
    if direction_score >= 12:
        if risk_score >= 65:
            return "bullish_but_crowded"
        if float(row.get("confidence_score") or 0.0) >= 55:
            return "risk_on_confirmed"
    if direction_score <= -12:
        if module_state == "bearish_but_improving":
            return "bearish_but_improving"
        return "bearish_pressure"
    return "neutral_wait_confirm"


def _calibrated_state(row: dict[str, Any]) -> str:
    module_id = str(row.get("radar_module") or "")
    direction_score = float(row.get("direction_score") or 0.0)
    risk_score = float(row.get("risk_score") or 0.0)
    confidence_score = float(row.get("confidence_score") or 0.0)
    conflict_score = float(row.get("conflict_score") or 0.0)
    module_state = str(row.get("module_state") or "")
    raw_effective_conflict = bool(row.get("raw_effective_conflict"))
    improving = module_state == "bearish_but_improving"

    if module_id == "event_policy" and risk_score >= 60:
        return "event_risk_locked"
    if improving and direction_score <= -2 and confidence_score >= 35:
        return "bearish_but_improving"
    if (
        module_state == "internal_conflict"
        and conflict_score >= 0.5
    ) or conflict_score >= 0.65 or raw_effective_conflict:
        return "conflict_no_trade"
    if direction_score >= 12:
        if risk_score >= 65:
            return "bullish_but_crowded"
        if confidence_score >= 55:
            return "risk_on_confirmed"
    if direction_score >= 4 and module_state == "support_dominant":
        if risk_score >= 55:
            return "bullish_but_crowded"
        if confidence_score >= 60:
            return "risk_on_confirmed"
    if direction_score <= -12:
        if improving:
            return "bearish_but_improving"
        return "bearish_pressure"
    if direction_score <= -2 and module_state == "pressure_dominant" and confidence_score >= 55:
        return "bearish_pressure"
    return "neutral_wait_confirm"


def _counter_table(counter: Counter[str]) -> str:
    total = sum(counter.values()) or 1
    lines = ["| state | count | ratio |", "|---|---:|---:|"]
    for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {key} | {value} | {value / total:.2%} |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
