# P5-C33 Dashboard Radar Node 轻量 3D Tilt 与拖拽深度协同

## 状态
DONE

## 所属 Phase
P5 Dashboard 与可视化层

## 背景
Dashboard 已具备 14 个 Radar module 节点、拖拽布局、动态远离/深度缩放和 SVG 连线。P5-C32 负责 BTC 中心节点 3D 金色光效；本卡只增强外围 Radar node 的轻量 3D tilt，并确保不破坏现有拖拽、远离和连线跟随。

## 目标
为 Dashboard 外围 Radar module card 增加轻量 3D hover tilt 和趋势边光，使节点更有空间层次；同时保留当前拖拽、靠近 BTC 放大、其他节点动态远离、连线实时跟随等交互。

## 技术方案
Radar node 拆成两层：

```html
<button class="node">
  <div class="node-tilt">
    card content
  </div>
</button>
```

- 外层 `node`：
  - 负责 `left/top`
  - 负责拖拽
  - 负责动态远离
  - 负责 scale / opacity / depth
  - 作为 SVG 连线锚点
- 内层 `node-tilt`：
  - 负责 hover 3D tilt
  - 负责趋势 glow / border light
  - 负责卡片内部视觉层

这样避免内层 tilt 覆盖外层拖拽 transform。

## 交互规则
- 默认状态：Radar node 只有轻微趋势边光，不持续大幅动画。
- hover 状态：当前 node 轻微 3D tilt。
- drag 状态：禁用 hover tilt，只保留拖拽抬起、阴影和外层 scale。
- 拖动某节点靠近 BTC：该节点继续放大，其他节点继续动态远离。
- 其他远离节点不额外 tilt，只保留现有 scale / opacity / depth。
- 移动端禁用 tilt，仅保留趋势颜色。

## 视觉规则
- bullish / support：青绿色边光。
- bearish / pressure：红色边光。
- mixed：黄色边光。
- quality / fallback / stale：紫色边光或虚线感。
- Radar node tilt 强度低于 BTC core：
  - `rotateX` 不超过 4deg
  - `rotateY` 不超过 5deg
- 不给 Radar node 使用金色 shimmer；金色只属于 BTC core。

## 非目标
- 不改变 Radar node 数据字段。
- 不重算 module score。
- 不改变 SVG 连线数据源。
- 不引入 Three.js。
- 不影响 P5-C03 的拖拽布局和 reset layout。

## DoD
- Radar node hover 有轻微 3D 倾斜。
- 拖拽时 tilt 不干扰拖拽位置。
- 拖动靠近 BTC 时，原有“当前节点放大、其他节点远离”的效果仍然存在。
- SVG 连线仍然连接到外层 node 位置，不因为 tilt 偏移。
- 趋势边光跟随 module direction。
- 移动端不出现 hover tilt 抖动。
- `prefers-reduced-motion` 下关闭 tilt transition 或明显降低动画。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录
- `frontend/src/App.vue`：Radar node 拆成外层 `.node` 与内层 `.node-tilt`，外层继续承载拖拽、位置、远离和连线锚点，内层承载 hover tilt。
- `frontend/src/App.vue`：新增 `handleRadarNodeMove` / `resetRadarNodeTilt`，拖拽开始时自动清零 tilt，移动端不启用 tilt。
- `frontend/src/styles.css`：新增轻量 3D tilt、趋势边光、drag 状态禁用 tilt、移动端与 `prefers-reduced-motion` 降级。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
