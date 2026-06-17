from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import MODULE_WEIGHTS, RISK_THRESHOLDS


@dataclass
class RiskModule:
    key: str
    name: str
    weight: float
    score: float
    contribution: float
    drivers: list[str]
    stable: list[str]


@dataclass
class AnalysisResult:
    latest_date: str | None
    score: float
    risk_color: str
    risk_label: str
    one_line: str
    modules: list[RiskModule]
    triggered_rules: list[str]
    stable_factors: list[str]
    latest_snapshot: dict[str, float | str | None]
    warnings: list[str]

    @property
    def verdict(self) -> str:
        return self.risk_color


def analyze_history(history: pd.DataFrame, warnings: list[str] | None = None) -> AnalysisResult:
    warnings = warnings or []
    if history.empty:
        return AnalysisResult(
            latest_date=None,
            score=0,
            risk_color="灰色",
            risk_label="数据不足",
            one_line="没有可分析的历史数据。",
            modules=[],
            triggered_rules=[],
            stable_factors=[],
            latest_snapshot={},
            warnings=warnings,
        )

    clean = history.copy()
    clean["date"] = pd.to_datetime(clean["date"], errors="coerce")
    clean = clean.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    clean = clean.set_index("date").ffill()

    modules = [
        _rates_and_usd_module(clean),
        _price_structure_module(clean),
        _etf_flows_module(clean),
        _cot_positioning_module(clean),
        _liquidity_stress_module(clean),
        _event_risk_module(clean),
    ]
    score = _clamp(sum(module.contribution for module in modules), 0, 100)
    triggered_rules = _triggered_rules(clean, score)
    if score >= 76 and not any("分数" in rule for rule in triggered_rules):
        triggered_rules.append("Gold Crash Risk Score 高于 76。")

    risk_color, risk_label = _risk_level(score, triggered_rules)
    stable_factors = _stable_factors(modules)
    drivers = [driver for module in modules for driver in module.drivers]
    one_line = _one_line(risk_color, score, drivers)

    return AnalysisResult(
        latest_date=_date_to_str(clean.index[-1]),
        score=round(score, 1),
        risk_color=risk_color,
        risk_label=risk_label,
        one_line=one_line,
        modules=modules,
        triggered_rules=triggered_rules,
        stable_factors=stable_factors,
        latest_snapshot=_latest_snapshot(clean),
        warnings=warnings,
    )


def _rates_and_usd_module(data: pd.DataFrame) -> RiskModule:
    real = _series(data, "real_yield_10y")
    dxy = _series(data, "dollar_index")
    dgs10 = _series(data, "us10y_yield")
    dgs2 = _series(data, "us2y_yield")

    real_20 = _change(real, 20) * 100
    real_60 = _change(real, 60) * 100
    real_level = _last(real)
    dxy_20 = _pct_change(dxy, 20)
    dxy_60 = _pct_change(dxy, 60)
    dgs10_20 = _change(dgs10, 20) * 100
    dgs2_20 = _change(dgs2, 20) * 100

    score = (
        0.35 * _scale(real_20, 0, 40)
        + 0.20 * _scale(real_60, 0, 80)
        + 0.15 * _scale(real_level, 0.5, 2.5)
        + 0.20 * _scale(dxy_20, 0, 3)
        + 0.10 * _scale(dxy_60, 0, 5)
    )
    if real_20 > 20 and dxy_20 > 2:
        score += 15

    drivers: list[str] = []
    stable: list[str] = []
    if real_20 > 20:
        drivers.append(f"10年实际利率20日上升 {real_20:.0f}bp")
    else:
        stable.append(f"10年实际利率20日变化 {real_20:.0f}bp，未达到快速上行阈值")
    if real_60 > 40:
        drivers.append(f"10年实际利率60日上升 {real_60:.0f}bp")
    if dxy_20 > 2:
        drivers.append(f"美元指数20日上涨 {dxy_20:.2f}%")
    else:
        stable.append(f"美元指数20日涨幅 {dxy_20:.2f}%，未明显走强")
    if dxy_60 > 4:
        drivers.append(f"美元指数60日上涨 {dxy_60:.2f}%")
    if dgs10_20 > 20 or dgs2_20 > 25:
        drivers.append("名义美债收益率快速上行，降息预期退潮")

    return _module("rates_and_usd", "实际利率与美元压力", score, drivers, stable)


