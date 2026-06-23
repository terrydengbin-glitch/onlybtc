# P5 Dashboard UI 高保真方案

## 1. 设计目标

P5 Dashboard 是 onlyBTC 的核心使用界面。

它不是传统后台，也不是交易终端，而是一个 BTC 趋势感知、预警、证据审计和多 LLM 总控讨论面板。

用户打开页面后，应立刻看到：

- BTC 当前状态
- 当前是否有预警
- 哪些雷达正在影响 BTC
- 哪些数据源异常或过期
- 多 LLM 总控讨论是否存在分歧
- 哪些关键数据需要继续观察

界面目标：

- 一屏建立市场状态感
- 拓扑关系清晰
- 预警等级醒目但克制
- 数据密度高，但不杂乱
- 支持点击深入，不在首屏堆长文
- 明确区分观察建议和交易建议

必须覆盖的页面/视图：

- Dashboard 主拓扑页
- BTC 详情抽屉
- Article 文章页
- Evidence 证据页
- LLM Debate 多模型讨论页
- Alerts 预警页
- Invalidation 反证页
- Data Quality 数据质量页
- Run Logs 运行日志页
- Source Detail 数据源详情页
- Radar Detail 雷达详情页
- History / Replay 历史回放页

## 2. 目标用户

目标用户是关注 BTC 短周期趋势变化的研究者、交易辅助分析者或系统维护者。

他们需要快速判断：

- 当前市场是否正常
- 系统是否发现敏感变化
- 哪些模块支持当前判断
- 哪些模块反对当前判断
- 是否有事件窗口、数据质量或杠杆风险
- LLM 总控结论是否可信

## 3. 整体布局

### 3.1 页面结构

页面采用单页 Dashboard。

推荐桌面端布局：

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC Price / 24h / Alert / Run Once / Updated            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                 拓扑雷达区：BTC 中心节点 + 周围雷达分组                      │
│                                                                            │
│     宏观       流动性       信用          资金流         杠杆                │
│                                                                            │
│                         ┌────────────────────┐                             │
│                         │      BTC 中心       │                             │
│                         │ state / bias / risk │                             │
│                         │ confidence / alert  │                             │
│                         └────────────────────┘                             │
│                                                                            │
│     链上       价格结构     期权          亚洲风险       事件/Fed           │
│                                                                            │
├───────────────────────────────┬────────────────────────────────────────────┤
│ 左下：预警与观察队列            │ 右下：多 LLM 总控讨论摘要                    │
├───────────────────────────────┴────────────────────────────────────────────┤
│ 右侧抽屉：详情、文章、证据、LLM Debate、反证、数据质量、运行日志               │
└────────────────────────────────────────────────────────────────────────────┘
```

首屏优先级：

1. BTC 中心判断
2. 当前最高预警
3. 拓扑雷达方向
4. Run Once 状态
5. 多 LLM 分歧程度

主页面评审结论：

- 当前主拓扑方向通过，可以作为 P5 主 Dashboard 高保真基准。
- 后续优化重点是导航可发现性、子页面入口、Run Once 可点击反馈、多 LLM 展示文案和拓扑线条筛选。

### 3.2 响应式布局

桌面端：

- 主拓扑图占页面 65%-70% 高度
- 底部两栏：预警队列 + 多 LLM 讨论摘要
- 右侧可滑出详情面板

平板端：

- 拓扑图仍保留
- 底部信息区变成上下堆叠
- 详情以全屏抽屉打开

移动端：

- 不强求完整拓扑
- 使用“中心状态卡 + 分组雷达列表 + 预警列表”
- 多 LLM 讨论以时间线呈现

## 4. 视觉风格

### 4.1 风格关键词

- 专业
- 克制
- 高密度
- 暗色金融终端
- 科研仪表盘
- 非营销页面
- 非交易下单界面

### 4.2 色彩建议

背景：

- 主背景：`#0B0F14`
- 面板背景：`#111820`
- 次级面板：`#151E27`
- 边框：`#263241`

文字：

- 主文字：`#E6EDF3`
- 次文字：`#9AA7B2`
- 弱文字：`#66717D`

状态色：

- bullish：`#2DD4BF`
- bearish：`#F87171`
- neutral：`#94A3B8`
- mixed：`#FBBF24`
- info：`#60A5FA`
- watch：`#FBBF24`
- warning：`#FB923C`
- critical：`#EF4444`
- data_quality_bad：`#A855F7`

注意：

- 不要使用大面积渐变
- 不要做营销式 hero
- 不要使用过多发光效果
- BTC 闪耀只在 warning / critical 时出现，且持续时间有限

### 4.3 字体与密度

建议：

- 字体：Inter / IBM Plex Sans / system-ui
- 数字：使用 tabular-nums
- 主标题 18-22px
- 面板标题 13-14px
- 数据值 13-16px
- 标签 11-12px

信息密度应接近研究终端，不要做大卡片留白式布局。

## 5. 核心区域设计

## 5.0 左侧导航栏

主 Dashboard 左侧可以保留竖向图标导航，但必须提升可理解性。

导航项建议：

- 拓扑
- 雷达
- 证据
- 预警
- 数据质量
- 运行日志
- 历史回放
- 设置

交互要求：

- 当前页面/视图高亮
- hover 显示 tooltip
- 支持展开模式，展开后显示图标 + 文字
- 点击导航项打开对应子页面或详情抽屉
- 图标不能成为唯一信息来源

展开示例：

```text
[拓扑]
[雷达]
[证据]
[预警]
[数据质量]
[运行日志]
[历史回放]
[设置]
```

默认状态：

- 桌面端默认收起为 icon rail
- hover 或点击展开
- 移动端不显示左侧 rail，改为底部或抽屉导航

## 5.1 Top Bar

Top Bar 固定在顶部。

内容从左到右：

- onlyBTC Logo / 系统名
- BTC 当前价格
- 24h 涨跌
- 当前状态
- 当前最高预警等级
- 最近更新时间
- 数据质量总体状态
- Run Once 按钮
- 设置按钮

全站 Top Bar 字段必须统一为：

```text
BTC 价格 / 24h 涨跌 / 当前状态 / 预警等级 / 数据质量 / 更新时间 / Run Once
```

禁止在不同页面混用以下表达：

- 当前策略
- 当前联动
- 告警级别
- 健康度

统一替换为：

- 当前状态
- 预警等级
- 数据质量

示例：

```text
onlyBTC   BTC 108,420.5  +2.14%   State: leverage_squeeze   Alert: warning   Updated 10:42:18   Run Once
```

Run Once 按钮状态：

- idle：Run Once
- running：Running...
- success：Done
- failed：Failed
- cooldown：Cooldown

点击 Run Once 后：

- 按钮进入 running
- Top Bar 显示当前阶段
- 右下角出现任务进度 toast
- 完成后更新拓扑和预警
- Run Once 区域可点击，点击后打开 Run Logs，并定位到当前 run_id

优化要求：

- Alert Level 必须使用胶囊样式，避免只靠文字颜色
- Run Once running 状态必须显示当前阶段，例如 Fetching / Radar Analysis / LLM Debate / Reviewing / Publishing
- Data Quality 需要显示总体状态点，healthy 为青绿色，degraded 为紫色，critical 为红紫色
- Top Bar 高度控制在 48-56px，保持研究终端感

Run Once running 状态展示：

```text
Running...
multi_llm_debate
View Run Logs
```

其中 `View Run Logs` 可作为 hover tooltip 或小链接出现。

## 5.2 BTC 中心节点

BTC 中心节点是页面视觉中心。

必须显示：

- BTC
- 当前状态
- direction_bias
- confidence
- risk_level
- alert_level
- 一句话结论
- 减产倒计时
- 最近更新时间

示例：

```text
BTC
leverage_squeeze
Bias: volatile_up
Confidence: 58%
Risk: medium_high
Alert: warning

Trend remains up, but leverage risk is rising.

Halving: 2028-04 est. / Block 1,050,000
```

视觉规则：

- neutral：细边框，低亮度
- watch：边框变黄
- warning：轻微橙色脉冲
- critical：红色边框 + 限时闪耀
- data_quality_bad：紫色角标

优化要求：

- BTC 节点不能过大，避免压迫拓扑空间
- warning 使用轻微橙色脉冲，不要持续强闪
- critical 才允许短时间强闪耀
- 中心节点需要展示 confidence 进度条，但不能像交易盈亏条
- Halving 信息应弱化显示，作为长期背景，不抢短线状态

点击 BTC 中心节点：

- 打开右侧详情面板
- 默认显示“当前总控结论”
- 可切换 Tab：文章 / Evidence / 多 LLM / 反证 / 数据质量

为了让入口更明显，BTC 中心节点右下角应提供一个弱按钮：

```text
View Details / 查看详情
```

点击该按钮等同于点击 BTC 中心节点，打开 `BTC / Overview`。

BTC 中心节点的一句话结论必须是可点击对象，并在 hover 时显示：

```text
Read Article / 阅读完整分析
```

点击该一句话结论或 `Read Article` 入口，打开 `BTC / Article`。如果当前没有新文章，则进入最近一次已生成文章，并在顶部显示“使用最近文章，数据快照时间可能滞后”。

## 5.3 拓扑雷达区

雷达节点围绕 BTC 中心节点分布。

建议分组：

- 宏观雷达
- 美元流动性
- 美债 / 信用压力
- 资金流
- BTC 采用率
- 链上筹码
- 减产倒计时
- K 线盘口
- 衍生品拥挤度
- 交易结构 / 流量
- 期权波动率
- 加密市场广度
- 亚洲风险
- 事件 / 政策
- Fed 政策与主席言论
- 宏观日历预警
- 数据质量

每个雷达节点显示：

- 模块名
- signal
- strength
- confidence
- 数据质量点
- 最近更新时间
- 是否触发 algorithm_alert

节点示例：

```text
ETF Flow
mixed · 0.61
7D positive, 1D weakening
updated 10:40
```

连线规则：

- bullish 影响：青绿色线
- bearish 影响：红色线
- mixed：黄色虚线
- neutral：灰线
- data stale：紫色虚线
- 线条粗细代表 strength

拓扑优化要求：

- 节点间距要足够，避免连线和文字重叠
- 每个节点最多显示 2 行摘要
- 更长解释放在 hover tooltip 或详情页
- mixed 节点使用黄色虚线，避免误读成 bearish
- data_quality 影响应通过节点透明度、虚线和角标表现

连线显示策略：

- 默认只显示强影响线和异常线
- strength 较低的中性线默认弱化
- hover 某个节点时，高亮该节点相关连线
- 点击某个节点时，固定高亮该节点影响路径
- 提供线条过滤：
  - 全部
  - 强影响
  - 异常 / 过期
  - bullish
  - bearish
  - mixed

图例必须显示：

```text
强影响 / 中等影响 / 弱影响
看多 / 看空 / mixed / neutral / 数据异常
```

交互：

- hover 节点：显示核心 evidence tooltip
- click 节点：打开模块详情
- click 连线：显示该模块如何影响 BTC 总控

## 5.4 预警与观察队列

