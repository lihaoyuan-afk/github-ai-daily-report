from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ModuleNotFoundError:
    yf = None

from config import ETF_SYMBOL, HISTORY_LOOKBACK_DAYS, MARKET_SYMBOLS


@dataclass
class FetchOutcome:
    data: pd.DataFrame
    errors: list[str]


class MacroDataFetcher:
    """Fetches recent market data and converts it into the history schema."""

    def __init__(self, lookback_days: int = HISTORY_LOOKBACK_DAYS) -> None:
        self.lookback_days = lookback_days

    def fetch_recent_history(self) -> FetchOutcome:
        errors: list[str] = []
        frames: list[pd.DataFrame] = []

        for metric_key, metric_config in MARKET_SYMBOLS.items():
            series, source, metric_errors = self._fetch_first_available_close(
                metric_key=metric_key,
                symbols=metric_config["symbols"],
            )
            errors.extend(metric_errors)
            if series.empty:
                continue

            if metric_key == "us10y_yield":
                series = self._normalize_treasury_yield(series)

            frame = pd.DataFrame({metric_key: series})
            frame[f"{metric_key}_source"] = source
            frames.append(frame)

        etf_frame, etf_errors = self._fetch_etf_flow_proxy()
        errors.extend(etf_errors)
        if not etf_frame.empty:
            frames.append(etf_frame)

        if not frames:
            return FetchOutcome(data=pd.DataFrame(), errors=errors)

        combined = pd.concat(frames, axis=1).sort_index()
        combined.index.name = "date"
        combined = combined.reset_index()
        combined["date"] = pd.to_datetime(combined["date"]).dt.date.astype(str)
        return FetchOutcome(data=combined, errors=errors)

    def _fetch_first_available_close(
        self,
        metric_key: str,
        symbols: Iterable[str],
    ) -> tuple[pd.Series, str | None, list[str]]:
        errors: list[str] = []

        for symbol in symbols:
            raw, error = self._download(symbol)
            if error:
                errors.append(f"{metric_key}: {error}")
                continue

            close = self._extract_column(raw, "Close")
            if close.empty:
                errors.append(f"{metric_key}: {symbol} 没有可用收盘价")
                continue

            close.name = metric_key
            return close, symbol, errors

        return pd.Series(dtype="float64"), None, errors

    def _fetch_etf_flow_proxy(self) -> tuple[pd.DataFrame, list[str]]:
        raw, error = self._download(ETF_SYMBOL)
        if error:
            return pd.DataFrame(), [f"gold_etf_flow_proxy: {error}"]

        close = self._extract_column(raw, "Close")
        volume = self._extract_column(raw, "Volume")
        if close.empty or volume.empty:
            return pd.DataFrame(), [f"gold_etf_flow_proxy: {ETF_SYMBOL} 缺少价格或成交量"]

        close_change = close.diff()
        direction = np.sign(close_change).fillna(0)
        flow_proxy = direction * close * volume

        frame = pd.DataFrame(
            {
                "gld_close": close,
                "gld_volume": volume,
                "gold_etf_flow_proxy": flow_proxy,
                "gold_etf_source": ETF_SYMBOL,
            }
        )
        return frame, []

    def _download(self, symbol: str) -> tuple[pd.DataFrame, str | None]:
        if yf is None:
            return pd.DataFrame(), "缺少 yfinance，请先运行 pip install -r requirements.txt"

        period = f"{self.lookback_days}d"
        try:
            data = yf.download(
                symbol,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as exc:  # noqa: BLE001 - third-party APIs raise mixed exceptions.
            return pd.DataFrame(), f"{symbol} 抓取失败：{exc}"

        if data is None or data.empty:
            return pd.DataFrame(), f"{symbol} 返回空数据"

        return self._normalize_index(data), None

    @staticmethod
    def _normalize_index(data: pd.DataFrame) -> pd.DataFrame:
        normalized = data.copy()
        normalized.index = pd.to_datetime(normalized.index).tz_localize(None).normalize()
        normalized = normalized[~normalized.index.duplicated(keep="last")]
        return normalized.sort_index()

    @staticmethod
    def _extract_column(data: pd.DataFrame, column_name: str) -> pd.Series:
        if data.empty:
            return pd.Series(dtype="float64")

        if isinstance(data.columns, pd.MultiIndex):
            if column_name not in data.columns.get_level_values(0):
                return pd.Series(dtype="float64")
            extracted = data[column_name]
            if isinstance(extracted, pd.DataFrame):
                extracted = extracted.iloc[:, 0]
        else:
            if column_name not in data.columns:
                return pd.Series(dtype="float64")
            extracted = data[column_name]

        return pd.to_numeric(extracted, errors="coerce").dropna()

    @staticmethod
    def _normalize_treasury_yield(series: pd.Series) -> pd.Series:
        median_value = series.dropna().median()
        if pd.notna(median_value) and median_value > 20:
            return series / 10
        return series
