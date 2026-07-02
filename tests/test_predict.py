from datetime import date

import pytest

from src.predict import build_predictions, classify_direction, confidence_label, expected_band


def test_classify_direction_thresholds():
    assert classify_direction({"win_rate": 0.75}) == ("Bullish", 0.75)
    assert classify_direction({"win_rate": 0.6}) == ("Bullish", 0.6)
    assert classify_direction({"win_rate": 0.25}) == ("Bearish", 0.25)
    assert classify_direction({"win_rate": 0.4}) == ("Bearish", 0.4)
    assert classify_direction({"win_rate": 0.5}) == ("Neutral", 0.5)
    assert classify_direction({"win_rate": None}) == ("Unknown", None)


def test_confidence_label_low_for_coin_flip_or_no_data():
    assert confidence_label(sample_size=10, win_rate=0.5) == "Low"
    assert confidence_label(sample_size=0, win_rate=None) == "Low"


def test_confidence_label_high_needs_both_sample_size_and_lopsidedness():
    # Strong lopsidedness but tiny sample -> not High.
    assert confidence_label(sample_size=1, win_rate=1.0) != "High"
    # Strong lopsidedness with enough events -> High.
    assert confidence_label(sample_size=8, win_rate=0.875) == "High"


def _kb_entry(reliable, last_close=100.0, forward_high_avg=5.0, forward_low_avg=-3.0, vol=None):
    return {
        "reliable": reliable,
        "last_close": last_close,
        "forward_high": {"avg": forward_high_avg},
        "forward_low": {"avg": forward_low_avg},
        "generic_volatility": {"forward_window_stdev_pct": vol},
    }


def test_expected_band_uses_earnings_history_when_reliable():
    entry = _kb_entry(reliable=True, last_close=100.0, forward_high_avg=5.0, forward_low_avg=-3.0)
    band = expected_band(entry)
    assert band["band_basis"] == "earnings_history"
    assert band["expected_high"] == pytest.approx(105.0)
    assert band["expected_low"] == pytest.approx(97.0)


def test_expected_band_falls_back_to_generic_volatility_when_not_reliable():
    entry = _kb_entry(reliable=False, last_close=200.0, vol=4.0)
    band = expected_band(entry)
    assert band["band_basis"] == "generic_volatility"
    assert band["expected_high"] == pytest.approx(208.0)
    assert band["expected_low"] == pytest.approx(192.0)


def test_expected_band_none_when_no_data_available():
    entry = _kb_entry(reliable=False, vol=None)
    band = expected_band(entry)
    assert band["expected_high"] is None
    assert band["expected_low"] is None


def _full_kb_entry(symbol, win_rate=0.7, sample_size=6, reliable=True):
    return {
        "symbol": symbol,
        "name": f"{symbol} Ltd",
        "sample_size": sample_size,
        "reliable": reliable,
        "last_close": 100.0,
        "last_close_date": "2026-06-30",
        "pre_earnings": {"avg": 1.0},
        "day0": {"avg": 2.0},
        "post_earnings": {"win_rate": win_rate, "avg": 3.0},
        "forward_high": {"avg": 5.0},
        "forward_low": {"avg": -3.0},
        "generic_volatility": {"forward_window_stdev_pct": 4.0},
    }


def test_build_predictions_filters_by_lookahead_window_and_sorts():
    today = date(2026, 7, 2)
    knowledge_base = {
        "NEAR": _full_kb_entry("NEAR"),
        "LATER": _full_kb_entry("LATER"),
        "TOOFAR": _full_kb_entry("TOOFAR"),
        "PAST": _full_kb_entry("PAST"),
        "NODATA": _full_kb_entry("NODATA"),
    }
    upcoming = [
        {"symbol": "LATER", "expected_date": "2026-07-20"},
        {"symbol": "NEAR", "expected_date": "2026-07-05"},
        {"symbol": "TOOFAR", "expected_date": "2026-09-01"},  # beyond 30-day lookahead
        {"symbol": "PAST", "expected_date": "2026-06-01"},    # already happened
        {"symbol": "UNKNOWN_SYMBOL", "expected_date": "2026-07-10"},  # not in KB
    ]

    predictions = build_predictions(knowledge_base, upcoming, today=today)

    symbols = [p["symbol"] for p in predictions]
    assert symbols == ["NEAR", "LATER"]  # sorted by date, out-of-window/unknown excluded
    assert predictions[0]["direction"] == "Bullish"
    assert predictions[0]["days_to_result"] == 3
    assert predictions[0]["expected_low"] == pytest.approx(97.0)
    assert predictions[0]["expected_high"] == pytest.approx(105.0)
