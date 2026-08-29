# equicast-datafeed

Resilient market-data client backing equicast's yfinance-based packages: rate
limiting and retry-with-backoff around `yfinance` calls, so any consumer
(`equicast-fx`, and future data packages) gets safe defaults for hitting
Yahoo Finance without hand-rolling error handling each time.

## Usage

```python
from equicast_datafeed import DatafeedClient

client = DatafeedClient(max_calls=1, period_seconds=1.0, max_retries=3)
info = client.get_info("GBPUSD=X")
history = client.get_history("GBPUSD=X", period="1y", interval="1d")
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
