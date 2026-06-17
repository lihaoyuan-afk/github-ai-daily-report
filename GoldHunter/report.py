from __future__ import annotations

from pathlib import Path

import pandas as pd

from analyzer import AnalysisResult
from config import DAILY_REPORT, EMAIL_SUMMARY, REPORT_TITLE


def generate_report(
    analysis: AnalysisResult,
    history: pd.DataFrame,
    output_path: Path = DAILY_REPORT,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {REPORT_TITLE}",
        "",
        f"- 日期：{analysis.latest_date or 'N/A'}",
        f"- 黄金大跌风险：**{analysis.risk_color}**（{analysis.risk_label}）",
        f"- Gold Crash Risk Score：**{analysis.score:.1f} / 100**",
        f"- 一句话判断：{analysis.one_line}",
        "",
        "## 主要压力来源",
        "",
        _drivers_list(analysis),
        "",
        "## 模块分数",
        "",
        _module_table(analysis),
        "",
        "## 核心指标快照",
        "",
        _snapshot_table(analysis),
        "",
        "## 触发的风险规则",
        "",
        _simple_list(analysis.triggered_rules, "暂未触发黄色/橙色/红色组合规则。"),
        "",
        "## 暂未恶化的部分",
        "",
        _simple_list(analysis.stable_factors, "暂无足够数据判断未恶化项。"),
        "",
        "## 判断",
        "",
        _judgement(analysis),
        "",
        "## 数据源说明",
        "",
        "- GLD价格与持仓：SPDR Gold Shares 官方 Historical Archive。",
        "- 实际利率、2年/10年美债、美元指数、VIX、高收益债利差、NFCI、SOFR、IORB、准备金：FRED 官方公开序列。",
        "- CFTC持仓：CFTC Disaggregated Futures Only，COMEX Gold Managed Money。",
        "- ICE DXY、LBMA金价、CME实时行情通常需要授权；本系统优先使用可自动化抓取的官方公开源。",
        "- 本报告是风险雷达，不预测明天涨跌，也不构成投资建议。",
    ]

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

    drivers = [driver for module in analysis.modules for driver in module.drivers]
    if drivers:
        reason = "；".join(drivers[:3])
    else:
        reason = "暂无多组风险共振"

    lines = [
        f"日期：{analysis.latest_date or '暂无数据'}",
        f"黄金大跌风险：{analysis.risk_color}",
        f"分数：{analysis.score:.1f}/100",
        f"主要原因：{reason}",
        f"判断：{analysis.one_line}",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _drivers_list(analysis: AnalysisResult) -> str:
    drivers = [driver for module in analysis.modules for driver in module.drivers]
    return _simple_list(drivers[:8], "暂无明显压力来源。")


def _module_table(analysis: AnalysisResult) -> str:
    rows = []
    for module in analysis.modules:
        rows.append(
            [
                module.name,
                f"{module.score:.1f}",
                f"{module.weight * 100:.0f}%",
                f"{module.contribution:.1f}",
                "；".join(module.drivers[:2]) if module.drivers else "暂无明显恶化",
            ]
        )
    return _markdown_table(["模块", "模块分", "权重", "贡献", "核心信号"], rows)


def _snapshot_table(analysis: AnalysisResult) -> str:
    snapshot = analysis.latest_snapshot
    rows = [
        ["GLD官方收盘价", _fmt(snapshot.get("gold_price"))],
        ["MA50 / MA100 / MA200", f"{_fmt(snapshot.get('ma50'))} / {_fmt(snapshot.get('ma100'))} / {_fmt(snapshot.get('ma200'))}"],
        ["60日高点回撤", _fmt(snapshot.get("drawdown_60d_pct"), "%")],
        ["10年实际利率", _fmt(snapshot.get("real_yield_10y"), "%")],
        ["10年实际利率20日变化", _fmt(snapshot.get("real_yield_20d_bp"), "bp")],
        ["美元指数20日涨幅", _fmt(snapshot.get("dollar_20d_pct"), "%")],
        ["GLD持仓", _fmt(snapshot.get("gld_tonnes"), " 吨")],
        ["GLD近20日持仓变化", _fmt(snapshot.get("gld_20d_flow_tonnes"), " 吨")],
        ["CFTC Managed Money净多头", _fmt(snapshot.get("cftc_mm_net_long"), " 张")],
        ["高收益债利差", _fmt(snapshot.get("hy_oas"), "%")],
        ["VIX", _fmt(snapshot.get("vix"))],
    ]
    return _markdown_table(["指标", "最新值"], rows)


def _judgement(analysis: AnalysisResult) -> str:
    if analysis.risk_color == "绿色":
        return "当前更接近正常波动，尚未看到实际利率、美元、资金流和价格结构的共振恶化。"
    if analysis.risk_color == "黄色":
        return "大跌风险开始上升，但仍需观察是否跌破更长期均线，以及ETF/CFTC是否继续恶化。"
    if analysis.risk_color == "橙色":
        return "未来10-30个交易日出现较大回撤的风险明显升高，建议进入防守观察状态。"
    if analysis.risk_color == "红色":
        return "当前不是普通小回调，而是宏观压力、资金流与价格结构共振恶化。"
    return "数据不足，暂不判断。"


def _simple_list(items: list[str], empty_text: str) -> str:
    if not items:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in items)


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


def _fmt(value: object | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if pd.isna(number):
        return "N/A"
    return f"{number:,.2f}{suffix}"
