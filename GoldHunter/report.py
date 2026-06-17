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
        "- 黄金价格口径改为 SPDR Gold Shares 官方历史档案中的 GLD 收盘价；XAU/USD、LBMA、ICE、CME 的实时官方接口通常需要授权或许可。",
        "- 美国10年期国债收益率使用 FRED DGS10，来源为 Federal Reserve H.15 Selected Interest Rates。",
        "- 美元指标使用 FRED DTWEXBGS，即美联储 H.10 的 Nominal Broad U.S. Dollar Index；它不是 ICE DXY，但属于官方美元强弱指标。",
        "- 黄金ETF资金流向使用 SPDR Gold Shares 官方历史档案中的 Tonnes of Gold 日变化，正值视为净流入，负值视为净流出。",
        "- 原油价格使用 FRED DCOILWTICO，来源为 U.S. Energy Information Administration 的 WTI Cushing 现货价。",
        "- 各官方源发布时间不同，报告使用每个指标的最新可得数据，并在今日数据表中标注数据日。",
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
        ["GLD官方收盘价", _fmt(_row_value(row, "gold_price")), _source(row, "gold_price")],
        ["美国10年期国债收益率", _fmt(_row_value(row, "us10y_yield"), "%"), _source(row, "us10y_yield")],
        ["美联储广义美元指数", _fmt(_row_value(row, "dxy")), _source(row, "dxy")],
        ["GLD官方黄金持仓", _fmt(_row_value(row, "gld_tonnes"), " 吨"), _source(row, "gold_etf")],
        ["GLD持仓日变化", _fmt(_row_value(row, "gold_etf_flow_proxy"), " 吨"), "SPDR Gold Shares Historical Archive"],
        ["WTI原油现货价格", _fmt(_row_value(row, "oil_price")), _source(row, "oil_price")],
    ]
    return _markdown_table(["指标", "最新值", "数据源/说明"], rows)


def _change_table(metric_changes: list[MetricChange]) -> str:
    rows = []
    for metric in metric_changes:
        suffix = " 吨" if metric.key == "gold_etf_flow_proxy" else ""
        rows.append(
            [
                metric.name,
                _fmt_change(metric.previous_change, metric.previous_change_pct, suffix=suffix),
                _fmt_change(metric.seven_day_change, metric.seven_day_change_pct, suffix=suffix),
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


def _source(row: pd.Series | None, key: str) -> str:
    source = _row_value(row, f"{key}_source")
    source_date = _row_value(row, f"{key}_source_date")
    if source and source_date:
        return f"{source}（数据日 {source_date}）"
    if source:
        return str(source)
    return "N/A"


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


def _fmt_change(delta: float | None, pct: float | None, suffix: str = "") -> str:
    if delta is None:
        return "N/A"
    sign = "+" if delta > 0 else ""
    if pct is None:
        return f"{sign}{delta:,.2f}{suffix}"
    pct_sign = "+" if pct > 0 else ""
    return f"{sign}{delta:,.2f}{suffix} ({pct_sign}{pct:,.2f}%)"
