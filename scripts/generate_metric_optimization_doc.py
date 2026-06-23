from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "指标优化.md"
TEMP = Path(os.environ.get("TEMP", "."))


def load_json(url: str, temp_name: str) -> tuple[dict[str, Any], str]:
    temp_path = TEMP / temp_name
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw = resp.read()
        temp_path.write_bytes(raw)
        return json.loads(raw.decode("utf-8-sig")), "live_api"
    except Exception:
        raw = temp_path.read_bytes()
        return json.loads(raw.decode("utf-8-sig")), f"cached:{temp_path}"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    if any(mark in text for mark in ("Ã", "Â", "ï¼", "锛", "涓", "鍋", "€")):
        try:
            repaired = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            if repaired and len(repaired) >= len(text) * 0.35:
                text = repaired
        except Exception:
            pass
    return text.replace("|", "/")


def fmt(value: Any, digits: int = 4) -> str:
    if value is None or value == "":
        return "-"
    try:
        number = float(value)
    except Exception:
        return clean_text(value)
    if abs(number) >= 1_000_000:
        return f"{number:.4g}"
    if abs(number) >= 1000:
        return f"{number:.2f}"
    if abs(number) >= 1:
        return f"{number:.4f}".rstrip("0").rstrip(".")
    return f"{number:.{digits}f}".rstrip("0").rstrip(".") or "0"


def yesno(value: Any) -> str:
    if value is True:
        return "Y"
    if value is False:
        return "N"
    return "-"


MODULE_NAMES = {
    "macro_radar": "宏观风险雷达",
    "treasury_credit": "利率与信用",
    "asia_risk": "亚洲风险",
    "event_policy": "事件与政策",
    "dollar_liquidity": "美元流动性",
    "fund_flow": "资金流",
    "crypto_breadth": "加密市场宽度",
    "kline_orderflow": "K线订单流",
    "derivatives_crowding": "衍生品拥挤",
    "trade_structure_flow": "交易结构与资金流向",
    "options_volatility": "期权与波动率",
    "btc_total_state": "BTC总体状态",
    "btc_adoption": "BTC采用与网络活动",
    "onchain_valuation": "链上估值",
}


