from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
HISTORY_CSV = DATA_DIR / "history.csv"
DAILY_REPORT = REPORTS_DIR / "daily_report.md"
EMAIL_SUMMARY = REPORTS_DIR / "email_summary.md"

HISTORY_LOOKBACK_DAYS = 45
OIL_SIGNIFICANT_MOVE_PCT = 2.0

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
SPDR_GLD_ARCHIVE_URL = (
    "https://api.spdrgoldshares.com/api/v1/historical-archive"
    "?exchange=NYSE&lang=en&product=gld"
)

OFFICIAL_SERIES = {
    "gold_price": {
        "name": "GLD官方收盘价",
        "source": "SPDR Gold Shares Historical Archive",
        "unit": "USD",
    },
    "us10y_yield": {
        "name": "美国10年期国债收益率",
        "source": "FRED DGS10 / Federal Reserve H.15",
        "fred_id": "DGS10",
        "unit": "%",
    },
    "dxy": {
        "name": "美联储广义美元指数",
        "source": "FRED DTWEXBGS / Federal Reserve H.10",
        "fred_id": "DTWEXBGS",
        "unit": "",
    },
    "oil_price": {
        "name": "WTI原油现货价格",
        "source": "FRED DCOILWTICO / U.S. EIA",
        "fred_id": "DCOILWTICO",
        "unit": "USD",
    },
}

REPORT_TITLE = "黄金宏观监控日报"
