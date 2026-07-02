"""Rank upcoming Nifty50 earnings by likely price-move direction and project
a 15-trading-day expected high/low band from the current price.

This is a statistical summary of *how the stock has behaved around its own
past results* - not a forecast of this quarter's numbers, not a model of
news/estimate revisions, and not investment advice. See README's
Limitations section before using this for anything real. Direction is
derived from the historical post-earnings 7-day win-rate; the expected band
is derived from the historical forward-15-day high/low distribution (or a
generic volatility fallback when a symbol has too little earnings history).

Run from the repo root:

    python -m src.predict
"""
import json
import logging
import sys
from datetime import date, datetime, timedelta

import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def classify_direction(post_earnings_stats: dict) -> tuple[str, float | None]:
    """Direction label from the historical post-earnings win-rate."""
    win_rate = post_earnings_stats.get("win_rate")
    if win_rate is None:
        return "Unknown", None
    if win_rate >= config.BULLISH_WIN_RATE:
        return "Bullish", win_rate
    if win_rate <= config.BEARISH_WIN_RATE:
        return "Bearish", win_rate
    return "Neutral", win_rate


def confidence_label(sample_size: int, win_rate: float | None) -> str:
    """How much weight the direction call deserves, from sample size + how
    lopsided the historical win-rate is (50/50 is no signal regardless of
    sample size).
    """
    if win_rate is None or sample_size == 0:
        return "Low"
    strength = abs(win_rate - 0.5) * 2  # 0 (coin flip) .. 1 (always same way)
    size_factor = min(sample_size / (config.MIN_SAMPLE_SIZE * 2), 1.0)
    score = strength * size_factor
    if score >= 0.5 and sample_size >= config.MIN_SAMPLE_SIZE:
        return "High"
    if score >= 0.25:
        return "Medium"
    return "Low"


def expected_band(kb_entry: dict) -> dict:
    """Expected 15-trading-day high/low band around the last close.

    Uses the earnings-specific forward_high/forward_low distribution when
    the symbol has >= MIN_SAMPLE_SIZE historical events; otherwise falls
    back to a symmetric band from the symbol's generic (non-earnings)
    volatility so every upcoming stock still gets a number, clearly flagged
    via ``band_basis``.
    """
    last_close = kb_entry["last_close"]

    if kb_entry["reliable"]:
        high_pct = kb_entry["forward_high"]["avg"]
        low_pct = kb_entry["forward_low"]["avg"]
        basis = "earnings_history"
    else:
        vol_pct = kb_entry["generic_volatility"]["forward_window_stdev_pct"]
        high_pct = vol_pct
        low_pct = -vol_pct if vol_pct is not None else None
        basis = "generic_volatility"

    if high_pct is None or low_pct is None:
        return {"expected_low": None, "expected_high": None, "band_basis": basis}

    return {
        "expected_low": round(last_close * (1 + low_pct / 100.0), 2),
        "expected_high": round(last_close * (1 + high_pct / 100.0), 2),
        "band_basis": basis,
    }


def build_predictions(
    knowledge_base: dict,
    upcoming: list[dict],
    today: date | None = None,
) -> list[dict]:
    today = today or datetime.now().date()
    horizon = today + timedelta(days=config.PREDICTION_LOOKAHEAD_DAYS)

    predictions = []
    for entry in upcoming:
        symbol = entry["symbol"]
        kb_entry = knowledge_base.get(symbol)
        if not kb_entry:
            continue

        expected_date = datetime.fromisoformat(entry["expected_date"]).date()
        if not (today <= expected_date <= horizon):
            continue

        direction, win_rate = classify_direction(kb_entry["post_earnings"])
        confidence = confidence_label(kb_entry["sample_size"], win_rate)
        band = expected_band(kb_entry)

        predictions.append(
            {
                "symbol": symbol,
                "name": kb_entry["name"],
                "expected_result_date": expected_date.isoformat(),
                "days_to_result": (expected_date - today).days,
                "direction": direction,
                "confidence": confidence,
                "post_earnings_win_rate": win_rate,
                "sample_size": kb_entry["sample_size"],
                "reliable_history": kb_entry["reliable"],
                "last_close": kb_entry["last_close"],
                "last_close_date": kb_entry["last_close_date"],
                "avg_pre_earnings_move_pct": kb_entry["pre_earnings"]["avg"],
                "avg_day0_move_pct": kb_entry["day0"]["avg"],
                "avg_post_earnings_move_pct": kb_entry["post_earnings"]["avg"],
                **band,
            }
        )

    predictions.sort(key=lambda p: p["expected_result_date"])
    return predictions


def main() -> int:
    if not config.KNOWLEDGE_BASE_FILE.exists():
        log.error("%s not found - run knowledge_base first.", config.KNOWLEDGE_BASE_FILE)
        return 1
    if not config.EARNINGS_UPCOMING_FILE.exists():
        log.error(
            "%s not found - run fetch_earnings_calendar first.",
            config.EARNINGS_UPCOMING_FILE,
        )
        return 1

    knowledge_base = json.loads(config.KNOWLEDGE_BASE_FILE.read_text())
    upcoming = json.loads(config.EARNINGS_UPCOMING_FILE.read_text())

    predictions = build_predictions(knowledge_base, upcoming)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.PREDICTIONS_FILE.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "lookahead_days": config.PREDICTION_LOOKAHEAD_DAYS,
                "predictions": predictions,
            },
            indent=2,
        )
    )
    log.info(
        "Wrote %d predictions (next %d days) to %s",
        len(predictions),
        config.PREDICTION_LOOKAHEAD_DAYS,
        config.PREDICTIONS_FILE,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