RULEBOOK: dict[str, dict[str, str]] = {
    "semantic.radar_rule": {
        "name": "通用 Radar 方向规则",
        "rule": "沿用 P2 Radar feature 的 base_direction/base_metric_score。metric_score > 0.0001 计正分，< -0.0001 计负分，否则为 0。",
        "zero": "P2 方向为 neutral/mixed，或变化幅度/阈值不足，或 base_metric_score 接近 0。",
        "opt": "这是 0 分最多的来源，需要为高价值指标补专用阈值或趋势解释。",
    },
    "semantic.context_only": {
        "name": "上下文/审计指标",
        "rule": "affects_signal=false 或 weight=0，只进入说明、审计、历史上下文，不参与方向评分。",
        "zero": "固定 0 分。",
        "opt": "若该指标应影响趋势，需要先在 P2 定义 affects_signal/weight 和语义方向。",
    },
    "semantic.unavailable": {
        "name": "不可用数据",
        "rule": "本轮无可靠生产数据，score_bucket=unavailable，不参与方向评分。",
        "zero": "不可用不等于中性，应在质量边界里显式提示。",
        "opt": "优先修数据源、fallback 或降级为非主信号。",
    },
    "semantic.macro_surprise.zero_neutral": {
        "name": "宏观惊喜 0 中性",
        "rule": "macro_surprise_score/aggregate_macro_surprise 当前值为 0 时，表示本轮没有明确超预期冲击，计 0。",
        "zero": "值等于 0。",
        "opt": "后续可增强 Forecast/Actual/Previous 后再细分正负惊喜。",
    },
    "semantic.etf_flow.absolute_negative": {
        "name": "ETF 净流出绝对方向",
        "rule": "etf_net_flow < 0 或 etf_flow_7d < 0 直接偏空；单日按 2.5 亿美元缩放，7日按 10 亿美元缩放，最低强度 0.05*weight。",
        "zero": "无。负值直接负分。",
        "opt": "可增加 3d 累计修复和流出收窄的二阶描述，但不要把净流出误判为偏多。",
    },
    "semantic.etf_flow.absolute_positive": {
        "name": "ETF 净流入绝对方向",
        "rule": "etf_net_flow > 0 或 etf_flow_7d > 0 直接偏多；缩放同 ETF 净流出。",
        "zero": "无。正值直接正分。",
        "opt": "可增加连续性确认。",
    },
    "semantic.funding.normalized": {
        "name": "Funding 温和区间",
        "rule": "Funding 位于温和区间；若 change_24h < 0 计轻微偏多 0.12*weight，否则 0。",
        "zero": "未降温或变化不明显。",
        "opt": "可补 funding 与 OI 联合拥挤规则。",
    },
    "semantic.oi.mild_change": {
        "name": "OI 小幅变化",
        "rule": "OI 小幅变化，中性 0。",
        "zero": "只作为微观结构观察项。",
        "opt": "可细化与成交量/价格联动。",
    },
    "semantic.basis.flat": {
        "name": "基差接近零",
        "rule": "-0.01 <= futures_basis <= 0.02，中性 0。",
        "zero": "未形成清晰方向。",
        "opt": "可结合期限结构变化。",
    },
    "semantic.ofr.low_stress": {
        "name": "OFR 低压力",
        "rule": "OFR FSI < -0.5，偏多，score=weight*min(abs(value)/3,1)。",
        "zero": "无。",
        "opt": "已具备阈值。",
    },
    "semantic.vix.normal": {
        "name": "VIX 常态",
        "rule": "15 <= VIX <= 22，中性 0。",
        "zero": "常态波动不单独给方向。",
        "opt": "可补 VIX 变化率。",
    },
    "semantic.put_call.protection_elevated": {
        "name": "Put/Call 保护需求高",
        "rule": "put_call_ratio > 1.2，偏空，score=-weight*min(value-1,0.8)。",
        "zero": "无。",
        "opt": "已具备阈值。",
    },
    "semantic.sopr.breakeven_test": {
        "name": "SOPR 盈亏平衡测试",
        "rule": "0.98 <= SOPR <= 1.02，中性 0。",
        "zero": "SOPR 接近 1，作为卖压/支撑观察项。",
        "opt": "可结合连续突破 1 的天数。",
    },
    "semantic.nupl.optimism_neutral": {
        "name": "NUPL 温和盈利",
        "rule": "0.25 <= NUPL < 0.5，中性 0。",
        "zero": "趋势健康但不是单独方向信号。",
        "opt": "可结合链上活跃度确认。",
    },
    "semantic.mvrv.low_constructive": {
        "name": "MVRV 偏低建设性",
        "rule": "0.5 <= MVRV Z < 1.2，偏多，score=0.18*weight。",
        "zero": "无。",
        "opt": "已具备阈值。",
    },
}


def rule_info(rule_id: Any) -> dict[str, str]:
    rid = clean_text(rule_id) or "-"
    if rid in RULEBOOK:
        return RULEBOOK[rid]
    if rid.endswith(".restrictive"):
        return {
            "name": "利率/真实利率限制性阈值",
            "rule": "treasury_2y>=4.0、treasury_10y>=4.2、treasury_30y>=4.5、real_yield_10y>=1.8、SOFR>=3.5 时偏空，score=-0.45*weight；低于阈值为 0。",
            "zero": "未达到限制性阈值。",
            "opt": "可加入斜率和变化率。",
        }
    if rid.endswith(".not_restrictive"):
        return {
            "name": "利率未限制",
            "rule": "利率低于限制性阈值，中性 0。",
            "zero": "单独方向贡献有限。",
            "opt": "可加入趋势变化。",
        }
    if ".context_required" in rid:
        return {
            "name": "成本基础上下文",
            "rule": "realized_price/cap_real_usd/STH/LTH cost basis 需要与 BTC 现价相对位置联动，本轮单独计 0。",
            "zero": "缺少相对价格位置规则。",
            "opt": "建议接入 btc_price 相对成本基础，生成支撑/压力分。",
        }
    if rid.startswith("semantic.options_iv") or rid.startswith("semantic.options_rv"):
        return {
            "name": "期权波动率阈值",
            "rule": "options_iv/options_rv > 70 偏空；<35 或常态区间计 0，用作波动观察。",
            "zero": "波动率未进入压力区或低波动仅观察。",
            "opt": "可补 IV-RV spread、skew。",
        }
    return {
        "name": rid,
        "rule": "当前使用该 semantic_rule_id 的代码路径，细节需在 P3 rulebook 中继续拆解。",
        "zero": "若 metric_score=0，说明当前规则未触发正负方向。",
        "opt": "建议审查是否需要专用阈值。",
    }


