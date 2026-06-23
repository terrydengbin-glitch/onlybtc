# P8-C06 雷达输出、特征值与模块 JSON 表

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

保存雷达模块的特征计算、模块输出 JSON、信号变化和对总控的贡献，支撑 Radar Detail、Evidence、Dashboard 拓扑和 History Replay。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- feature_values：feature_name、metric_id、current_value、change_24h、change_7d、percentile、z_score、weight。
- radar_outputs：module_id、signal、strength、confidence、algorithm_alert、data_quality、updated_at。
- module_json_outputs：output_json、schema_version、run_id、snapshot_id。
- 保存 previous_signal、strength_delta、confidence_delta。
- 支持按 module_id + observed_at 查询历史输出。

## 输入

- P2 雷达模块输出。
- P3 算法预警输出。

## 输出

- 雷达输出表。
- 特征值表。
- 模块 JSON 表。
- Radar Detail 聚合查询。

## 验收标准

- 每个雷达模块输出可追溯到 run_id。
- Radar Detail 能展示当前值和历史窗口。
- History Replay 能冻结当时模块状态。

## 依赖任务

P8-C04、P2-C01

## 备注

复杂 JSON 可保存，但 signal、confidence、alert 等关键字段必须拆列。
