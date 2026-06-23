from __future__ import annotations

import argparse
import html
import json
import os
import sqlite3
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "onlybtc.sqlite3"
REPORT_DIR = PROJECT_ROOT / "reports"
MD_REPORT = REPORT_DIR / "p4-gpt-independent-validation-report.md"
HTML_REPORT = REPORT_DIR / "p4-gpt-independent-validation-report.html"
CONTEXT_JSON = REPORT_DIR / "p4-gpt-independent-validation-context.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run GPT independent validation against latest P1/P2/P3/P4 data."
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to onlyBTC sqlite database.")
    parser.add_argument("--model", default=None, help="OpenAI model override.")
    parser.add_argument("--max-evidence-per-analyst", type=int, default=12)
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("ONLYBTC_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = (
        os.environ.get("ONLYBTC_OPENAI_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = args.model or os.environ.get("ONLYBTC_OPENAI_MODEL") or "gpt-4.1"
    data = load_latest_context(Path(args.db), args.max_evidence_per_analyst)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if not api_key:
        print(
            json.dumps(
                {
                    "status": "blocked_missing_openai_api_key",
                    "context_json": str(CONTEXT_JSON),
                    "message": (
                        "Missing ONLYBTC_OPENAI_API_KEY or OPENAI_API_KEY; "
                        "context was exported but GPT validation was not run."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    prompt = build_prompt(data)
    gpt_report = call_openai_chat(
        api_key=api_key,
        base_url=base_url,
        model=model,
        prompt=prompt,
    )
    md = build_markdown_report(data, gpt_report, model)
    html_report = build_html_report(md)
    MD_REPORT.write_text(md, encoding="utf-8")
    HTML_REPORT.write_text(html_report, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "completed",
                "model": model,
                "markdown_report": str(MD_REPORT),
                "html_report": str(HTML_REPORT),
                "snapshot_id": data["snapshot"]["snapshot_id"],
                "debate_id": data["final_json"]["debate_id"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_latest_context(db_path: Path, max_evidence_per_analyst: int) -> dict[str, Any]:
    if not db_path.exists():
        raise SystemExit(f"SQLite database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        snapshot = one(
            conn,
            """
            select snapshot_id, run_id, state, bias, confidence, risk_level, alert_level,
                   payload, created_at
            from dashboard_snapshots
            order by created_at desc, id desc
            limit 1
            """,
        )
        final_json = parse_json(snapshot["payload"])
        debate_id = final_json["debate_id"]
        pack_id = final_json["evidence_pack_id"]
        judge = one(
            conn,
            """
            select payload from judge_syntheses
            where debate_id = ?
            order by created_at desc, id desc
            limit 1
            """,
            [debate_id],
        )
        review = one(
            conn,
            """
            select issues, required_changes from adversarial_reviews
            where debate_id = ?
            order by created_at desc, id desc
            limit 1
            """,
            [debate_id],
        )
        votes = all_rows(
            conn,
            """
            select model_name, vote, confidence, evidence_ids, changed
            from llm_model_votes
            where debate_id = ?
            order by model_name
            """,
            [debate_id],
        )
        challenges = all_rows(
            conn,
            """
            select challenger, target, issue, severity
            from llm_challenges
            where debate_id = ?
            order by created_at
            """,
            [debate_id],
        )
        evidence = load_evidence(conn, pack_id, max_evidence_per_analyst)
        report_paths = {
            "p1_html": str(REPORT_DIR / "p1-c22-真实数据全链路验收报告.html"),
            "p2_html": str(REPORT_DIR / "p2-radar-quality-report.html"),
            "p3_html": str(REPORT_DIR / "p3-algorithm-audit-report.html"),
            "p4_html": str(REPORT_DIR / "p4-controller-audit-report.html"),
        }
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "snapshot": dict(snapshot) | {"payload": None},
            "final_json": final_json,
            "judge": parse_json(judge["payload"]),
            "review": {
                "issues": parse_json(review["issues"]),
                "required_changes": parse_json(review["required_changes"]),
            },
            "votes": [row_to_json(row, json_fields={"evidence_ids"}) for row in votes],
            "challenges": [challenge_row(row) for row in challenges],
            "evidence_by_analyst": evidence,
            "report_paths": report_paths,
        }
    finally:
        conn.close()


def load_evidence(
    conn: sqlite3.Connection,
    pack_id: str,
    max_per_analyst: int,
) -> dict[str, list[dict[str, Any]]]:
    rows = all_rows(
        conn,
        """
        select evidence_id, module_id, claim, direction, strength, data
        from evidence_items
        where pack_id = ?
        order by id
        """,
        [pack_id],
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        data = parse_json(row["data"])
        analyst = data.get("assigned_analyst") or "global_or_state"
        item = {
            "evidence_id": row["evidence_id"],
            "module_id": row["module_id"],
            "claim": row["claim"],
            "direction": row["direction"],
            "strength": row["strength"],
            "source_layer": data.get("source_layer"),
            "metric_id": data.get("metric_id"),
            "source_id": data.get("source_id"),
            "source_run_id": data.get("source_run_id"),
            "value": data.get("value"),
            "quality_score": data.get("quality_score"),
            "role": data.get("role"),
            "event_type": data.get("event_type"),
            "event_phase": data.get("event_phase"),
            "publish_impact": data.get("publish_impact"),
            "history_available": data.get("history_available"),
        }
        grouped.setdefault(str(analyst), []).append(item)
    return {
        analyst: sorted(
            items,
            key=lambda item: (
                float(item.get("quality_score") or 0),
                abs(float(item.get("strength") or 0)),
            ),
            reverse=True,
        )[:max_per_analyst]
        for analyst, items in grouped.items()
    }


def build_prompt(data: dict[str, Any]) -> str:
    compact = {
        "run_ids": {
            "collect_run_id": infer_collect_run_id(data),
            "p2_radar_run_id": infer_radar_run_id(data),
            "p3_run_id": data["final_json"].get("run_id"),
            "evidence_pack_id": data["final_json"].get("evidence_pack_id"),
            "debate_id": data["final_json"].get("debate_id"),
            "snapshot_id": data["snapshot"].get("snapshot_id"),
        },
        "p4_final_controller": data["final_json"],
        "p4_judge": data["judge"],
        "p4_adversarial_review": data["review"],
        "p4_votes": data["votes"],
        "p4_challenges": data["challenges"],
        "evidence_by_analyst": data["evidence_by_analyst"],
        "report_paths": data["report_paths"],
    }
    return (
        "You are GPT acting as an independent validation line for the onlyBTC P4 "
        "agent system. Use only the supplied JSON; do not add external market facts. "
        "Write in Simplified Chinese.\n\n"
        "Task:\n"
        "1. Independently simulate four analysts: Macro & Event, Liquidity & Flow, "
        "Microstructure, On-chain & Market Structure.\n"
        "2. Simulate cross-examination between the analysts.\n"
        "3. Produce one independent judge conclusion.\n"
        "4. Compare your independent conclusion with the supplied P4 final controller.\n"
        "5. Decide whether the P4 result is within expectation, and list follow-up tasks "
        "if there are meaningful gaps.\n\n"
        "Required output format: Markdown with sections:\n"
        "- Run ID 对齐\n"
        "- GPT 四分析师独立结论\n"
        "- GPT 交叉质询\n"
        "- GPT 主裁判结论\n"
        "- P4 主链结果摘要\n"
        "- GPT vs P4 对照矩阵\n"
        "- 是否符合预期\n"
        "- 后续建议任务\n\n"
        "Rules: cite evidence_id values and data values where available; preserve "
        "state-machine, run_mode, fallback, event-window and data-quality constraints; "
        "no trading advice.\n\n"
        "Input JSON:\n"
        f"{json.dumps(compact, ensure_ascii=False, indent=2)}"
    )


def call_openai_chat(api_key: str, base_url: str, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful financial-system audit validator. "
                    "You do not provide trading instructions."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI request failed: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"OpenAI request failed: {exc}") from exc
    parsed = json.loads(body)
    return str(parsed["choices"][0]["message"]["content"])


def build_markdown_report(data: dict[str, Any], gpt_report: str, model: str) -> str:
    final_json = data["final_json"]
    header = f"""# P4-C19 GPT 独立验证报告

生成时间：{data["generated_at"]}

模型：`{model}`

本报告是独立验证子线输出，只读现有 P1/P2/P3/P4 数据，不写回生产 Final Controller。

## 本轮 P4 主链摘要

- `collect_run_id`: `{infer_collect_run_id(data)}`
- `p2_radar_run_id`: `{infer_radar_run_id(data)}`
- `p3_run_id`: `{final_json.get("run_id")}`
- `evidence_pack_id`: `{final_json.get("evidence_pack_id")}`
- `debate_id`: `{final_json.get("debate_id")}`
- `snapshot_id`: `{data["snapshot"].get("snapshot_id")}`
- `runtime_mode`: `{final_json.get("runtime_mode")}`
- `llm_runtime_integrity`: `{final_json.get("llm_runtime_integrity")}`
- `fallback_used`: `{final_json.get("fallback_used")}`
- `trend_state`: `{final_json.get("trend_state")}`
- `risk_state`: `{final_json.get("risk_state")}`
- `confidence`: `{final_json.get("confidence")}`
- `blocked_by`: `{", ".join(final_json.get("blocked_by") or [])}`

## GPT 独立推理与对照

"""
    return header + "\n" + gpt_report.strip() + "\n"


def build_html_report(markdown_text: str) -> str:
    escaped = html.escape(markdown_text)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>P4-C19 GPT 独立验证报告</title>
  <style>
    body {{ margin: 0; background: #08131c; color: #dbeafe; font-family: Arial, sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }}
  </style>
</head>
<body>
<main>
<pre>{escaped}</pre>
</main>
</body>
</html>
"""


def one(
    conn: sqlite3.Connection,
    sql: str,
    params: list[Any] | None = None,
) -> sqlite3.Row:
    row = conn.execute(textwrap.dedent(sql), params or []).fetchone()
    if row is None:
        raise SystemExit("Expected one row but query returned none.")
    return row


def all_rows(
    conn: sqlite3.Connection,
    sql: str,
    params: list[Any] | None = None,
) -> list[sqlite3.Row]:
    return list(conn.execute(textwrap.dedent(sql), params or []).fetchall())


def parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return {}
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def row_to_json(row: sqlite3.Row, json_fields: set[str] | None = None) -> dict[str, Any]:
    json_fields = json_fields or set()
    output = dict(row)
    for field in json_fields:
        output[field] = parse_json(output.get(field))
    return output


def challenge_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = row_to_json(row)
    payload["issue"] = parse_json(payload.get("issue"))
    return payload


def infer_collect_run_id(data: dict[str, Any]) -> str | None:
    for items in data["evidence_by_analyst"].values():
        for item in items:
            run_id = item.get("source_run_id")
            if isinstance(run_id, str) and run_id.startswith("collect-"):
                return run_id
    return None


def infer_radar_run_id(data: dict[str, Any]) -> str | None:
    for items in data["evidence_by_analyst"].values():
        for item in items:
            run_id = item.get("source_run_id")
            if isinstance(run_id, str) and run_id.startswith("radar-"):
                return run_id
    return None


if __name__ == "__main__":
    sys.exit(main())
