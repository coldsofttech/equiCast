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
  ticker alike.
- **Stock data pipeline (`equicast-datafeed`, `equicast-stock`)** — a
  scheduled pipeline that extracts stock ticker profiles from Yahoo Finance
  and lands them in the same S3 bucket as Parquet. Only company profiles so
  far (no daily prices or metrics yet).

## Disclaimer

FX profile and price data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only — not
financial advice, with no guarantee of accuracy, completeness, or
timeliness. FX metrics (volatility, Sharpe ratio, max drawdown, CAGR) are
calculated by equicast, not sourced from a licensed provider — validate
their accuracy yourself before relying on them. Stock profile data is
sourced the same way via yfinance, with the same caveat. See
[equicast-datafeed](packages/datafeed/README.md#disclaimer),
[equicast-fx](packages/fx/README.md#disclaimer),
[equicast-metrics](packages/metrics/README.md#disclaimer), and
[equicast-stock](packages/stock/README.md#disclaimer) for the full text;
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
TSLA, QCOM, AVGO) yields a profile and daily prices — no risk/performance
metrics yet.

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
— see [the stock pipeline docs](docs/stock-pipeline.md). Lands in the same
bucket as FX data:

```
s3://equicast-market-data-<env>/
└── stock=AAPL/
    ├── profile.parquet
    ├── year=2025/price.parquet
    └── year=2026/price.parquet
```

Refreshed every 6 hours automatically, offset 2 hours from the FX schedule so
the two pipelines never overlap.

## Documentation

- [Local setup](docs/local-setup.md) — get every package running on your machine
- [FX pipeline: deployment and execution](docs/fx-pipeline.md) — build the image,
  deploy the infrastructure, and run/schedule the ingestion pipeline
- [Stock pipeline: deployment and execution](docs/stock-pipeline.md) — same,
  for the stock ticker pipeline
- [AWS ↔ GitHub OIDC setup](docs/aws-github-oidc-setup.md) — how GitHub Actions
  authenticates to AWS (Terraform, ECR/S3 deploy, FX/stock ingestion), and how
  to troubleshoot it
- [Changelog](CHANGELOG.md)
