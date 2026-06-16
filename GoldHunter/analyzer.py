from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from config import OIL_SIGNIFICANT_MOVE_PCT


@dataclass
class MetricChange:
    key: str
    name: str
    current: float | None
    previous: float | None
    seven_day_ref: float | None
    previous_change: float | None
    previous_change_pct: float | None
    seven_day_change: float | None
    seven_day_change_pct: float | None
    score: float
    signal: str
    note: str


@dataclass
class AnalysisResult:
    latest_date: str | None
    previous_date: str | None
    seven_day_ref_date: str | None
    score: float
    verdict: str
    explanation: str
    metric_changes: list[MetricChange]
    warnings: list[str]


METRICS = {
    "gold_price": "黄金价格",
    "us10y_yield": "美国10年期国债收益率",
    "dxy": "美元指数",
    "gold_etf_flow_proxy": "黄金ETF资金流向代理",
    "oil_price": "原油价格",
}


def analyze_history(history: pd.DataFrame, warnings: list[str] | None = None) -> AnalysisResult:
    warnings = warnings or []
    if history.empty:
        return AnalysisResult(
            latest_date=None,
            previous_date=None,
            seven_day_ref_date=None,
            score=0,
            verdict="数据不足",
            explanation="没有可分析的历史数据。",
            metric_changes=[],
            warnings=warnings,
        )

    clean = history.copy()
    clean["date"] = pd.to_datetime(clean["date"])
    clean = clean.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)

    latest = clean.iloc[-1]
    previous = clean.iloc[-2] if len(clean) >= 2 else None
    seven_day_ref = _find_seven_day_reference(clean, latest["date"])

    metric_changes = [
        _analyze_gold(latest, previous, seven_day_ref),
        _analyze_us10y(latest, previous, seven_day_ref),
        _analyze_dxy(latest, previous, seven_day_ref),
        _analyze_etf_flow(latest, previous, seven_day_ref),
        _analyze_oil(latest, previous, seven_day_ref),
    ]

    score = sum(metric.score for metric in metric_changes)
    verdict = _verdict_from_score(score)
    explanation = _build_explanation(metric_changes, verdict, score)

    return AnalysisResult(
        latest_date=_date_to_str(latest["date"]),
        previous_date=_date_to_str(previous["date"]) if previous is not None else None,
        seven_day_ref_date=_date_to_str(seven_day_ref["date"]) if seven_day_ref is not None else None,
        score=score,
        verdict=verdict,
        explanation=explanation,
        metric_changes=metric_changes,
        warnings=warnings,
    )


def _find_seven_day_reference(clean: pd.DataFrame, latest_date: pd.Timestamp) -> pd.Series | None:
    target_date = latest_date - timedelta(days=7)
    candidates = clean[clean["date"] <= target_date]
    if candidates.empty:
        return None
    return candidates.iloc[-1]


def _analyze_gold(latest: pd.Series, previous: pd.Series | None, seven_day_ref: pd.Series | None) -> MetricChange:
    current = _value(latest, "gold_price")
    previous_value = _value(previous, "gold_price")
    delta = _delta(current, previous_value)

    if delta is None:
        score, signal, note = 0, "中性", "黄金价格数据不足。"
    elif delta > 0:
        score, signal, note = 1, "偏多", "黄金价格上涨，价格趋势对黄金本身有支撑。"
    elif delta < 0:
        score, signal, note = -1, "偏空", "黄金价格下跌，短线价格动能偏弱。"
    else:
        score, signal, note = 0, "中性", "黄金价格基本持平。"

    return _metric_change("gold_price", current, previous_value, seven_day_ref, score, signal, note)


def _analyze_us10y(latest: pd.Series, previous: pd.Series | None, seven_day_ref: pd.Series | None) -> MetricChange:
    current = _value(latest, "us10y_yield")
    previous_value = _value(previous, "us10y_yield")
    delta = _delta(current, previous_value)

    if delta is None:
        score, signal, note = 0, "中性", "美债收益率数据不足。"
    elif delta < 0:
        score, signal, note = 1, "偏多", "10年期美债收益率下降，降低持有黄金的机会成本。"
    elif delta > 0:
        score, signal, note = -1, "偏空", "10年期美债收益率上升，提高持有黄金的机会成本。"
    else:
        score, signal, note = 0, "中性", "10年期美债收益率基本持平。"

    return _metric_change("us10y_yield", current, previous_value, seven_day_ref, score, signal, note)


