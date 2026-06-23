# P5-C34 Dashboard BTC Core 动态投影与 3D 悬浮感增强

## 状态
DONE

## 所属 Phase
P5 Dashboard 与可视化层

## 背景
P5-C32 已完成 BTC 中心卡的 3D tilt、金色 BTC 字体、低频扫光和末端星芒。当前还缺少一个更自然的空间反馈：鼠标移动到 BTC 卡片上时，卡片底部投影应随倾斜角度轻微偏移，让用户感觉卡片真的悬浮在 Dashboard 画布上。

## 目标
增强 BTC 中心卡 hover 时的 3D 悬浮感：

- 鼠标进入 BTC 卡片时，底部阴影增强。
- 阴影方向跟随卡片倾斜角度反向轻微偏移。
- 鼠标离开后阴影回到默认状态。
- 保持 BTC 字体金光、星芒、趋势边光和决策信息可读性。

## 技术方案
- 复用现有 `handleBtcMove`。
- 增加独立 `<span class="btc-dynamic-shadow">` 投影层，避免与 BTC radar ring / status pulse 伪元素冲突。
- 新增 CSS 变量：
  - `--btc-shadow-x`
  - `--btc-shadow-y`
  - `--btc-shadow-scale-x`
  - `--btc-shadow-scale-y`
  - `--btc-shadow-blur`
  - `--btc-shadow-opacity`
- 在鼠标移动时根据相对位置计算阴影偏移：
  - 鼠标靠左，阴影略向右。
  - 鼠标靠右，阴影略向左。
  - 鼠标靠上，阴影略向下并增强。
  - 鼠标靠下，阴影略收短。
- `resetBtcTilt` 同步恢复阴影变量。

## 视觉规则
- 阴影必须克制，不盖过 BTC 金色标题。
- 阴影不能造成卡片文字模糊或对比度下降。
- 不改变卡片尺寸和布局。
- 不影响外围 Radar node 拖拽、连线、hover tilt。
- 移动端不启用动态投影，仅保留静态阴影。
- `prefers-reduced-motion` 下关闭动态阴影过渡或降为静态。

## 非目标
- 不改 P4.5 数据契约。
- 不改 Dashboard API。
- 不改 BTC 决策文案和分数。
- 不引入 Three.js 或 canvas。
- 不调整 Radar node 的 P5-C33 行为。

## DoD
- BTC 卡片 hover 时底部阴影明显增强。
- 阴影方向随鼠标位置和卡片倾斜角度动态变化。
- 鼠标离开后 tilt 和阴影都回到默认状态。
- BTC 金色闪光、末端星芒仍正常显示。
- 决策文字、按钮和 score ring 不被阴影影响。
- 移动端不出现阴影跳动。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录
- `frontend/src/App.vue`：BTC 中心卡增加独立 `btc-dynamic-shadow` 投影层。
- `frontend/src/App.vue`：`handleBtcMove` 根据鼠标相对位置同步更新 tilt 与动态投影变量。
- `frontend/src/App.vue`：`resetBtcTilt` 同步恢复 tilt 和投影默认状态。
- `frontend/src/styles.css`：新增动态投影层的偏移、缩放、模糊、透明度变量，并在 reduced motion 下退化为静态投影。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
