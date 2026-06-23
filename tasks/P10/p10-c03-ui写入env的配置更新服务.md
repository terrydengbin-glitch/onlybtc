# P10-C03 UI 写入 .env 的配置更新服务

## 状态

DONE

## 所属 Phase

P10 API Key 配置与密钥管理

## 任务目标

允许用户通过主页 API Settings 弹窗更新 `.env` 配置，同时保证写入安全、可审计、可回滚。

## 实施范围

- 使用 Path Resolver 定位项目根目录 `.env`。
- 保留未知配置项与注释。
- 更新指定 env key，不覆盖其他配置。
- 写入前创建 `.env` 备份。
- 写入后刷新 Settings cache。
- 操作日志不记录明文 key。

## 验收标准

- UI 保存 FRED key 后，后端可立即读取。
- `.env` 原有内容不会被破坏。
- 写入失败有明确错误提示。

## 执行记录

- 新增 `backend/src/onlybtc/core/env_writer.py`，按 provider registry 白名单写入 `.env`。
- 写入规则：仅允许 registry 声明的 `ONLYBTC_*` key；拒绝未知 key 与多行值；保留未知配置项、注释和原有行；缺失 key 追加到文件尾部。
- 写入前创建 `backups/env/.env.<timestamp>.bak`，写入使用 UTF-8 和临时文件替换。
- 新增 `POST /api/settings/env`，写入成功后刷新 settings cache，并返回脱敏 settings summary。
- 前端 Settings / API Keys 页面接入 provider registry，支持输入新 key 并保存；保存后清空输入并刷新 settings。
- API 与 UI 响应只返回 `updated_keys`、`backup_path`、masked provider 状态，不返回明文 key。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_env_settings_update.py backend\tests\test_settings_provider_status.py backend\tests\test_provider_registry.py -q` -> 10 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\core\env_writer.py backend\src\onlybtc\api\app.py` -> passed。
- `npm run build` -> passed。
- 重启后端 `8118` 后，`/api/health` -> healthy，`/api/settings` -> provider_count 10。
- 运行态 smoke test：`POST /api/settings/env` with unsupported key -> 400 Bad Request；未写入真实 `.env`。
- 前端 `5188` -> 200；后端日志未发现 Traceback / ERROR / RuntimeWarning。
