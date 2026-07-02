"""Central, tunable configuration for the Nifty50 earnings tracker pipeline.

Every stage (fetch -> knowledge base -> predict -> dashboard) reads its
parameters from here so the whole pipeline can be re-tuned in one place.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
PRICES_DIR = DATA_DIR / "prices"
DOCS_DIR = ROOT_DIR / "docs"  # dashboard output (GitHub Pages serves /docs)

CONSTITUENTS_FILE = DATA_DIR / "nifty50_constituents.json"
EARNINGS_HISTORY_FILE = DATA_DIR / "earnings_history.json"
EARNINGS_UPCOMING_FILE = DATA_DIR / "earnings_upcoming.json"
KNOWLEDGE_BASE_FILE = DATA_DIR / "knowledge_base.json"
PREDICTIONS_FILE = DATA_DIR / "predictions.json"
DASHBOARD_OUTPUT_FILE = DOCS_DIR / "index.html"
DASHBOARD_TEMPLATE_FILE = ROOT_DIR / "src" / "templates" / "dashboard_template.html"

# ---------------------------------------------------------------------------
# Earnings-window analysis (the "knowledge base")
# ---------------------------------------------------------------------------
# Trading-day window sizes used to characterize the pattern around a result date.
PRE_WINDOW_DAYS = 7    # trading days before the result date
POST_WINDOW_DAYS = 7   # trading days after the result date
FORWARD_DAYS = 15      # trading days used for the "expected high/low" projection

# How far back to look for historical result dates when building the knowledge base.
LOOKBACK_QUARTERS = 8  # ~2 years of quarterly results
LOOKBACK_YEARS = 3     # price history fetch window (must cover lookback quarters + buffer)

# A symbol needs at least this many past earnings events before its stats are
# considered reliable enough to drive a prediction (vs. a generic volatility fallback).
MIN_SAMPLE_SIZE = 4

# ---------------------------------------------------------------------------
# Prediction thresholds
# ---------------------------------------------------------------------------
# Only surface upcoming earnings within this many calendar days.
PREDICTION_LOOKAHEAD_DAYS = 30

# Post-earnings 7-day win-rate thresholds used to classify direction.
BULLISH_WIN_RATE = 0.60
BEARISH_WIN_RATE = 0.40

# ---------------------------------------------------------------------------
# Networking (NSE scraping is fragile; be polite and resilient)
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT_SECONDS = 15
REQUEST_RETRIES = 3
REQUEST_RETRY_BACKOFF_SECONDS = 2.0
REQUEST_DELAY_SECONDS = 1.0  # min delay between consecutive requests to one host

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

NSE_BASE_URL = "https://www.nseindia.com"
NSE_ARCHIVES_NIFTY50_CSV = (
    "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
)