def _analyze_dxy(latest: pd.Series, previous: pd.Series | None, seven_day_ref: pd.Series | None) -> MetricChange:
    current = _value(latest, "dxy")
    previous_value = _value(previous, "dxy")
    delta = _delta(current, previous_value)

    if delta is None:
        score, signal, note = 0, "中性", "美元指数数据不足。"
    elif delta < 0:
        score, signal, note = 1, "偏多", "美元指数下降，通常利好以美元计价的黄金。"
    elif delta > 0:
        score, signal, note = -1, "偏空", "美元指数上升，通常压制以美元计价的黄金。"
    else:
        score, signal, note = 0, "中性", "美元指数基本持平。"

    return _metric_change("dxy", current, previous_value, seven_day_ref, score, signal, note)


def _analyze_etf_flow(latest: pd.Series, previous: pd.Series | None, seven_day_ref: pd.Series | None) -> MetricChange:
    current = _value(latest, "gold_etf_flow_proxy")

    if current is None:
        score, signal, note = 0, "中性", "黄金ETF资金流向代理数据不足。"
    elif current > 0:
        score, signal, note = 1, "偏多", "GLD资金流向代理为正，显示ETF端买盘更强。"
    elif current < 0:
        score, signal, note = -1, "偏空", "GLD资金流向代理为负，显示ETF端卖盘更强。"
    else:
        score, signal, note = 0, "中性", "GLD资金流向代理接近中性。"

    previous_value = _value(previous, "gold_etf_flow_proxy")
    return _metric_change("gold_etf_flow_proxy", current, previous_value, seven_day_ref, score, signal, note)


def _analyze_oil(latest: pd.Series, previous: pd.Series | None, seven_day_ref: pd.Series | None) -> MetricChange:
    current = _value(latest, "oil_price")
    previous_value = _value(previous, "oil_price")
    change_pct = _pct_change(current, previous_value)

    if change_pct is None:
        score, signal, note = 0, "中性", "原油价格数据不足。"
    elif change_pct <= -OIL_SIGNIFICANT_MOVE_PCT:
        score, signal, note = 0.5, "偏多", "原油明显回落，通胀压力边际缓和。"
    elif change_pct >= OIL_SIGNIFICANT_MOVE_PCT:
        score, signal, note = -0.5, "偏空", "原油明显上涨，可能推升通胀与利率预期。"
    else:
        score, signal, note = 0, "中性", "原油变动未达到明显阈值。"

    return _metric_change("oil_price", current, previous_value, seven_day_ref, score, signal, note)


def _metric_change(
    key: str,
    current: float | None,
    previous_value: float | None,
    seven_day_ref: pd.Series | None,
    score: float,
    signal: str,
    note: str,
) -> MetricChange:
    seven_day_value = _value(seven_day_ref, key)
    return MetricChange(
        key=key,
        name=METRICS[key],
        current=current,
        previous=previous_value,
        seven_day_ref=seven_day_value,
        previous_change=_delta(current, previous_value),
        previous_change_pct=_pct_change(current, previous_value),
        seven_day_change=_delta(current, seven_day_value),
        seven_day_change_pct=_pct_change(current, seven_day_value),
        score=score,
        signal=signal,
        note=note,
    )


def _value(row: pd.Series | None, key: str) -> float | None:
    if row is None or key not in row:
        return None
    value = row[key]
    if pd.isna(value):
        return None
    return float(value)


def _delta(current: float | None, reference: float | None) -> float | None:
    if current is None or reference is None:
        return None
    return current - reference


def _pct_change(current: float | None, reference: float | None) -> float | None:
    if current is None or reference in (None, 0):
        return None
    return (current - reference) / reference * 100


def _verdict_from_score(score: float) -> str:
    if score >= 2:
        return "偏多"
    if score <= -2:
        return "偏空"
    return "震荡"


def _build_explanation(metric_changes: list[MetricChange], verdict: str, score: float) -> str:
    positive = [metric.name for metric in metric_changes if metric.score > 0]
    negative = [metric.name for metric in metric_changes if metric.score < 0]

    parts = [f"综合得分为 {score:g}，当前判断为{verdict}。"]
    if positive:
        parts.append(f"偏多因素主要来自：{'、'.join(positive)}。")
    if negative:
        parts.append(f"偏空因素主要来自：{'、'.join(negative)}。")
    if not positive and not negative:
        parts.append("主要指标方向不明确，暂以震荡处理。")
    return "".join(parts)


def _date_to_str(value: pd.Timestamp) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")
