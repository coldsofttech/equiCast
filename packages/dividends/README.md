# equicast-dividends

Generic dividend history for any yfinance equity-like symbol — a stock
ticker (`AAPL`) today, an ETF ticker in the future — since the underlying
data (ex-dividend date, cash amount per share) is shaped the same way
regardless of asset class. Mirrors `equicast-metrics`' `MetricsClient` in
spirit: a small, generic client built on `equicast-datafeed`, reusable by
any asset-class package rather than living inside one.

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing a `DividendsClient` logs this as a one-line warning the first
time it happens in a process. Unlike `FXClient`/`StockClient`, this uses its
own distinct message rather than reusing `equicast-datafeed`'s — so it's
always visible even when `DatafeedClient`'s disclaimer already fired earlier
in the same process (e.g. constructed first in a CLI's `run()`), the same
way `equicast-metrics`' disclaimer is always visible.

## Usage

```python
from equicast_dividends import DividendsClient

DividendsClient("AAPL").dividends()
# [{"ticker": "AAPL", "currency": "USD", "ex_dividend_date": "2026-02-10",
#   "price": 0.26, "last_updated": "2026-08-30T09:00:00+00:00",
#   "source": "yfinance"},
#  ...]
```

One record per ex-dividend date. By default covers this calendar year only;
`dividends(full_load=True)` covers the symbol's entire dividend history
instead — same year-to-date/full-history split as `FXClient.prices()`/
`StockClient.prices()`, even though yfinance's underlying dividends call has
no period parameter of its own (the full series is always fetched in one
call; the default just filters it down to the current year).

A symbol with no dividend history (growth stocks, non-dividend-paying
tickers) simply returns `[]`.

### On `payment_date`

There isn't one. yfinance's dividend history (scraped from Yahoo Finance's
dividend table) only has two columns: ex-dividend date and cash amount per
share — no payment date, for any ticker, at any point in history. `price` is
the dividend amount per share (not a stock price) for that ex-dividend date.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
