"""Minimal NSE website client.

NSE's public JSON endpoints (nseindia.com/api/...) are unauthenticated but
gate on a browser-like session: you must first GET a normal page to receive
session cookies, then attach those cookies + browser headers to subsequent
API requests. This is the same pattern used by open-source tools such as
nsepython/jugaad-data.

This is an undocumented API, not an official one. It can change shape or
start blocking a given IP/User-Agent without notice, and NSE's own site
reliability varies. Every caller in this project treats failures here as
expected and degrades gracefully (skips the symbol, logs a warning) rather
than crashing the pipeline.
"""
import logging
import time
from typing import Any, Optional

import requests

import config

log = logging.getLogger(__name__)


class NSEClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": config.NSE_BASE_URL + "/",
            }
        )
        self._last_request_at = 0.0
        self._warmed_up = False

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = config.REQUEST_DELAY_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def warm_up(self, force: bool = False) -> None:
        """Visit the NSE homepage to obtain the session cookies the API needs."""
        if self._warmed_up and not force:
            return
        self._throttle()
        self.session.get(config.NSE_BASE_URL, timeout=config.REQUEST_TIMEOUT_SECONDS)
        self._warmed_up = True

    def get_json(self, path: str, params: Optional[dict] = None) -> Any:
        """GET an NSE API path (e.g. '/api/corporate-announcements') as JSON.

        Retries with backoff on failure; raises the last exception if every
        attempt fails so callers can decide how to degrade.
        """
        self.warm_up()
        url = f"{config.NSE_BASE_URL}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(1, config.REQUEST_RETRIES + 1):
            self._throttle()
            try:
                resp = self.session.get(
                    url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
                )
                if resp.status_code in (401, 403):
                    # Session likely stale or rejected - re-warm once and retry.
                    self.warm_up(force=True)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
                last_exc = exc
                backoff = config.REQUEST_RETRY_BACKOFF_SECONDS * attempt
                log.warning(
                    "NSE request failed (attempt %d/%d) for %s %s: %s - retrying in %.1fs",
                    attempt,
                    config.REQUEST_RETRIES,
                    url,
                    params or "",
                    exc,
                    backoff,
                )
                time.sleep(backoff)
        assert last_exc is not None
        raise last_exc
