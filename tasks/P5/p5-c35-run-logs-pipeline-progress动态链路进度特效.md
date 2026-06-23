# P5-C35 Run Logs Pipeline Progress 动态链路进度特效

## 状态
DONE

## 所属 Phase
P5 Dashboard 与可视化层

## 背景
P5-C15 已完成 Run Logs 运行日志页，能够展示 run lineage、stage grid、warnings/errors、审计报告链接和 latest run 状态。当前页面在点击 `Run Full Chain` 后可以进入运行中状态，但缺少一套清晰、可视化、与真实 stage 状态绑定的动态 Pipeline 进度特效。

## 目标
在 Run Logs 页面顶部新增或升级一个 Pipeline Progress 组件，用于展示：

- `P1 collect -> P2 radar -> P3 scoring -> P4.5 final -> LLM analyst`
- 每个阶段的状态节点。
- 数据包沿链路流动的视觉反馈。
- 运行中、完成、降级、失败、等待等状态。
- 审计链路正在推进的实时感。

## 交互与状态规则
- `state.running = true` 时启用动态特效。
- 阶段节点状态来自 `stages`：
  - completed：绿色 done。
  - running / pending：金色 active。
  - completed_with_llm_errors：紫色/黄色 degraded。
  - failed / error：红色 failed。
  - unknown：灰蓝 waiting。
- 进度条长度根据已完成阶段数量计算。
- 数据包动画只在 running 或 active 阶段存在时播放。
- LLM timeout 或 completed_with_llm_errors 时，LLM 节点显示 degraded，但 deterministic 主报告仍应显示可审计。
- 点击阶段节点可定位到对应 stage card 或打开该阶段 audit report。

## 视觉方案
- 横向轨道展示五个核心节点：
  - P1 Collect
  - P2 Radar
  - P3 Scoring
  - P4.5 Final
  - LLM Analyst
- 轨道底线为低亮蓝色。
- 已完成进度为 cyan -> blue -> gold 渐变。
- 当前 active 节点有扫描环和呼吸光。
- 小光点沿进度轨道移动，表示数据包传递。
- Run card 背景保留暗色工作台风格，不做全屏 hero。
- 与当前 Dashboard 暗色视觉系统一致，不使用过度装饰。

## 移动端与可访问性
- 小屏改为纵向 stage list 或隐藏轨道流光，只保留阶段状态和文本。
- `prefers-reduced-motion` 下关闭 packet animation、stripe animation、scan ring，保留静态进度状态。
- 所有节点必须有可读文本，不仅依赖颜色判断状态。

## 非目标
- 不修改 P1/P2/P3/P4.5 后端 pipeline。
- 不修改 FastAPI 契约。
- 不改变 Run Full Chain 的执行逻辑。
- 不覆盖 P5-C15 的 stage grid 和 audit reports。
- 不引入 canvas、Three.js 或外部动画库。

## DoD
- Run Logs 页顶部出现 Pipeline Progress 动态链路组件。
- 阶段节点能按真实 `stages` 状态显示 done / active / degraded / failed / waiting。
- `state.running = true` 时轨道和 packet 动画可见。
- 完成或失败后动画停止或降级为静态结果。
- 进度长度与阶段完成度一致。
- LLM 降级状态不误导为全链路失败。
- 点击阶段节点能关联到 stage card 或对应 audit report。
- 移动端不溢出、不遮挡。
- `prefers-reduced-motion` 下动画降级。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录
- 已将 Run Logs 顶部 current chain 卡片升级为 Pipeline Progress 组件。
- 已接入 `stages`、`latestRun`、`state.running`，支持 done / active / degraded / failed / waiting 状态。
- 已新增 cyan -> blue -> gold 进度轨道、移动 packet、active 扫描环、运行中面板扫光。
- 已保留 P5-C15 的 stage grid、run lineage、audit reports 和 warning/error 区块。
- 阶段节点点击时会打开该阶段 `audit_report`，没有报告时保持静态。
- 已加入移动端纵向降级和 `prefers-reduced-motion` 动画降级。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