位置：底部左侧。

显示当前活跃 alert。

字段：

- alert_level
- alert_type
- title
- summary
- trigger_modules
- created_at
- cooldown_until
- watch_next

列表按优先级排序：

1. critical
2. warning
3. watch
4. info

卡片示例：

```text
WARNING · risk
杠杆拥挤风险上升
Funding 和 OI 同步升高，但现货成交没有同步放大。

Watch:
- BTC 是否站稳 4H 结构
- 现货成交是否补量
- Funding 是否继续升高
```

点击预警：

- 打开详情
- 显示 supporting_evidence
- 显示 conflicting_evidence
- 显示 auto_upgrade_condition
- 显示 auto_downgrade_condition

## 5.5 多 LLM 总控讨论摘要

位置：底部右侧。

展示 DeepSeek、Qwen、火山、Kimi 的讨论结果。

首屏摘要字段：

- consensus_score
- disagreement_level
- final_state
- minority_objection
- publish_allowed

字段展示文案建议：

```text
Consensus: 71%
Disagreement: medium
Final State: leverage_squeeze
Minority Objection: 1 active
Publish: allowed
```

不要直接显示工程布尔值：

```text
minority_objection: yes
publish_allowed: true
```

应替换为：

```text
Minority Objection: none / 1 active / 2 active
Publish: allowed / blocked / review required
```

模型卡片：

```text
DeepSeek
Vote: leverage_squeeze
Confidence: 64%
Changed: no
Top evidence: 4

Qwen
Vote: mixed
Confidence: 58%
Changed: yes
```

视觉规则：

- 模型观点一致：卡片边框接近
- 分歧大：卡片之间显示黄色分歧标记
- 少数派强反证：单独突出显示
- 主裁判采纳：显示 accepted 标签
- 主裁判拒绝：显示 rejected 标签

点击“查看讨论过程”：

- 打开多 LLM 详情面板
- 显示三轮过程：
  1. 独立盲审
  2. 交叉质询
  3. 修正与收敛
- 显示主裁判合成逻辑
- 显示反方审查结果

## 5.6 右侧详情面板

右侧详情面板用于深入查看，不打断主拓扑。

Tab：

- Overview
- Article
- Evidence
- LLM Debate
- Alerts
- Invalidation
- Data Quality
- Run Logs

## 5.7 主页面到子页面的导航规则

主 Dashboard 不使用复杂顶部多级导航。所有子页面默认通过右侧详情抽屉打开，并支持全屏展开。

核心原则：

- 主拓扑负责快速感知
- 右侧抽屉负责深入解释
- 点击主页面对象时，自动打开最相关的 Tab
- 抽屉顶部 Tab 始终可手动切换
- 抽屉支持关闭、全屏、返回主拓扑

### 5.7.1 点击入口映射

| 主页面点击对象 | 默认打开 Tab | 定位对象 | 用途 |
|---|---|---|---|
| BTC 中心节点 | Overview | 当前 BTC 总控结果 | 查看当前状态、主导驱动、冲突证据、信心解释 |
| BTC 中心节点 View Details | Overview | 当前 BTC 总控结果 | 明确进入 BTC 详情 Overview |
| BTC 中心节点的一句话结论 | Article | 最新文章 | 查看完整中文分析文章 |
| BTC 中心节点 Read Article | Article | 最新文章 | 明确进入 BTC 文章页 |
| 右侧详情抽屉 Article Tab | Article | 当前 snapshot 文章 | 从 Overview 切换到完整文章 |
| Quick View 的 Article | Article | 最新文章 | 从主拓扑底部快速进入文章 |
| 雷达节点单击 | Radar Detail | 对应 module_id | 查看该雷达模块完整状态、算法、证据、反证与上游来源 |
| 雷达节点 Evidence 入口 | Evidence | 对应 module_id | 查看该雷达 evidence + data |
| 雷达节点连线 | Evidence | 对应模块对 BTC 的影响 | 查看该模块如何影响总控 |
| Radar Detail 的 view evidence | Evidence | module_id / evidence_id | 查看模块证据审计 |
| Radar Detail 的 view source health | Data Quality | module_id upstream sources | 查看该模块上游来源健康 |
| Overview 的 Key Driver 行 | Evidence | 对应 module_id + evidence_id | 查看该驱动背后的数据与解释 |
| Overview 的 Conflicting Evidence 行 | Evidence | 对应 evidence_id | 查看冲突证据是否足够强 |
| 数据源节点 | Data Quality | 对应 source_id | 查看数据源健康、延迟、fallback |
| Data Quality 的 source 行 | Source Detail | source_id | 查看单个数据源配置、原始响应、标准化数据与影响面 |
| Data Quality 的 fallback chain | Source Detail | source_id / fallback_source_id | 查看 fallback 关系与当前使用来源 |
| Evidence 的 related_sources 行 | Source Detail | source_id | 查看该证据使用的数据源详情 |
| Run Logs 的 failed_source_id | Source Detail | source_id + run_id | 查看失败源的错误上下文与重试记录 |
| 数据质量节点 | Data Quality | overall quality | 查看系统数据质量和 confidence cap |
| Top Bar 的数据质量状态 | Data Quality | overall quality | 查看整体数据可靠性与系统限制 |
| Overview 的 Confidence Discount | Data Quality | quality_discount | 查看数据质量如何影响置信度 |
| Article 的数据质量说明 | Data Quality | article snapshot quality | 查看文章使用的数据快照质量 |
| Evidence 的 source_health_summary | Data Quality | source group | 查看该证据相关来源健康 |
| Run Logs 中的数据失败阶段 | Data Quality | source_id / job_id | 查看失败源、重试与 fallback |
| 预警卡片 | Alerts | 对应 alert_id | 查看预警详情、证据、升级/降级条件 |
| Alerts 中的 supporting evidence | Evidence | 对应 evidence_id | 查看预警成立依据 |
| Alerts 中的 conflicting evidence | Evidence | 对应 evidence_id | 查看预警被削弱的依据 |
| 预警队列标题 | Alerts | active alerts | 查看全部活跃预警 |
| Top Bar 预警等级胶囊 | Alerts | current highest alert | 查看当前最高预警与全部活跃预警 |
| BTC Overview 的 Alert Level | Alerts | 当前状态关联预警 | 查看该状态为什么触发预警 |
| Radar Detail 的 algorithm_alert | Alerts | 该模块触发的预警 | 查看模块级预警详情 |
| 多 LLM 摘要面板 | LLM Debate | 最新 debate_id | 查看多模型讨论过程 |
| 模型卡片 | LLM Debate | 对应 model + round | 查看该模型观点、证据和修正 |
| LLM Debate 中的 evidence chip | Evidence | 对应 evidence_id | 查看模型引用的证据原文 |
| 少数派反证 | LLM Debate | minority_objection | 查看少数派反证是否被采纳 |
| What Would Change The View | Invalidation | 对应反证条件 | 查看触发距离和触发后动作 |
| 反证条件标签 | Invalidation | 对应 invalidation_id | 查看模块级或总控级反证 |
| Article 中的反证条件 | Invalidation | 对应 invalidation_id | 查看该条件的触发距离和历史状态 |
| Alerts 的 Related Invalidation | Invalidation | 对应 alert_id + invalidation_id | 查看预警解除、升级或反向条件 |
| Evidence 的 invalidation_signals | Invalidation | 对应 module_id + invalidation_id | 查看模块证据失效条件 |
| Radar Detail 的 view invalidation | Invalidation | 对应 module_id | 查看该雷达模块全部反证条件 |
| Run Once 按钮 | Run Logs | 当前 run_id | 查看当前全流程运行阶段 |
| Run Once 状态文本 | Run Logs | 当前 step | 查看运行日志和 worker 状态 |
| Top Bar Running 状态 | Run Logs | 当前 run_id / current_step | 查看当前运行进度 |
| 任务进度 toast | Run Logs | 当前 run_id | 查看当前任务明细 |
| Data Quality 的 failed job | Run Logs | job_id | 查看失败抓取、重试和错误上下文 |
| LLM Debate 的 run_id | Run Logs | run_id + debate_step | 查看多模型讨论所在运行链路 |
| Article 的生成记录 | Run Logs | publish_step / article_id | 查看文章生成与发布阶段 |
| 文章 evidence 标记 | Evidence | 对应 evidence_id | 从文章跳到证据 |
| 历史回放入口 | History / Replay | 对应 snapshot_id | 查看历史快照和评分 |
| Alerts 的历史预警 | History / Replay | linked_snapshot_id / alert_id | 回放预警触发时的上下文和后续验证 |
| Article 的历史版本 | History / Replay | article_id / snapshot_id | 查看文章生成时的数据快照 |
| Run Logs 的 snapshot_id | History / Replay | snapshot_id | 查看该次运行产出的历史状态 |
| LLM Debate 的历史 debate | History / Replay | debate_id / snapshot_id | 查看当时模型分歧与后续结果 |

### 5.7.2 右侧抽屉行为

抽屉打开时：

- 保持主拓扑在左侧可见
- 抽屉宽度默认 480-560px
- 宽屏可以扩展到 600-720px
- 小屏直接全屏

抽屉顶部必须显示：

- 当前对象标题
- 当前对象状态
- 更新时间
- 全屏按钮
- 关闭按钮

右上角关闭按钮规范：

- 所有详情页 / 子页面右上角必须提供 `关闭` 按钮或 `X` 图标。
- `关闭` 不能被设置齿轮、更多菜单或其他图标替代。
- 如果页面同时需要设置入口，设置入口必须放在关闭按钮左侧或页面内容区，不能占用最右关闭位置。
- 关闭按钮 hover tooltip：`关闭 / Close`。

抽屉 Tab：

```text
Overview / Article / Evidence / LLM Debate / Alerts / Invalidation / Data Quality / Run Logs
```

Tab 规则：

- 默认 Tab 由点击对象决定
- 用户可随时切换 Tab
- 切换 Tab 时保留当前上下文对象
- 例如点击 ETF Flow 打开 Evidence 后，切到 Invalidation，应显示 ETF Flow 相关反证
- 例如点击 warning 预警打开 Alerts 后，切到 Evidence，应显示该预警关联证据

### 5.7.3 全屏模式

复杂子页面支持全屏展开：

- LLM Debate
- Evidence
- Data Quality
- Run Logs
- History / Replay

全屏模式要求：

- 左上角显示返回 Dashboard
- 保留 Top Bar 简版
- 保留当前对象上下文
- 支持返回右侧抽屉模式

### 5.7.4 快捷入口

为避免用户不知道可点击，主页面应提供轻量 Quick View 入口。

建议位置：

- BTC 中心节点下方
- 或右侧详情面板顶部
- 或主拓扑底部工具条

文案：

```text
Quick View:
Overview · Article · Evidence · LLM Debate · Alerts · Invalidation · Data Quality · Run Logs
```

也可以使用更明确的文案：

```text
Open Detail:
Overview · Article · Evidence · LLM Debate · Alerts · Invalidation · Data Quality · Run Logs
```

视觉要求：

