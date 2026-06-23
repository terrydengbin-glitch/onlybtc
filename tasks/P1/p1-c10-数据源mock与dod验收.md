# P1-C10 数据源 Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座

## 任务目标

用 mock 数据源、fixture 和离线样本验证数据采集、清洗、fallback、质量评分与历史窗口计算链路。P1-C10 未通过，不进入 P2。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 为 FRED、交易所、官方数据源、Playwright 抓取源准备 mock response。
- 验证数据源注册表、清洗标准化、fallback、source health。
- 验证 BTC 区块高度与减产倒计时 mock。
- 验证历史窗口字段可从 P8 `metric_values` 读取并计算。
- 验证异常数据、缺字段、延迟数据、fallback 降权场景。

## 输入

P1-C01 至 P1-C09，P8-C03、P8-C04、P8-C09。

## 输出

- 数据源 mock fixtures。
- 数据清洗与 fallback 测试。
- source health mock report。
- P1 DoD 验收清单。

## 验收标准

- 每类数据源至少有成功、延迟、失败、fallback 四类测试样本。
- 标准化后的指标能写入或映射到 P8 metric schema。
- source health 能正确反映数据延迟、缺字段、fallback、rate limit。
- 历史窗口计算结果可被 P2 雷达消费。
- P1 DoD 全部通过后，才允许进入 P2。

## 依赖任务

P1-C01、P1-C02、P1-C03、P1-C04、P1-C05、P1-C06、P1-C07、P1-C08、P1-C09、P8-C04

## 备注

真实数据源不可用时，后续 Phase 必须能使用 P1 mock fixtures 和 P8 seed data 继续开发。
