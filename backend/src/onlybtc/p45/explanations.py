from __future__ import annotations

from typing import Any

from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.sources.registry import METRIC_DEFINITIONS

METRIC_EXPLANATION_OVERRIDES: dict[str, str] = {
    "btc_price": "BTC 现货价格，用于确认当前方向动能和风险资产主趋势。",
    "btc_1h_close": "BTC 最近 1 小时收盘价，用于判断短周期价格动能。",
    "btc_funding_rate": "永续合约资金费率，用于衡量多空杠杆成本和拥挤度。",
    "btc_open_interest": "BTC 合约未平仓量，用于观察杠杆规模、趋势确认或拥挤风险。",
    "dxy_proxy": "美元指数代理，美元走强通常压制 BTC 等风险资产流动性。",
    "vix": "美股隐含波动率，代表风险厌恶和波动风险溢价。",
    "ofr_fsi": "OFR 金融压力指数，用于衡量宏观金融系统压力。",
    "treasury_10y": "美国 10 年期国债收益率，限制性利率会压制 BTC 估值。",
    "real_yield_10y": "美国 10 年期真实利率，真实利率偏高会抬升持有现金的机会成本。",
    "sofr": "美元隔夜融资利率，代表短端美元资金约束。",
    "etf_net_flow": "美国现货 BTC ETF 单日净流，代表机构现货边际需求。",
    "etf_flow_7d": "美国现货 BTC ETF 7 日净流，用于观察机构资金趋势持续性。",
    "stablecoin_supply": "稳定币总供应，用于观察链上可用购买力和加密美元流动性。",
    "exchange_balance_delta_1d_proxy": "交易所 BTC 余额变化代理，下降通常表示可交易供给收缩。",
    "mvrv_zscore": "MVRV Z-Score，用于判断链上估值是否低估、中性或过热。",
    "nupl": "NUPL，用于观察市场未实现盈亏和周期性获利压力。",
    "sopr": "SOPR，用于判断链上花费是否处于盈利、亏损或盈亏平衡测试区。",
    "futures_basis": "期货基差，用于观察期限结构、杠杆做多热度和贴水压力。",
    "put_call_ratio": "BTC 期权 Put/Call 比率，用于观察保护性需求和下行担忧。",
    "macro_surprise_score": "宏观数据惊喜分数，用于观察实际数据相对预期的 BTC 冲击。",
    "aggregate_macro_surprise": "聚合宏观惊喜分数，用于判断多个宏观事件的合成冲击。",
}


def metric_explanation_catalog() -> dict[str, str]:
    definitions = {item.metric_id: item for item in METRIC_DEFINITIONS}
    result: dict[str, str] = {}
    for module in RADAR_MODULES:
        for rule in module.metrics:
            metric_id = rule.metric_id
            definition = definitions.get(metric_id)
            name = getattr(definition, "name", metric_id)
            result[metric_id] = METRIC_EXPLANATION_OVERRIDES.get(
                metric_id,
                f"{name}，用于 {module.module_id} Radar 的 BTC 趋势、风险或上下文判断。",
            )
    return result


def build_metric_brief(item: dict[str, Any]) -> str:
    catalog = metric_explanation_catalog()
    metric_id = str(item.get("metric_id") or "unknown_metric")
    base = catalog.get(metric_id, str(item.get("metric_explanation") or metric_id))
    value = item.get("value")
    direction = item.get("direction")
    score = item.get("metric_score")
    bucket = item.get("score_bucket")
    quality = item.get("quality_score")
    semantic = item.get("semantic_rule_id")
    warning = item.get("semantic_warning")
    warning_text = f" 注意：{warning}" if warning else ""
    return (
        f"{base} 当前值={value if value is not None else '不可用'}，"
        f"方向={direction}，分数={score}，分桶={bucket}，质量={quality}，"
        f"语义规则={semantic}。{warning_text}"
    )


def catalog_coverage() -> dict[str, Any]:
    radar_metrics = {
        rule.metric_id for module in RADAR_MODULES for rule in module.metrics
    }
    catalog = metric_explanation_catalog()
    return {
        "radar_metric_count": len(radar_metrics),
        "catalog_metric_count": len(catalog),
        "missing_metric_ids": sorted(radar_metrics - set(catalog)),
    }