- 小字号
- 低对比度
- hover 高亮
- 不抢 BTC 中心节点视觉焦点
- 每个入口必须有清晰 hover 状态
- 推荐使用小胶囊按钮或下划线链接，避免看起来像普通文本
- 当前打开的 Tab 需要高亮

### 5.7.5 面包屑与返回

子页面需要显示当前上下文。

示例：

```text
Dashboard / BTC / Evidence / ETF Flow
Dashboard / Alerts / warning / leverage_squeeze
Dashboard / LLM Debate / 2026-05-19T10:42
Dashboard / Data Quality / OKX
```

返回规则：

- 关闭抽屉：回到主拓扑
- 返回按钮：回到上一个上下文
- 全屏返回：回到 Dashboard + 右侧抽屉

## 6. 关键组件清单

### 6.1 AppShell

包含：

- TopBar
- MainTopology
- BottomPanels
- DetailDrawer
- Toast / TaskProgress

### 6.2 BtcCenterNode

Props：

- btc_state
- direction_bias
- confidence
- risk_level
- alert_level
- summary
- halving_countdown
- updated_at
- data_quality

### 6.3 RadarNode

Props：

- module_id
- name
- signal
- strength
- confidence
- data_quality
- algorithm_alert
- updated_at
- top_observation

### 6.4 AlertCard

Props：

- alert_level
- alert_type
- title
- summary
- trigger_modules
- watch_next
- cooldown_until

### 6.5 DebatePanel

Props：

- debate_id
- models
- consensus_score
- disagreement_level
- minority_objection
- final_state
- publish_allowed

### 6.6 RunOnceControl

Props：

- status
- current_step
- started_at
- finished_at
- error

## 7. 子页面与详情视图

所有子页面优先使用右侧详情抽屉呈现，必要时可以全屏展开。

抽屉宽度建议：桌面端 480-560px，宽屏端 600-720px，小屏端全屏。

抽屉顶部固定显示：标题、当前对象状态、更新时间、关闭按钮、全屏展开按钮。

### 7.1 BTC 详情 Overview

目标：解释当前 BTC 总状态。

内容区块：

- Current State
- Key Drivers
- Conflicting Evidence
- Confidence Explanation
- Risk Level Explanation
- What Would Change The View
- Watch Next

Current State 显示：state、bias、confidence、risk_level、alert_level、previous_state、updated_at。

Key Drivers 每条显示模块名、方向、strength 和简短解释；Conflicting Evidence 每条必须能点击跳转到来源模块。

Confidence Explanation 需要显示扣分来源，例如 data_quality_discount、event_window_discount、disagreement_discount。

What Would Change The View 分成两列：看涨强化将来自、看跌/反转将来自。每条都必须是可观察条件，不能出现交易动作。

推荐布局：

```text
┌──────────────────────────────────────────────┐
│ BTC / Overview                               │
│ 当前状态 leverage_squeeze · updated 10:42     │
├──────────────────────────────────────────────┤
│ Current State                                │
│ state / bias / confidence / risk / alert     │
├──────────────────────────────────────────────┤
│ Key Drivers                                  │
│ 表格：Factor / Signal / Impact / Why         │
├──────────────────────────────────────────────┤
│ Conflicting Evidence                         │
│ 列表：冲突证据 + 来源模块 + 跳转入口          │
├──────────────────────────────────────────────┤
│ Confidence Explanation                       │
│ confidence bar + discounts                   │
├──────────────────────────────────────────────┤
│ Risk Level Explanation                       │
│ 风险构成：杠杆 / 流动性 / 宏观 / 事件          │
├──────────────────────────────────────────────┤
│ What Would Change The View                   │
│ 看涨强化来自 / 看跌或反转来自                  │
├──────────────────────────────────────────────┤
│ Watch Next                                   │
│ 下一次更新重点观察                            │
└──────────────────────────────────────────────┘
```

Current State 字段：

- State: `leverage_squeeze`
- Bias: `volatile_up`
- Confidence: `58%`
- Risk Level: `medium_high`
- Alert Level: `warning`
- Previous State: `volatile_up`
- Updated At: `10:42`

Key Drivers 表格字段：

- Factor
- Signal
- Impact
- Why it matters

示例：

| Factor | Signal | Impact | Why it matters |
|---|---|---:|---|
| ETF Flow | bullish / mixed | +0.14 | 7D 净流入仍为正，但 1D 转弱 |
| K-line & Orderflow | bullish | +0.16 | 现货跟随，趋势延续 |
| Derivatives Crowding | bearish | -0.18 | Funding 与 OI 快速上升 |

Confidence Explanation 必须显示：

- base_confidence
- data_quality_discount
- event_window_discount
- disagreement_discount
- final_confidence

示例：

```text
Base 75% - disagreement 12% - event window 5% = final 58%
```

Risk Level Explanation 必须说明 risk_level 来自哪里：

- leverage risk
- liquidity risk
- macro risk
- event risk
- data quality risk

What Would Change The View 必须只写观察条件。

禁止：

- 推荐仓位
- 开仓点
- 止损位
- 买入 / 卖出

允许：

- BTC 失守 4H 结构后风险升高
- ETF flow 连续转负会削弱当前判断
- Funding 高位但现货不跟会提高杠杆风险

### 7.2 Article 文章页

目标：阅读系统生成的完整中文分析文章。

入口：

- 主拓扑 BTC 中心节点的一句话结论
- BTC 中心节点 `Read Article / 阅读完整分析`
- 右侧详情抽屉顶部 `Article` Tab
- 主拓扑底部 `Quick View: Article`
- Alerts 页面中的“查看关联文章”
- History / Replay 页面中的“查看当时文章”

顶部信息：文章生成时间、触发原因、alert_level、publish_allowed、使用的数据快照时间、使用的 debate_id、模型裁判结果。

页面定位：

- Article 是系统最终可读报告，不是交易指令页。
- 文章必须把总控结论、关键证据、冲突证据、反证条件和数据质量说明放在同一阅读流里。
- 用户读完后应知道“当前系统为什么这样判断、哪些条件会改变判断、接下来重点观察什么”。
- 文章正文中的证据编号必须可点击跳转到 Evidence 页。
- 文章中的反证条件必须可点击跳转到 Invalidation 页。

文章结构：

1. BTC 当前状态一句话
2. 今日主导因子
3. 宏观环境
4. 美元流动性
5. 资金流
6. 杠杆与衍生品
7. 链上估值与筹码
8. 价格结构
9. 期权与波动率
10. 事件风险
11. 观察建议与风险提示
12. 当前判断的反证条件
13. 数据质量说明

交互：点击 evidence 标记跳到 Evidence 页；点击反证条件跳到 Invalidation 页；点击模型摘要跳到 LLM Debate 页。

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├───────────────┬──────────────────────────────────────────────┬───────────────┤
│ Article Meta  │ Article Body                                 │ Context Panel │
│ - article_id  │ 1. BTC 当前状态一句话                         │ - Evidence    │
│ - trigger     │ 2. 今日主导因子                               │ - Model Judge │
│ - snapshot    │ 3. 宏观环境                                   │ - Invalidation│
│ - publish     │ 4. 美元流动性                                 │ - Data Quality│
│ - author      │ ...                                           │ - Quick Links │
│ - read time   │ 13. 数据质量说明                              │               │
└───────────────┴──────────────────────────────────────────────┴───────────────┘
```

左侧 Article Meta：

- 文章标题
- 文章 ID
- 生成原因：scheduled / anomaly_triggered / manual_run_once
- 文章版本
- 生成时间与数据快照时间
- alert_level 与 publish_allowed
- 文章目录锚点
- 关联页面入口：Overview / Evidence / LLM Debate / Invalidation / Data Quality

中间 Article Body：

- 正文宽度控制在适合阅读的范围，避免铺满屏幕。
- 每个段落最多 3-5 行，核心判断先给结论，再给证据。
- 每个关键判断后面显示 evidence chip，例如 `E-1042`、`E-1060`。
- 重要状态词使用一致颜色：bullish / bearish / mixed / warning / critical。
- “观察建议与风险提示”只允许写观察重点和风险变化条件。
- “当前判断的反证条件”必须放在正文后段，不能隐藏在侧边栏。

右侧 Context Panel：

- 关键证据：列出 Top Evidence chips，点击进入 Evidence。
- 模型摘要：展示 consensus_score、disagreement_level、minority_objection、judge_result。
- 反证条件：展示 3-5 条最重要的 invalidation condition。
- 数据质量：展示 completeness、freshness、source conflict、confidence cap。
- 快捷导航：Evidence / LLM Debate / Invalidation / History Replay。

文章页状态：

- `latest`：当前最新文章。
- `stale`：文章对应的数据快照已经落后当前 Dashboard。
- `blocked`：多 LLM 或反方审查阻止发布，仅内部可见。
- `draft`：仍在生成或等待审查。

按钮：

- `收藏`
- `分享`
- `导出 PDF`
- `查看 Evidence Pack`
- `查看 LLM Debate`
- `返回 Overview`

Article 页面禁止出现：

- 推荐仓位
- 建议仓位
- 开仓区间
- 止损
- 止盈
- 杠杆
- 做多 / 做空指令
- 买入 / 卖出指令

如果需要表达风险强弱，使用以下替代表达：

```text
风险暴露参考：低 / 中 / 高
观察优先级：低 / 中 / 高
当前建议：保持观察，等待反证条件确认
```

示例替换：

```text
错误：推荐仓位（参考）30%-50%
正确：风险暴露参考：中等；观察优先级：高；等待反证条件确认。
```

### 7.3 Evidence 证据页

目标：让用户看到每个结论背后的 evidence + data。

入口：

- 左侧导航栏 `证据`
- 主拓扑雷达节点
- 主拓扑雷达节点到 BTC 的连线
- BTC Overview 的 Key Drivers 行
- BTC Overview 的 Conflicting Evidence 行
- Article 正文中的 evidence chip
- Alerts 里的 supporting evidence / conflicting evidence
- LLM Debate 里的 evidence chip
- Radar Detail 的 `view evidence`
- History / Replay 的“查看当时 Evidence Pack”

页面定位：

- Evidence 是“证据审计页”，不是文章页，也不是模型推理页。
- 它要证明每个 Claim 是否有 Data 支撑，并说明 Interpretation 如何从 Data 得出。
- 用户应能看到：数据来自哪里、是否过期、趋势窗口是什么、是否存在冲突来源、该证据如何影响 BTC 总控。
- 没有 Data 的 Claim 不允许进入 Evidence 页面。
- LLM 的观点不能替代 Evidence；Evidence 页只展示结构化数据、算法特征和可追溯解释。

布局：左侧模块列表，中间证据详情，右侧来源与质量上下文。

模块列表显示：module_name、signal、strength、confidence、data_quality、algorithm_alert。

证据详情显示：evidence_summary、supporting_data、historical_features、conflicting_evidence、risk_flags、invalidation_signals。

证据卡片格式：

```text
Claim:
7D ETF flow remains positive.

Data:
etf_flow_7d = ...

