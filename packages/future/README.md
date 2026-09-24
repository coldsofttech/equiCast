# equicast-future

Class-based futures contract data extraction, built on
[equicast-datafeed](../datafeed/README.md).

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing a `FutureClient` logs this as a one-line warning the first
time it happens in a process (shared with `equicast-datafeed`'s own
disclaimer, so you won't see it twice).

## Usage

```python
from equicast_future import FutureClient

client = FutureClient("GOLD", "GC=F")
profile = client.profile()
# {
#     "key": "GOLD", "symbol": "GC=F", "name": "Gold",
#     "exchange": "CMX", "currency": "USD", "region": None,
#     "last_updated": "2026-08-28T21:29:05+00:00", "source": "yfinance",
#     "day_open": 2410.5, "day_high": 2455.2, "day_low": 2398.1,
#     "day_close": 2440.3, "year_open": 2100.0, "year_high": 2500.8,
#     "year_low": 1900.4, "year_close": 2440.3,
# }
```

A future is a single yfinance symbol (like a stock ticker), not a pair
(like an FX pair) — so `FutureClient` mirrors
[equicast-benchmark's `BenchmarkClient`](../benchmark/README.md) exactly (no
dividends, no fundamentals; a futures contract pays none and has no
earnings/balance sheet), just keyed by a single `key`/`symbol` pair instead
of `from_currency`/`to_currency`. `key` is a stable, human-readable S3
partition identifier you choose (e.g. `"GOLD"`); `symbol` is the exact
yfinance ticker to fetch (e.g. `"GC=F"`) — see
`config/futures.prod.yaml` for the full list. `name` is derived from
yfinance's own `longName`/`shortName` (falling back between the two, same
as `equicast-stock`/`equicast-benchmark`), not stored in config.

## CLI

Reads the futures listed in a config file, fetches a profile for each, and
writes one Parquet file per future to `<out>/future=<KEY>/profile.parquet`:

```bash
uv run equicast-future --config config/futures.dev.yaml --out ./output
```

## Configuration

`config/futures.dev.yaml` and `config/futures.prod.yaml` each list the
futures to extract for that environment (`future-ingestion.yml` picks
between them — see [docs/future-pipeline.md](../../docs/future-pipeline.md)):

```yaml
futures:
  - key: GOLD
    symbol: "GC=F"
  - key: SILVER
    symbol: "SI=F"
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