def _price_structure_module(data: pd.DataFrame) -> RiskModule:
    price = _series(data, "gold_price")
    current = _last(price)
    ma50 = price.rolling(50).mean().iloc[-1]
    ma100 = price.rolling(100).mean().iloc[-1]
    ma200 = price.rolling(200).mean().iloc[-1]
    ret20 = _pct_change(price, 20)
    ret60 = _pct_change(price, 60)
    high60 = price.tail(60).max()
    drawdown60 = (current / high60 - 1) * 100 if high60 else np.nan
    vol20 = price.pct_change().tail(20).std() * np.sqrt(252) * 100

    below50 = current < ma50 if pd.notna(ma50) else False
    below100 = current < ma100 if pd.notna(ma100) else False
    below200 = current < ma200 if pd.notna(ma200) else False

    score = 0
    score += 20 if below50 else 0
    score += 25 if below100 else 0
    score += 25 if below200 else 0
    score += _scale(-drawdown60, 2, 12) * 20 / 100
    score += _scale(-ret20, 0, 8) * 10 / 100
    score = _clamp(score, 0, 100)

    drivers: list[str] = []
    stable: list[str] = []
    if below50:
        drivers.append("黄金价格跌破 MA50")
    else:
        stable.append("黄金价格仍在 MA50 上方，短期结构未破坏")
    if below100:
        drivers.append("黄金价格跌破 MA100")
    else:
        stable.append("黄金价格仍在 MA100 上方")
    if below200:
        drivers.append("黄金价格跌破 MA200")
    if drawdown60 <= -6:
        drivers.append(f"黄金较60日高点回撤 {drawdown60:.2f}%")
    elif drawdown60 > -4:
        stable.append(f"60日回撤 {drawdown60:.2f}%，更像正常波动")
    if pd.notna(vol20) and vol20 > 25 and below50:
        drivers.append(f"20日波动率升至 {vol20:.1f}%，破位信号更危险")

    return _module("price_structure", "黄金价格结构", score, drivers, stable)


def _etf_flows_module(data: pd.DataFrame) -> RiskModule:
    tonnes = _series(data, "gld_tonnes")
    flow20 = _change(tonnes, 20)
    flow60 = _change(tonnes, 60)
    holdings = _last(tonnes)
    flow20_pct = flow20 / holdings * 100 if holdings else np.nan
    flow60_pct = flow60 / holdings * 100 if holdings else np.nan

    score = 0.6 * _scale(-flow20_pct, 0, 2.0) + 0.4 * _scale(-flow60_pct, 0, 5.0)
    drivers: list[str] = []
    stable: list[str] = []
    if flow20 < 0:
        drivers.append(f"GLD近20个交易日持仓下降 {abs(flow20):.2f} 吨")
    else:
        stable.append(f"GLD近20个交易日持仓增加 {flow20:.2f} 吨")
    if flow60 < 0:
        drivers.append(f"GLD近60个交易日持仓下降 {abs(flow60):.2f} 吨")
    else:
        stable.append("GLD近60个交易日未出现持续流出")

    return _module("etf_flows", "ETF资金流压力", score, drivers, stable)


def _cot_positioning_module(data: pd.DataFrame) -> RiskModule:
    net = _series(data, "cftc_mm_net_long")
    price = _series(data, "gold_price")
    if net.dropna().empty:
        return _module("cot_positioning", "CFTC持仓压力", 0, [], ["CFTC黄金持仓数据暂不可用"])

    current = _last(net)
    change4w = _change(net, 20)
    change4w_pct = change4w / abs(current - change4w) * 100 if current != change4w else 0
    percentile = _percentile_rank(net.dropna(), current)
    price_below_ma50 = _last(price) < price.rolling(50).mean().iloc[-1]

    crowding_score = percentile * 100
    reversal_score = _scale(-change4w_pct, 0, 25)
    score = 0.4 * crowding_score + 0.6 * reversal_score
    if percentile >= 0.8 and change4w_pct <= -20 and price_below_ma50:
        score += 15

    drivers: list[str] = []
    stable: list[str] = []
    if percentile >= 0.8:
        drivers.append(f"Managed Money净多头处于近年高分位 {percentile * 100:.0f}%")
    else:
        stable.append(f"Managed Money净多头分位 {percentile * 100:.0f}%，拥挤度不极端")
    if change4w_pct <= -20:
        drivers.append(f"Managed Money净多头近4周下降 {abs(change4w_pct):.1f}%")
    else:
        stable.append(f"Managed Money净多头近4周变化 {change4w_pct:.1f}%")

    return _module("cot_positioning", "CFTC持仓拥挤与反转", score, drivers, stable)