Interpretation:
Supports persistent demand, but 1D flow is weakening.
```

要求：没有 data 的 claim 不展示；stale 数据必须有角标；conflicting evidence 必须单独分区。

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├────────────────┬──────────────────────────────────────────────┬──────────────┤
│ Module List    │ Evidence Detail                              │ Context      │
│ - Macro        │ Header: selected module + signal + quality    │ - sources    │
│ - USD Liquidity│ Claim / Data / Interpretation                 │ - health     │
│ - ETF Flow     │ Evidence Summary                              │ - raw/normal  │
│ - Derivatives  │ Supporting Data Top 5                         │ - history    │
│ - Data Quality │ Historical Features                           │ - links      │
└────────────────┴──────────────────────────────────────────────┴──────────────┘
```

左侧 Module List：

- 搜索模块名称或 evidence_id。
- 筛选：signal、data_quality、algorithm_alert、source_status、module_group。
- 每个模块行显示：
  - module_name
  - signal：bullish / bearish / mixed / neutral
  - strength
  - confidence
  - data_quality：high / medium / low / stale
  - algorithm_alert：none / watch / warning / critical
- 点击模块后，中间区域定位到该模块的 evidence。

中间 Evidence Detail：

- 顶部显示当前模块：
  - module_id
  - module_name
  - signal
  - strength
  - confidence
  - data_quality
  - updated_at
  - related_alerts
- 核心三段必须固定出现：
  - Claim：该证据支持什么主张。
  - Data：用于支持 Claim 的具体数值、窗口、变化率、历史分位。
  - Interpretation：为什么这些 Data 支持或削弱当前判断。
- 支持数据区：
  - 显示 Top 5 关键数据点。
  - 每个数据点显示当前值、变化窗口、方向、权重、时效。
  - stale 或 fallback 数据必须有角标。
- 历史特征区：
  - 显示 24h / 7d / 30d / 90d 趋势。
  - 对需要趋势判断的数据，必须显示过去窗口对比。
- 冲突证据区：
  - 单独列出与当前 Claim 方向相反或强度不足的证据。
  - 显示 contradiction_strength、source、time_window、impact。
- 风险标记区：
  - 显示 risk_flags：event_window、data_delay、source_conflict、overcrowding、macro_shock。
- 反证信号区：
  - 显示与该模块相关的 invalidation_signals，并允许跳转到 Invalidation。

右侧 Context Panel：

- related_sources：来源名称、method、freshness、status。
- source_health_summary：健康 / 延迟 / 过期 / 不可用比例。
- source_conflicts：相同指标在不同来源的差异。
- data_quality_note：解释该模块置信度是否被降权。
- quick links：Overview / Article / LLM Debate / Invalidation / Source Detail。

Evidence 状态：

- `high_quality`：数据完整、时效正常、来源一致。
- `medium_quality`：部分来源延迟或存在轻微冲突。
- `low_quality`：关键字段缺失、来源冲突明显、置信度降权。
- `stale`：超过 freshness SLA，仍展示但必须降权。
- `fallback`：主来源失败，使用备用来源。

Evidence 页禁止：

- 用 LLM 结论替代数据。
- 显示没有 Data 的 Claim。
- 隐藏 stale / fallback / source conflict。
- 给出买入、卖出、开仓、止损、止盈、杠杆、仓位建议。

### 7.4 LLM Debate 多模型讨论页

目标：完整可视化 DeepSeek、Qwen、火山、Kimi 的讨论过程。

页面定位：

- LLM Debate 是“结构化审议页”，不是自由聊天页。
- 所有模型必须基于同一份冻结的 Evidence Pack 推理。
- 模型不能引入未在 Evidence Pack 中出现的新事实。
- 页面要让用户看清：每个模型最初怎么判断、谁质询了谁、质询基于哪些证据、观点是否修正、主裁判为何采纳或拒绝。
- 最终结论不能简单按多数票决定，必须经过状态机约束、数据质量约束、强反证条件、证据权重和多模型共识共同合成。

入口：

- 主拓扑底部多 LLM 总控讨论摘要
- 主拓扑模型卡片
- 右侧详情抽屉顶部 `LLM Debate` Tab
- Overview 的模型摘要 / 分歧标签
- Article 的模型摘要或 `查看 LLM Debate`
- Evidence 页中被模型引用的 evidence chip
- Run Logs 中的 `multi_llm_debate` 阶段
- History / Replay 中的历史 LLM Debate

辩论形式：

- 不使用普通聊天气泡作为主结构。
- 使用“轮次卡片 + 质询链路 + 修正记录 + 裁判合成”的审计式布局。
- 可以保留简短原文摘录，但必须挂在结构化字段下面。

页面分为 5 层：

1. Evidence Pack 摘要
2. Round 1 独立盲审
3. Round 2 交叉质询
4. Round 3 修正与收敛
5. 主裁判合成 + 反方审查

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC state / alert / data quality / Run Once               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Debate Summary: consensus / disagreement / final_state / publish_allowed     │
├──────────────────────────────────────────────────────────────────────────────┤
│ 1 Evidence Pack Summary                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ 2 Round 1 Independent Review: DeepSeek / Qwen / 火山 / Kimi                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ 3 Round 2 Cross Challenge: A -> B challenge cards with evidence refs          │
├──────────────────────────────────────────────────────────────────────────────┤
│ 4 Round 3 Revision: changed / stable / confidence adjustment                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ 5 Judge Synthesis + Adversarial Review                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### 7.4.1 Evidence Pack 摘要

显示：当前模块 JSON 数量、触发的 algorithm_alert、状态机候选状态、数据质量摘要、事件窗口状态、预警候选等级。

使用紧凑摘要卡，不展示全部原始数据。

必须显示：

- evidence_pack_id
- snapshot_time
- module_json_count
- valid_evidence_count
- stale_evidence_count
- triggered_algorithm_alert_count
- state_machine_candidates
- data_quality_score
- event_window_status
- confidence_cap

Evidence Pack 必须是只读冻结态。辩论过程中不允许模型修改 Evidence Pack，只能引用 evidence_id。

#### 7.4.2 Round 1 独立盲审

模型卡片：

```text
DeepSeek
State Vote: leverage_squeeze
Bias Vote: volatile_up
Confidence: 66%
Risk: medium_high
Alert Vote: warning
Top Evidence: 8
Conflicts: 3
```

每张卡可展开：top_evidence、conflicting_evidence、invalidation_focus、reasoning_summary、must_not_publish_reason。

Round 1 规则：

- 模型之间互不可见。
- 每个模型必须输出同一份结构化 JSON。
- 必须列出 top_evidence 和 conflicting_evidence。
- 必须给出 confidence，并说明 confidence_discount。
- 必须声明是否存在 must_not_publish_reason。
- 如果引用证据，必须使用 evidence_id，不能只写自然语言。

Round 1 输出字段：

```text
model_id
state_vote
bias_vote
risk_vote
alert_vote
confidence
top_evidence[]
conflicting_evidence[]
invalidation_focus[]
confidence_discount[]
reasoning_summary
must_not_publish_reason
```

#### 7.4.3 Round 2 交叉质询

用连线图或列表展示模型质询关系。

质询卡：

```text
Qwen -> Kimi
Issue: overconfidence
Description: Kimi ignored ETF 1D weakening and funding crowding.
Evidence Reference: derivatives.algorithm_alert
```

过滤器：ignored_conflict、overconfidence、weak_evidence、state_machine_violation、data_quality_issue。

Round 2 规则：

- 系统根据 Round 1 的差异自动生成质询任务。
- 质询不是开放聊天，而是定向 challenge。
- 每条 challenge 必须指向 target_model、target_claim、issue_type 和 evidence_id。
- 被质询模型必须回答是否接受质询、是否修正信心、是否改变状态判断。
- 未回答或回答缺少 evidence_id 的质询标记为 invalid_response。

质询类型：

```text
ignored_conflict
overconfidence
weak_evidence
state_machine_violation
data_quality_issue
event_window_underweight
minority_objection
```

质询卡字段：

```text
challenger_model
target_model
issue_type
target_claim
evidence_refs[]
challenge_summary
required_response
severity
target_response
accepted_challenge
confidence_change
state_changed
```

#### 7.4.4 Round 3 修正与收敛

显示哪些模型改变观点。

字段：changed_from_round_1、previous_vote、final_vote、change_reason、remaining_disagreement。

视觉规则：改变观点的模型卡片显示 changed 标签；未改变显示 stable 标签。

Round 3 规则：

- 每个模型必须在看过质询后重新提交最终判断。
- 如果观点不变，必须解释为什么冲突证据不足以改变判断。
- 如果观点改变，必须说明被哪条 challenge 或 evidence 触发。
- 页面需要显示 confidence_delta 和 disagreement_delta。

修正记录字段：

```text
model_id
changed_from_round_1
previous_state_vote
final_state_vote
previous_confidence
final_confidence
confidence_delta
accepted_challenges[]
rejected_challenges[]
remaining_disagreement
change_reason
```

#### 7.4.5 主裁判合成

显示：consensus_score、disagreement_level、state_votes、direction_votes、minority_objection、accepted_by_judge、confidence_discount、final_state、risk_level、final_confidence、publish_allowed。

重点解释：为什么没有简单按多数票决定；少数派反证是否被采纳；哪些观点被拒绝；哪些硬约束影响了结论。

主裁判合成优先级：

```text
硬规则 / 状态机约束
> 数据质量约束
> 强反证条件
> 高权重 Evidence
> 多模型共识
> 单模型观点
```

裁判必须输出：

- accepted_claims
- rejected_claims
- minority_objection_status
- evidence_weight_summary
- confidence_discount_reason
- final_state_reason
- publish_allowed_reason

如果多数模型一致但少数派引用强反证，页面必须保留少数派意见，并降低 final_confidence 或阻止 publish_allowed。

字段语义必须严格区分：

```text
final_state: leverage_squeeze / healthy_uptrend / exhaustion / macro_pressure / range_accumulation / distribution / event_compression / mixed
risk_level: low / medium / medium_high / high / critical
final_confidence: 0-100%
```

禁止把 `medium_high`、`high` 这类风险等级写进 `final_state`。

正确示例：

```text
final_state: leverage_squeeze
risk_level: medium_high
final_confidence: 70%
```

#### 7.4.6 反方审查

显示：review_passed、issues、required_changes、confidence_adjustment、final_allowed。

如果审查不通过，页面显示 blocked 状态，并解释为什么没有自动发文。

反方审查检查项：

- 是否忽略关键 conflicting_evidence
- 是否过度自信
- 是否违反状态机约束
- 是否在数据质量不足时仍允许发文
- 是否把风险等级误写成状态
- 是否出现交易建议、仓位、杠杆、止损、买入卖出指令
- 是否遗漏事件窗口或宏观数据公布窗口

LLM Debate 页面必须支持：

- 按模型过滤
- 按 issue_type 过滤
- 按 evidence_id 搜索
- 点击 evidence chip 跳转 Evidence
- 点击 invalidation chip 跳转 Invalidation
- 点击 run_id 跳转 Run Logs
- 历史回放中查看当时 debate，不受当前数据覆盖

LLM Debate 页面禁止：

