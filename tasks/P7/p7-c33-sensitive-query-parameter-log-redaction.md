# P7-C33 Sensitive Query Parameter Log Redaction

## 状态

DONE

## 所属 Phase

P7 动态校准与生产化增强

## 任务目标

修复启动与采集日志中第三方 HTTP URL 可能带出 `api_key` 等敏感 query 参数的问题，确保日志、报告和本地重定向文件不保存明文 key/token。

## 背景依据

- [P7-C07](p7-c07-权限审计与配置化新增数据源.md)
- P7-C32 重启 onlyBTC 后端时发现 `httpx` INFO 日志会输出带 query 的完整 URL。

## 实施范围

- 在 `onlybtc.core.logging.configure_logging()` 中增加敏感 query/header 字段脱敏 filter。
- 降低 `httpx` / `httpcore` logger 到 warning，避免正常请求 URL 在 INFO 日志中刷屏。
- 覆盖 `api_key`、`token`、`authorization`、`cookie`、`password`、`secret` 等关键字。
- 清理本次重启产生的 onlyBTC backend 重定向日志。

## 验收标准

- [x] logging filter 能把 `api_key=...` 脱敏。
- [x] `httpx` / `httpcore` 默认不再输出 INFO 级完整 URL。
- [x] 本地 onlyBTC backend 重定向日志不保留明文 `api_key=` 值。
- [x] 不影响业务日志输出。

## 执行记录

- `onlybtc.core.logging.configure_logging()` 新增 `SensitiveValueFilter` 与 `redact_sensitive_log_text()`。
- 覆盖敏感字段：`api_key`、`access_token`、`token`、`authorization`、`cookie`、`password`、`secret`。
- `httpx` / `httpcore` logger 默认降到 `WARNING`，避免 INFO 级完整请求 URL 进入日志。
- 已清理 `logs/onlybtc-backend-8118.*.log` 与 `logs/onlybtc.log` 中已有 `api_key=` 明文值。
- 已重启 onlyBTC 后端，当前监听 `http://127.0.0.1:8118`；前端仍监听 `http://127.0.0.1:5188`。

## 验证结果

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_logging.py -q` -> 2 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\core\logging.py` -> passed。
- `Select-String -Path logs\onlybtc*.log -Pattern 'api_key=[^<]'` -> no matches。
- `curl.exe -I http://127.0.0.1:5188/` -> HTTP 200。
- `GET http://127.0.0.1:8118/api/event-window/latest` -> `status=ok`。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_logging.py -q`
- 手动检查 `logs/onlybtc-backend-8118.*.log`。
