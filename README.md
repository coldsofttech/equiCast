# equiCast

Equity and FX market data ingestion, storage, and forecasting toolkit.

## What's inside

- **`equicast`** — core Python package: pulls historical price data from
  yfinance and caches it as Parquet.
- **Backend (Django REST API)** — exposes market data over HTTP, backed by
  `equicast`, for the frontend to consume.
- **Frontend (React)** — a UI for looking up ticker history through the
  backend API.
- **FX data pipeline (`equicast-datafeed`, `equicast-metrics`, `equicast-fx`)**
  — a scheduled pipeline that extracts FX pair data from Yahoo Finance and
  lands it in S3 as Parquet, ready for downstream analysis.
- **`equicast-metrics`** — generic risk/performance metrics (volatility,
  Sharpe ratio, max drawdown, CAGR) for any yfinance symbol, FX pair or stock
  ticker alike, plus stock-only valuation/fundamental metrics (PE, EPS,
  margins, returns, leverage).
- **`equicast-dividends`** — generic dividend history (ex-dividend date,
  amount per share) for any yfinance equity-like symbol, built the same way
  as `equicast-metrics` so a future ETF package can reuse it too.
- **`equicast-events`** — generic corporate events (earnings reports, analyst
  rating changes, stock splits) for any yfinance equity-like symbol, built
  the same way as `equicast-dividends`/`equicast-metrics`.
- **Stock data pipeline (`equicast-datafeed`, `equicast-metrics`,
  `equicast-dividends`, `equicast-events`, `equicast-stock`)** — a scheduled
  pipeline that extracts stock ticker profiles, daily prices, dividends,
  events, and metrics from Yahoo Finance and lands them in the same S3
  bucket as Parquet.
- **ETF data pipeline (`equicast-datafeed`, `equicast-dividends`,
  `equicast-etf`)** — a scheduled pipeline that extracts ETF ticker
  profiles, daily prices, and dividends from Yahoo Finance and lands them
  in the same S3 bucket as Parquet. No events or metrics yet.

## Disclaimer