- 把对话做成无结构聊天流。
- 展示没有 evidence_id 的关键结论。
- 用多数票直接决定 final_state。
- 隐藏少数派强反证。
- 生成买卖、仓位、杠杆、止损、止盈等交易动作。

### 7.5 Alerts 预警页

目标：展示当前和历史预警。

页面定位：

- Alerts 是“预警运营页”，用于管理系统发现的风险变化、观察队列和预警有效性。
- 它不是交易执行页，不提供买卖、仓位、止损、杠杆、开仓区间。
- 用户应能看清：当前有哪些预警、为什么触发、支持证据是什么、冲突证据是什么、下一步观察什么、什么时候升级或降级、历史上这类预警是否有效。
- 预警可以被静默、降级、记录处置、标记已处理，但这些动作只影响通知和运营状态，不改变原始数据与历史审计记录。

入口：

- Top Bar 的 `预警等级` 胶囊
- 主拓扑底部 `预警与观察队列`
- 主拓扑中的 warning / critical 雷达节点
- BTC Overview 的 Alert Level
- Article 中的 alert_level 和触发原因
- Evidence Detail 的 related_alerts
- Invalidation 页面中的 triggered / near_trigger 条件
- History / Replay 中的历史预警

Tabs：Active、History、Scoring。

Active 按 critical / warning / watch / info 排序，每条显示 trigger_modules、supporting_evidence、watch_next、cooldown_until。

History 使用时间线展示 alert_level、created_at、resolved_at、final_score。

Scoring 显示 precision、recall、lead_time、false_positive_rate、alert_fatigue。

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Summary Cards: active / new 24h / avg lead time / false positive / fatigue   │
├───────────────────────┬────────────────────────────────┬─────────────────────┤
│ Filters + Alert List  │ Selected Alert Detail           │ Actions + Metrics   │
│ Active / History      │ trigger / evidence / conditions │ scoring / links     │
└───────────────────────┴────────────────────────────────┴─────────────────────┘
```

顶部 Summary Cards：

- 活跃预警数量
- Critical / Warning / Watch / Info 数量
- 24h 新增预警
- 平均领先时间 Lead Time
- 30d 误报率 False Positive Rate
- Alert Fatigue 预警疲劳度

Active Tab：

- 左侧列表按等级和创建时间排序。
- 每条预警必须显示：
  - alert_id
  - alert_level：critical / warning / watch / info
  - alert_type：risk / market / event / data / system
  - title
  - summary
  - trigger_modules
  - created_at
  - cooldown_until
  - status：active / silenced / downgraded / resolved
  - evidence_count
  - conflict_count
  - watch_next
- 点击预警后，中间详情区显示完整解释。

预警详情区：

- Header：alert_level、alert_type、title、status、created_at、next_check_at。
- Trigger Summary：为什么触发。
- Trigger Modules：触发模块及贡献度。
- Supporting Evidence：支持证据，点击跳转 Evidence。
- Conflicting Evidence：冲突证据，点击跳转 Evidence。
- Auto Upgrade Conditions：升级条件。
- Auto Downgrade Conditions：降级条件。
- Watch Next：接下来观察的具体数据变化。
- Related Invalidation：相关反证条件。
- Related Article：关联文章。
- Related Debate：关联 LLM Debate。

右侧 Actions + Metrics：

- `静默 1 小时`
- `降低等级`
- `记录处置`
- `标记已处理`
- `查看 Evidence`
- `查看 Invalidation`
- `查看关联文章`
- `查看历史相似预警`

动作规则：

- 静默只影响通知，不改变 alert_level 原始记录。
- 降低等级必须记录 reason。
- 标记已处理必须记录 operator_note。
- 系统自动 resolved 时必须保留触发时和解除时的 evidence snapshot。
- 所有人工操作进入 audit log。

History Tab：

- 时间线按 created_at 分组。
- 支持筛选：level、type、module、status、validity_result、date_range。
- 每条历史预警显示：
  - created_at
  - resolved_at
  - duration
  - max_level
  - final_status
  - final_score
  - validity_result：validated / false_positive / missed_opportunity / inconclusive
  - linked_snapshot_id
- 历史预警可以跳转到 History / Replay 查看当时 Dashboard、Evidence Pack 和后续评分。

Scoring Tab：

- 不使用 `Call Accuracy`。
- 使用 `Alert Validity / 预警有效性`。
- 展示 7d / 30d / 90d 指标：
  - Alert Validity
  - Precision
  - Recall
  - Lead Time
  - False Positive Rate
  - Missed Alert Rate
  - Alert Fatigue
  - Level Escalation Accuracy
- 支持按 alert_type 和 module_group 拆分。

预警等级语义：

- `info`：信息提示，不要求立即关注。
- `watch`：观察条件接近，需要加入观察队列。
- `warning`：风险变化已经形成，需要重点关注。
- `critical`：多模块强触发或系统级风险，界面允许短时强提醒。

预警状态语义：

- `active`：当前有效。
- `silenced`：通知被静默，但预警仍有效。
- `downgraded`：人工或系统降级。
- `resolved`：触发条件已经解除。
- `expired`：超过有效窗口，自动过期。

升级 / 降级机制：

- 预警升级由算法规则触发，LLM 只能解释，不直接升级。
- 预警降级可以由算法触发，也可以由人工记录处置触发，但必须保留原因。
- 数据质量低时，critical 必须受到限制，最多 warning，除非硬规则明确允许。
- 事件窗口内的 warning 需要显示事件倒计时和数据公布时间。

按钮文案规范：

- 不使用“确认处理”
- 使用“记录处置”或“标记已处理”
- 如果只是关闭当前提醒，使用“静默 1 小时”或“降低等级”

原因：避免用户误解为执行交易动作。

预警有效性命名：

- 不使用 Call Accuracy
- 使用 Alert Validity / 预警有效性
- 或 Signal Validity / 判断有效性

Scoring 区块建议字段：

- Alert Validity
- Precision
- Recall
- Lead Time
- False Positive Rate
- Alert Fatigue

### 7.6 Invalidation 反证页

目标：展示哪些条件会推翻当前判断，以及是否触发。

页面定位：

- Invalidation 是“判断推翻条件控制台”。
- 它回答的问题不是“为什么当前判断成立”，而是“什么情况会让当前判断失效”。
- 页面必须显示每条反证条件的触发距离、影响范围、触发后动作、解除条件和历史命中表现。
- 反证条件必须来自规则、模块配置或总控策略，不能由 LLM 临时编造。
- LLM 可以解释反证条件的重要性，但不能直接新增或删除系统级反证条件。

入口：

- BTC Overview 的 `What Would Change The View`
- Article 正文中的“当前判断的反证条件”
- Alerts 的 `Related Invalidation`
- Evidence Detail 的 `invalidation_signals`
- LLM Debate 的 `invalidation_focus`
- Radar Detail 的 `view invalidation`
- History / Replay 中查看历史反证触发情况

分区：总控级反证、模块级反证、已触发反证、接近触发的反证、已解决反证。

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Summary: not_triggered / near_trigger / triggered / resolved                 │
├───────────────────────┬────────────────────────────────┬─────────────────────┤
│ Filters + Scope Tree  │ Invalidation Conditions         │ Response Mechanism  │
│ total / module / tag  │ condition / distance / action   │ trigger flow / logs │
└───────────────────────┴────────────────────────────────┴─────────────────────┘
```

顶部 Summary Cards：

- 未触发 not_triggered 数量
- 接近触发 near_trigger 数量
- 已触发 triggered 数量
- 已解决 resolved 数量
- 高严重级别条件数量
- 当前状态被推翻风险：low / medium / high

左侧过滤与范围：

- 搜索 invalidation_id 或关键词。
- Scope：
  - 总控级 total_control
  - 模块级 module
  - 信号级 signal
  - 数据质量级 data_quality
- Status：
  - not_triggered
  - near_trigger
  - triggered
  - resolved
- Severity：
  - low
  - medium
  - high
  - critical
- Impact：
  - 影响总控决策
  - 影响核心模块
  - 影响辅助模块
  - 影响发文许可

反证条件列表字段：

- invalidation_id
- condition_name
- scope
- related_module
- current_status
- distance_to_trigger
- threshold
- current_value
- severity
- impact
- last_updated
- action_if_triggered
- evidence_refs
- related_alerts

反证卡：


```text
ETF flow turns negative for 2 consecutive sessions
Scope: module / ETF Flow
Status: not_triggered
Distance: 1 day negative, needs 2 days
Action if triggered: rerun module + total control
```

状态：not_triggered、near_trigger、triggered、resolved。

状态语义：

- `not_triggered`：距离触发仍较远，不影响当前判断。
- `near_trigger`：接近阈值，需要进入 Watch Next。
- `triggered`：已经触发，必须执行 action_if_triggered。
- `resolved`：反证条件解除，影响降级或清除。

触发距离 Distance：

- 数值型：显示当前值、阈值、距离百分比。
- 连续天数型：显示已满足天数 / 需要天数。
- 事件窗口型：显示距离事件时间。
- 结构型：显示是否跌破 / 站回关键结构。
- 数据质量型：显示缺失率、延迟、冲突比例。

触发后动作 action_if_triggered：

- rerun_module：重跑相关模块。
- rerun_total_control：重跑总控融合。
- downgrade_signal：降低模块信号强度。
- reduce_confidence：降低总控置信度。
- escalate_alert：升级预警。
- block_publish：阻止自动发文。
- request_review：进入人工复核或多 LLM 复核。

右侧 Response Mechanism：

- 展示反证触发后的系统流程。
- 总控级反证触发：
  1. 降级当前状态或切换状态候选
  2. 重算核心模块权重与置信度
  3. 重新生成 Evidence Pack
  4. 重新执行 multi_llm_debate
  5. 更新 BTC Overview 和 Alerts
  6. 若 publish_allowed 变更，更新 Article 状态
- 模块级反证触发：
  1. 降级该模块信号或切换方向
  2. 重算模块 confidence
  3. 通知总控 fusion
  4. 若影响足够大，触发总控重评估

详情展开区：

- Condition Definition：条件定义。
- Current Measurement：当前值、阈值、触发距离。
- Evidence Links：支撑该反证条件的数据与 evidence。
- Related State：会影响哪些 state / bias / risk_level。
- Related Alerts：触发后会影响哪些预警。
- History：过去 30d / 90d 是否触发，触发后是否有效。
- Resolution Rule：如何判定已解除。

反证页与 Alerts 的区别：

- Alerts 关注“当前已经提醒用户的风险变化”。
- Invalidation 关注“什么条件会推翻或削弱当前判断”。
- 一个反证 near_trigger 可能只进入 Watch Next，不一定生成 warning。
- 一个反证 triggered 可能导致预警升级、状态切换或发文阻断。

反证页禁止：

- 使用买入、卖出、仓位、杠杆、止损、止盈语言。
- 用 LLM 自由文本临时创建关键反证。
- 只写模糊描述而不写阈值、当前值或距离。
- 触发后不说明系统动作。

### 7.7 Data Quality 数据质量页

目标：展示系统当前数据可靠性。

页面定位：

