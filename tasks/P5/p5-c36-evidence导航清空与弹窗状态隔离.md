# P5-C36 Evidence 导航清空与弹窗状态隔离

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

P5-C29 将 Evidence 详情从右侧分栏改成弹窗。当前弹窗显示条件为：

```text
activePage === "evidence" && state.selectedEvidenceDetail
```

因此如果用户之前打开过某条 evidence detail，再通过左侧导航或右侧抽屉进入 Evidence 子页面，而导航动作没有清空 `selectedEvidenceDetail`，页面会复用上一条详情并无端弹出证据弹窗。

这是前端状态隔离问题，不是 P1/P2/P3/P4.5 数据问题。

## 问题链条

```text
用户打开某条 evidence detail
  -> state.selectedEvidenceDetail 被写入
  -> 用户关闭或跳转到其他页面
  -> 某些入口只执行 activePage = "evidence"
  -> selectedEvidenceDetail 未被清空
  -> Evidence 页面 mounted/render 时弹窗条件成立
  -> 无端弹出旧 evidence detail
```

## 目标

- 进入 Evidence 列表页时默认不弹窗。
- 只有明确点击 evidence card / metric chip / alert evidence / URL 带 `evidence_id` 时才打开详情弹窗。
- 普通导航到 Evidence 页时必须清空 `selectedEvidenceDetail`、`selectedEvidenceId` 与 route context 的 `evidence_id`。
- 保留从 Dashboard / Article / Radar / Alert 点击具体 evidence 时自动打开弹窗的能力。

## 实施方案

1. 统一 Evidence 普通导航入口，不再直接写 `activePage = 'evidence'`。
2. 在 `navigateTo('evidence')` 或新增 `openEvidenceList()` 中区分：
   - `withDetail=true`：保留 detail，用于 `openEvidenceDetail(evidenceId)`。
   - `withDetail=false`：清空 detail，用于菜单/按钮进入 Evidence 列表。
3. `closeEvidenceDetail()` 同步清理 `state.routeContext.evidence_id`。
4. `hydrateRouteSelection()` 只在 URL / route context 明确有 `evidence_id` 时加载 detail。
5. 增加回归校验：
   - 普通进入 Evidence 页不出现 `.modal-backdrop`。
   - 点击 evidence card 后才出现 `.modal-backdrop`。
   - 关闭弹窗后再次进入 Evidence 页不复用旧详情。

## DoD

- 左侧导航点击“证据”不会自动弹出旧详情。
- 右侧抽屉点击 Evidence 不会自动弹出旧详情。
- Dashboard / Article / Radar / Alert 中点击具体 evidence 仍能打开详情弹窗。
- 关闭弹窗会清空 selected evidence 和 URL route context。
- `npm run build` 通过。
- P5 页面 DoD / dashboard contract 校验通过。

## 关联任务

P5-C10, P5-C20, P5-C29, P5-C31, P5-C17, P9-C03

## 执行记录

- 已确认根因：Evidence 弹窗由 `activePage === "evidence" && state.selectedEvidenceDetail` 控制，普通导航进入 Evidence 页时未清理上一条 `selectedEvidenceDetail`，导致旧证据详情被复用并自动弹窗。
- 已将普通 Evidence 导航统一走 `navigateTo("evidence")`，进入列表页时自动调用 `closeEvidenceDetail()` 清空旧详情。
- 已让 `openEvidenceDetail(evidenceId)` 使用 `navigateTo("evidence", { keepEvidenceDetail: true })`，保留“点击具体 evidence 才打开弹窗”的行为。
- `closeEvidenceDetail()` 已同步清理 `state.routeContext.evidence_id`，避免 URL / route context 残留旧 evidence。

## 验证结果

```text
npm run build
passed

.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py
P5 dashboard contract validation passed.

.\.venv\Scripts\python.exe scripts\validate_p5_page_dod.py
P5 page DoD validation passed.
```
