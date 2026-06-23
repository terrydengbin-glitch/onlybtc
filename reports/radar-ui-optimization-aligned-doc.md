# Radar 子页面 UI 优化对齐方案：整齐卡片版

状态：方案确认稿

## 目标

在现有 onlyBTC 的 **雷达子页面** 内优化 UI，不重做全站页面结构，也不改拓扑子页面：

```text
保留：
  顶部状态栏
  左侧导航
  雷达子页面内的中心模块/模块概览卡
  雷达子页面内的左右两列 radar module 卡
  底部 horizon / alert 区
  右侧 detail drawer
  雷达圆环、网格、扫描氛围

移除/弱化：
  module -> BTC 连线
  metric -> module 连线
  metric -> BTC 连线
  满屏黄色虚线
```

趋势判断改为：

```text
卡片颜色 + 状态标签 + score bar + top drivers
```

不再依赖线条表达趋势。

## 本次修改边界

只优化 **雷达子页面** 中的 radar div / radar content div。

这次不优化拓扑子页面。拓扑页如果也有类似视觉问题，后续单独开任务处理。

允许修改：

```text
雷达子页面 radar div 内部：
  canvas toolbar
  module cards
  雷达子页面内部的 BTC / selected module 展示卡
  module card 排列
  radar background rings / sweep effect
  card color / score bar / state chip
  top 3 按钮触发右侧已有 drawer 的内容入口
```

禁止修改：

```text
全局 topbar
左侧主导航
右侧 drawer 容器布局
底部 horizon_views div
底部 alerts / invalidation / confirmation div
拓扑子页面 topology div
overview/article/evidence/history/settings 页面
FastAPI contract
P4.5 payload contract
btc_trend_cockpit 数据结构
```

实施时只改雷达子页面中 radar div 的 template / computed display helpers / scoped CSS。其他 div 只允许被动读取既有状态，不做结构调整。

## 核心交互

### 默认雷达子页面

只显示 14 个 radar module 卡片与中心 BTC cockpit 卡。

每张 module card 显示：

```text
module name
state / signal_stage
一句话摘要
score bar
top 3 按钮
```

### 点击 module card

右侧 detail drawer 展开：

```text
module summary
scores
top support drivers
top pressure drivers
top conflict drivers
data_quality_flags
metric table
```

### 点击 top 3

不在画布上展开参数卡，不画线。

只在右侧 detail drawer 中显示 top metrics。

## 颜色语义

```text
support / bullish:
  cyan-green border + green score bar

pressure / bearish:
  red border + red score bar

warning / mixed:
  gold border + gold score bar

neutral:
  blue-gray border + muted score bar

data quality / conflict:
  purple border + purple chip
```

## 布局规则

### 主画布

```text
左列：
  Macro Radar
  Treasury Credit
  Dollar Liquidity
  BTC Adoption
  Kline Orderflow
  Crypto Breadth

中心：
  BTC Cockpit v2

右列：
  Asia Risk
  BTC Total State
  Event Policy
  Fund Flow
  Onchain Valuation
  Derivatives Crowding
  Trade Structure Flow
  Options Volatility
```

实际排序可沿用现有 `topologyModules` 顺序，但视觉上必须两侧整齐对齐。

### 卡片尺寸

```text
module card:
  width: 220-250px
  min-height: 96px
  border-radius: 8px
  text max 2 lines

BTC card:
  width: 320-360px
  center fixed
```

## 禁止项

1. 不在默认拓扑页展示 metric 小卡片。
2. 不在默认拓扑页画 metric 连接线。
3. 不用线条表达趋势强弱。
4. 不让长文本撑爆 module card。
5. 不把 context-only / score=0 指标放在主画布。

## 实施顺序

```text
P5 UI:
  1. topology canvas 关闭/隐藏动态连线层
  2. module cards 改为双列整齐布局
  3. module card 文案压缩为 2 行
  4. top 3 改为打开右侧 detail drawer
  5. 中心 BTC card 保持 cockpit v2
  6. 保留雷达圆环和扫描背景
  7. build + dashboard contract
```

## DoD

1. 雷达子页面中默认只有 BTC/selected module 卡 + module 卡，无 metric 散卡。
2. 默认无连接线，或仅保留极淡背景装饰线，不表达业务关系。
3. 趋势可通过卡片颜色和 score bar 一眼识别。
4. 点击 module 后，右侧 drawer 能看到 top metrics。
5. 文本不溢出、不遮挡。
6. `npm run build` 通过。
7. P5 dashboard contract 通过。