- Data Quality 是“数据可靠性控制台”。
- 它不是简单的接口监控页，而是解释数据质量如何影响 BTC 总控结论、模块权重、confidence cap、预警等级和发文许可。
- 用户应能看清：哪些来源健康、哪些来源过期、哪些字段缺失、哪些来源冲突、fallback 是否生效、哪些模块被降权、当前数据质量是否限制 critical 或 publish_allowed。

入口：

- Top Bar 的 `数据质量` 状态
- 主拓扑 Data Quality 节点
- 任意数据源节点
- Overview 的 Confidence Explanation / quality discount
- Article 的数据质量说明
- Evidence 的 related_sources / source_health_summary
- Alerts 中因数据质量导致的降级说明
- Run Logs 的 fetch / cleaning / validation 失败记录
- Source Detail 的返回入口

分区：Overall Quality、Source Health、Stale Modules、Missing Fields、Conflicting Sources、Playwright Jobs、API Rate Limits、Module Discounts、System Constraints。

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Summary: overall score / confidence cap / stale / critical / rate limit      │
├───────────────────────┬────────────────────────────────┬─────────────────────┤
│ Filters + Groups      │ Source Health + Quality Tables  │ Selected Source     │
│ source group/status   │ stale/missing/conflict/rate     │ fallback/effects    │
├───────────────────────┴────────────────────────────────┴─────────────────────┤
│ Bottom: stale modules / missing fields / conflicting sources / module discounts│
└──────────────────────────────────────────────────────────────────────────────┘
```

顶部 Summary Cards：

- Overall Quality：0-100 分。
- Confidence Cap：当前总控置信度上限。
- Degraded Sources：降级来源数量。
- Critical Blocks：阻止 critical 或 publish 的硬阻断数量。
- Playwright Jobs：成功率、失败数、超时数。
- API Rate Limits：当前限流数量 / 总 API 数。
- Freshness SLA：满足更新频率的数据比例。

质量评分维度：

- completeness：字段完整度。
- freshness：数据时效性。
- consistency：来源一致性。
- availability：来源可用性。
- fallback_success：fallback 生效率。
- validation_pass_rate：校验通过率。
- conflict_severity：来源冲突严重度。

Source Health 表格：

Source Health 表格：

| Source | Method | Last Success | Status | Fallback | Quality |
|---|---|---|---|---|---|

Source Health 字段：

- source_id
- source_name
- source_group：macro / exchange / onchain / derivatives / options / news / event / system
- method：FRED / official_api / rest_api / websocket / playwright / cache
- preferred_source
- fallback_source
- last_success_at
- freshness_delay
- status：healthy / stale / error / missing / conflicting / rate_limited
- quality_score
- affected_modules
- current_weight
- fallback_weight

点击来源行：

- 右侧 Selected Source 显示：
  - source profile
  - latest status
  - fallback chain
  - recent errors
  - normalized data preview
  - raw response link
  - affected modules
  - confidence impact
  - retry history
  - rate limit status

Stale Modules：

- 显示因数据过期被降权的模块。
- 字段：module_id、source、last_success、delay、stale_status、discount_factor、affected_signal。
- stale 不等于不可用，但必须降低 confidence。

Missing Fields：

- 显示关键字段缺失。
- 字段：field_name、module、source、missing_rate、impact_level、fallback_status。
- 如果核心字段缺失，模块不得输出 high confidence。

Conflicting Sources：

- 显示同一指标不同来源的差异。
- 字段：metric、source_a、source_b、value_a、value_b、difference_pct、severity、resolution_policy。
- 冲突未解决时，Evidence 和 LLM Debate 必须展示冲突提示。

Playwright Jobs：

- 显示无 API 来源的抓取任务。
- 字段：job_id、source、target_url、status、duration、last_success、last_error、retry_count、screenshot_available。
- 失败时必须显示 fallback 或 cache 是否可用。

API Rate Limits：

- 显示当前限流来源。
- 字段：source、limit_window、used、remaining、reset_at、throttle_policy、affected_modules。
- 限流不能静默失败，必须进入 Data Quality 和 Run Logs。

Module Discounts：

- 显示数据质量如何影响模块和总控。
- 字段：module_id、base_confidence、quality_discount、final_confidence、discount_reason、confidence_cap_effect。
- 例：OKX funding stale -> Derivatives confidence 从 0.79 降为 0.64。

System Constraints：

- 当 Overall Quality 低于阈值：
  - 限制 final_confidence 上限。
  - 降低相关模块权重。
  - 禁止 automatic critical，除非硬规则触发。
  - 可能 block_publish。
  - 在 Article 和 Overview 中显示数据质量说明。

质量状态语义：

- `healthy`：数据完整、及时、一致，不限制总控。
- `degraded`：部分过期或冲突，降低 confidence。
- `warning`：关键模块受影响，限制 critical 或发文。
- `critical`：核心数据不可用，阻止自动发文或总控强结论。

数据质量阈值建议：

```text
quality >= 85: healthy
70 <= quality < 85: degraded
50 <= quality < 70: warning
quality < 50: critical
```

视觉规则：healthy 青色，stale 黄色，error 红色，conflicting 紫色。

数据质量差时，必须明确显示 confidence cap、哪些模块被降权、是否阻止 critical。

Data Quality 页面必须支持：

- 按 source_group 过滤。
- 按 status 过滤。
- 按 affected_module 搜索。
- 点击 source 进入 Source Detail。
- 点击 module 进入 Evidence / Radar Detail。
- 点击 failed job 进入 Run Logs。
- 查看 fallback chain。
- 查看 normalized data。
- 查看 raw response。
- 查看半自动数据源状态：`auto` / `semi_auto` / `manual`。
- 对 Bitbo 等需要验证态的数据源显示 `manual_reauth_required`。
- 提供 `Open Verify Window`、`Retry Collect`、`View Last Capture` 操作入口。
- Source Detail 与 Settings 同步展示 `requires_human_verified_profile`、`profile_dir`、`last_verified_at`。

Data Quality 页面禁止：

- 只显示接口是否成功，不显示对判断的影响。
- 隐藏 fallback 使用情况。
- 隐藏 stale / conflict / missing field。
- 把半自动源重新验证需求误判为系统崩溃。
- 数据质量差时仍展示高置信度且无解释。

### 7.8 Run Logs 运行日志页

目标：展示定时任务、Run Once 和 Worker 状态。

页面定位：

- Run Logs 是“全流程运行审计页”。
- 它用于解释系统在某一次定时运行或手动 Run Once 中到底做了什么、跑到哪一步、哪些 worker 执行、哪些数据失败、哪些阶段耗时异常、最终产出了哪些对象。
- 它不是普通日志文本页，而是 run_id 维度的流水线可视化、任务历史和失败排障入口。

入口：

- Top Bar 的 `Run Once`
- Top Bar 的 `Running... / current_step`
- 右下角任务进度 toast
- 右侧详情抽屉 `Run Logs` Tab
- Data Quality 的 failed job
- Source Detail 的 retry history
- LLM Debate 的 run_id
- Article 的生成记录
- History / Replay 的历史 run

内容：当前运行任务、最近 Run Once、定时任务历史、worker 状态、失败重试、每阶段耗时、产物链接、实时日志。

Run Once 阶段：queued、fetching、cleaning、feature_calculation、radar_analysis、module_llm、fusion、multi_llm_debate、review、alert_policy、publish、completed。

运行日志卡：

```text
Run Once #2026-05-19-1042
Status: running
Current Step: multi_llm_debate
Elapsed: 01:34
Triggered By: manual_run_once
```

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Summary: running tasks / last run once / avg duration / failed jobs / workers│
├──────────────────┬──────────────────────────────────────────┬────────────────┤
│ Left Status      │ Center Run Timeline + Logs                │ Right Details  │
│ current run      │ stages / runs / retries / failures        │ stage/worker   │
└──────────────────┴──────────────────────────────────────────┴────────────────┘
```

顶部 Summary Cards：

- Running Tasks：当前运行中任务数。
- Last Run Once Result：最近一次手动运行结果。
- Avg Execution Time：最近 N 次平均耗时。
- Failed Jobs Today：今日失败任务数。
- Active Workers：在线 worker 数。
- Queue Depth：当前队列长度。

左侧 Status 栏：

- 当前任务卡：
  - run_id
  - trigger_type：scheduled / manual_run_once / anomaly_triggered / retry
  - status：queued / running / success / failed / cancelled
  - current_step
  - started_at
  - elapsed
  - progress
  - estimated_finish_at
- Worker 状态：
  - worker_id
  - online / offline / busy / failed
  - current_job
  - cpu / memory
  - heartbeat_delay
- System Notifications：
  - worker offline
  - source delay
  - retry started
  - publish blocked

中间主区域 Tabs：

- Run Logs：当前运行日志。
- Task History：定时任务与 Run Once 历史。
- Retry Records：失败重试记录。
- Failure Analysis：失败聚合分析。

Run Timeline：

- 每个 run 必须显示阶段链路：
  - queued
  - fetching
  - cleaning
  - feature_calculation
  - radar_analysis
  - module_llm
  - fusion
  - multi_llm_debate
  - review
  - alert_policy
  - publish
  - completed
- 每个阶段显示：
  - status：pending / running / completed / failed / skipped
  - start_time
  - duration
  - worker_id
  - input_count
  - output_count
  - error_count
  - artifact_links

Run History 表格：

- run_id
- trigger_type
- status
- started_at
- duration
- current_step / result
- progress
- failed_step
- output_snapshot_id
- article_id
- debate_id
- alert_count

右侧 Stage Details：

- 当前选中阶段信息：
  - stage_name
  - status
  - started_at
  - elapsed
  - estimated_duration
  - worker_id
  - retry_count
  - input / output summary
  - token usage（仅 LLM 阶段）
  - cost estimate（仅 LLM 阶段，可选）
- Worker Execution：
  - worker_id
  - current_task
  - resource usage
  - heartbeat
- Live Logs：
  - 时间戳
  - level：debug / info / warning / error
  - message
  - linked source_id / module_id / run_id
- Progress Toasts：
  - 最近完成阶段
  - 当前运行阶段
  - 失败和重试提示

失败与重试规则：

- fetching 失败：优先走 fallback source，其次 cache，最后标记 Data Quality。
- cleaning 失败：标记字段级 missing / invalid，并降权模块。
- feature_calculation 失败：阻止该模块输出 high confidence。
- module_llm 失败：允许重试，失败后该模块进入 algorithm-only fallback。
- multi_llm_debate 失败：阻止自动发文，保留 rule_fusion 结果。
- publish 失败：不影响 Dashboard 状态，但 Article 状态为 draft / blocked。

产物链接：

- snapshot_id -> History / Replay。
- evidence_pack_id -> Evidence。
- debate_id -> LLM Debate。
- article_id -> Article。
- alert_ids -> Alerts。
- failed_source_id -> Data Quality / Source Detail。

Run Logs 状态语义：

