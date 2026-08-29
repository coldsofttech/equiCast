# equicast-datafeed

Resilient market-data client backing equicast's yfinance-based packages: rate
limiting and retry-with-backoff around `yfinance` calls, so any consumer
(`equicast-fx`, and future data packages) gets safe defaults for hitting
Yahoo Finance without hand-rolling error handling each time.

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing a `DatafeedClient` logs this as a one-line warning the first
time it happens in a process (via Python's `logging`, so it still reaches
the console even if nothing else has configured a handler).

## Usage

```python
from equicast_datafeed import DatafeedClient

client = DatafeedClient(max_calls=1, period_seconds=1.0, max_retries=3)
info = client.get_info("GBPUSD=X")
history = client.get_history("GBPUSD=X", period="1y", interval="1d")
```

Also exports the shared decimal-precision policy used across equicast's
market-data packages (`equicast-fx`, `equicast-metrics`): every numeric field
they compute or re-emit is rounded to `DECIMAL_PRECISION` (8) decimal places,
via `round_value`, to cut off float64 representation noise (e.g.
`1.3504753112792969` → `1.35047531`) while staying well above FX's ~5-decimal
(pipette) precision and the ~4-6 decimals meaningful for risk/performance
ratios.

```python
from equicast_datafeed import DECIMAL_PRECISION, round_value

round_value(1.3504753112792969)  # 1.35047531
round_value(None)  # None
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
