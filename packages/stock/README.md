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

Reads the stock tickers listed in a config file, fetches a profile for each,
and writes one Parquet file per ticker to
`<out>/stock=<TICKER>/profile.parquet`:

```bash
uv run equicast-stock --config config/stocks.yaml --out ./output
```

Only `profile()` is implemented so far — no prices or metrics yet, unlike
`equicast-fx`.

## Configuration

`config/stocks.yaml` lists the stock tickers to extract (currently AAPL,
MSFT, GOOGL, AMZN, NVDA, META, TSLA, QCOM, AVGO).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
