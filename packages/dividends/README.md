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

One record per ex-dividend date. By default covers this calendar year to
date, plus any future-dated entries (`index.year >= this year`, not `==
this year`) — in practice a no-op today, since yfinance's dividend data is
derived from price history and never has a date past today, but keeps the
filter's direction correct rather than relying on that absence.
`dividends(full_load=True)` covers the symbol's entire dividend history
instead — same year-to-date/full-history split as `FXClient.prices()`/
`StockClient.prices()`, even though yfinance's underlying dividends call has
no period parameter of its own (the full series is always fetched in one
call; the default just filters it down).

A symbol with no dividend history (growth stocks, non-dividend-paying
tickers) simply returns `[]`.

### On `payment_date`

There isn't one. yfinance's dividend history (scraped from Yahoo Finance's
dividend table) only has two columns: ex-dividend date and cash amount per
share — no payment date, for any ticker, at any point in history. `price` is
the dividend amount per share (not a stock price) for that ex-dividend date.

## `dividend_frequency`

```python
from equicast_dividends import DividendsClient, dividend_frequency

dividend_frequency(DividendsClient("AAPL").dividends(full_load=True))
# "quarterly"
```

Classifies a symbol's payout cadence from its ex-dividend-date history into
`"weekly"`, `"monthly"`, `"quarterly"`, `"half_yearly"`, `"yearly"`,
`"irregular"` (a real, still-active payer whose recent gaps don't fit any of
the above — e.g. a one-off special dividend thrown into an otherwise-
quarterly schedule, or a genuinely erratic payer), or `"not_applicable"`
(fewer than 2 recorded payouts to measure a gap from at all — no dividend
history, or a single just-started one).

Takes `dividends()`'s own record list — not a symbol — so it works from
whatever history a caller already fetched (`equicast-stock`/`equicast-etf`'s
CLIs merge this into `profile.parquet`'s `dividend_frequency` field, reusing
the same `dividends(full_load=True)` call they need for `dividend.parquet`
anyway rather than fetching twice). Uses the most recent 10 payouts (or
however many exist, down to 2), sorted internally regardless of the input
list's own order, and classifies the *median* day-gap between consecutive
payouts in that sample — median rather than mean so one unusually long/short
gap doesn't shift the result on its own. See
[`frequency.py`](src/equicast_dividends/frequency.py) for the exact day-gap
bands each label matches.

## `median_payout_gap_days`

```python
from equicast_dividends import DividendsClient, median_payout_gap_days

median_payout_gap_days(DividendsClient("AAPL").dividends(full_load=True))
# 91.0
```

The raw number `dividend_frequency()` classifies — the median day-gap itself
(a `float`, or `None` below the 2-payout minimum), not rounded to a
canonical per-label value. `dividend_frequency()` calls this internally;
exposed separately for a caller (e.g.
[`equicast-forecasting`](../forecasting/README.md)) that needs the ticker's
*actual* empirical cadence to step forward by, not just which named band it
falls into — a payer whose real median gap is 84 days keeps stepping by 84,
not by "quarterly"'s canonical ~91.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
