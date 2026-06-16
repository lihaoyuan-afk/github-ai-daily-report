from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
HISTORY_CSV = DATA_DIR / "history.csv"
DAILY_REPORT = REPORTS_DIR / "daily_report.md"
EMAIL_SUMMARY = REPORTS_DIR / "email_summary.md"

HISTORY_LOOKBACK_DAYS = 45
OIL_SIGNIFICANT_MOVE_PCT = 2.0

MARKET_SYMBOLS = {
    "gold_price": {
        "name": "黄金价格",
        "symbols": ["XAUUSD=X", "GC=F", "GLD"],
        "unit": "USD",
    },
    "us10y_yield": {
        "name": "美国10年期国债收益率",
        "symbols": ["^TNX"],
        "unit": "%",
    },
    "dxy": {
        "name": "美元指数",
        "symbols": ["DX-Y.NYB", "DX=F", "UUP"],
        "unit": "",
    },
    "oil_price": {
        "name": "原油价格",
        "symbols": ["CL=F", "BZ=F"],
        "unit": "USD",
    },
}

ETF_SYMBOL = "GLD"

REPORT_TITLE = "黄金宏观监控日报"
