# equicast-metrics

Generic risk/performance metrics for any yfinance symbol — an FX pair
(`GBPUSD=X`) or a stock ticker (`AAPL`) alike, since the calculation only
needs a daily close-price history, regardless of asset class. Also offers
stock-only valuation/fundamental metrics (PE, EPS, margins, returns,
leverage) via `fundamentals()` — FX pairs have no earnings or balance sheet,
so that method rejects them.

## Disclaimer

These metrics (volatility, Sharpe ratio, max drawdown, CAGR) are calculated
by equicast for educational and informational purposes only. They are not
sourced from a licensed financial data provider and have not been
independently verified — please validate their accuracy yourself before
relying on them. Not financial advice.

Constructing a `MetricsClient` logs this as a one-line warning the first
time it happens in a process (via Python's `logging`, so it still reaches
the console even if nothing else has configured a handler). Since
`MetricsClient` also builds on `equicast-datafeed` internally, you'll
typically see that package's yfinance-sourcing disclaimer alongside it.

## Usage

```python
from equicast_metrics import MetricsClient

MetricsClient("AAPL").metrics()
# {"volatility": 0.24, "sharpe_ratio": 0.81, "max_drawdown": -0.18,
#  "cagr_1y": 0.21, "cagr_2y": 0.15, "cagr_3y": 0.12, "cagr_5y": 0.19,
#  "cagr_10y": 0.22, "last_updated": "2026-08-29T12:00:00+00:00",
#  "source": "equicast"}

MetricsClient("GBPUSD=X").metrics()

MetricsClient("AAPL").fundamentals()
# {"trailing_pe": 30.1, "forward_pe": 27.4, "trailing_eps": 6.13,
#  "forward_eps": 6.75, "peg": 2.05, "price_to_book": 45.2,
#  "price_to_sales": 8.1, "ev_ebitda": 21.3, "gross_margin": 0.462,
#  "operating_margin": 0.312, "profit_margin": 0.24,
#  "return_on_equity": 1.52, "return_on_assets": 0.29,
#  "debt_to_equity": 148.6, "free_cash_flow_per_share": 6.42,
#  "last_updated": "2026-08-30T09:00:00+00:00", "source": "yfinance"}

MetricsClient("GBPUSD=X").fundamentals()  # raises UnsupportedSymbolError
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

## `fundamentals()` — valuation and fundamental metrics (stock only)

Stock tickers only — `fundamentals()` raises `UnsupportedSymbolError` for a
symbol ending in `"=X"` (yfinance's FX pair suffix), since FX pairs have no
earnings, margins, or balance sheet.

For each field, `fundamentals()` prefers yfinance's `.info` dict directly,
then a ratio built from *other* `.info` fields, and only as a last resort a
line item pulled from the ticker's annual balance sheet / income statement
(fetched lazily, at most once each per call, since most tickers resolve
every field from `.info` alone):

- **`trailing_pe`**/**`forward_pe`** — trailing/forward price-to-earnings.
  `.info`'s `trailingPE`/`forwardPE`, else current price ÷ EPS.
  `forward_pe` has no statement fallback — forward earnings estimates aren't
  in historical financials.
- **`trailing_eps`**/**`forward_eps`** — `.info`'s `trailingEps`/`forwardEps`,
  else (`trailing_eps` only) the income statement's Diluted EPS row, else net
  income ÷ shares outstanding. `forward_eps` has no fallback, for the same
  reason as `forward_pe`.
- **`peg`** — `.info`'s `trailingPegRatio`/`pegRatio`, else
  `trailing_pe / (earningsGrowth * 100)`.
- **`price_to_book`** — `.info`'s `priceToBook`, else market cap ÷
  stockholders' equity.
- **`price_to_sales`** — `.info`'s `priceToSalesTrailing12Months`, else
  market cap ÷ total revenue (from `.info` or the income statement).
- **`ev_ebitda`** — `.info`'s `enterpriseToEbitda`, else enterprise value ÷
  EBITDA (both from `.info`).
- **`gross_margin`**/**`operating_margin`**/**`profit_margin`** — `.info`'s
  `grossMargins`/`operatingMargins`/`profitMargins`, else the matching
  income statement line item (gross profit/operating income/net income) ÷
  total revenue.
- **`return_on_equity`**/**`return_on_assets`** — `.info`'s
  `returnOnEquity`/`returnOnAssets`, else net income ÷ stockholders' equity
  (or total assets), pulled from the balance sheet and income statement.
- **`debt_to_equity`** — `.info`'s `debtToEquity` (a percentage, e.g. `150.0`
  == 150%), else `(total liabilities / stockholders' equity) * 100` from the
  balance sheet, scaled to match.
- **`free_cash_flow_per_share`** — no direct yfinance field: always built
  from `freeCashflow` ÷ shares outstanding, falling back to
  (`operatingCashflow` + `capitalExpenditures`) ÷ shares outstanding (capex
  is reported negative by yfinance, so this subtracts it). Always counts as
  a fallback for the `source` field below, even when its inputs came
  straight from `.info`.
- **`last_updated`**/**`source`** — same meaning as `metrics()`'s, but
  `source` reflects *this* call: `"yfinance"` only if every field above came
  directly from `.info`, `"equicast"` if any field needed a derived ratio or
  a balance sheet/income statement line item.

Any field can come back `None` if yfinance doesn't have it and none of the
fallbacks apply (e.g. a newly-listed company with no prior-year financials).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
