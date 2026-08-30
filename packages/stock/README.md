# equicast-stock

Class-based stock ticker market data extraction, built on
[equicast-datafeed](../datafeed/README.md).

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing a `StockClient` logs this as a one-line warning the first time
it happens in a process (shared with `equicast-datafeed`'s own disclaimer,
so you won't see it twice).

## Usage

```python
from equicast_stock import StockClient

client = StockClient("AAPL")
profile = client.profile()
# {
#     "ticker": "AAPL",
#     "name": "Apple Inc.",
#     "quote_type": "EQUITY",
#     "exchange": "NMS",
#     "currency": "USD",
#     "description": "Apple Inc. designs, manufactures, and markets smartphones, ...",
#     "sector": "Technology",
#     "industry": "Consumer Electronics",
#     "website": "https://www.apple.com",
#     "beta": 1.2,
#     "payout_ratio": 0.15,
#     "dividend_rate": 1.0,
#     "dividend_yield": 0.005,
#     "market_cap": 3000000000000,
#     "volume": 50000000,
#     "day_open": 227.5, "day_high": 229.1, "day_low": 226.8,
#     "day_close": 228.5, "day_average": 227.95,
#     "year_open": 180.0, "year_high": 260.1, "year_low": 164.08,
#     "year_close": 228.5, "year_average": 212.09,
#     "moving_average_50_days": 220.45, "moving_average_200_days": 200.12,
#     "address": "One Apple Park Way, Cupertino, CA 95014",
#     "country": "United States",
#     "region": "North America",
#     "full_time_employees": 164000,
#     "ceos": [{"name": "Timothy D. Cook", "role": "CEO & Director"}],
#     "ipo_date": "1980-12-12T14:30:00+00:00",
#     "last_updated": "2026-08-29T21:29:05+00:00",
#     "source": "yfinance",
# }
```

`dividend_rate`/`dividend_yield`/`payout_ratio` are `None` for tickers that
don't pay a dividend — yfinance simply omits those keys rather than
reporting zero.

### On the price-range fields

`day_*`/`year_*`/`moving_average_*` mirror `equicast-fx`'s `FXClient.profile()`
exactly (same source fields, same logic): `day_close` is the live price;
`year_*` uses a trailing 52-week window (`year_open` from a
`history(period="1y")` call, everything else from yfinance's own
`fiftyTwoWeekHigh`/`fiftyTwoWeekLow`); `*_average` fields are the high/low
midpoint, not a mean of daily closes; `moving_average_50_days`/
`moving_average_200_days` come straight from yfinance's own 50/200-day
averages. All rounded to 8 decimal places (`equicast-datafeed`'s
`round_value`), `None` wherever the underlying yfinance field is missing.

### On `address`

Formatted from `address1`/`address2`/`city`/`state`/`zip` (e.g. "One Apple
Park Way, Cupertino, CA 95014"), `None` if none of those are present. Kept
separate from `country`/`region` — those come from yfinance's own
`country`/`region` keys, not parsed out of this string, so all three stay
independently filterable.

### On `ceos`

Each entry is `{"name": ..., "role": ...}`. Tried in order of reliability,
stopping at the first tier that finds a match:

1. `companyOfficers` — structured, most reliable. Matches on "CEO" (matches
   "Co-CEO" too) or "Chief Executive Officer" in each officer's title;
   `role` is that officer's actual title as reported (e.g. "Chairman,
   President and CEO"), not normalized.
2. `executiveTeam` — an alternate structured field yfinance populates for
   some tickers/versions when `companyOfficers` has no CEO entry. `role` is
   likewise their actual title.
3. `longBusinessSummary` — free-text pattern match for a capitalized name
   next to a "CEO"/"Chief Executive Officer" mention, only tried when
   neither structured field yields a match. Prose is inherently harder to
   parse reliably, so this tier can occasionally miss a name or return none
   at all. There's no real title to report here, so `role` is always the
   literal string `"CEO"` rather than an extracted phrase.

`StockClient.profile()` returns `ceos` as a real `list[dict]`, but
`write_profile_parquet` JSON-encodes it to a plain string column in the
Parquet file itself. pandas/pyarrow round-trip a native `list[dict]` column
fine, but common Parquet viewers (browser-based tools, editor extensions)
are JS-based and just call `toString()` on nested objects, rendering
`[object Object]` instead of the actual data — a JSON string reads
correctly in any viewer. Consumers reading the Parquet file directly need
`json.loads()` to get it back as structured data.

### On `ipo_date`

yfinance doesn't expose a true IPO date. `ipo_date` is sourced from
`firstTradeDateMilliseconds` (falling back to `firstTradeDateEpochUtc`) — the
first date Yahoo Finance itself has trading data for, which can differ from
the actual IPO date for older listings, relistings, or spin-offs. Treat it
as approximate, not authoritative. Formatted as a full ISO 8601 datetime,
same as `last_updated` (e.g. `"1980-12-12T14:30:00+00:00"`), not just a date.

## CLI

Reads the stock tickers listed in a config file, fetches a profile, daily
prices, dividends, events, and metrics for each, and writes:

- `<out>/stock=<TICKER>/profile.parquet` — one row, current snapshot
- `<out>/stock=<TICKER>/year=<YYYY>/price.parquet` — one row per trading day,
  for the current year only by default
- `<out>/stock=<TICKER>/year=<YYYY>/dividend.parquet` — one row per
  ex-dividend date, for the current year only by default (empty for tickers
  with no dividend history)
- `<out>/stock=<TICKER>/year=<YYYY>/events.parquet` — one row per event
  (earnings report, analyst rating change, stock split), for the current
  year only by default (empty for tickers/years with none of the three)
- `<out>/stock=<TICKER>/metrics.parquet` — one row, combining
  `equicast-metrics`' risk/performance metrics (volatility, Sharpe ratio,
  max drawdown, CAGR) with its stock-only fundamentals (PE, EPS, margins,
  returns, leverage, FCF/share)

```bash
uv run equicast-stock --config config/stocks.yaml --out ./output
```

Add `--full-load` to fetch each ticker's entire available yfinance history
for prices, dividends, and events, writing one
`price.parquet`/`dividend.parquet`/`events.parquet` per year found (current
year included) — same as `equicast-fx`'s `--full-load`. It does not affect
`metrics.parquet`:

```bash
uv run equicast-stock --config config/stocks.yaml --out ./output --full-load
```

`prices()` returns records shaped `{ticker, currency, date, open, high, low,
close, average, last_updated, source}` — `currency` comes from a
`get_info()` call (yfinance doesn't return it alongside `history()`'s OHLC
data).

### On `dividend.parquet`

Written from [`equicast-dividends`](../dividends/README.md)'
`DividendsClient` — a generic client (not part of `StockClient`) built the
same way `equicast-metrics`' `MetricsClient` is, so it's reusable by any
future asset-class package (e.g. ETFs) rather than living inside
`equicast-stock` itself.

Records are shaped `{ticker, currency, ex_dividend_date, price,
last_updated, source}`. `price` is the dividend cash amount per share, not a
stock price. There's no `payment_date` field — yfinance's dividend history
only has ex-dividend date and amount, for any ticker, at any point in
history; see equicast-dividends's README for details. Tickers with no
dividend history simply produce no `dividend.parquet` file for that year.

### On `events.parquet`

Written from [`equicast-events`](../events/README.md)' `EventsClient` — a
generic client (not part of `StockClient`), built the same way
`equicast-dividends`' `DividendsClient` is, so it's reusable by any future
asset-class package.

Records are shaped `{ticker, event_type, date, eps_estimate, reported_eps,
surprise_pct, firm, from_grade, to_grade, action, ratio, last_updated,
source}`, combining three distinct event types (earnings reports, analyst
rating changes, stock splits) into one file per year — `event_type` says
which, and only that type's fields are populated (the rest `None`). See
equicast-events's README for exactly how each type is sourced. Tickers/years
with none of the three simply produce no `events.parquet` file.

### On `metrics.parquet`

Built from two independent `equicast-metrics` calls on one `MetricsClient`,
merged into a single row:

- `MetricsClient.metrics()` — generic risk/performance metrics, works the
  same way as for an FX pair (see [equicast-metrics's
  README](../metrics/README.md)).
- `MetricsClient.fundamentals()` — stock-only valuation/fundamental metrics
  (trailing/forward PE, trailing/forward EPS, PEG, price-to-book,
  price-to-sales, EV/EBITDA, gross/operating/profit margin, return on
  equity/assets, debt-to-equity, free cash flow per share). See
  [equicast-metrics's README](../metrics/README.md#fundamentals--valuation-and-fundamental-metrics-stock-only)
  for exactly how each field is sourced/derived.

Both calls compute their own `last_updated`/`source` independently (a moment
apart); the merge keeps the later `last_updated` and reports `source` as
`"equicast"` if either call needed to compute anything, `"yfinance"` only if
every field in both came directly from yfinance's `.info`.

## Configuration

`config/stocks.yaml` lists the stock tickers to extract (currently AAPL,
MSFT, GOOGL, AMZN, NVDA, META, TSLA, QCOM, AVGO).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
