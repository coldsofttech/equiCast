# equicast-metrics

Generic risk/performance metrics for any yfinance symbol — an FX pair
(`GBPUSD=X`) or a stock ticker (`AAPL`) alike, since the calculation only
needs a daily close-price history, regardless of asset class.

## Usage

```python
from equicast_metrics import MetricsClient

MetricsClient("AAPL").metrics()
# {"volatility": 0.24, "sharpe_ratio": 0.81, "max_drawdown": -0.18,
#  "cagr_1y": 0.21, "cagr_2y": 0.15, "cagr_3y": 0.12, "cagr_5y": 0.19,
#  "cagr_10y": 0.22, "last_updated": "2026-08-29T12:00:00+00:00",
#  "source": "equicast"}

MetricsClient("GBPUSD=X").metrics()
```

## What each field means

- **`volatility`** — annualized standard deviation of daily returns over the
  trailing 1 year (`std(daily returns) * sqrt(252)`).
- **`sharpe_ratio`** — annualized Sharpe ratio over the trailing 1 year,
  assuming a 0% risk-free rate: `mean(daily returns) / std(daily returns) * sqrt(252)`.
- **`max_drawdown`** — largest peak-to-trough decline over the trailing 1
  year, as a negative fraction (e.g. `-0.18` = -18%).
- **`cagr_1y`/`cagr_2y`/`cagr_3y`/`cagr_5y`/`cagr_10y`** — compound annual
  growth rate over each trailing window, `None` if the symbol doesn't have
  enough history to cover it.
- **`source`** — `"yfinance"` only if every field above came directly from
  yfinance's `.info` (in practice this never happens: only `cagr_1y` has a
  yfinance equivalent, via `fiftyTwoWeekChangePercent`); otherwise
  `"equicast"`, meaning at least one field was calculated from historical
  price data rather than read directly from yfinance.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
