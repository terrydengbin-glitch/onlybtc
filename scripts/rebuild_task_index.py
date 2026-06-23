from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
OUTPUT = ROOT / "task index.rebuild.preview.md"

PHASE_TITLES = {
    "P0": "工程底座与项目初始化",
    "P1": "数据源接入与采集层",
    "P2": "Radar 指标与模块层",
    "P3": "算法、事件窗口与评分层",
    "P4": "Agent 推理与总控融合（Legacy）",
    "P4.5": "Research Report 与 P4 替代主线",
    "P5": "Dashboard 与可视化层",
    "P6": "发布、通知与策略表达",
    "P7": "回测、评估与策略校准",
    "P8": "SQLite、历史数据与持久化",
    "P9": "FastAPI 聚合 API 与运维质控",
    "P10": "扩展与配置治理",
}

PHASE_ORDER = ["P0", "P1", "P2", "P3", "P4", "P4.5", "P5", "P6", "P7", "P8", "P9", "P10"]

BAD_MARKERS = (
    "�",
    "鐨",
    "涓",
    "鍙",
    "绛",
    "鏁",
    "浠",
    "鐘",
    "濂",
    "绋",
    "璺",
    "闆",
    "棰",
    "鍏",
    "撴",
)

STATUS_VALUES = {
    "TODO": "TODO",
    "DONE": "DONE",
    "DOING": "DOING",
    "IN_PROGRESS": "DOING",
    "IN PROGRESS": "DOING",
    "LEGACY": "LEGACY",
    "LAGACY": "LEGACY",
    "BLOCKED": "BLOCKED",
    "SKIPPED": "SKIPPED",
}


def has_mojibake(value: str) -> bool:
    return any(marker in value for marker in BAD_MARKERS)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def task_id_from_filename(path: Path) -> tuple[str, str, int] | None:
    match = re.match(r"(?i)^(p\d+(?:\.\d+)?)-c(\d+)-(.+)$", path.stem)
    if not match:
        return None
    phase = match.group(1).upper()
    number = int(match.group(2))
    task_id = f"{phase}-C{number:02d}"
    return phase, task_id, number


def title_from_filename(path: Path) -> str:
    parsed = task_id_from_filename(path)
    if not parsed:
        return path.stem
    raw = re.sub(r"(?i)^p\d+(?:\.\d+)?-c\d+-", "", path.stem)
    return raw.replace("-", " ").strip()


def parse_heading_title(text: str, fallback_id: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("# "):
            continue
        heading = line[2:].strip()
        if has_mojibake(heading):
            return None
        heading = re.sub(rf"^{re.escape(fallback_id)}\s*[-|：:]*\s*", "", heading, flags=re.IGNORECASE)
        heading = heading.strip()
        if heading:
            return heading
    return None


def parse_status(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if re.match(r"^##\s*(状态|status)\s*$", line, flags=re.IGNORECASE):
            for candidate in lines[index + 1 : index + 6]:
                if not candidate or has_mojibake(candidate):
                    continue
                normalized = candidate.strip().strip("|` ").upper()
                if normalized in STATUS_VALUES:
                    return STATUS_VALUES[normalized]
    head = "\n".join(lines[:25]).upper()
    if "\nLEGACY\n" in head or "\nLAGACY\n" in head:
        return "LEGACY"
    if "\nDONE\n" in head:
        return "DONE"
    return "TODO"


def parse_task(path: Path) -> dict[str, object] | None:
    parsed = task_id_from_filename(path)
    if parsed is None:
        return None
    phase, task_id, number = parsed
    text = read_text(path)
    title = parse_heading_title(text, task_id) or title_from_filename(path)
    status = parse_status(text)
    rel = path.relative_to(ROOT).as_posix()
    return {
        "phase": phase,
        "number": number,
        "id": task_id,
        "title": title,
        "status": status,
        "link": rel,
    }


def collect_tasks() -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {phase: [] for phase in PHASE_ORDER}
    for path in TASKS_DIR.rglob("*.md"):
        if path.parent.name.lower() == "ui":
            continue
        task = parse_task(path)
        if not task:
            continue
        phase = str(task["phase"])
        result.setdefault(phase, []).append(task)
    for tasks in result.values():
        tasks.sort(key=lambda item: int(item["number"]))
    return result


def collect_extra_docs() -> list[Path]:
    docs: list[Path] = []
    for path in TASKS_DIR.rglob("*.md"):
        if path.parent.name.lower() == "ui":
            continue
        if parse_task(path) is None:
            docs.append(path)
    return sorted(docs, key=lambda item: item.as_posix().lower())


def render_index() -> str:
    tasks_by_phase = collect_tasks()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = [
        "# onlyBTC Task Index",
        "",
        f"> Rebuilt from `tasks/` task-card files at `{now}`.",
        "> 乱码修复策略：以任务卡文件名和可读 Markdown 标题为准；旧 P4 Agent 主线保留为 Legacy 审计参考，P4.5 为当前研究报告主线。",
        "",
        "## UI / Design References",
        "",
        "| 文档 | 链接 |",
        "|---|---|",
        "| P5 Dashboard UI Prototype | [p5-dashboard-ui-prototype](tasks/ui/p5-dashboard-ui-prototype.md) |",
        "| P5 Subpages UI Prototype | [p5-subpages-ui-prototype](tasks/ui/p5-subpages-ui-prototype.md) |",
        "| Dashboard High-Fidelity Reference | [ui-references](ui-references/) |",
        "",
    ]

    extra_docs = collect_extra_docs()
    if extra_docs:
        lines.extend(
            [
                "## Phase / Architecture Docs",
                "",
                "| 文档 | 链接 |",
                "|---|---|",
            ]
        )
        for path in extra_docs:
            rel = path.relative_to(ROOT).as_posix()
            lines.append(f"| {path.stem} | [{path.stem}]({rel}) |")
        lines.append("")

    for phase in PHASE_ORDER:
        tasks = tasks_by_phase.get(phase, [])
        if not tasks:
            continue
        lines.extend(
            [
                f"## {phase} {PHASE_TITLES.get(phase, '')}".rstrip(),
                "",
                "| 状态 | 任务卡 | 标题 | 链接 |",
                "|---|---|---|---|",
            ]
        )
        for task in tasks:
            task_id = str(task["id"])
            lines.append(
                f"| {task['status']} | {task_id} | {task['title']} | [{task_id}]({task['link']}) |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT.write_text(render_index(), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