- `queued`：已进入队列，尚未执行。
- `running`：正在执行。
- `completed`：成功完成全部必要阶段。
- `partial_success`：核心结果生成，但部分来源或模块失败。
- `failed`：关键阶段失败，未生成可用结果。
- `blocked`：审查或数据质量阻止发文/发布。
- `cancelled`：用户或系统取消。

Run Logs 页面必须支持：

- 按 run_id 搜索。
- 按 trigger_type 过滤。
- 按 status 过滤。
- 按 failed_step 过滤。
- 导出日志。
- 跳转到 Data Quality / Evidence / LLM Debate / Article / Alerts / History。
- 展开单阶段详细日志。

Run Logs 页面禁止：

- 只显示纯文本日志，不展示阶段状态。
- 失败原因没有 source_id、module_id 或 stage_name。
- Run Once 运行中没有 progress。
- publish blocked 时不解释阻止原因。

### 7.9 Source Detail 数据源详情页

打开方式：点击任意数据源节点，或从 Data Quality 表格点击 source。

页面定位：

- Source Detail 是“单个数据源的排障与验证页”。
- 它用于回答：这个数据从哪里来、怎么抓、多久更新、是否通过校验、失败后走哪个 fallback、标准化后变成什么字段、影响哪些模块和置信度。
- 它不是普通接口详情页，必须展示该来源对 BTC 总控判断的影响面。

入口：

- 主拓扑数据源节点
- Data Quality 的 Source Health 表格
- Data Quality 的 fallback chain
- Evidence 的 related_sources 行
- Run Logs 的 failed_source_id
- Source Health / Source Detail 之间的 fallback 跳转

显示：source_id、source_name、source_group、preferred_source、method、endpoint_or_target、fallback_source、validation_status、update_frequency、last_success_at、last_error、data_quality、latest_value、normalized_preview、historical_quality、affected_modules。

操作：refresh source、view raw response、view normalized data、view fallback chain。

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Source Header: source name / status / quality / method / last success        │
├───────────────────────┬────────────────────────────────┬─────────────────────┤
│ Source Profile        │ Data Preview + Validation       │ Health + Fallback   │
│ config / schedule     │ raw / normalized / fields       │ chain / errors      │
├───────────────────────┴────────────────────────────────┴─────────────────────┤
│ Bottom: affected modules / retry history / historical quality / rate limits   │
└──────────────────────────────────────────────────────────────────────────────┘
```

Source Header：

- source_name
- status：healthy / stale / error / missing / conflicting / rate_limited
- quality_score
- method：FRED / official_api / rest_api / websocket / playwright / cache
- source_group
- last_success_at
- freshness_delay
- current_weight
- fallback_active

Source Profile：

- source_id
- provider
- method
- endpoint_or_target_url
- update_frequency
- timeout
- retry_policy
- parser_or_normalizer
- validation_schema
- owner_module
- environment_required：API key / cookie / playwright / none

Data Preview：

- latest_value
- previous_value
- change_24h / change_7d
- timestamp
- raw response preview
- normalized data preview
- mapped fields
- missing fields
- unit / scale / timezone

Validation：

- schema validation
- freshness validation
- range validation
- cross-source validation
- duplicate detection
- anomaly check
- validation_errors

Fallback Chain：

- primary source
- fallback 1
- fallback 2
- cache fallback
- current active source
- fallback reason
- fallback weight
- fallback quality discount

Recent Errors：

- error_time
- error_type
- message
- affected_run_id
- retry_count
- resolved_status
- link_to_run_logs

Affected Modules：

- module_id
- metric_used
- weight
- confidence_impact
- discount_factor
- latest_consumed_at
- output_signal_impact

Historical Quality：

- 24h / 7d / 30d 成功率
- latency trend
- stale count
- conflict count
- error count
- fallback usage count

Rate Limits：

- limit_window
- used
- remaining
- reset_at
- throttle_policy
- affected_jobs

Source Detail 操作：

- `Refresh Source`：手动刷新该来源。
- `View Raw Response`：查看原始响应。
- `View Normalized Data`：查看标准化结果。
- `View Fallback Chain`：查看 fallback 路径。
- `View Run Logs`：查看该来源最近任务。
- `Open Data Quality`：返回数据质量总览。
- `Open Evidence`：查看该来源参与的证据。

操作限制：

- 手动 Refresh 需要进入 Run Logs 留痕。
- 如果来源 rate_limited，Refresh 按钮必须置灰或显示冷却时间。
- Raw Response 需要脱敏 API key、cookie、token。
- Playwright source 应显示最近 screenshot 是否可用，但不在主页面直接展示大图。

Source Detail 页面禁止：

- 只显示 endpoint，不显示标准化字段。
- 只显示成功/失败，不显示对模块和总控的影响。
- fallback 生效时不标注当前 active source。
- raw response 暴露密钥或敏感 cookie。

### 7.10 Radar Detail 雷达详情页

打开方式：点击任意雷达节点。

页面定位：

- Radar Detail 是“单个雷达模块的完整解释页”。
- 它解释一个模块如何从上游数据形成 signal、strength、confidence、risk_flags 和 algorithm_alert，并说明它如何影响 BTC 总控。
- 它与 Evidence 页不同：Evidence 关注 Claim/Data/Interpretation；Radar Detail 关注模块级计算、权重、历史趋势、输出 JSON 和总控影响。
- 它与 Source Detail 不同：Source Detail 关注单个数据源；Radar Detail 聚合多个数据源、特征和规则。

入口：

- 主拓扑雷达节点单击
- 左侧导航 `雷达`
- Overview 的 Key Drivers 行
- Evidence 页的 module header
- Alerts 的 trigger_modules
- Data Quality 的 affected_modules
- History / Replay 中的历史雷达节点

显示：module_id、module_name、module_group、signal、strength、confidence、algorithm_alert、evidence_summary、historical_features、risk_flags、invalidation_signals、data_quality、upstream_sources、feature_weights、state_machine_contribution、output_json。

操作：rerun module、view evidence、view invalidation、view source health。

右上角按钮备注：

- Radar Detail 右上角必须显示 `关闭 / X`。
- 生成图中若右上角误显示为设置齿轮，应在实现时改为关闭按钮。
- 设置入口不得替代关闭按钮；如需要模块设置，放入操作区或更多菜单。

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC price / state / alert / data quality / Run Once       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Module Header: module / signal / strength / confidence / alert / updated     │
├───────────────────────┬────────────────────────────────┬─────────────────────┤
│ Module Summary        │ Features + Evidence             │ Impact + Context    │
│ signal/rules/quality  │ charts/tables/evidence          │ BTC impact/sources  │
├───────────────────────┴────────────────────────────────┴─────────────────────┤
│ Bottom: risk flags / invalidation / upstream sources / module JSON           │
└──────────────────────────────────────────────────────────────────────────────┘
```

Module Header：

- module_name
- module_id
- module_group
- signal：bullish / bearish / mixed / neutral
- strength：0-1
- confidence：0-1
- algorithm_alert：none / watch / warning / critical
- data_quality
- updated_at
- current_weight_in_total_control

Module Summary：

- 当前模块一句话解释。
- 模块的核心判断：
  - signal
  - direction
  - strength
  - confidence
  - risk_level contribution
- 与上一轮相比：
  - previous_signal
  - signal_changed
  - strength_delta
  - confidence_delta
- 数据质量折扣：
  - base_confidence
  - quality_discount
  - final_confidence

Feature Calculation：

- 展示该模块的关键特征。
- 每个特征显示：
  - feature_name
  - current_value
  - change_24h
  - change_7d
  - z_score / percentile
  - direction
  - weight
  - source
  - freshness
- 对趋势敏感指标必须显示历史窗口，不允许只看当前值。

Evidence Summary：

- 展示该模块输出的 top_evidence。
- 每条 evidence 显示 evidence_id、claim、impact、weight、data_quality。
- 点击 evidence_id 跳转 Evidence。

Historical Features：

- 显示 24h / 7d / 30d / 90d 小图或趋势表。
- 显示模块信号历史变化：
  - signal timeline
  - strength trend
  - confidence trend
  - alert trigger history

Impact On BTC：

- 显示该模块对 BTC 总控的影响：
  - contribution_score
  - direction
  - total_control_weight
  - current impact：support / conflict / neutral
  - whether key_driver
  - whether conflicting_evidence
- 解释该模块在当前总控中是主导因子、辅助因子还是冲突因子。

Risk Flags：

- event_window
- data_delay
- source_conflict
- overcrowding
- liquidity_stress
- macro_shock
- model_disagreement

Invalidation Signals：

- 列出该模块的反证条件。
- 每条显示 status、distance、action_if_triggered。
- 点击跳转 Invalidation。

Upstream Sources：

- source_id
- method
- last_success_at
- status
- quality_score
- fallback_active
- contribution_to_module
- 点击跳转 Source Detail / Data Quality。

Module JSON：

- 显示该模块输出给总控的结构化 JSON 摘要。
- 允许展开查看字段：
  - module_id
  - signal
  - strength
  - confidence
  - evidence_ids
  - risk_flags
  - invalidation_signals
  - data_quality
  - algorithm_alert
  - generated_at

操作规则：

- `Rerun Module`：只重跑该模块，必须进入 Run Logs 留痕。
- `View Evidence`：进入 Evidence 并定位 module_id。
- `View Invalidation`：进入 Invalidation 并定位 module_id。
- `View Source Health`：进入 Data Quality 并筛选 upstream_sources。
- `Open LLM Context`：查看该模块被 LLM Debate 如何引用。

Radar Detail 页面禁止：

- 只展示最终 signal，不展示特征和证据。
- 只展示当前值，不展示趋势窗口。
- 模块数据质量差却仍显示高 confidence 且无解释。
- 出现买卖、仓位、杠杆、止损、止盈语言。

### 7.11 History / Replay 历史回放页

目标：复盘历史判断和预警。

功能：按时间选择历史状态、回放当时 Dashboard 状态、查看当时 Evidence Pack、查看当时多 LLM 讨论、查看后续 24h / 72h / 7D 评分。

布局：左侧时间线，中间历史 Dashboard 快照，右侧评分与复盘。

用途：校准权重、分析误报、分析漏报、优化 prompt。

页面定位：

- History / Replay 是“历史判断复盘与反馈学习页”。
- 它用于回答：系统当时判断了什么、当时依据是什么、当时有没有预警、后来市场是否验证、哪些证据被采纳或忽略、模型分歧是否降低了过度自信。
- 它不是行情回放工具，也不是交易复盘工具；它复盘的是系统判断质量和预警有效性。

入口：

- 左侧导航 `历史回放`
- Alerts 历史预警
- Article 历史版本
- Evidence Pack 历史快照
- LLM Debate 历史记录
- Run Logs 的 snapshot_id
- Data Quality 历史质量异常
- Radar Detail 历史模块状态

