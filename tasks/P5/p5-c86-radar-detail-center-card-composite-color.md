# P5-C86 Radar Detail Center Card Composite Color

## 状态

DONE

## 背景

Radar Detail 子页面中，中心模块卡片当前虽然绑定了 `moduleDisplayClass(selectedRadarModule)`，但 CSS 默认仍以青绿色边框和光晕为主。

实际业务上，类似 `derivatives_crowding` 的状态可能是：

```text
module_score = -0.294
module_effective_direction = neutral
signal_stage = early_warning
pressure_drivers > support_drivers
btc_implication = trend_fragile
```

这类状态不是 confirmed bearish，但也不应该显示为绿色支撑卡。它应该表现为 `mixed / warning / fragile`，让用户一眼看出：存在压力，但还没有被 BTC response / residual 确认为最终方向。

当前问题属于 UI 表达层未跟上业务语义，不是后端分数链条断裂。

## 目标

让 Radar Detail 中心卡、模块切换按钮和必要的模块状态 chip 根据以下字段联合染色：

```text
module_score
module_effective_score
module_direction
module_effective_direction
signal_stage
btc_implication
support_drivers
pressure_drivers
conflict_drivers
data_quality_flags
```

核心原则：

```text
confirmed bearish / clear negative score => red pressure
confirmed bullish / clear positive score => green support
early_warning + pressure > support => yellow/orange mixed warning
early_warning + support > pressure => cyan/green weak support warning
neutral + score near zero => neutral gray-blue
data quality / stale / fallback => purple quality
```

## 范围

涉及：

- `frontend/src/App.vue`
- `frontend/src/styles.css`
- Radar Detail 子页面
- Radar module switch buttons
- Radar center module card

不涉及：

- 后端评分算法
- P4.5 acceptance / residual gate
- Event Window UI
- Dashboard BTC 主卡 final confirmed 逻辑

## 业务判色规则建议

新增或调整前端函数，例如：

```text
moduleCompositeTone(module):
  1. data_quality_flags / freshness stale / fallback => quality
  2. effective_direction bearish 且 abs(score) >= threshold => bear
  3. effective_direction bullish 且 abs(score) >= threshold => bull
  4. signal_stage in early_warning/fast_signal 且 pressure > support => mixed_pressure
  5. signal_stage in early_warning/fast_signal 且 support > pressure => mixed_support
  6. score <= -0.10 且 pressure > support => bear 或 mixed_pressure
  7. score >= +0.10 且 support > pressure => bull 或 mixed_support
  8. conflict_drivers 非空或 direction conflict => mixed
  9. else neutral
```

衍生品模块特殊边界：

```text
derivatives_crowding:
  crowding_fragility_warning / trend_fragile / early_warning
  不直接染成 confirmed red；
  应染成 mixed_pressure / warning amber。
```

## UI 要求

中心卡应有明确视觉区分：

```text
bull: green/cyan border + support glow
bear: red border + pressure glow
mixed_pressure: amber/orange border + warning glow
mixed_support: teal/amber mixed border + weak support glow
neutral: muted blue-gray border
quality: purple border
```

模块切换按钮同样使用该判色逻辑，避免按钮和中心卡颜色不一致。

中心卡中增加小型解释标签，优先展示：

```text
score -0.294
stage early_warning
pressure 1 / support 0
tone mixed_pressure
```

## DoD

- [x] `derivatives_crowding` 在 `pressure_drivers > support_drivers` 且 `signal_stage=early_warning` 时不再显示绿色中心卡。
- [x] 中心卡颜色由 `module_score + signal_stage + support/pressure + effective_direction` 联合决定。
- [x] 模块切换按钮和中心卡使用同一套 tone 逻辑。
- [x] `neutral` 但有显著 pressure 的模块显示为 warning/mixed，而不是 support。
- [x] `confirmed_signal + bullish` 仍显示 support green。
- [x] `confirmed_signal + bearish` 显示 pressure red。
- [x] `data_quality / stale / fallback` 优先显示 quality purple。
- [x] 不改变后端分数、不改变 P4.5 confirmed gate。
- [x] `npm run build` 通过。

## 验收命令

```powershell
cd frontend
npm run build
```

## 人工验收

打开 Radar Detail：

```text
1. 选择 derivatives_crowding。
2. 若 support=2 / pressure=7 或 module_score<0 且 early_warning，应显示 warning/mixed pressure，而非绿色。
3. 选择 confirmed bullish 模块，应显示绿色。
4. 选择 confirmed bearish 模块，应显示红色。
```
