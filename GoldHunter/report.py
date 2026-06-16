from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyzer import AnalysisResult, MetricChange
from config import DAILY_REPORT, EMAIL_SUMMARY, REPORT_TITLE


def generate_report(
    analysis: AnalysisResult,
    history: pd.DataFrame,
    output_path: Path = DAILY_REPORT,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    latest_row = _latest_row(history)

    lines = [
        f"# {REPORT_TITLE}",
        "",
        f"- 报告日期：{analysis.latest_date or 'N/A'}",
        f"- 综合得分：{analysis.score:g}",
        f"- 黄金多空判断：**{analysis.verdict}**",
        "",
        "## 今日数据表",
        "",
        _today_table(latest_row),
        "",
        "## 各指标变化",
        "",
        _change_table(analysis.metric_changes),
        "",
        "## 简短解释",
        "",
        analysis.explanation,
        "",
        "## 指标备注",
        "",
        "- 黄金价格优先使用 XAU/USD，失败后回退到 COMEX 黄金期货或 GLD。",
        "- 美国10年期国债收益率使用 Yahoo Finance 的 ^TNX；如返回数值为收益率乘以10，程序会自动换算为百分比。",
        "- 黄金ETF资金流向使用 GLD 的价格与成交量生成代理值：上涨日为正、下跌日为负。它不是官方持仓变化，但可作为公开数据下的资金方向参考。",
        f"- 原油“明显上涨/回落”的阈值为日变化 2%。",
    ]

    if analysis.previous_date:
        lines.insert(4, f"- 上一可用交易日：{analysis.previous_date}")
    if analysis.seven_day_ref_date:
        lines.insert(5, f"- 7日前参考日：{analysis.seven_day_ref_date}")
    if analysis.warnings:
        lines.extend(["", "## 数据抓取提示", ""])
        lines.extend(f"- {warning}" for warning in analysis.warnings)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def generate_email_summary(
    analysis: AnalysisResult,
    output_path: Path = EMAIL_SUMMARY,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    positive = [metric.name for metric in analysis.metric_changes if metric.score > 0]
    negative = [metric.name for metric in analysis.metric_changes if metric.score < 0]
    reason_parts = []
    if positive:
        reason_parts.append(f"利多：{'、'.join(positive)}")
    if negative:
        reason_parts.append(f"利空：{'、'.join(negative)}")
    reason = "；".join(reason_parts) if reason_parts else "信号不明显"

    lines = [
        f"日期：{analysis.latest_date or '暂无数据'}",
        f"结论：{analysis.verdict}",
        f"得分：{analysis.score:g}",
        f"简述：{reason}",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _latest_row(history: pd.DataFrame) -> pd.Series | None:
    if history.empty:
        return None
    clean = history.copy()
    clean["date"] = pd.to_datetime(clean["date"])
    return clean.sort_values("date").iloc[-1]


def _today_table(row: pd.Series | None) -> str:
    rows = [
        ["黄金价格", _fmt(_row_value(row, "gold_price")), _row_value(row, "gold_price_source") or "N/A"],
        ["美国10年期国债收益率", _fmt(_row_value(row, "us10y_yield"), "%"), _row_value(row, "us10y_yield_source") or "N/A"],
        ["美元指数", _fmt(_row_value(row, "dxy")), _row_value(row, "dxy_source") or "N/A"],
        ["黄金ETF GLD收盘价", _fmt(_row_value(row, "gld_close")), _row_value(row, "gold_etf_source") or "N/A"],
        ["黄金ETF资金流向代理", _fmt_money(_row_value(row, "gold_etf_flow_proxy")), "GLD price x volume proxy"],
        ["原油价格", _fmt(_row_value(row, "oil_price")), _row_value(row, "oil_price_source") or "N/A"],
    ]
    return _markdown_table(["指标", "最新值", "数据源/说明"], rows)


def _change_table(metric_changes: list[MetricChange]) -> str:
    rows = []
    for metric in metric_changes:
        rows.append(
            [
                metric.name,
                _fmt_change(metric.previous_change, metric.previous_change_pct),
                _fmt_change(metric.seven_day_change, metric.seven_day_change_pct),
                metric.signal,
                f"{metric.score:g}",
                metric.note,
            ]
        )
    return _markdown_table(["指标", "较上一可用日", "较7日前", "信号", "得分", "说明"], rows)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    escaped_headers = [_escape_cell(header) for header in headers]
    output = [
        "| " + " | ".join(escaped_headers) + " |",
        "| " + " | ".join("---" for _ in escaped_headers) + " |",
    ]
    for row in rows:
        output.append("| " + " | ".join(_escape_cell(str(cell)) for cell in row) + " |")
    return "\n".join(output)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _row_value(row: pd.Series | None, key: str) -> object | None:
    if row is None or key not in row:
        return None
    value = row[key]
    if pd.isna(value):
        return None
    return value


def _fmt(value: object | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_money(value: object | None) -> str:
    if value is None:
        return "N/A"
    number = float(value)
    sign = "-" if number < 0 else ""
    abs_number = abs(number)
    if abs_number >= 1_000_000_000:
        return f"{sign}${abs_number / 1_000_000_000:,.2f}B"
    if abs_number >= 1_000_000:
        return f"{sign}${abs_number / 1_000_000:,.2f}M"
    return f"{sign}${abs_number:,.0f}"


def _fmt_change(delta: float | None, pct: float | None) -> str:
    if delta is None:
        return "N/A"
    sign = "+" if delta > 0 else ""
    if pct is None:
        return f"{sign}{delta:,.2f}"
    pct_sign = "+" if pct > 0 else ""
    return f"{sign}{delta:,.2f} ({pct_sign}{pct:,.2f}%)"