def zero_reason(item: dict[str, Any]) -> str:
    bucket = item.get("score_bucket")
    rule = clean_text(item.get("semantic_rule_id"))
    if bucket == "unavailable" or item.get("available") is False:
        return "数据不可用"
    if bucket != "zero":
        return "-"
    if rule == "semantic.context_only":
        return "上下文/审计，不参与评分"
    if ".context_required" in rule:
        return "需要组合指标，当前单独计 0"
    neutral_rules = {
        "semantic.macro_surprise.zero_neutral",
        "semantic.sopr.breakeven_test",
        "semantic.nupl.optimism_neutral",
        "semantic.vix.normal",
        "semantic.basis.flat",
        "semantic.oi.mild_change",
    }
    if rule in neutral_rules:
        return "落入中性阈值区间"
    if rule == "semantic.radar_rule":
        if clean_text(item.get("direction")) in {"neutral", "mixed"}:
            return "P2 方向中性/混合"
        return "通用规则分数接近 0"
    return "规则未触发正负分"


def candidate_level(item: dict[str, Any]) -> str:
    if item.get("score_bucket") != "zero" or item.get("available") is False:
        return "-"
    rule = clean_text(item.get("semantic_rule_id"))
    role = clean_text(item.get("role"))
    affects = item.get("affects_signal")
    weight = float(item.get("module_weight") or item.get("weight") or 0)
    if rule == "semantic.context_only":
        return "P2先判定是否应入信号"
    if ".context_required" in rule:
        return "高：补组合规则"
    if rule == "semantic.radar_rule" and affects is not False and (
        role in {"primary_signal", "core_signal", "primary"} or weight >= 0.06
    ):
        return "高：补专用阈值"
    if rule == "semantic.radar_rule":
        return "中：评估阈值"
    if zero_reason(item) == "落入中性阈值区间":
        return "低：阈值已有"
    return "中"


def metric_rule_summary(item: dict[str, Any]) -> str:
    info = rule_info(item.get("semantic_rule_id"))
    reason = clean_text(item.get("score_reason"))
    if reason and len(reason) < 180 and "锛" not in reason:
        return reason
    return info["rule"]


def table(headers: list[str], rows: list[list[Any]]) -> str:
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        output.append("| " + " | ".join(clean_text(cell) for cell in row) + " |")
    return "\n".join(output)


