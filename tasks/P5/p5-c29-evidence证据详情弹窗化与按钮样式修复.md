# P5-C29 Evidence 证据详情弹窗化与按钮样式修复

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

P5-C10/P5-C28 已完成 Evidence 数据接入、列表压缩与评分可读化，但证据详情仍采用左右分栏。用户希望 Evidence 页面保持满宽列表，点击卡片后以弹窗展示完整详情，同时修复白底默认按钮样式。

## 目标

- Evidence 页面只保留满宽证据列表，不再左右分栏展示详情。
- 点击 evidence card 后打开 modal 弹窗展示完整详情。
- 弹窗内继续保留完整审计字段。
- 点击遮罩、关闭按钮、`Esc` 可关闭弹窗。
- `Reset filters`、`Open Source Detail` 等按钮统一为暗色项目样式。
- 移动端弹窗可用，内容可滚动。

## 实施内容

- 移除 `evidence-layout.has-detail` 双栏详情布局。
- 将原右侧 `evidence-detail` 改为页面级 `modal-backdrop + evidence-modal`。
- 新增 `closeEvidenceDetail()` 和 `Esc` 关闭逻辑。
- 弹窗保留 value、metric score、effective score、quality、source、freshness、horizon、duplicate、history、boundary flags。
- 修复 Evidence 工具栏按钮和弹窗按钮样式，避免白底默认按钮。

## DoD

- Evidence 页没有左右分栏详情。
- 点击任意 evidence 后弹窗打开。
- 弹窗展示完整审计字段。
- 白底默认按钮消失。
- `npm run build` 通过。
- P5 dashboard contract 和 page DoD 校验通过。

## 验收记录

- `npm run build` 通过。
- `scripts/validate_p5_dashboard_contract.py` 通过。
- `scripts/validate_p5_page_dod.py` 通过。
