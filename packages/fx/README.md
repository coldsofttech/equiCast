# equicast-fx

Class-based FX pair market data extraction, built on
[equicast-datafeed](../datafeed/README.md).

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
