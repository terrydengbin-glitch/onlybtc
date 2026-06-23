# P5-C59 雷达子页面 UI 整齐卡片与指标折叠优化

## 状态

DONE

## 背景

Radar Detail 雷达子页面在新增大量指标后，metric node 与 edge 过多，导致视觉噪声高、卡片拥挤、趋势含义不清。当前优化只针对雷达子页面 `activePage === 'radar'` 内的 radar div，不修改 Dashboard 拓扑页、右侧抽屉、底部时间尺度/预警区、API、P4.5 契约或 BTC cockpit 业务逻辑。

## 目标

把雷达子页面从“全量 metric 散点 + 连线”调整为“整齐参数卡片 + 状态颜色 + 折叠明细”的展示方式：

- 雷达背景效果保留，仅作为氛围和空间锚点。
- 不再用线条连接主卡和参数卡。
- 趋势/压力/支撑通过卡片边框颜色、状态标签和 score bar 表达。
- 主卡保留 selected module 的状态、质量、score、语义标签。
- 指标卡默认只展示 top contribution，不把几十上百个 metric 全部铺开。
- context-only、score=0、data-quality 类指标弱化到明细/表格，不进入主雷达画布干扰趋势阅读。

## 范围

允许修改：

- `frontend/src/App.vue` 的 `activePage === 'radar'` 分支
- `frontend/src/styles.css` 中雷达子页面相关样式

不允许修改：

- Dashboard 拓扑页布局和连线逻辑
- BTC cockpit / P4.5 输出契约
- P8/P9/API 数据结构
- 其他页面 div 与导航布局

## DoD

1. 雷达子页面 radar div 不再渲染 metric edge 连线。
2. 雷达子页面参数卡片整齐排放，不再随机散落。
3. 主卡与参数卡之间无业务连线，趋势只通过颜色、标签、score bar 表达。
4. 默认画布只展示 top metrics，完整 metrics 仍可在下方 audit table 查看。
5. 点击参数卡仍能更新右侧 selected metric 明细。
6. Dashboard 拓扑页不受影响。
7. `npm run build` 通过。
8. P5 dashboard contract 验收通过或说明当前服务不可用。

## 验收记录

- `npm run build`：通过。
- `python scripts/validate_p5_dashboard_contract.py --base-url http://127.0.0.1:8118`：通过。
- 修改范围限定在雷达子页面 `activePage === 'radar'` 的 radar div 与相关 CSS；Dashboard 拓扑页未修改。