def _liquidity_stress_module(data: pd.DataFrame) -> RiskModule:
    dxy = _series(data, "dollar_index")
    hy = _series(data, "hy_oas")
    vix = _series(data, "vix")
    nfci = _series(data, "nfci")
    sofr = _series(data, "sofr")
    iorb = _series(data, "iorb")

    hy_20 = _change(hy, 20) * 100
    vix_20 = _change(vix, 20)
    dxy_20 = _pct_change(dxy, 20)
    nfci_level = _last(nfci)
    spread = _last(sofr - iorb)

    score = (
        0.30 * _scale(hy_20, 0, 100)
        + 0.25 * _scale(vix_20, 0, 12)
        + 0.20 * _scale(dxy_20, 0, 3)
        + 0.15 * _scale(nfci_level, -0.5, 0.5)
        + 0.10 * _scale(spread * 100, 0, 15)
    )

    drivers: list[str] = []
    stable: list[str] = []
    if hy_20 > 50:
        drivers.append(f"高收益债利差20日扩大 {hy_20:.0f}bp")
    else:
        stable.append("高收益债利差未快速扩大")
    if vix_20 > 8:
        drivers.append(f"VIX近20日上升 {vix_20:.1f}")
    else:
        stable.append("VIX未明显飙升")
    if nfci_level > 0:
        drivers.append("NFCI高于0，金融条件偏紧")
    else:
        stable.append("NFCI尚未显示系统性金融条件收紧")

    return _module("liquidity_stress", "美元流动性与抛售压力", score, drivers, stable)


def _event_risk_module(data: pd.DataFrame) -> RiskModule:
    return _module(
        "event_risk",
        "事件风险",
        0,
        [],
        ["事件日历暂未接入；CPI、PCE、FOMC、NFP仍需人工关注"],
    )


def _triggered_rules(data: pd.DataFrame, score: float) -> list[str]:
    price = _series(data, "gold_price")
    ma50 = price.rolling(50).mean().iloc[-1]
    ma100 = price.rolling(100).mean().iloc[-1]
    ma200 = price.rolling(200).mean().iloc[-1]
    current = _last(price)
    dd60 = (current / price.tail(60).max() - 1) * 100
    real60 = _change(_series(data, "real_yield_10y"), 60) * 100
    real20 = _change(_series(data, "real_yield_10y"), 20) * 100
    dxy60 = _pct_change(_series(data, "dollar_index"), 60)
    dxy20 = _pct_change(_series(data, "dollar_index"), 20)
    etf20 = _change(_series(data, "gld_tonnes"), 20)
    cot = _series(data, "cftc_mm_net_long")
    cot_4w_pct = np.nan
    if not cot.dropna().empty:
        cot_change = _change(cot, 20)
        base = _last(cot) - cot_change
        cot_4w_pct = cot_change / abs(base) * 100 if base else np.nan
    hy20 = _change(_series(data, "hy_oas"), 20) * 100

    yellow_conditions = [
        current < ma50,
        real20 > 20,
        dxy20 > 2,
        etf20 < 0,
        pd.notna(cot_4w_pct) and cot_4w_pct < 0,
    ]
    orange_conditions = [
        current < ma100,
        dd60 <= -6,
        real60 > 40,
        dxy60 > 4,
        etf20 < 0 and current < ma50,
        pd.notna(cot_4w_pct) and cot_4w_pct <= -20,
        hy20 > 50,
    ]

    rules: list[str] = []
    if sum(bool(x) for x in yellow_conditions) >= 2:
        rules.append("黄色规则：至少两个早期压力信号同时出现。")
    if sum(bool(x) for x in orange_conditions) >= 3:
        rules.append("橙色规则：至少三个较大回撤风险信号同时出现。")
    if (
        (current < ma100 or current < ma200)
        and real20 > 20
        and dxy20 > 2
        and etf20 < 0
        and pd.notna(cot_4w_pct)
        and cot_4w_pct <= -20
    ):
        rules.append("红色规则：价格破位、实际利率、美元、ETF与CFTC同时恶化。")
    if score > 76:
        rules.append("分数规则：Gold Crash Risk Score 高于 76。")
    return rules


