from __future__ import annotations

import sys

import pandas as pd

from analyzer import analyze_history
from config import DATA_DIR, HISTORY_CSV, REPORTS_DIR
from data_fetcher import MacroDataFetcher
from report import generate_email_summary, generate_report


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    existing_history = _load_history()
    fetch_outcome = MacroDataFetcher().fetch_recent_history()

    if fetch_outcome.data.empty and existing_history.empty:
        analysis = analyze_history(pd.DataFrame(), fetch_outcome.errors)
        report_path = generate_report(analysis, pd.DataFrame())
        email_path = generate_email_summary(analysis)
        print(f"没有抓到可用行情数据，已生成空报告：{report_path}")
        print(f"已生成邮件摘要：{email_path}")
        return 0

    history = _merge_history(existing_history, fetch_outcome.data)
    _save_history(history)

    analysis = analyze_history(history, fetch_outcome.errors)
    report_path = generate_report(analysis, history)
    email_path = generate_email_summary(analysis)

    print(f"已更新历史数据：{HISTORY_CSV}")
    print(f"已生成日报：{report_path}")
    print(f"已生成邮件摘要：{email_path}")
    print(f"黄金多空判断：{analysis.verdict}（得分 {analysis.score:g}）")
    return 0


def _load_history() -> pd.DataFrame:
    if not HISTORY_CSV.exists():
        return pd.DataFrame()

    try:
        history = pd.read_csv(HISTORY_CSV)
    except Exception as exc:  # noqa: BLE001 - keep the command usable if CSV is damaged.
        print(f"读取历史数据失败，将从本次数据重新生成：{exc}")
        return pd.DataFrame()

    if "date" not in history.columns:
        print("历史数据缺少 date 列，将从本次数据重新生成。")
        return pd.DataFrame()
    return history


def _merge_history(existing: pd.DataFrame, recent: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in [existing, recent] if not frame.empty]
    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True, sort=False)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.dropna(subset=["date"])

    def last_valid(series: pd.Series) -> object:
        non_null = series.dropna()
        if non_null.empty:
            return pd.NA
        return non_null.iloc[-1]

    merged = merged.sort_values("date").groupby("date", as_index=False).agg(last_valid)
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    return merged.reset_index(drop=True)


def _save_history(history: pd.DataFrame) -> None:
    history.to_csv(HISTORY_CSV, index=False, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