FX, stock, and ETF profile/price data is sourced via
[yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance) for
educational and informational purposes only — not financial advice, with no
guarantee of accuracy, completeness, or timeliness. FX/stock risk metrics
(volatility, Sharpe ratio, max drawdown, CAGR) and stock fundamentals (PE,
EPS, margins, returns, leverage) are calculated by equicast where yfinance
doesn't provide them directly, not sourced from a licensed provider —
validate their accuracy yourself before relying on them. An ETF profile's
`website` field is also equicast's own addition (a small static
`fund_family` → issuer-website lookup), since yfinance never populates
`website` for ETFs — see [equicast-etf's README](packages/etf/README.md#on-website)
for details. See
[equicast-datafeed](packages/datafeed/README.md#disclaimer),
[equicast-fx](packages/fx/README.md#disclaimer),
[equicast-metrics](packages/metrics/README.md#disclaimer),
[equicast-dividends](packages/dividends/README.md#disclaimer),
[equicast-events](packages/events/README.md#disclaimer),
[equicast-stock](packages/stock/README.md#disclaimer), and
[equicast-etf](packages/etf/README.md#disclaimer) for the full text;
each is also logged as a console warning the first time its client is used.

## FX data products

Each configured FX pair (default: GBP→USD, USD→GBP, GBP→EUR, EUR→GBP) yields
three kinds of data. Every numeric field below is rounded to 8 decimal places
— comfortably above FX's ~5-decimal pipette precision and the ~4-6 decimals
meaningful for risk/performance ratios, while cutting off the float64
representation noise you'd otherwise see (e.g. `1.3504753112792969`).

### Profile — a current snapshot

```python
from equicast_fx import FXClient

FXClient("GBP", "USD").profile()
# {"from_currency": "GBP", "to_currency": "USD", "exchange": "CCY",
#  "region": "US", "description": "GBP/USD",
#  "last_updated": "2026-08-28T21:29:05+00:00", "source": "yfinance",
#  "day_open": 1.3594, "day_high": 1.3598, "day_low": 1.3527,
#  "day_close": 1.3537, "day_average": 1.3563,
#  "year_open": 1.3505, "year_high": 1.3847, "year_low": 1.3012,
#  "year_close": 1.3537, "year_average": 1.3429,
#  "moving_average_50_days": 1.3417, "moving_average_200_days": 1.3431}
```

`day_close` is the live price — FX trades ~24/5, so there's no settled daily
close. `year_*` uses a trailing 52-week window; `*_average` fields are the
high/low midpoint, not a mean of daily closes.

### Prices — daily history

```python
FXClient("GBP", "USD").prices()
# [{"from_currency": "GBP", "to_currency": "USD", "date": "2026-01-02",
#   "open": 1.3475, "high": 1.3502, "low": 1.3435, "close": 1.3474,
#   "average": 1.3468, "last_updated": "2026-08-29T11:10:39+00:00",
#   "source": "yfinance"},
#  ...]
```

One row per trading day. By default covers the current year only; a full
historical load (every year available) can be requested separately — see
[the FX pipeline docs](docs/fx-pipeline.md).

### Metrics — risk and performance

```python
from equicast_metrics import MetricsClient

MetricsClient("GBPUSD=X").metrics()
# {"volatility": 0.066, "sharpe_ratio": 0.062, "max_drawdown": -0.048,
#  "cagr_1y": -0.007, "cagr_2y": 0.011, "cagr_3y": 0.024,
#  "cagr_5y": -0.002, "cagr_10y": 0.003,
#  "last_updated": "2026-08-29T11:55:00+00:00", "source": "equicast"}
```

`volatility`/`sharpe_ratio`/`max_drawdown` use a trailing 1-year window
(Sharpe assumes a 0% risk-free rate); the five `cagr_*` fields cover 1/2/3/5/10
years, `None` where a pair doesn't have enough history yet. `equicast-metrics`
is generic — it works the same way for a stock ticker (`MetricsClient("AAPL")`)
as for an FX pair, checking yfinance for an existing value first (only
`cagr_1y` has one) before calculating it.

### Where it lands

The pipeline writes all three as Parquet to S3, partitioned by pair and —
for prices — by year:

```
s3://equicast-market-data-<env>/
└── fx=GBPUSD/
    ├── profile.parquet
    ├── metrics.parquet
    ├── year=2025/price.parquet
    └── year=2026/price.parquet
```

Refreshed every 6 hours automatically.

## Stock data products

Each configured stock ticker (default: AAPL, MSFT, GOOGL, AMZN, NVDA, META,
TSLA, QCOM, AVGO) yields a profile, daily prices, dividends, events, and
metrics.

```python
from equicast_stock import StockClient

StockClient("AAPL").profile()
# {"ticker": "AAPL", "name": "Apple Inc.", "quote_type": "EQUITY",
#  "exchange": "NMS", "currency": "USD",
#  "description": "Apple Inc. designs, manufactures, and markets smartphones, ...",
#  "sector": "Technology", "industry": "Consumer Electronics",
#  "website": "https://www.apple.com", "beta": 1.2, "payout_ratio": 0.15,
#  "dividend_rate": 1.0, "dividend_yield": 0.005, "market_cap": 3000000000000,
#  "volume": 50000000, "day_open": 227.5, "day_high": 229.1, "day_low": 226.8,
#  "day_close": 228.5, "day_average": 227.95, "year_open": 180.0,
#  "year_high": 260.1, "year_low": 164.08, "year_close": 228.5,
#  "year_average": 212.09, "moving_average_50_days": 220.45,
#  "moving_average_200_days": 200.12,
#  "address": "One Apple Park Way, Cupertino, CA 95014",
#  "country": "United States", "region": "North America",
#  "full_time_employees": 164000,
#  "ceos": [{"name": "Timothy D. Cook", "role": "CEO & Director"}],
#  "ipo_date": "1980-12-12T14:30:00+00:00",
#  "last_updated": "2026-08-29T21:29:05+00:00", "source": "yfinance"}
```

`ceos` and `ipo_date` are best-effort — yfinance has no dedicated field for
either; see [equicast-stock's README](packages/stock/README.md) for how
they're derived.

```python
StockClient("AAPL").prices()
# [{"ticker": "AAPL", "currency": "USD", "date": "2026-01-02",
#   "open": 225.30, "high": 227.32, "low": 224.29, "close": 226.31,
#   "average": 225.805, "last_updated": "2026-08-29T11:10:39+00:00",
#   "source": "yfinance"},
#  ...]
```

One row per trading day. By default covers the current year only; a full
historical load (every year available) can be requested the same way as FX
— see [the stock pipeline docs](docs/stock-pipeline.md).

```python
from equicast_dividends import DividendsClient

DividendsClient("AAPL").dividends()
# [{"ticker": "AAPL", "currency": "USD", "ex_dividend_date": "2026-02-10",
#   "price": 0.26, "last_updated": "2026-08-30T09:00:00+00:00",
#   "source": "yfinance"},
#  ...]
```

One record per ex-dividend date; `price` is the dividend amount per share,
not a stock price. By default covers this year to date (plus any
future-dated entries, though yfinance's dividend data has none in
practice), same full-history option as prices. There's no `payment_date`
field — yfinance's
dividend history only has ex-dividend date and amount, for any ticker, at
any point in history. `equicast-dividends` is generic the same way
`equicast-metrics` is — built for any yfinance equity-like symbol, not
`equicast-stock`-specific, so it's ready to reuse for ETFs later.

```python
from equicast_events import EventsClient

EventsClient("AAPL").events()
# [{"ticker": "AAPL", "event_type": "earnings", "date": "2026-01-30",
#   "eps_estimate": None, "reported_eps": 2.18, "surprise_pct": -3.5,
#   "firm": None, "from_grade": None, "to_grade": None, "action": None,
#   "ratio": None, "last_updated": "2026-08-30T09:00:00+00:00", "source": "yfinance"},
#  {"ticker": "AAPL", "event_type": "rating", "date": "2026-03-01",
#   "eps_estimate": None, "reported_eps": None, "surprise_pct": None,
#   "firm": "Morgan Stanley", "from_grade": "Equal-Weight", "to_grade": "Overweight",
#   "action": "up", "ratio": None, "last_updated": "2026-08-30T09:00:00+00:00",
#   "source": "yfinance"},
#  ...]
```

One record per event — earnings report, analyst rating change, or stock
split — tagged by `event_type`, with only that type's fields populated (the
rest `None`), combined into a single list rather than three separate calls.
Same year-to-date-plus-future-entries default / `full_load=True` option as
dividends and prices (only earnings ever has future-dated entries).
`equicast-events` is generic the same way `equicast-dividends` is;
see [equicast-events's README](packages/events/README.md) for exactly how
each event type is sourced.

```python
MetricsClient("AAPL").metrics()   # volatility, Sharpe ratio, max drawdown, CAGR — same as FX
MetricsClient("AAPL").fundamentals()
# {"trailing_pe": 30.1, "forward_pe": 27.4, "trailing_eps": 6.13,
#  "forward_eps": 6.75, "peg": 2.05, "price_to_book": 45.2,
#  "price_to_sales": 8.1, "ev_ebitda": 21.3, "gross_margin": 0.462,
#  "operating_margin": 0.312, "profit_margin": 0.24,
#  "return_on_equity": 1.52, "return_on_assets": 0.29,
#  "debt_to_equity": 148.6, "free_cash_flow_per_share": 6.42,
#  "last_updated": "2026-08-30T09:00:00+00:00", "source": "yfinance"}
```

`fundamentals()` is stock-only — valuation/leverage metrics have no meaning
for an FX pair, so `equicast-metrics` raises `UnsupportedSymbolError` if
called with one. See [equicast-metrics's
README](packages/metrics/README.md#fundamentals--valuation-and-fundamental-metrics-stock-only)
for exactly how each field is sourced/derived.

The pipeline writes all five as Parquet, landing in the same bucket as FX
data — `stock=<TICKER>/metrics.parquet` merges `metrics()` and
`fundamentals()` into one row, and `year=<YYYY>/events.parquet` combines all
three event types for that year into one file:

```
s3://equicast-market-data-<env>/
└── stock=AAPL/
    ├── profile.parquet
    ├── metrics.parquet
    ├── year=2025/price.parquet
    ├── year=2025/dividend.parquet
    ├── year=2025/events.parquet
    ├── year=2026/price.parquet
    ├── year=2026/dividend.parquet
    └── year=2026/events.parquet
```

Refreshed every 6 hours automatically, offset 2 hours from the FX schedule so
the two pipelines never overlap.

## ETF data products

Each configured ETF ticker (default: VOO, QQQ, VTI, AGG, GLD) yields a
profile, daily prices, and dividends — no events or metrics yet.

```python
from equicast_etf import ETFClient

ETFClient("VOO").profile()
# {"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "quote_type": "ETF",
#  "exchange": "PCX", "currency": "USD",
#  "description": "The fund manager employs an indexing investment approach ...",
#  "category": "Large Blend", "fund_family": "Vanguard",
#  "website": "https://www.vanguard.com", "beta": 1.0, "expense_ratio": 0.03,
#  "dividend_rate": None, "dividend_yield": 0.0107,
#  "total_assets": 1686884319232, "nav_price": 708.98, "volume": 8067208,
#  "day_open": 709.39, "day_high": 712.6692, "day_low": 706.26,
#  "day_close": 707.24, "day_average": 709.4646, "year_open": 588.29,
#  "year_high": 716.39, "year_low": 578.46, "year_close": 707.24,
#  "year_average": 647.425, "moving_average_50_days": 693.1996,
#  "moving_average_200_days": 652.7322, "ytd_return": 10.11602,
#  "three_year_average_return": 0.2217858, "five_year_average_return": 0.1294499,
#  "inception_date": "2010-09-07T00:00:00+00:00",
#  "last_updated": "2026-08-28T20:00:00+00:00", "source": "yfinance"}
```

An ETF has no company behind it, so `equicast-stock`'s company-specific
fields (`sector`/`industry`, `market_cap`, `ceos`, `address`/`country`/
`region`/`full_time_employees`) don't apply here — replaced by fund-specific
fields (`category`, `total_assets`, `expense_ratio`, `nav_price`,
`ytd_return`/`three_year_average_return`/`five_year_average_return`,
`inception_date`). See [equicast-etf's README](packages/etf/README.md#how-this-differs-from-equicast-stocks-profile)
for the full field-by-field comparison, and how `website`/`beta` are
derived.

```python
ETFClient("VOO").prices()
# [{"ticker": "VOO", "currency": "USD", "date": "2026-01-02",
#   "open": 626.83, "high": 627.84, "low": 621.43, "close": 624.50,
#   "average": 624.64, "last_updated": "2026-08-30T09:48:13+00:00",
#   "source": "yfinance"},
#  ...]
```

One row per trading day. By default covers the current year only; a full
historical load (every year available) can be requested the same way as
FX/stock — see [the ETF pipeline docs](docs/etf-pipeline.md).

```python
from equicast_dividends import DividendsClient

DividendsClient("VOO").dividends()
# [{"ticker": "VOO", "currency": "USD", "ex_dividend_date": "2026-03-27",
#   "price": 1.872, "last_updated": "2026-08-30T09:58:48+00:00",
#   "source": "yfinance"},
#  ...]
```

One record per ex-dividend date; `price` is the dividend amount per share,
not an ETF price. By default covers the current year only, same
full-history option as prices. Empty for tickers with no dividend history
(e.g. `GLD`, a gold trust that pays no distribution). `equicast-dividends`
is the same generic client `equicast-stock` uses, not ETF- or
stock-specific. Lands in the same bucket as FX/stock data:

```
s3://equicast-market-data-<env>/
└── etf=VOO/
    ├── profile.parquet
    ├── year=2025/price.parquet
    ├── year=2025/dividend.parquet
    ├── year=2026/price.parquet
    └── year=2026/dividend.parquet
```

Refreshed every 6 hours automatically, offset 4 hours from the FX schedule
and 2 hours from the stock schedule so none of the three pipelines overlap.

## Documentation

- [Local setup](docs/local-setup.md) — get every package running on your machine
- [FX pipeline: deployment and execution](docs/fx-pipeline.md) — build the image,
  deploy the infrastructure, and run/schedule the ingestion pipeline
- [Stock pipeline: deployment and execution](docs/stock-pipeline.md) — same,
  for the stock ticker pipeline
- [ETF pipeline: deployment and execution](docs/etf-pipeline.md) — same,
  for the ETF ticker pipeline
- [AWS ↔ GitHub OIDC setup](docs/aws-github-oidc-setup.md) — how GitHub Actions
  authenticates to AWS (Terraform, ECR/S3 deploy, FX/stock/ETF ingestion), and
  how to troubleshoot it
- [Changelog](CHANGELOG.md)
