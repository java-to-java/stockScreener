"""Fetch Nifty50 earnings (financial results) dates from NSE.

Produces two files:

- ``data/earnings_history.json``  - past quarterly result dates per symbol,
  going back ``config.LOOKBACK_QUARTERS`` quarters. This is what
  ``knowledge_base.py`` uses to measure the historical pattern.
- ``data/earnings_upcoming.json`` - future result dates, sourced from NSE's
  board-meeting intimations (companies must notify the exchange of the
  board meeting date at which quarterly results will be approved, typically
  1-2 weeks ahead). This is what ``predict.py`` scans for stocks reporting soon.

Run from the repo root:

    python -m src.fetch_earnings_calendar

Requires real internet access to nseindia.com. NSE's endpoints are
undocumented and change shape occasionally - see ``nse_client.py``. If a
symbol's request fails, it is skipped with a warning rather than aborting
the whole run; check the summary printed at the end.
"""
import json
import logging
import sys
from datetime import datetime, timedelta

import config
from src.constituents import load_constituents
from src.nse_client import NSEClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# NSE date format used across these endpoints.
NSE_DATE_FMT = "%d-%m-%Y"


def _parse_nse_date(value: str):
    for fmt in (NSE_DATE_FMT, "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def fetch_historical_results(client: NSEClient, symbol: str) -> list[dict]:
    """Past quarterly result filings for one symbol, most recent first."""
    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=365 * config.LOOKBACK_YEARS)
    data = client.get_json(
        "/api/corporates-financial-results",
        params={
            "index": "equities",
            "symbol": symbol,
            "from_date": from_date.strftime(NSE_DATE_FMT),
            "to_date": to_date.strftime(NSE_DATE_FMT),
        },
    )
    events = []
    for row in data or []:
        result_date = _parse_nse_date(
            row.get("re_broadcast_date") or row.get("date") or ""
        )
        if not result_date:
            continue
        events.append(
            {
                "symbol": symbol,
                "result_date": result_date.isoformat(),
                "quarter": row.get("re_qtr") or row.get("period") or None,
            }
        )
    events.sort(key=lambda e: e["result_date"], reverse=True)
    return events[: config.LOOKBACK_QUARTERS]


def fetch_upcoming_result_date(client: NSEClient, symbol: str) -> dict | None:
    """Next board-meeting intimation for financial results, if any is on file."""
    data = client.get_json(
        "/api/corporate-board-meetings",
        params={"index": "equities", "symbol": symbol},
    )
    today = datetime.now().date()
    candidates = []
    for row in data or []:
        purpose = (row.get("bm_purpose") or "").lower()
        if "financial result" not in purpose and "results" not in purpose:
            continue
        bm_date = _parse_nse_date(row.get("bm_date") or "")
        if bm_date and bm_date >= today:
            candidates.append(bm_date)
    if not candidates:
        return None
    next_date = min(candidates)
    return {
        "symbol": symbol,
        "expected_date": next_date.isoformat(),
        "source": "nse_board_meeting",
    }


def main() -> int:
    constituents = load_constituents()
    client = NSEClient()

    history: list[dict] = []
    upcoming: list[dict] = []
    failures: list[str] = []

    for c in constituents:
        try:
            history.extend(fetch_historical_results(client, c.symbol))
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{c.symbol} (history): {exc}")
            log.warning("Skipping historical results for %s: %s", c.symbol, exc)

        try:
            entry = fetch_upcoming_result_date(client, c.symbol)
            if entry:
                upcoming.append(entry)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{c.symbol} (upcoming): {exc}")
            log.warning("Skipping upcoming board meeting for %s: %s", c.symbol, exc)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.EARNINGS_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    config.EARNINGS_UPCOMING_FILE.write_text(json.dumps(upcoming, indent=2))

    log.info(
        "Wrote %d historical result events (%d symbols) and %d upcoming results.",
        len(history),
        len({e["symbol"] for e in history}),
        len(upcoming),
    )
    if failures:
        log.warning(
            "%d/%d symbol requests failed - see warnings above. "
            "NSE frequently rate-limits or blocks scripted access; "
            "re-running later or lowering request rate may help.",
            len(failures),
            len(constituents) * 2,
        )
    return 0 if history or upcoming else 1


if __name__ == "__main__":
    sys.exit(main())
