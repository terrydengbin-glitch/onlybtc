# P5-C28 Evidence 页面排版压缩与评分可读化

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

P5-C10 已经打通 Evidence API 和详情页，但页面在未选中证据时仍保留右侧空白详情区，导致列表只占左半屏；同时列表卡片展示过多 raw evidence 文本，阅读负担较重。

## 目标

- Evidence 页面未选中证据时，列表占满内容区宽度。
- 选中证据后，页面切换为左侧证据列表 + 右侧详情。
- 列表卡片保留评分、方向、质量、freshness、source 等核心审计字段。
- 列表卡片不再展示大段原始数据，长说明截断为 2 行。
- 详情页继续保留完整审计字段。

## 实施内容

- `evidence-layout` 默认改为单栏满宽。
- 仅在 `state.selectedEvidenceDetail` 存在时增加 `has-detail` 双栏布局。
- Evidence 列表改为双列卡片，详情展开后左侧自动降为单列。
- 增加 `score-chip`，明确显示 `score_bucket/direction`。
- 保留 `score / effective score / quality / freshness`。
- 列表说明使用 `evidenceOneLine()` 并通过 CSS 限制两行。

## DoD

- Evidence 列表无右侧空白大区。
- 每条 evidence 列表项仍能看到 score / effective score / quality / freshness。
- 长文本在列表中截断，完整内容只在详情中展示。
- `npm run build` 通过。
- P5 dashboard contract 和 page DoD 校验通过。

## 验收记录

- `npm run build` 通过。
- `scripts/validate_p5_dashboard_contract.py` 通过。
- `scripts/validate_p5_page_dod.py` 通过。
