# P7-C05 Playwright 抓取稳定性增强

## 状态

DONE

## 所属 Phase

P7

## 任务目标

在现有 Playwright source、artifact、provider auth 基础上建立抓取稳定性增强与审计层，明确登录态文件安全边界、provider 级 profile/storage state、headless verification、source health 降级、selector/artifact 可观测性和后续 P7-C08 可验收报告。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 新增 Playwright stability governance module，汇总 Playwright source registry、provider auth 状态、artifact 路径、source health event、P7-C04 data quality 线索。
- 检查登录态目录是否位于 `.gitignore` 覆盖的 `playwright-artifacts/auth/` 下。
- 检查 auth status 是否只保存脱敏字段，禁止 cookie、token、authorization、localStorage 进入 status/report。
- 为未配置或验证失败的登录态 provider 输出 provider health warning 建议，不阻塞全局采集。
- 输出 `reports/p7-c05-playwright-stability-report.json/md`。
- 本任务不启动真实浏览器登录，不要求用户提供密码，不修改采集策略或生产门控。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。
- 增加可复用登录态 Playwright 能力：
  - headed 登录 bootstrap。
  - provider 级 browser profile / storage state。
  - headless 登录态复用验证。
  - artifact、截图、selector 版本与 source health 记录。
  - cookie、token、authorization header、localStorage 必须脱敏，禁止进入日志和仓库。
- 支持 `glassnode` 作为首个登录态勘探 provider，承接 P1-C14。

## 输入

- `onlybtc.sources.registry.SOURCE_CONFIGS` 中的 Playwright source。
- `onlybtc.sources.provider_auth` 的 `glassnode` 登录态路径与 status。
- P7-C04 `source_health_monitor` 报告与 `SourceHealthEvent`。
- `.gitignore` 中的 artifact 忽略规则。
- P1-C14 / P7-C07 / P7-C08 后续 provider 授权与生产 mock 需求。

## 输出

- Playwright stability module：`backend/src/onlybtc/governance/playwright_stability.py`。
- 报告生成脚本：`scripts/generate_p7_c05_playwright_stability_report.py`。
- 测试：`backend/tests/test_p7_playwright_stability.py`。
- 报告：`reports/p7-c05-playwright-stability-report.json/md`。

## 验收标准

- 与《开发文档.md》的总体架构一致。
- 任务产物能被后续任务引用。
- 关键状态、错误和数据质量可观测。
- 不绕过状态机、反方审查、预警等级或数据质量约束。
- [x] 报告明确 `applied_to_production=false`。
- [x] 用户不提供密码即可完成本地登录态保存能力已有 CLI/模块入口，报告能发现 provider auth 配置。
- [x] 登录态文件位于被 `.gitignore` 忽略的目录，例如 `playwright-artifacts/auth/`。
- [x] auth status/report 不包含 cookie、token、authorization header、localStorage 等敏感字段。
- [x] 登录态未配置或失效时输出 provider health warning，不阻塞全局采集。
- [x] Playwright source coverage、fallback、artifact、recent health warning 可观测。
- [x] 测试覆盖 ignored auth path、敏感字段检测、未登录态降级、报告生成。
- [x] 不绕过状态机、反方审查、预警等级或数据质量约束。

## 执行记录

- 新增 `backend/src/onlybtc/governance/playwright_stability.py`。
- 新增 `scripts/generate_p7_c05_playwright_stability_report.py`。
- 新增 `backend/tests/test_p7_playwright_stability.py`。
- 生成 `reports/p7-c05-playwright-stability-report.json`。
- 生成 `reports/p7-c05-playwright-stability-report.md`。
- 当前报告识别 16 个 Playwright source。
- 当前 `.gitignore` 已覆盖 `playwright-artifacts/*`。
- 当前 `glassnode` provider auth 未配置/未验证，报告输出 `provider_auth_not_verified` warning，并建议降级为 provider health warning。
- 当前 glassnode 两个 Playwright source 已在审计报告中关联 `linked_provider_id=glassnode`，但本任务未改变采集行为。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_playwright_stability.py -q`：5 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c05_playwright_stability_report.py`：通过，生成 JSON/MD 报告。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\governance scripts\generate_p7_c05_playwright_stability_report.py`：通过。

## 依赖任务

P1-C06、P1-C13、P1-C14、P10-C01、P10-C04。

## 备注

登录态 Playwright 是补充能力，不替代官方 API key。生产长期运行优先使用 provider API。
- P7-C05 本轮只做可审计稳定性增强层，不执行 headed login。
- 本任务未打开浏览器、未读取或输出 storage state 内容、未写入任何登录敏感字段。
