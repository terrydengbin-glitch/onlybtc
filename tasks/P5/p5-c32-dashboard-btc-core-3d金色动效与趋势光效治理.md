# P5-C32 Dashboard BTC Core 3D 金色动效与趋势光效治理

## 状态
DONE

## 所属 Phase
P5 Dashboard 与可视化层

## 背景
Dashboard 主屏已经具备 BTC 中心节点、14 个 Radar module 节点、拖拽布局、动态远离/深度缩放、SVG 连线、右侧摘要和子页面跳转。P5-C32 只增强中心 BTC Decision Node 的视觉层，不改变 P1/P2/P3/P4.5 数据契约，不改变 final_view、confidence、horizon、invalidation 或 publish article 的业务逻辑。

## 目标
把 Dashboard 中心 BTC 卡片升级为克制版 3D Core Node：

- 鼠标悬停时有轻微空间倾斜。
- BTC 标题为金黄色金属质感，并低频闪金光。
- 背后保留柔和 radar ring / halo。
- 光效跟随趋势状态变化。
- 不影响中心卡片的信息密度、可读性和现有按钮交互。

## 视觉原则
- 不是全屏 hero，不替代当前 Dashboard。
- 只增强中心 BTC card，不影响 14 个 Radar node 的布局。
- 动画低频、轻量、专业，不做强 glitch。
- 金色 BTC 字体作为第一视觉，但不得遮挡 final_view、confidence、reason、action button。
- 光效颜色跟随 `final_view`：
  - bullish：金色 + 青绿色边光
  - bearish：暗金 + 红色边光
  - neutral / watch：金色 + 蓝灰柔光
  - mixed：金色 + 黄色边光
  - quality issue：紫色轻闪

## 实施范围
- BTC 中心卡增加 hover 3D tilt：
  - `--btc-rx`
  - `--btc-ry`
  - `transform-style: preserve-3d`
  - `perspective`
- BTC 标题升级为 `.btc-gold-text`：
  - 金色渐变
  - 金属高光
  - 低频 shimmer
- 中心卡背景增加轻量 radar ring / halo。
- 鼠标离开后 tilt 回到 0。
- 移动端禁用 tilt，仅保留静态金色标题。
- 支持 `prefers-reduced-motion`：关闭或降低 shimmer、ring rotate、tilt transition。

## 非目标
- 不做全屏 `btc-stage`。
- 不引入 Three.js。
- 不重写 Dashboard 拓扑。
- 不改变 final_view / confidence / reason 的业务逻辑。
- 不把 signal chip 写死为装饰数据，继续使用真实 Dashboard API 数据。

## DoD
- BTC 中心卡 hover 时有轻微 3D 移动感。
- BTC 字体为金黄色金属质感，并偶尔闪金光。
- 动效颜色跟随 final_view / quality 状态。
- 决策文字、confidence、reason、按钮仍然清晰可读。
- 移动端不出现抖动或遮挡。
- `prefers-reduced-motion` 下动画明显减少或关闭。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录
- `frontend/src/App.vue`：为 BTC 中心卡接入 hover tilt 事件，鼠标离开后自动复位。
- `frontend/src/styles.css`：新增 BTC 金色字体、低频 shimmer、radar ring / halo、趋势状态边光、移动端 tilt 禁用和 reduced motion 降级。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