def main() -> None:
    evidence, evidence_source = load_json(
        "http://127.0.0.1:8118/api/p45/evidence?limit=1000",
        "onlybtc_evidence.json",
    )
    module_payload, module_source = load_json(
        "http://127.0.0.1:8118/api/p45/radar-modules/latest",
        "onlybtc_modules.json",
    )
    items = evidence.get("items") or []
    modules = module_payload.get("modules") or []
    run = evidence.get("run_lineage") or {}

    by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_module[clean_text(item.get("radar_module") or "unknown")].append(item)
    module_map = {clean_text(module.get("radar_module")): module for module in modules}

    bucket_counts = Counter(clean_text(item.get("score_bucket")) for item in items)
    rule_counts = Counter(clean_text(item.get("semantic_rule_id")) for item in items)
    zero_items = [item for item in items if item.get("score_bucket") == "zero"]
    candidate_items = [
        item for item in zero_items if candidate_level(item) not in {"-", "低：阈值已有"}
    ]

    lines: list[str] = [
        "# 指标优化.md - P3 指标评分规则评估版",
        "",
        "> 用途：把当前系统里所有 scored evidence、指标评分规则、模块聚合规则摊开，供后续 P3 评分优化评估。本文档只描述当前实现，不修改任何算法。",
        "",
        "## 0. 本次抽样范围",
        "",
        table(
            ["字段", "值"],
            [
                ["数据来源", f"evidence={evidence_source}; modules={module_source}"],
                ["collect_run_id", run.get("collect_run_id") or "-"],
                ["p2_radar_run_id", run.get("p2_radar_run_id") or "-"],
                ["p3_run_id", run.get("p3_run_id") or "-"],
                ["final_run_id", run.get("final_run_id") or "-"],
                ["指标 evidence 数", str(len(items))],
                ["Radar module 数", str(len(modules))],
                ["score_bucket 分布", ", ".join(f"{k}={v}" for k, v in bucket_counts.items())],
                ["零分占比", fmt(len(zero_items) / max(len(items), 1), 4)],
            ],
        ),
        "",
        "## 1. 当前 P3 评分总规则",
        "",
        "### 1.1 单指标评分",
        "",
        "```text\nbase_metric_score = P2 Radar feature.score\nbase_direction    = P2 Radar feature.direction\nmetric_score      = semantic_override(metric_id, current, change, weight) 或 base_metric_score\nscore_bucket      = positive if metric_score > 0.0001; negative if < -0.0001; zero otherwise\nunavailable       = available=false 或 feature_run_scope in {provider_required, missing}\n```",
        "",
        "### 1.2 有效分",
        "",
        "```text\nmetric_effective_score = metric_score * quality_score * freshness_weight * horizon_weight * duplicate_adjustment\n\nfreshness_weight: collection fresh=1.0, stale=0.65, expired=0.25; business current=1.0, expected_lag=0.95, lagging=0.85, outdated=0.65, unknown=0.9\nhorizon_weight: h24=1.0, d3=0.9, d7=0.8, structural=0.7\nduplicate_adjustment: 同 duplicate_group_id 总绝对分超过 group cap 时按 cap/total 降权，最低 0.2\n```",
        "",
        "### 1.3 模块评分",
        "",
        "```text\nmodule_score = Σ metric_score\nmodule_effective_score = Σ metric_effective_score\n\nif unavailable_share >= 0.5 and abs(module_score) < 0.08: module_direction = unavailable\nelif abs(module_score) < 0.08 and both positive/negative exist: module_direction = mixed\nelif abs(module_score) < 0.08: module_direction = neutral\nelse module_direction = bullish if module_score > 0 else bearish\n\nmodule_effective_direction = sign(module_effective_score) with ±0.0001 threshold\nmodule_strength = min(abs(module_score), 1.0)\n```",
        "",
        "## 2. Semantic Rulebook 摘要",
        "",
    ]

    rule_rows = []
    for rule_id, count in rule_counts.most_common():
        info = rule_info(rule_id)
        rule_rows.append([rule_id, str(count), info["name"], info["rule"], info["zero"], info["opt"]])
    lines.append(table(["semantic_rule_id", "指标数", "规则名", "当前评分规则", "为何可能为0", "优化建议"], rule_rows))
    lines.append("")

    lines.extend(["## 3. 模块评分概览", ""])
    module_rows = []
    for module_id in sorted(by_module.keys()):
        module = module_map.get(module_id, {})
        module_items = by_module[module_id]
        counts = Counter(clean_text(item.get("score_bucket")) for item in module_items)
        zero_ratio = counts.get("zero", 0) / max(len(module_items), 1)
        module_rows.append(
            [
                module_id,
                MODULE_NAMES.get(module_id, module_id),
                fmt(module.get("module_score")),
                fmt(module.get("module_effective_score")),
                clean_text(module.get("module_direction")),
                clean_text(module.get("module_effective_direction")),
                fmt(module.get("module_weight")),
                fmt(module.get("module_quality_score")),
                f"+{counts.get('positive', 0)} / -{counts.get('negative', 0)} / 0={counts.get('zero', 0)} / NA={counts.get('unavailable', 0)}",
                fmt(zero_ratio),
            ]
        )
    lines.append(table(["module", "中文", "module_score", "effective", "direction", "effective_dir", "module_weight", "quality", "分布", "zero_ratio"], module_rows))
    lines.append("")

    lines.extend(["## 4. 零分指标治理视图", ""])
    zero_reason_counts = Counter(zero_reason(item) for item in zero_items)
    lines.append(table(["零分原因", "数量"], [[reason, str(count)] for reason, count in zero_reason_counts.most_common()]))
    lines.extend(["", "### 4.1 优先优化候选", ""])
    if candidate_items:
        candidate_rows = []
        for item in sorted(
            candidate_items,
            key=lambda entry: (
                clean_text(entry.get("radar_module")),
                -abs(float(entry.get("weight") or 0)),
                clean_text(entry.get("metric_id")),
            ),
        ):
            candidate_rows.append(
                [
                    clean_text(item.get("radar_module")),
                    clean_text(item.get("metric_id")),
                    clean_text(item.get("metric_name")),
                    clean_text(item.get("role")),
                    yesno(item.get("affects_signal")),
                    fmt(item.get("weight")),
                    clean_text(item.get("semantic_rule_id")),
                    zero_reason(item),
                    candidate_level(item),
                ]
            )
        lines.append(table(["module", "metric_id", "name", "role", "affects", "weight", "rule", "zero_reason", "建议优先级"], candidate_rows))
    else:
        lines.append("本轮没有识别出高/中优先级零分优化候选。")
    lines.append("")

    lines.extend(["## 5. 全量指标与当前评分规则", ""])
    sorted_modules = sorted(by_module.keys())
    for index, module_id in enumerate(sorted_modules, start=1):
        module_items = sorted(
            by_module[module_id],
            key=lambda item: (clean_text(item.get("score_bucket")), clean_text(item.get("metric_id"))),
        )
        module = module_map.get(module_id, {})
        lines.extend([f"### 5.{index} {MODULE_NAMES.get(module_id, module_id)} / `{module_id}`", ""])
        lines.append(
            table(
                ["模块字段", "值"],
                [
                    ["module_score", fmt(module.get("module_score"))],
                    ["module_effective_score", fmt(module.get("module_effective_score"))],
                    ["module_direction", clean_text(module.get("module_direction"))],
                    ["module_effective_direction", clean_text(module.get("module_effective_direction"))],
                    ["module_weight", fmt(module.get("module_weight"))],
                    ["module_quality_score", fmt(module.get("module_quality_score"))],
                    [
                        "模块评分规则",
                        "module_score=Σmetric_score；abs(module_score)<0.08 时按 mixed/neutral/unavailable 处理，否则按正负号定 bullish/bearish。",
                    ],
                ],
            )
        )
        lines.append("")
        metric_rows = []
        for item in module_items:
            metric_rows.append(
                [
                    clean_text(item.get("metric_id")),
                    clean_text(item.get("metric_name")),
                    clean_text(item.get("source_id")),
                    clean_text(item.get("role")),
                    yesno(item.get("affects_signal")),
                    fmt(item.get("value")),
                    clean_text(item.get("direction")),
                    fmt(item.get("metric_score")),
                    fmt(item.get("metric_effective_score")),
                    clean_text(item.get("score_bucket")),
                    clean_text(item.get("semantic_rule_id")),
                    zero_reason(item),
                    candidate_level(item),
                    metric_rule_summary(item),
                ]
            )
        lines.append(
            table(
                [
                    "metric_id",
                    "name",
                    "source",
                    "role",
                    "affects",
                    "value",
                    "dir",
                    "score",
                    "effective",
                    "bucket",
                    "rule_id",
                    "0分原因",
                    "优化优先级",
                    "当前评分规则",
                ],
                metric_rows,
            )
        )
        lines.append("")

    lines.extend(
        [
            "## 6. 初步优化方向",
            "",
            "1. 先处理 `semantic.radar_rule` 且长期为 0 的主信号指标：这类指标数量最多，通常代表 P2 给了 neutral/mixed 或 base_score 太小，P3 没有专用阈值。",
            "2. 对 `context_required` 指标补组合规则：例如 realized_price、STH/LTH cost basis 必须和 btc_price 相对位置结合，否则永远只能作为上下文。",
            "3. 对 `context_only` 指标逐个确认是否应该参与方向：如果只是审计字段就保留 0；如果业务上会影响 BTC 趋势，需要回 P2 设置 affects_signal 和 weight。",
            "4. 对中性阈值区间指标不要盲目改成非 0：SOPR 接近 1、VIX 常态、NUPL 温和区间这类 0 分是合理的，但可以增加趋势斜率、连续天数、跨指标确认。",
            "5. 模块层面建议同时看 `module_score` 与 `module_effective_score`，避免低质量、过期或重复指标对方向过度贡献。",
            "",
            "## 7. 下一步建议",
            "",
            "- 用本文档评估每个 0 分指标：保留 0、补阈值、改上下文、修数据源四类。",
            "- 评估后进入 P3-C22：只先改高优先级主信号，避免一次性重写全部规则导致方向漂移。",
            "- 每改一批规则后全链条跑 P1/P2/P3/P4.5，观察 zero_ratio、module_direction 和 final_view 是否稳定。",
            "",
        ]
    )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"generated={OUT}")
    print(
        f"metrics={len(items)} modules={len(modules)} zero={len(zero_items)} candidates={len(candidate_items)}"
    )


if __name__ == "__main__":
    main()
