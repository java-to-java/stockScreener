"""Build the earnings-pattern knowledge base from price history + result dates.

For every past earnings event of a symbol, this measures:

- the cumulative return in the ``PRE_WINDOW_DAYS`` trading days before it
- the single-day move on the result date itself
- the cumulative return in the ``POST_WINDOW_DAYS`` trading days after it
- the best/worst point reached in the ``FORWARD_DAYS`` trading days after it
  (relative to the close on the result date) - this is what calibrates the
  "expected high/low" band in predict.py

Those per-event numbers are then aggregated per symbol (mean/median/stdev/
win-rate) into ``data/knowledge_base.json``. Everything in this module is
pure computation over a price DataFrame + a list of dates, so it is fully
unit-testable with synthetic data (see tests/) without any network access.
"""
import json
import logging
import math
import statistics
import sys
from datetime import date, datetime

import pandas as pd

import config
from src.constituents import load_constituents

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def load_price_history(symbol: str) -> pd.DataFrame:
    path = config.PRICES_DIR / f"{symbol}.csv"
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def _first_trading_index_on_or_after(dates: pd.Series, target: date) -> int | None:
    ts = pd.Timestamp(target)
    matches = dates[dates >= ts]
    if matches.empty:
        return None
    return matches.index[0]


def compute_event_stats(
    prices: pd.DataFrame,
    result_date: date,
    pre_window: int = config.PRE_WINDOW_DAYS,
    post_window: int = config.POST_WINDOW_DAYS,
    forward_days: int = config.FORWARD_DAYS,
) -> dict | None:
    """Stats for a single historical earnings event, or None if there isn't
    enough surrounding price history in ``prices`` to compute the full window
    (e.g. the event is too close to the start/end of the available data).
    """
    dates = prices["Date"]
    t0 = _first_trading_index_on_or_after(dates, result_date)
    if t0 is None:
        return None
    if t0 - pre_window < 0 or t0 + forward_days >= len(prices):
        return None

    close = prices["Close"]
    high = prices["High"]
    low = prices["Low"]

    pre_start_close = close.iloc[t0 - pre_window]
    pre_end_close = close.iloc[t0 - 1] if t0 - 1 >= 0 else close.iloc[t0]
    prev_close = close.iloc[t0 - 1] if t0 - 1 >= 0 else close.iloc[t0]
    t0_close = close.iloc[t0]

    post_end_idx = min(t0 + post_window, len(prices) - 1)
    post_end_close = close.iloc[post_end_idx]

    forward_high_slice = high.iloc[t0 + 1 : t0 + 1 + forward_days]
    forward_low_slice = low.iloc[t0 + 1 : t0 + 1 + forward_days]

    def pct(a, b):
        return float((a - b) / b * 100.0) if b else 0.0

    return {
        "result_date": result_date.isoformat(),
        "trading_date": dates.iloc[t0].date().isoformat(),
        "pre_return_pct": pct(pre_end_close, pre_start_close),
        "day0_return_pct": pct(t0_close, prev_close),
        "post_return_pct": pct(post_end_close, t0_close),
        "forward_high_pct": pct(forward_high_slice.max(), t0_close),
        "forward_low_pct": pct(forward_low_slice.min(), t0_close),
    }


def _series_stats(values: list[float]) -> dict:
    if not values:
        return {"avg": None, "median": None, "stdev": None, "win_rate": None}
    avg = statistics.fmean(values)
    median = statistics.median(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    win_rate = sum(1 for v in values if v > 0) / len(values)
    return {
        "avg": round(avg, 3),
        "median": round(median, 3),
        "stdev": round(stdev, 3),
        "win_rate": round(win_rate, 3),
    }


def aggregate_symbol_stats(events: list[dict]) -> dict:
    """Roll up per-event stats for one symbol into summary statistics."""
    return {
        "sample_size": len(events),
        "pre_earnings": _series_stats([e["pre_return_pct"] for e in events]),
        "day0": _series_stats([e["day0_return_pct"] for e in events]),
        "post_earnings": _series_stats([e["post_return_pct"] for e in events]),
        "forward_high": _series_stats([e["forward_high_pct"] for e in events]),
        "forward_low": _series_stats([e["forward_low_pct"] for e in events]),
        "events": events,
    }


def compute_generic_volatility(prices: pd.DataFrame, forward_days: int = config.FORWARD_DAYS) -> dict:
    """Non-earnings-specific volatility, used as a fallback when a symbol has
    too few historical earnings events to trust the earnings-specific stats.
    """
    daily_returns = prices["Close"].pct_change().dropna()
    if daily_returns.empty:
        return {"daily_stdev_pct": None, "forward_window_stdev_pct": None}
    daily_stdev_pct = float(daily_returns.std()) * 100.0
    return {
        "daily_stdev_pct": round(daily_stdev_pct, 3),
        "forward_window_stdev_pct": round(daily_stdev_pct * math.sqrt(forward_days), 3),
    }


def build_knowledge_base(earnings_history: list[dict]) -> dict:
    by_symbol: dict[str, list[dict]] = {}
    for entry in earnings_history:
        by_symbol.setdefault(entry["symbol"], []).append(entry)

    knowledge_base = {}
    for c in load_constituents():
        try:
            prices = load_price_history(c.symbol)
        except FileNotFoundError:
            log.warning("No price history for %s - run fetch_price_history first. Skipping.", c.symbol)
            continue

        result_dates = [
            datetime.fromisoformat(e["result_date"]).date()
            for e in by_symbol.get(c.symbol, [])
        ]
        events = []
        for rd in result_dates:
            stats = compute_event_stats(prices, rd)
            if stats:
                events.append(stats)

        entry = aggregate_symbol_stats(events)
        entry["symbol"] = c.symbol
        entry["name"] = c.name
        entry["reliable"] = entry["sample_size"] >= config.MIN_SAMPLE_SIZE
        entry["generic_volatility"] = compute_generic_volatility(prices)
        entry["last_close"] = float(prices["Close"].iloc[-1])
        entry["last_close_date"] = prices["Date"].iloc[-1].date().isoformat()
        knowledge_base[c.symbol] = entry

    return knowledge_base


def main() -> int:
    if not config.EARNINGS_HISTORY_FILE.exists():
        log.error(
            "%s not found - run fetch_earnings_calendar first.",
            config.EARNINGS_HISTORY_FILE,
        )
        return 1

    earnings_history = json.loads(config.EARNINGS_HISTORY_FILE.read_text())
    kb = build_knowledge_base(earnings_history)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.KNOWLEDGE_BASE_FILE.write_text(json.dumps(kb, indent=2))

    reliable = sum(1 for v in kb.values() if v["reliable"])
    log.info(
        "Built knowledge base for %d symbols (%d with >= %d historical events).",
        len(kb),
        reliable,
        config.MIN_SAMPLE_SIZE,
    )
    return 0 if kb else 1


if __name__ == "__main__":
    sys.exit(main())