推荐布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / historical mode / snapshot time / return realtime         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Filters: date range / state / alert level / validity / major events          │
├───────────────────────┬────────────────────────────────┬─────────────────────┤
│ Timeline              │ Historical Snapshot Replay      │ Replay Analysis     │
│ snapshots/events      │ dashboard state at that time    │ 24h/72h/7D scoring  │
├───────────────────────┴────────────────────────────────┴─────────────────────┤
│ Bottom: key drivers / triggered alerts / linked evidence / historical links   │
└──────────────────────────────────────────────────────────────────────────────┘
```

顶部 Historical Mode：

- 页面必须明显显示当前处于历史模式。
- Top Bar 应显示：
  - historical snapshot time
  - current replay index
  - return realtime 按钮
  - data snapshot id
- 历史模式下不允许误导用户为当前实时状态。

左侧 Timeline：

- 按时间列出 snapshot、alert、state_change、run_once、article_publish、data_quality_event。
- 每条显示：
  - snapshot_time
  - btc_price_at_snapshot
  - state
  - alert_level
  - confidence
  - trigger_type
  - major_event_tag
- 支持筛选：
  - date_range
  - state
  - alert_level
  - validity_result
  - model_disagreement_level
  - data_quality_status
  - major_event_only

中间 Historical Snapshot Replay：

- 回放当时 Dashboard 主拓扑。
- 必须冻结当时数据，不受当前数据覆盖。
- 显示当时：
  - BTC 中心状态
  - 雷达节点 signal / strength / confidence
  - 预警队列
  - 多 LLM 摘要
  - 数据质量
  - 当时文章状态
- 支持播放控制：
  - previous snapshot
  - next snapshot
  - play / pause
  - speed 1x / 2x / 5x
  - jump to realtime

右侧 Replay Analysis：

- 后续表现评分：
  - 24h result
  - 72h result
  - 7D result
  - max adverse move
  - volatility realized
  - state transition after snapshot
- 判断有效性：
  - Signal Validity
  - Alert Validity
  - confidence calibration
  - false_positive / false_negative / inconclusive
- 预警有效性：
  - lead_time
  - precision contribution
  - recall contribution
  - whether alert was early / late / unnecessary
- 多 LLM 复盘：
  - models agreed / disagreed
  - minority_objection_result
  - whether disagreement reduced overconfidence
  - which model was closer to later outcome
- 数据质量复盘：
  - whether stale / missing / conflict affected judgment
  - confidence cap at that time
  - later corrected data if available

底部复盘区：

- Key Drivers：当时 Top 5 驱动。
- Triggered Alerts：当时触发的预警。
- Evidence Links：当时 Evidence Pack。
- Historical LLM Debate：当时多模型讨论。
- Article Snapshot：当时生成文章。
- Run Logs：产出该 snapshot 的 run。

评分命名规范：

- 不使用 `Call Accuracy`。
- 如果评价预警，使用 `Alert Validity / 预警有效性`。
- 如果评价总控状态判断，使用 `Signal Validity / 判断有效性`。
- 如果评价模型置信度，使用 `Confidence Calibration / 置信度校准`。

命名规范：

- 不使用 Call Accuracy
- 使用 Alert Validity / 预警有效性
- 如果评价的是总控判断，使用 Signal Validity / 判断有效性

复盘页应突出：

- 当时系统是否提前预警
- 预警是否被后续走势验证
- 是否误报
- 是否漏报
- 多 LLM 分歧是否帮助降低过度自信
- 哪些证据当时被采纳或忽略

复盘结果分类：

- `validated`：后续走势或风险演化支持当时判断。
- `false_positive`：当时预警或风险判断没有被后续验证。
- `false_negative`：系统未预警，但后续出现应识别风险。
- `missed_opportunity`：有证据但权重不足，系统没有及时识别。
- `inconclusive`：后续走势不足以判断，或数据质量不允许评价。

History / Replay 页面必须支持：

- 跳转 Evidence Pack。
- 跳转 LLM Debate。
- 跳转 Article。
- 跳转 Alerts。
- 跳转 Run Logs。
- 导出 replay report。
- 标记误报 / 漏报原因。
- 记录校准建议，但不直接改生产权重。

History / Replay 页面禁止：

- 把历史状态误显示为当前状态。
- 只回放价格，不回放当时证据和数据质量。
- 只展示结果好坏，不展示当时判断依据。
- 用交易盈亏评价系统质量。
- 出现买卖、仓位、杠杆、止损、止盈语言。

## 8. 状态设计

### 8.1 数据源状态

- normal
- updating
- stale
- error
- missing
- conflicting

### 8.2 模块信号

- bullish
- bearish
- neutral
- mixed

### 8.3 预警等级

- info
- watch
- warning
- critical

### 8.4 Run Once 状态

- idle
- queued
- running
- success
- failed
- cooldown

### 8.5 多 LLM 讨论状态

- not_started
- round_1_running
- round_2_challenge
- round_3_revision
- judge_synthesizing
- review_running
- completed
- blocked

## 9. 高保真页面描述

### 9.1 默认正常状态

画面：

- 暗色背景
- BTC 中心节点为 neutral 或 healthy_uptrend
- 周围雷达节点多数为灰/青色
- 底部预警队列为空或只有 info
- 多 LLM 共识分数正常

用户感受：

- 市场平稳
- 系统在线
- 无需立即深入

### 9.2 Warning 状态

画面：

- BTC 中心节点橙色轻微脉冲
- 一个或多个雷达节点变为 warning
- 底部预警队列出现 warning 卡片
- 多 LLM 面板显示 partial consensus

用户感受：

- 市场结构可能变化
- 需要观察 watch_next
- 不输出交易建议

### 9.3 Critical 状态

画面：

- BTC 中心节点红色边框和短时闪耀
- 关键路径连线变粗
- 预警队列顶部出现 critical
- 右侧详情面板自动提示可查看文章
- 多 LLM 面板显示主裁判结论和反方审查通过情况

用户感受：

- 系统发现重要变化
- 应查看证据和反证
- 仍然不出现买卖按钮

### 9.4 数据质量异常状态

画面：

- 数据质量节点紫色
- 相关雷达节点变成虚线或低透明度
- BTC confidence 自动降低
- 预警最多 warning，不能 critical

用户感受：

- 当前结论可信度下降
- 需要先修复数据源

### 9.5 多 LLM 高分歧状态

画面：

- DebatePanel 显示 disagreement_level = high
- 模型卡片颜色分裂
- 少数派反证高亮
- 最终状态偏 mixed / volatile / unclear
- confidence 明显折扣

用户感受：

- 系统没有强行给结论
- 分歧本身被明确展示

## 10. 高保真生成提示词

可直接用于 UI 高保真生成：

```text
Design a high-fidelity dark professional financial research dashboard for a BTC trend sensing system named onlyBTC.

The screen is a single-page topology dashboard, not a trading terminal and not a marketing page.

At the top, show a compact fixed top bar with onlyBTC logo, BTC price, 24h change, current state, alert level, data quality, last updated time, and a Run Once button.

The main area is a topology map. In the center, place a prominent BTC status node showing state, direction bias, confidence, risk level, alert level, one-line conclusion, and halving countdown. Around it, arrange radar nodes: Macro, USD Liquidity, Credit Pressure, Fund Flow, ETF Flow, Adoption, On-chain, Price Structure, Derivatives, Market Microstructure, Options Volatility, Crypto Breadth, Asia Risk, Event Policy, Fed Policy, Macro Calendar, Data Quality.

Use restrained dark colors: background #0B0F14, panels #111820, borders #263241, main text #E6EDF3. Use teal for bullish, red for bearish, yellow for mixed/watch, orange for warning, red for critical, purple for data quality issues.

Connections between radar nodes and BTC show influence direction and strength. Bullish lines are teal, bearish lines are red, mixed lines are yellow dashed, stale data lines are purple dashed.

Bottom left panel shows active alerts and watchlist. Bottom right panel shows multi-LLM debate summary with DeepSeek, Qwen, Volcengine, and Kimi model cards, consensus score, disagreement level, minority objection, and judge result.

Right side drawer can open with tabs: Overview, Article, Evidence, LLM Debate, Alerts, Invalidation, Data Quality, Run Logs.

Add a subtle Quick View entry near the BTC center node or bottom toolbar: Overview, Article, Evidence, LLM Debate, Alerts, Invalidation, Data Quality, Run Logs. Make it clear that clicking BTC opens Overview, clicking radar nodes opens Evidence, clicking alerts opens Alerts, clicking LLM cards opens LLM Debate, clicking Data Quality opens Data Quality, and clicking Run Once opens Run Logs.

The design should be dense, calm, and professional, like a research operations dashboard. No buy/sell buttons, no trading controls, no marketing hero, no oversized cards.
```

### 10.1 子页面高保真生成提示词

用于生成右侧详情抽屉和子页面：

```text
Design high-fidelity detail drawer screens for the onlyBTC dark BTC trend sensing dashboard.

Create a right-side drawer UI with tabs: Overview, Article, Evidence, LLM Debate, Alerts, Invalidation, Data Quality, Run Logs.

The drawer should preserve context from the clicked dashboard object. If the user clicked an ETF Flow radar node, open Evidence focused on ETF Flow. If the user clicked a warning alert, open Alerts focused on that alert. If the user clicked a model card, open LLM Debate focused on that model and round. If the user clicked Run Once, open Run Logs focused on the current run_id.

The Overview tab explains the current BTC state with sections for Current State, Key Drivers, Conflicting Evidence, Confidence Explanation, Risk Level Explanation, What Would Change The View, and Watch Next.

The Evidence tab has a left module list and a right evidence detail panel. Each evidence card must show Claim, Data, and Interpretation. Claims without data should not appear.

The LLM Debate tab visualizes DeepSeek, Qwen, Volcengine, and Kimi across three rounds: independent blind review, cross-challenge, and revision. Show model cards, confidence, state vote, bias vote, top evidence count, challenges, changed labels, consensus score, disagreement level, minority objection, judge synthesis, and adversarial review.

The Alerts tab shows Active, History, and Scoring views with alert level, trigger modules, supporting evidence, conflicting evidence, watch next, cooldown, precision, recall, lead time, and false positive rate.

The Invalidation tab shows module-level and total-control invalidation conditions with not_triggered, near_trigger, triggered, and resolved states.

The Data Quality tab shows source health, stale modules, missing fields, conflicting sources, Playwright jobs, API rate limits, confidence cap, and module discounts.

The Run Logs tab shows Run Once and worker execution phases: queued, fetching, cleaning, feature_calculation, radar_analysis, module_llm, fusion, multi_llm_debate, review, alert_policy, publish, completed.

Use the same dark professional style as the main dashboard. Keep information dense and readable. Do not include trading controls, buy/sell buttons, position sizing, stop loss, leverage, or trading plan elements.
```

## 11. 不要出现的元素

- Buy / Sell 按钮
- 开仓、止损、仓位、杠杆控件
- 推荐仓位
- 建议仓位
- 仓位区间
- 开仓区间
- 止盈止损价格
- 做多 / 做空指令
- 交易计划卡片
- 营销式 hero
- 大面积渐变背景
- 装饰性发光球
- 过度卡片化布局
- “稳赚”“预测必涨”等语言
- 无数据依据的结论

允许出现的替代表达：

- 风险暴露参考
- 观察优先级
- 观察建议
- 风险提示
- 反证条件
- 下一步观察重点
- 数据质量说明
