# P1-C18 Fed Speech Risk 公开源与评分引擎

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座

## 任务定位

把 `fed_speech_risk` 从抽象占位指标升级为可采集、可计算、可解释的政策沟通风险信号。

核心拆分：

```text
fed_speech_risk =
  讲话日程风险
  + 发言人权重
  + 主题敏感度
  + 已发布讲话鹰鸽倾向
  + FOMC blackout / FOMC communication 风险
```

P1 只做公开源采集和规则评分。LLM 内容推理放到 P4/P6，但必须消费本任务保存的 evidence data，不能凭空判断。

## 已接入数据源

| Source ID | 来源 | 方法 | 输出 |
|---|---|---|---|
| `fed-rss-all-speeches` | Federal Reserve Speeches RSS | RSS + 官方正文抓取 | 最新讲话、speaker、title、url、content score |
| `fed-rss-all-testimony` | Federal Reserve Testimony RSS | RSS + 官方正文抓取 | 最新证词、speaker、title、url、content score |
| `fed-calendar` | Federal Reserve Calendar | HTML parse + fallback calendar | `next_fed_speech_hours_until`、`fed_speech_scheduled_risk` |
| `fed-fomc-blackout-calendar` | FOMC calendar/static rule | 静态 FOMC 日期 + blackout 规则 | `fomc_blackout_active`、`fomc_event_risk` |

## 已落库指标

```yaml
metrics:
  fed_speaker_weight:
    unit: score_1_5
    meaning: 发言人政策影响力权重

  fed_speech_hawkish_score:
    unit: score_0_1
    meaning: 讲话文本偏鹰程度

  fed_speech_dovish_score:
    unit: score_0_1
    meaning: 讲话文本偏鸽程度

  fed_speech_content_risk:
    unit: score_minus1_to1
    meaning: 鹰鸽净风险；正值偏 BTC 利空，负值偏 BTC 利多

  fed_speech_risk:
    unit: score_0_1
    meaning: 当前 Fed 讲话融合风险

  next_fed_speech_hours_until:
    unit: hours
    meaning: 下一次 Fed 沟通事件倒计时

  fed_speech_scheduled_risk:
    unit: score_0_1
    meaning: 未来讲话日程风险

  fomc_blackout_active:
    unit: bool
    meaning: 当前是否处于 FOMC blackout 期

  fomc_event_risk:
    unit: score_0_1
    meaning: FOMC statement / SEP / Powell press conference 风险
```

## 评分规则

### Speaker weight

```yaml
powell_or_chair: 5
vice_chair: 4
ny_fed_president: 4
board_governor: 3
regional_fed_president: 2
unknown_or_staff: 1
```

### Topic keywords

```yaml
rate_path:
  - policy rate
  - federal funds rate
  - rate path
  - rate cuts
  - hikes

inflation:
  - inflation
  - price stability
  - PCE
  - CPI

labor_market:
  - employment
  - unemployment
  - payrolls
  - labor market
  - wage

balance_sheet_qt_qe:
  - balance sheet
  - QT
  - reserves
  - asset purchases
```

### Content risk

```text
content_risk =
  hawkish_score
  - dovish_score
  + uncertainty_score * 0.25
```

解释：

| content_risk | BTC 含义 |
|---|---|
| `> 0.12` | 偏鹰，通常压制 BTC 风险偏好 |
| `< -0.12` | 偏鸽，通常支持 BTC 风险偏好 |
| `-0.12 ~ 0.12` | 中性或混合 |

### FOMC blackout

当前版本用静态 FOMC 日期和规则计算：

```text
blackout_start = FOMC 前第二个周六
blackout_end = FOMC 结束后次日 23:59 ET 附近
```

blackout 期间普通 Fed speech 风险降低，但 FOMC statement、SEP、Powell press conference、minutes 风险升高。

## FastAPI 对接

已新增：

```text
GET /api/fed/speeches/latest
GET /api/fed/speeches/upcoming
GET /api/fed/speech-risk/latest
GET /api/fed/blackout
```

## P2-C14 对接

事件政策雷达已消费：

```yaml
event_policy:
  - fed_speech_risk
  - fed_speech_scheduled_risk
  - fed_speech_content_risk
  - fomc_event_risk
  - macro_surprise_score
  - cpi_days_until
  - fomc_days_until
  - pce_days_until
  - nfp_days_until
```

## 当前实测结果

执行真实采集：

```powershell
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id fed-rss-all-speeches --source-id fed-rss-all-testimony --source-id fed-calendar --source-id fed-fomc-blackout-calendar
```

结果：

```text
collected: 4
errors: []
Fed speeches RSS: HTTP 200
Fed testimony RSS: HTTP 200
Fed calendar: HTTP 200
官方 speech/testimony 正文抓取: HTTP 200
```

当前样本指标：

```yaml
fed_speech_scheduled_risk: 0.02
next_fed_speech_hours_until: 560.45
fomc_blackout_active: 0
fomc_event_risk: 0.14
```

`fed-calendar` 当前主要依赖 fallback FOMC communication window，后续可用 FXStreet / Investing 补未来 Fed speaker 明细。

## 验收

- Fed RSS 可采集并解析标题、链接、发布时间。
- 官方正文抓取可用，失败时降级为 RSS title + description。
- 规则版鹰鸽评分可生成 `fed_speech_content_risk`。
- `fed_speech_risk` 已落库，可被 P2-C14 消费。
- FOMC blackout 状态和 FOMC event risk 已落库。
- FastAPI 查询接口已补齐。
- 测试覆盖 RSS parser、speech score、blackout active window、mock 落库。
- `ruff check src tests` 通过。
- `pytest` 通过，当前 29 passed。

## 后续增强

- 用 FXStreet / Investing / ForexFactory 补未来 Fed speaker 日程，减少 `fed-calendar` 对 fallback 的依赖。
- P4/P6 接入 LLM 内容评分，但必须引用官方正文、speaker、title、topic keywords。
- 加入讲话后市场反应窗口：DXY、US10Y、FedWatch、Nasdaq、BTC 30m/2h 变化。
- 年度更新 FOMC 日期和 blackout calendar，过期后标记 source stale。
