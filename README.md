# equiCast

Equity and FX market data ingestion, storage, and forecasting toolkit.

## What's inside

- **`equicast`** — core Python package: pulls historical price data from
  yfinance and caches it as Parquet.
- **Backend (Django REST API)** — exposes market data over HTTP, backed by
  `equicast`, for the frontend to consume.
- **Frontend (React)** — a UI for looking up ticker history through the
  backend API.
- **FX data pipeline (`equicast-datafeed`, `equicast-fx`)** — a scheduled
  pipeline that extracts FX pair data from Yahoo Finance and lands it in S3
  as Parquet, ready for downstream analysis.

## FX data products

Each configured FX pair (default: GBP→USD, USD→GBP, GBP→EUR, EUR→GBP) yields
two kinds of data, both sourced from Yahoo Finance:

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

### Where it lands

The pipeline writes both as Parquet to S3, partitioned by pair and — for
prices — by year:

```
s3://equicast-market-data-<env>/
└── fx=GBPUSD/
    ├── profile.parquet
    ├── year=2025/price.parquet
    └── year=2026/price.parquet
```

Refreshed every 6 hours automatically.

## Documentation

- [Local setup](docs/local-setup.md) — get every package running on your machine
- [FX pipeline: deployment and execution](docs/fx-pipeline.md) — build the image,
  deploy the infrastructure, and run/schedule the ingestion pipeline
- [Changelog](CHANGELOG.md)
