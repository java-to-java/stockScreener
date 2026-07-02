# stockScreener - Nifty50 Earnings Tracker

Tracks how each Nifty50 stock has historically moved around its own quarterly
result dates, and uses that pattern to flag which upcoming results are worth
watching - with a likely direction and an expected 15-trading-day price
range.

**This is a price-action pattern summary, not a forecast.** It does not read
news, analyst estimates, or the actual result content - see
[Limitations](#limitations) before using it for anything real.

## What it does

1. **Knowledge base**: for every Nifty50 stock, look at its last ~8 quarterly
   results and measure, for each one: the return in the week before, the
   single-day move on the result date, the return in the week after, and how
   far the stock ran up/down (high/low) in the 15 trading days that followed.
2. **Prediction**: for stocks with a result due in the next 30 days, project
   an expected 15-day high/low band from that same historical pattern, and
   classify direction (Bullish / Bearish / Neutral) from the historical
   post-earnings win-rate.
3. **Dashboard**: renders it all as a static, filterable/sortable page at
   `docs/index.html` - open it directly or serve `/docs` via GitHub Pages.

## Architecture

```
src/constituents.py          Nifty50 symbol list (seed + NSE refresh)
src/fetch_constituents.py    refresh the list from NSE's archives CSV
src/nse_client.py            session/cookie handling + retries for nseindia.com
src/fetch_earnings_calendar.py   past + upcoming result dates, from NSE
src/fetch_price_history.py   daily OHLCV per symbol, from Yahoo Finance (yfinance)
src/knowledge_base.py        the pattern-statistics engine (pure, unit-tested)
src/predict.py                direction + expected-range engine (pure, unit-tested)
src/dashboard.py             renders docs/index.html from predictions.json
src/pipeline.py              runs the stages above in order
```

Data flows one way: constituents -> earnings calendar + price history ->
knowledge base -> predictions -> dashboard. Every stage also writes/reads a
JSON file in `data/`, so you can inspect or re-run any single stage.

## Quickstart

```bash
pip install -r requirements.txt

python -m src.pipeline
# equivalent to running each stage in order:
#   python -m src.fetch_constituents      # optional, refreshes data/nifty50_constituents.json
#   python -m src.fetch_earnings_calendar # -> data/earnings_history.json, data/earnings_upcoming.json
#   python -m src.fetch_price_history     # -> data/prices/<SYMBOL>.csv
#   python -m src.knowledge_base          # -> data/knowledge_base.json
#   python -m src.predict                 # -> data/predictions.json
#   python -m src.dashboard               # -> docs/index.html

open docs/index.html   # or: python -m http.server -d docs
```

Run just the tests (no network needed):

```bash
pytest -q
```

### A note on network access

`fetch_earnings_calendar.py` and `fetch_price_history.py` need real internet
access to `nseindia.com` and Yahoo Finance. **This was built in a sandboxed
dev environment that blocks both** (outbound access is allowlisted to a
handful of dev-tooling domains), so the fetch stages could not be exercised
against live data here - only the pure computation stages
(`knowledge_base.py`, `predict.py`) and the dashboard were verified, using
synthetic price/earnings data and a real browser screenshot. Run the fetch
stages from a normal machine or CI (see `.github/workflows/refresh.yml`,
which runs the full pipeline daily and commits the refreshed data + dashboard).

## Methodology

- **Direction**: classified from the historical **post-earnings 7-trading-day
  win-rate** (fraction of past results after which the stock was up 7
  trading days later). >= 60% -> Bullish, <= 40% -> Bearish, else Neutral.
- **Confidence**: combines sample size and how lopsided the win-rate is - a
  60% win-rate on 4 events is weaker evidence than 85% on 8 events. Always
  "Low" below `MIN_SAMPLE_SIZE` (default 4) historical events.
- **Expected 15-day range**: the average of how far past results ran up
  (`forward_high`) and down (`forward_low`) in the 15 trading days following
  the result, applied to the current price. Symbols without enough
  historical events fall back to a band from the stock's general (non-
  earnings) volatility - flagged via `band_basis: "generic_volatility"` in
  the data and in the dashboard, since it carries no earnings-specific
  signal.
- All thresholds and window sizes live in `config.py`.

## Limitations

- **Price action only.** No analyst estimates, no actual-vs-estimate
  comparison, and no news/sentiment analysis feed into this. Two stocks with
  identical historical win-rates can have very different setups this
  quarter for reasons this tool cannot see.
- **Small samples.** ~8 quarters of history is not a lot of data points;
  treat "Low confidence" and `generic_volatility`-based bands as indicative
  at best.
- **NSE scraping is unofficial and fragile.** `nse_client.py` uses the same
  session/cookie pattern as other open-source NSE tools against undocumented
  endpoints - it can break if NSE changes its site, and commonly rate-limits
  or blocks scripted access. `fetch_earnings_calendar.py` skips (and logs) a
  symbol on failure rather than aborting the run; check the run's warnings.
- **The Nifty50 constituent list drifts.** NSE reshuffles the index twice a
  year. `src/constituents.py`'s seed list is a reference snapshot - run
  `python -m src.fetch_constituents` to refresh it from NSE's official CSV.
- **Not investment advice.** This is a statistics exercise over public price
  history, published as-is with no guarantee of accuracy or completeness.

## Possible extensions (not built)

- Analyst estimate revisions and estimate-vs-actual surprise history.
- News/sentiment scoring in the pre/post-result windows.
- Sector-relative or Nifty-relative (beta-adjusted) returns instead of raw
  returns, to separate stock-specific reaction from broad market moves on
  the same day.
