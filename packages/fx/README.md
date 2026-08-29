# equicast-fx

Class-based FX pair market data extraction, built on
[equicast-datafeed](../datafeed/README.md).

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing an `FXClient` logs this as a one-line warning the first time it
happens in a process (shared with `equicast-datafeed`'s own disclaimer, so
you won't see it twice).

## Usage

```python
from equicast_fx import FXClient

client = FXClient("GBP", "USD")
profile = client.profile()
# {
#     "from_currency": "GBP",
#     "to_currency": "USD",
#     "exchange": "CCY",
#     "region": "US",
#     "description": "GBP/USD",
#     "last_updated": "2026-08-28T21:29:05+00:00",
#     "source": "yfinance",
# }
```

## CLI

Reads the FX pairs listed in a config file, fetches a profile for each, and
writes one Parquet file per pair to `<out>/fx=<PAIR>/profile.parquet`:

```bash
uv run equicast-fx --config config/fx_pairs.yaml --out ./output
```

## Configuration

`config/fx_pairs.yaml` lists the FX pairs to extract:

```yaml
pairs:
  - from: GBP
    to: USD
  - from: USD
    to: GBP
  - from: GBP
    to: EUR
  - from: EUR
    to: GBP
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
