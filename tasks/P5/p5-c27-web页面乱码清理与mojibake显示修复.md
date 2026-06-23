# P5-C27 Web 页面乱码清理与 Mojibake 显示修复

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

P5 Vue 页面在多轮编辑后出现静态 UI 文案乱码，同时部分 P4.5 动态字段来自上游 payload，存在 UTF-8 被错误按 Latin-1 解码后的 mojibake，例如 `ï¼Œç...`。本任务只修复前端显示层，不修改上游数据、不修改 SQLite。

## 实施内容

- 逐项清理 `frontend/src/App.vue` 中可见静态乱码文案。
- 保留页面业务结构、API 字段和 store 契约不变。
- 将常见分隔符乱码统一为 `·` 或 `->`。
- 修复左侧导航、Dashboard、Overview、Alerts、Invalidation、Data Quality、Source、Run Logs、History、右侧摘要区等可见静态文本。
- 在 `text()` 出口增加轻量 `repairMojibake()`，仅在检测到典型 mojibake 且字符串可安全按 Latin-1 bytes 还原时尝试 UTF-8 解码。

## DoD

- `App.vue` 中不再出现已知 mojibake 片段。
- 动态 evidence/article 文本经过 `text()` 输出时可自动修复常见 mojibake。
- 不改变 API、store、DTO 和上游落盘数据。
- 前端构建通过。
- P5 Dashboard contract 校验通过。
- P5 page DoD 校验通过。

## 验收记录

- `npm run build` 通过。
- `scripts/validate_p5_dashboard_contract.py` 通过。
- `scripts/validate_p5_page_dod.py` 通过。
