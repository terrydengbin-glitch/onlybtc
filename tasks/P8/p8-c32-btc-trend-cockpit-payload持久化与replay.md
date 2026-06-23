# P8-C32 BTC Trend Cockpit payload 持久化与 replay

状态：DONE

## 目标

确保 `btc_trend_cockpit.v2` 跟随 final payload 一起持久化，并在 latest、history replay、overview 等入口读取同一份历史快照。

```text
final_payload.btc_trend_cockpit
  -> SQLite persisted snapshot
  -> latest replay
  -> history replay
```

## 范围

- 不优先新增表，除非现有 final payload 存储无法承载。
- 优先复用现有 final run / article / report payload JSON 持久化链路。
- 历史 replay 必须返回当时 run 对应的 cockpit，而不是重新计算最新状态。

## DoD

1. run once 后 SQLite 中 final payload 包含 `btc_trend_cockpit`。
2. latest 读取与 history replay 读取到的同一 run cockpit 关键字段一致。
3. replay 不重新计算 cockpit。
4. 旧历史 run 缺失 cockpit 时兼容返回空对象或 fallback，不报错。
5. P8 repository / replay targeted pytest 通过。
