"""Fetch daily OHLCV price history for every Nifty50 constituent via Yahoo Finance.

Writes one CSV per symbol to ``data/prices/<SYMBOL>.csv`` with columns
Date, Open, High, Low, Close, Volume. ``knowledge_base.py`` and ``predict.py``
read these back in.

Run from the repo root:

    python -m src.fetch_price_history

Requires the ``yfinance`` package and real internet access to Yahoo Finance
(blocked by this project's own sandbox network policy at dev time - see
README - but expected to work in a normal environment or CI).
"""
import logging
import sys
import time

import config
from src.constituents import load_constituents

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def fetch_one(ticker: str):
    import yfinance as yf

    hist = yf.Ticker(ticker).history(
        period=f"{config.LOOKBACK_YEARS}y", interval="1d", auto_adjust=False
    )
    if hist.empty:
        raise ValueError(f"No price data returned for {ticker}")
    hist = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
    hist.index.name = "Date"
    return hist


def main() -> int:
    try:
        import yfinance  # noqa: F401
    except ImportError:
        log.error(
            "yfinance is not installed. Run: pip install -r requirements.txt"
        )
        return 1

    constituents = load_constituents()
    config.PRICES_DIR.mkdir(parents=True, exist_ok=True)

    ok, failed = 0, []
    for c in constituents:
        try:
            hist = fetch_one(c.yf_ticker)
            hist.to_csv(config.PRICES_DIR / f"{c.symbol}.csv")
            ok += 1
        except Exception as exc:  # noqa: BLE001 - continue past single-symbol failures
            failed.append(c.symbol)
            log.warning("Failed to fetch price history for %s: %s", c.symbol, exc)
        time.sleep(config.REQUEST_DELAY_SECONDS)

    log.info("Fetched price history for %d/%d symbols.", ok, len(constituents))
    if failed:
        log.warning("Failed symbols: %s", ", ".join(failed))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
