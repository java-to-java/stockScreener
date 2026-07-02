"""Refresh the Nifty50 constituent list from NSE's published archives CSV.

Run from the repo root:

    python -m src.fetch_constituents

Writes ``data/nifty50_constituents.json``, which ``constituents.load_constituents()``
prefers over the hardcoded seed list. Safe to re-run any time (e.g. after NSE's
semi-annual index reshuffle in March/September).

Requires real internet access to archives.nseindia.com - this will fail in
network-restricted sandboxes, which is expected; the pipeline falls back to
the seed list in that case.
"""
import logging
import sys

import requests

import config
from src.constituents import parse_nse_csv, save_constituents, SEED_CONSTITUENTS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def fetch() -> list:
    resp = requests.get(
        config.NSE_ARCHIVES_NIFTY50_CSV,
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    constituents = parse_nse_csv(resp.text)
    if len(constituents) < 45:  # sanity check, index has ~50 members
        raise ValueError(
            f"Parsed only {len(constituents)} constituents - CSV format may have "
            "changed. Refusing to overwrite the existing list."
        )
    return constituents


def main() -> int:
    try:
        constituents = fetch()
    except Exception as exc:  # noqa: BLE001 - this is a best-effort refresh script
        log.warning(
            "Could not refresh Nifty50 constituents from NSE (%s). "
            "Keeping the existing/seed list (%d symbols).",
            exc,
            len(SEED_CONSTITUENTS),
        )
        return 1
    save_constituents(constituents)
    log.info("Saved %d constituents to %s", len(constituents), config.CONSTITUENTS_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
