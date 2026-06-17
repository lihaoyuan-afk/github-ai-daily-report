from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import zipfile

import pandas as pd
import requests

from config import (
    CFTC_DISAGG_YEAR_URL,
    CFTC_GOLD_CONTRACT_CODE,
    CFTC_YEARS_BACK,
    FRED_CSV_URL,
    FRED_SERIES,
    HISTORY_LOOKBACK_DAYS,
    SPDR_GLD_ARCHIVE_URL,
)


@dataclass
class FetchOutcome:
    data: pd.DataFrame
    errors: list[str]


class MacroDataFetcher:
    """Fetches official public data for the gold crash-risk radar."""

    def __init__(self, lookback_days: int = HISTORY_LOOKBACK_DAYS) -> None:
        self.lookback_days = lookback_days

    def fetch_recent_history(self) -> FetchOutcome:
        errors: list[str] = []
        frames: list[pd.DataFrame] = []

        spdr_frame, spdr_errors = self._fetch_spdr_gld_archive()
        errors.extend(spdr_errors)
        if not spdr_frame.empty:
            frames.append(spdr_frame)

        fred_frame, fred_errors = self._fetch_fred_series()
        errors.extend(fred_errors)
        if not fred_frame.empty:
            frames.append(fred_frame)

        cftc_frame, cftc_errors = self._fetch_cftc_gold_managed_money()
        errors.extend(cftc_errors)
        if not cftc_frame.empty:
            frames.append(cftc_frame)

        if not frames:
            return FetchOutcome(data=pd.DataFrame(), errors=errors)

        combined = pd.concat(frames, axis=1).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.ffill().tail(self.lookback_days)
        combined.index.name = "date"
        combined = combined.reset_index()
        combined["date"] = pd.to_datetime(combined["date"]).dt.date.astype(str)
        return FetchOutcome(data=combined, errors=errors)

    def _fetch_fred_series(self) -> tuple[pd.DataFrame, list[str]]:
        frames: list[pd.DataFrame] = []
        errors: list[str] = []

        for metric_key, config in FRED_SERIES.items():
            series_id = config["fred_id"]
            url = FRED_CSV_URL.format(series_id=series_id)
            try:
                raw = pd.read_csv(url)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{metric_key}: FRED {series_id} 抓取失败：{exc}")
                continue

            if "observation_date" not in raw.columns or series_id not in raw.columns:
                errors.append(f"{metric_key}: FRED {series_id} 返回字段异常")
                continue

            raw["date"] = pd.to_datetime(raw["observation_date"], errors="coerce")
            raw[metric_key] = pd.to_numeric(raw[series_id], errors="coerce")
            raw = raw.dropna(subset=["date", metric_key]).sort_values("date")
            if raw.empty:
                errors.append(f"{metric_key}: FRED {series_id} 无可用数据")
                continue

            frame = raw[["date", metric_key]].set_index("date").tail(self.lookback_days)
            frame[f"{metric_key}_source"] = config["source"]
            frame[f"{metric_key}_source_date"] = frame.index.date.astype(str)
            frames.append(frame)

        if not frames:
            return pd.DataFrame(), errors

        return pd.concat(frames, axis=1).sort_index(), errors

    def _fetch_spdr_gld_archive(self) -> tuple[pd.DataFrame, list[str]]:
        headers = {
            "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "User-Agent": "GoldHunter/2.0 (+https://github.com/lihaoyuan-afk/github-ai-daily-report)",
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
        except Exception as exc:  # noqa: BLE001
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

        frame = raw.set_index("date").tail(self.lookback_days)
        result = pd.DataFrame(
            {
                "gold_price": frame["Closing Price"],
                "gld_close": frame["Closing Price"],
                "gld_volume": frame["Daily Share Volume"],
                "gld_tonnes": frame["Tonnes of Gold"],
                "gld_total_ounces": frame["Total Ounces of Gold in the Trust"],
            },
            index=frame.index,
        )
        result["gld_tonnes_change"] = result["gld_tonnes"].diff()
        result["gold_price_source"] = "SPDR Gold Shares Historical Archive"
        result["gold_price_source_date"] = result.index.date.astype(str)
        result["gld_tonnes_source"] = "SPDR Gold Shares Historical Archive"
        result["gld_tonnes_source_date"] = result.index.date.astype(str)
        return result, []

    def _fetch_cftc_gold_managed_money(self) -> tuple[pd.DataFrame, list[str]]:
        current_year = datetime.utcnow().year
        years = range(current_year - CFTC_YEARS_BACK, current_year + 1)
        rows: list[pd.DataFrame] = []
        errors: list[str] = []

        for year in years:
            url = CFTC_DISAGG_YEAR_URL.format(year=year)
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                with zipfile.ZipFile(BytesIO(response.content)) as archive:
                    name = archive.namelist()[0]
                    with archive.open(name) as handle:
                        raw = pd.read_csv(handle, low_memory=False)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"cftc_gold: {year} 年 CFTC 数据抓取失败：{exc}")
                continue

            gold = raw[raw["CFTC_Contract_Market_Code"].astype(str).str.zfill(6) == CFTC_GOLD_CONTRACT_CODE].copy()
            if gold.empty:
                gold = raw[raw["Market_and_Exchange_Names"].astype(str).str.contains("GOLD - COMMODITY EXCHANGE", case=False, na=False)].copy()
            if gold.empty:
                errors.append(f"cftc_gold: {year} 年未找到 COMEX Gold 合约")
                continue
            rows.append(gold)

        if not rows:
            return pd.DataFrame(), errors

        combined = pd.concat(rows, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["Report_Date_as_YYYY-MM-DD"], errors="coerce")
        numeric_columns = [
            "M_Money_Positions_Long_All",
            "M_Money_Positions_Short_All",
            "Open_Interest_All",
        ]
        for column in numeric_columns:
            combined[column] = pd.to_numeric(combined[column], errors="coerce")
        combined = combined.dropna(subset=["date"]).sort_values("date")
        combined = combined.drop_duplicates("date", keep="last")
        if combined.empty:
            return pd.DataFrame(), errors

        result = pd.DataFrame(index=combined["date"])
        result["cftc_mm_long"] = combined["M_Money_Positions_Long_All"].to_numpy()
        result["cftc_mm_short"] = combined["M_Money_Positions_Short_All"].to_numpy()
        result["cftc_open_interest"] = combined["Open_Interest_All"].to_numpy()
        result["cftc_mm_net_long"] = result["cftc_mm_long"] - result["cftc_mm_short"]
        result["cftc_mm_net_long_ratio"] = result["cftc_mm_net_long"] / result["cftc_open_interest"]
        result["cftc_source"] = "CFTC Disaggregated Futures Only, COMEX Gold"
        result["cftc_source_date"] = result.index.date.astype(str)
        return result.tail(self.lookback_days), errors