def _latest_snapshot(data: pd.DataFrame) -> dict[str, float | str | None]:
    price = _series(data, "gold_price")
    real = _series(data, "real_yield_10y")
    dxy = _series(data, "dollar_index")
    tonnes = _series(data, "gld_tonnes")
    net = _series(data, "cftc_mm_net_long")
    hy = _series(data, "hy_oas")
    vix = _series(data, "vix")

    return {
        "gold_price": _last(price),
        "ma50": price.rolling(50).mean().iloc[-1],
        "ma100": price.rolling(100).mean().iloc[-1],
        "ma200": price.rolling(200).mean().iloc[-1],
        "drawdown_60d_pct": (_last(price) / price.tail(60).max() - 1) * 100,
        "real_yield_10y": _last(real),
        "real_yield_20d_bp": _change(real, 20) * 100,
        "dollar_20d_pct": _pct_change(dxy, 20),
        "gld_tonnes": _last(tonnes),
        "gld_20d_flow_tonnes": _change(tonnes, 20),
        "cftc_mm_net_long": _last(net) if not net.dropna().empty else None,
        "hy_oas": _last(hy),
        "vix": _last(vix),
    }


def _module(key: str, name: str, score: float, drivers: list[str], stable: list[str]) -> RiskModule:
    module_score = round(_clamp(score, 0, 100), 1)
    weight = MODULE_WEIGHTS[key]
    return RiskModule(
        key=key,
        name=name,
        weight=weight,
        score=module_score,
        contribution=round(module_score * weight, 2),
        drivers=drivers,
        stable=stable,
    )


def _risk_level(score: float, rules: list[str]) -> tuple[str, str]:
    if any(rule.startswith("红色") for rule in rules) or score > RISK_THRESHOLDS["orange_max"]:
        return "红色", "大跌风险高"
    if any(rule.startswith("橙色") for rule in rules) or score > RISK_THRESHOLDS["yellow_max"]:
        return "橙色", "大跌风险明显升高"
    if any(rule.startswith("黄色") for rule in rules) or score > RISK_THRESHOLDS["green_max"]:
        return "黄色", "压力开始上升"
    return "绿色", "大跌风险低"


def _stable_factors(modules: list[RiskModule]) -> list[str]:
    stable = []
    for module in modules:
        stable.extend(module.stable[:2])
    return stable[:8]


def _one_line(color: str, score: float, drivers: list[str]) -> str:
    if color == "绿色":
        return "当前更像正常波动，尚未出现大跌风险共振。"
    if color == "黄色":
        return "黄金大跌风险开始上升，需要观察是否进一步跌破关键均线。"
    if color == "橙色":
        return "未来10-30个交易日出现较大回撤的风险明显升高。"
    if color == "红色":
        return "当前不是普通回调，属于多组压力共振恶化。"
    return f"当前风险分数为 {score:.1f}。"


def _series(data: pd.DataFrame, column: str) -> pd.Series:
    if column not in data:
        return pd.Series(dtype="float64")
    return pd.to_numeric(data[column], errors="coerce").ffill()


def _last(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return float("nan")
    return float(clean.iloc[-1])


def _change(series: pd.Series, periods: int) -> float:
    clean = series.dropna()
    if len(clean) <= periods:
        return float("nan")
    return float(clean.iloc[-1] - clean.iloc[-periods - 1])


def _pct_change(series: pd.Series, periods: int) -> float:
    clean = series.dropna()
    if len(clean) <= periods:
        return float("nan")
    base = clean.iloc[-periods - 1]
    if base == 0:
        return float("nan")
    return float((clean.iloc[-1] / base - 1) * 100)


def _scale(value: float, low: float, high: float) -> float:
    if pd.isna(value):
        return 0
    if high == low:
        return 0
    return _clamp((value - low) / (high - low) * 100, 0, 100)


def _clamp(value: float, low: float, high: float) -> float:
    if pd.isna(value):
        return 0
    return max(low, min(high, float(value)))


def _percentile_rank(series: pd.Series, value: float) -> float:
    clean = series.dropna()
    if clean.empty or pd.isna(value):
        return 0
    return float((clean <= value).mean())


def _date_to_str(value: pd.Timestamp) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")
