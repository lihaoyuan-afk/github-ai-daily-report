from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
HISTORY_CSV = DATA_DIR / "history.csv"
DAILY_REPORT = REPORTS_DIR / "daily_report.md"
EMAIL_SUMMARY = REPORTS_DIR / "email_summary.md"

HISTORY_LOOKBACK_DAYS = 430
REPORT_TITLE = "黄金大跌风险日报"

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
SPDR_GLD_ARCHIVE_URL = (
    "https://api.spdrgoldshares.com/api/v1/historical-archive"
    "?exchange=NYSE&lang=en&product=gld"
)
CFTC_DISAGG_YEAR_URL = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
CFTC_GOLD_CONTRACT_CODE = "088691"
CFTC_YEARS_BACK = 5

FRED_SERIES = {
    "real_yield_10y": {
        "fred_id": "DFII10",
        "name": "10年实际利率",
        "source": "FRED DFII10 / Federal Reserve",
        "unit": "%",
    },
    "us2y_yield": {
        "fred_id": "DGS2",
        "name": "2年美债收益率",
        "source": "FRED DGS2 / Federal Reserve H.15",
        "unit": "%",
    },
    "us10y_yield": {
        "fred_id": "DGS10",
        "name": "10年美债收益率",
        "source": "FRED DGS10 / Federal Reserve H.15",
        "unit": "%",
    },
    "dollar_index": {
        "fred_id": "DTWEXBGS",
        "name": "美联储广义美元指数",
        "source": "FRED DTWEXBGS / Federal Reserve H.10",
        "unit": "",
    },
    "hy_oas": {
        "fred_id": "BAMLH0A0HYM2",
        "name": "美国高收益债利差",
        "source": "FRED BAMLH0A0HYM2 / ICE BofA",
        "unit": "%",
    },
    "vix": {
        "fred_id": "VIXCLS",
        "name": "VIX",
        "source": "FRED VIXCLS / CBOE",
        "unit": "",
    },
    "nfci": {
        "fred_id": "NFCI",
        "name": "芝加哥联储金融条件指数",
        "source": "FRED NFCI / Federal Reserve Bank of Chicago",
        "unit": "",
    },
    "sofr": {
        "fred_id": "SOFR",
        "name": "SOFR",
        "source": "FRED SOFR / Federal Reserve Bank of New York",
        "unit": "%",
    },
    "iorb": {
        "fred_id": "IORB",
        "name": "IORB",
        "source": "FRED IORB / Federal Reserve",
        "unit": "%",
    },
    "reserves": {
        "fred_id": "WRESBAL",
        "name": "美联储银行准备金",
        "source": "FRED WRESBAL / Federal Reserve",
        "unit": "USD bn",
    },
}

MODULE_WEIGHTS = {
    "rates_and_usd": 0.30,
    "price_structure": 0.25,
    "etf_flows": 0.15,
    "cot_positioning": 0.15,
    "liquidity_stress": 0.10,
    "event_risk": 0.05,
}

RISK_THRESHOLDS = {
    "green_max": 30,
    "yellow_max": 55,
    "orange_max": 75,
}
