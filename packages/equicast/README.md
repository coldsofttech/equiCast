# equicast

Core Python package: equity market data ingestion (via yfinance) and Parquet
storage. Depended on by `equicast-backend`.

## Usage

```python
from equicast.data.fetch import fetch_history
from equicast.data.storage import read_parquet, write_parquet

df = fetch_history("AAPL", period="1y", interval="1d")
write_parquet(df, "AAPL")
read_parquet("AAPL")
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
