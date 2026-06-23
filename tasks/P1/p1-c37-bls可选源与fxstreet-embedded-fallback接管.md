# P1-C37 / BLS 可选源与 FXStreet、Embedded Fallback 接管

## 状态
DONE

## 优先级
P1

## 所属 Phase
P1 数据源与历史数据底座

## 背景

`official-macro-event-calendar` 在 live run 中反复遇到 BLS 官方日历页面 `403 Forbidden`：

```text
https://www.bls.gov/schedule/news_release/current_year.asp
https://www.bls.gov/schedule/2026/home.htm
https://www.bls.gov/schedule/news_release/bls.ics
```

这不是 CPI/NFP 事件缺失，而是 BLS 官方页面/日历资源对脚本访问做了拦截。当前系统已有 embedded fallback 可以补 CPI/NFP 日期，但 P1 审计仍把 BLS 403 作为采集错误展示，容易误导为 P1 数据源失败。

## 目标

将 BLS 官方日历降级为可选 official source。BLS 403 时，不阻断链路，不计入高危采集失败；CPI/NFP 事件窗口由 fallback 栈接管：

```text
BLS official html / ics optional
  -> FXStreet economic calendar runtime fallback / cross-check
  -> embedded official calendar fallback
```

Fed/FOMC 继续使用 Fed 官方源，PCE/GDP 继续使用 BEA 官方源，不把 Fed/BEA 误当成 BLS 等效源。

## 修改范围

- P1 source registry：声明 BLS optional 与 fallback policy。
- P1 source client：BLS 403 且 CPI/NFP fallback 已补齐时，改为 warning/diagnostic，不进入 blocking errors。
- P1 raw payload：增加 official_blocked、fallback_provider、fallback_stack、source_resolution 字段。
- P1-C22 审计：显示“BLS official blocked, fallback covered”，不要归类为采集失败。
- Tests：覆盖 BLS 403 + embedded fallback resolved 不抛错、不产生 blocking error。

## DoD

- [ ] BLS 403 时 `official-macro-event-calendar` 仍能输出 `cpi_days_until` / `nfp_days_until`。
- [ ] Raw payload `source_resolution.bls.status` 能明确显示 official blocked 与 fallback 接管。
- [ ] BLS 403 且 fallback covered 时，不再作为 P1 高危采集失败。
- [ ] Fed/FOMC 与 BEA/PCE 官方源逻辑不变。
- [ ] P1/P2/P3/P4.5 全链条重跑通过，并输出 HTML。

## 执行记录

已完成：

- `official-macro-event-calendar` 增加 `optional_official_sources=["bls"]` 与 BLS fallback policy。
- BLS 官方 HTML/ICS 类资源 403 时，记录到 `diagnostics` 和 `source_resolution.bls`，不再进入 blocking `errors`。
- 当 embedded fallback 补齐 CPI/NFP 时，`source_resolution.bls.status=official_blocked_embedded_fallback`。
- 保留 Fed/FOMC 官方源、BEA/PCE 官方源原逻辑，不把 Fed/BEA 误当成 BLS 替代。
- 宏观事件指标在 BLS 403 场景下继续输出 `cpi_days_until` / `nfp_days_until`。

验证：

- `backend/tests/test_sources.py` 35 passed。
- 单源 live 采集 `official-macro-event-calendar` completed，CLI `errors=[]`、`warnings=[]`。
- Raw payload spot-check：
  - `source_resolution.bls.status=official_blocked_embedded_fallback`
  - `official_blocked=true`
  - `blocking_error=false`
  - `fallback_provider=embedded_official_calendar_table`
- P1/P2/P3/P4.5 全链条 live run completed。
  - collect_run_id: `collect-20260523131038-8eeaf2`
  - p2_radar_run_id: `radar-20260523131225-c683d1`
  - p3_run_id: `p3-20260523131226-188da9`
  - final_run_id: `p45final-20260523131229-15b0bb`
