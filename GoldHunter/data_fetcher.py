from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pandas as pd
import requests

from config import FRED_CSV_URL, HISTORY_LOOKBACK_DAYS, OFFICIAL_SERIES, SPDR_GLD_ARCHIVE_URL


@dataclass
class FetchOutcome:
    data: pd.DataFrame
    errors: list[str]


class MacroDataFetcher:
    """Fetches official or near-official public datasets for the gold macro report."""

    def __init__(self, lookback_days: int = HISTORY_LOOKBACK_DAYS) -> None:
        self.lookback_days = lookback_days

    def fetch_recent_history(self) -> FetchOutcome:
        errors: list[str] = []
        frames: list[pd.DataFrame] = []

        spdr_frame, spdr_errors = self._fetch_spdr_gld_archive()
        errors.extend(spdr_errors)
        if not spdr_frame.empty:
            frames.append(spdr_frame)

        for metric_key in ["us10y_yield", "dxy", "oil_price"]:
            frame, metric_errors = self._fetch_fred_metric(metric_key)
            errors.extend(metric_errors)
            if not frame.empty:
                frames.append(frame)

        if not frames:
            return FetchOutcome(data=pd.DataFrame(), errors=errors)

        combined = pd.concat(frames, axis=1).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.ffill()
        combined = combined.tail(self.lookback_days)
        combined.index.name = "date"
        combined = combined.reset_index()
        combined["date"] = pd.to_datetime(combined["date"]).dt.date.astype(str)
        return FetchOutcome(data=combined, errors=errors)

    def _fetch_fred_metric(self, metric_key: str) -> tuple[pd.DataFrame, list[str]]:
        config = OFFICIAL_SERIES[metric_key]
        series_id = config["fred_id"]
        url = FRED_CSV_URL.format(series_id=series_id)

        try:
            raw = pd.read_csv(url)
        except Exception as exc:  # noqa: BLE001 - network/data source failures should not crash.
            return pd.DataFrame(), [f"{metric_key}: FRED {series_id} 抓取失败：{exc}"]

        if "observation_date" not in raw.columns or series_id not in raw.columns:
            return pd.DataFrame(), [f"{metric_key}: FRED {series_id} 返回字段异常"]

        raw["date"] = pd.to_datetime(raw["observation_date"], errors="coerce")
        raw[metric_key] = pd.to_numeric(raw[series_id], errors="coerce")
        raw = raw.dropna(subset=["date", metric_key]).sort_values("date")

        if raw.empty:
            return pd.DataFrame(), [f"{metric_key}: FRED {series_id} 无可用数据"]

        frame = raw[["date", metric_key]].set_index("date").tail(self.lookback_days)
        frame[f"{metric_key}_source"] = config["source"]
        frame[f"{metric_key}_source_date"] = frame.index.date.astype(str)
        return frame, []

    def _fetch_spdr_gld_archive(self) -> tuple[pd.DataFrame, list[str]]:
        headers = {
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "User-Agent": "GoldHunter/1.0 (+https://github.com/lihaoyuan-afk/github-ai-daily-report)",
        }

        try:
            response = requests.get(SPDR_GLD_ARCHIVE_URL, headers=headers, timeout=30)
            response.raise_for_status()
            raw = pd.read_excel(
                BytesIO(response.content),
                sheet_name="US GLD Historical Archive",
                usecols=[
                    "Date",
                    "Closing Price",
                    "Daily Share Volume",
                    "Tonnes of Gold",
                    "Total Ounces of Gold in the Trust",
                ],
            )
        except Exception as exc:  # noqa: BLE001 - keep report generation alive.
            return pd.DataFrame(), [f"spdr_gld_archive: SPDR官方档案抓取失败：{exc}"]

        raw["date"] = pd.to_datetime(raw["Date"], errors="coerce")
        for column in [
            "Closing Price",
            "Daily Share Volume",
            "Tonnes of Gold",
            "Total Ounces of Gold in the Trust",
        ]:
            raw[column] = pd.to_numeric(raw[column], errors="coerce")

        raw = raw.dropna(subset=["date", "Closing Price"]).sort_values("date")
        if raw.empty:
            return pd.DataFrame(), ["spdr_gld_archive: SPDR官方档案无可用数据"]

        raw["gold_etf_flow_proxy"] = raw["Tonnes of Gold"].diff()
        frame = raw.set_index("date").tail(self.lookback_days)
        result = pd.DataFrame(
            {
                "gold_price": frame["Closing Price"],
                "gld_close": frame["Closing Price"],
                "gld_volume": frame["Daily Share Volume"],
                "gld_tonnes": frame["Tonnes of Gold"],
                "gld_total_ounces": frame["Total Ounces of Gold in the Trust"],
                "gold_etf_flow_proxy": frame["gold_etf_flow_proxy"],
            },
            index=frame.index,
        )
        result["gold_price_source"] = OFFICIAL_SERIES["gold_price"]["source"]
        result["gold_price_source_date"] = result.index.date.astype(str)
        result["gold_etf_source"] = "SPDR Gold Shares Historical Archive"
        result["gold_etf_source_date"] = result.index.date.astype(str)
        return result, []
