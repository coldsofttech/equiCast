# equicast-benchmark

Class-based benchmark (market index) data extraction, built on
[equicast-datafeed](../datafeed/README.md).

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing a `BenchmarkClient` logs this as a one-line warning the first
time it happens in a process (shared with `equicast-datafeed`'s own
disclaimer, so you won't see it twice).

## Usage

```python
from equicast_benchmark import BenchmarkClient

client = BenchmarkClient("SP500", "^GSPC")
profile = client.profile()
# {
#     "key": "SP500", "symbol": "^GSPC", "name": "S&P 500",
#     "exchange": "SNP", "currency": "USD", "region": "US",
#     "last_updated": "2026-08-28T21:29:05+00:00", "source": "yfinance",
#     "day_open": 6410.5, "day_high": 6455.2, "day_low": 6398.1,
#     "day_close": 6440.3, "year_open": 6100.0, "year_high": 6500.8,
#     "year_low": 5200.4, "year_close": 6440.3,
# }
```

A benchmark is a single yfinance symbol (like a stock ticker), not a pair
(like an FX pair) — so `BenchmarkClient` mirrors
[equicast-fx's `FXClient`](../fx/README.md) closely (no dividends, no
fundamentals; an index pays none and has no earnings/balance sheet), just
keyed by a single `key`/`symbol` pair instead of `from_currency`/
`to_currency`. `key` is a stable, human-readable S3 partition identifier
you choose (e.g. `"SP500"`); `symbol` is the exact yfinance ticker to fetch
(e.g. `"^GSPC"`) — see `config/benchmarks.prod.yaml` for the full list and
where each symbol came from. `name` is derived from yfinance's own
`longName`/`shortName` (falling back between the two, same as
`equicast-stock`), not stored in config.

## CLI

Reads the benchmarks listed in a config file, fetches a profile for each,
and writes one Parquet file per benchmark to
`<out>/benchmark=<KEY>/profile.parquet`:

```bash
uv run equicast-benchmark --config config/benchmarks.dev.yaml --out ./output
```

## Configuration

`config/benchmarks.dev.yaml` and `config/benchmarks.prod.yaml` each list the
benchmarks to extract for that environment (`benchmark-ingestion.yml` picks
between them — see [docs/benchmark-pipeline.md](../../docs/benchmark-pipeline.md)):

```yaml
benchmarks:
  - key: SP500
    symbol: "^GSPC"
  - key: FTSE100
    symbol: "^FTSE"
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
