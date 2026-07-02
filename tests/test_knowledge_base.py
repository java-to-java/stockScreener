from datetime import date

import pandas as pd
import pytest

from src.knowledge_base import (
    aggregate_symbol_stats,
    compute_event_stats,
    compute_generic_volatility,
)


def make_prices(closes, start="2024-01-01"):
    dates = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": [1000] * len(closes),
        }
    )


def test_compute_event_stats_measures_day0_jump():
    closes = [100.0] * 30 + [110.0] * 30  # +10% jump on the result date
    prices = make_prices(closes)
    result_date = prices["Date"].iloc[30].date()

    stats = compute_event_stats(prices, result_date, pre_window=7, post_window=7, forward_days=15)

    assert stats is not None
    assert stats["day0_return_pct"] == pytest.approx(10.0, abs=0.01)
    # Flat before the jump -> no pre-earnings drift.
    assert stats["pre_return_pct"] == pytest.approx(0.0, abs=0.01)
    # Flat after the jump -> no further post-earnings drift.
    assert stats["post_return_pct"] == pytest.approx(0.0, abs=0.01)
    # High/low bands are within the +/-1% intraday range used in the fixture.
    assert stats["forward_high_pct"] == pytest.approx(1.0, abs=0.01)
    assert stats["forward_low_pct"] == pytest.approx(-1.0, abs=0.01)


def test_compute_event_stats_returns_none_when_too_close_to_start():
    closes = [100.0] * 60
    prices = make_prices(closes)
    # Only 3 trading days of history before this date - less than pre_window=7.
    result_date = prices["Date"].iloc[3].date()

    assert compute_event_stats(prices, result_date, pre_window=7, post_window=7, forward_days=15) is None


def test_compute_event_stats_returns_none_when_too_close_to_end():
    closes = [100.0] * 60
    prices = make_prices(closes)
    # Only a few trading days left after this date - less than forward_days=15.
    result_date = prices["Date"].iloc[55].date()

    assert compute_event_stats(prices, result_date, pre_window=7, post_window=7, forward_days=15) is None


def test_compute_event_stats_returns_none_for_date_outside_history():
    closes = [100.0] * 60
    prices = make_prices(closes)
    assert compute_event_stats(prices, date(2099, 1, 1)) is None


def test_aggregate_symbol_stats_win_rate_and_avg():
    events = [
        {"pre_return_pct": 1.0, "day0_return_pct": 5.0, "post_return_pct": 2.0, "forward_high_pct": 6.0, "forward_low_pct": -1.0},
        {"pre_return_pct": -1.0, "day0_return_pct": -3.0, "post_return_pct": -1.0, "forward_high_pct": 2.0, "forward_low_pct": -4.0},
        {"pre_return_pct": 2.0, "day0_return_pct": 4.0, "post_return_pct": 3.0, "forward_high_pct": 7.0, "forward_low_pct": -0.5},
    ]
    agg = aggregate_symbol_stats(events)

    assert agg["sample_size"] == 3
    # 2 of 3 post-earnings moves are positive.
    assert agg["post_earnings"]["win_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert agg["post_earnings"]["avg"] == pytest.approx((2.0 - 1.0 + 3.0) / 3, abs=1e-3)


def test_aggregate_symbol_stats_handles_no_events():
    agg = aggregate_symbol_stats([])
    assert agg["sample_size"] == 0
    assert agg["post_earnings"]["win_rate"] is None


def test_compute_generic_volatility_scales_with_sqrt_of_window():
    # Alternating +1%/-1% daily returns has a known, non-zero stdev.
    closes = [100.0]
    for i in range(40):
        closes.append(closes[-1] * (1.01 if i % 2 == 0 else 1 / 1.01))
    prices = make_prices(closes)

    vol = compute_generic_volatility(prices, forward_days=15)

    assert vol["daily_stdev_pct"] > 0
    assert vol["forward_window_stdev_pct"] == pytest.approx(
        vol["daily_stdev_pct"] * (15 ** 0.5), rel=1e-3
    )
