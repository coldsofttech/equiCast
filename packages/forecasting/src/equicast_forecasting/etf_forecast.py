"""Top-level ETF forecast entry point (GitHub issue #67): routes an ETF to
one of three type schemas (etf_type_registry.py), then combines the
generic Monte Carlo engine (monte_carlo.py) - the same one stock_forecast.py
(issue #66) uses - with a real expense-ratio drag for the long horizon
(etf_signals.py) into one daily probability-band series, same output shape
as stock/FX forecasting.

Horizon regimes (identical day-boundaries to FX/stock - see regimes.py):
  - 1w-1m ("short"): no directional drift. Volatility throughout the whole
    simulation is calibrated to a GARCH(1,1)-with-EWMA-fallback estimate
    (volatility.py), same as FX/stock.
  - 6m-2y ("medium"): Monte Carlo bootstrap, no bias - 0.0 drift, per the
    issue's own "Same model split as stocks" note (stock's medium regime
    is explicitly unbiased too).
  - 3y-10y ("long"): Monte Carlo bootstrap + a bias - but *not* a
    valuation-reversion one. Stock's long horizon reverts a starting-
    multiple z-score toward its own historical average (see
    stock_forecast.py); that needs a reconstructable historical multiple
    series, which funds can't supply (ETFs file no annual financial
    statements the way stocks do - see etf_signals.py's module docstring).
    What every ETF genuinely does have is its own real expense ratio - a
    *known*, structural drag on total return, not a speculative signal -
    so that's what drives the long-horizon bias instead: a constant daily
    log-return drag of `-expense_ratio / DAYS_PER_YEAR`, active for as long
    as the long regime's drift schedule keeps it tapered in. Unlike stock's
    `_long_drift` (which spreads a one-time valuation gap evenly over the
    years remaining, since a multiple reverting toward its mean is a
    one-shot adjustment), this is a flat, ongoing rate - a fee doesn't
    "revert," it just keeps applying - so there's no `reversion_years`
    division here.

One Monte Carlo simulation spans the entire horizon, exactly as
stock_forecast.py's own docstring describes (resampled historical return
blocks, rescaled to the GARCH/EWMA volatility estimate, with the
day-varying drift schedule applied on top) - see that module for the full
reasoning, unchanged here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from equicast_datafeed import DatafeedClient, round_value

from equicast_forecasting.etf_signals import compute_etf_signals
from equicast_forecasting.etf_type_registry import route_etf_type
from equicast_forecasting.monte_carlo import (
    DEFAULT_BLOCK_SIZE,
    DEFAULT_NUM_PATHS,
    monte_carlo_bands,
)
from equicast_forecasting.regimes import DAYS_PER_YEAR, drift_schedule, regime_for_day
from equicast_forecasting.volatility import daily_log_returns, estimate_daily_volatility


def _long_drift(expense_ratio: float | None) -> float:
    """The expense-ratio-drag daily log return: a fund's real annual
    expense ratio, spread evenly across every day (not just the long
    regime - see module docstring for why this doesn't scale by a
    reversion window the way stock's valuation-reversion bias does). `0.0`
    when `expense_ratio` is `None` (yfinance didn't report one)."""
    if expense_ratio is None:
        return 0.0
    return -expense_ratio / DAYS_PER_YEAR


def etf_price_bands(
    prices: list[dict[str, Any]],
    symbol: str,
    category: str | None,
    datafeed: DatafeedClient | None = None,
    years: int = 10,
    num_paths: int = DEFAULT_NUM_PATHS,
) -> list[dict[str, Any]]:
    """Project `years` years of daily probability bands (p10/p50/p90) for
    `symbol`, from real price history (`prices`, each needing at least
    `date`/`close` keys, the shape `ETFClient.prices()` already returns)
    plus whatever real ETF signals are available for `category`'s routed
    type (see etf_signals.py).

    Each returned record: `{ticker, etf_type, etf_type_key, date, p10,
    p50, p90, regime, volatility_model, expense_ratio, dividend_yield,
    nav_premium_discount, aggregate_pe, last_updated, source: "equicast"}`
    - `etf_type`/`etf_type_key` are the routed schema's own `label`/`key`
    (see etf_type_registry.EtfTypeSchema). Every one of the four signal
    fields (see etf_signals.compute_etf_signals) is independently `None`
    whenever yfinance doesn't report the underlying `.info` field for this
    ticker. Every field is a per-ticker constant, repeated on every daily
    row rather than split into a separate file - same reasoning
    stock_price_bands' own docstring gives (Parquet's dictionary/RLE
    encoding compresses a repeated constant column to almost nothing).

    Raises `etf_type_registry.UnroutableEtfTypeError` if `category` matches
    none of the three registered types - "fail loudly," per the issue
    (mirroring issue #66's own stock routing requirement), rather than
    ever guessing a generic template that doesn't fit. Raised *before*
    touching `prices` or fetching anything further, so an unroutable ETF
    fails fast.

    Returns `[]` for fewer than `DEFAULT_BLOCK_SIZE + 1` price records -
    not enough real history to draw even one resampled return block from,
    let alone estimate a meaningful GARCH/EWMA volatility.
    """
    schema = route_etf_type(category)

    if len(prices) < DEFAULT_BLOCK_SIZE + 1:
        return []

    sorted_prices = sorted(prices, key=lambda record: record["date"])
    closes = [record["close"] for record in sorted_prices]
    last_price = closes[-1]
    last_date = date.fromisoformat(sorted_prices[-1]["date"])

    volatility_estimate = estimate_daily_volatility(closes)
    historical_returns = daily_log_returns(closes)

    datafeed = datafeed or DatafeedClient()
    signals = compute_etf_signals(datafeed, symbol)

    num_days = years * DAYS_PER_YEAR
    daily_drift = drift_schedule(medium_drift=0.0, long_drift=_long_drift(signals["expense_ratio"]))

    bands = monte_carlo_bands(
        last_price,
        historical_returns,
        num_days,
        daily_drift=daily_drift,
        target_daily_volatility=volatility_estimate.daily_volatility,
        num_paths=num_paths,
    )

    fetched_at = datetime.now(UTC).isoformat()
    return [
        {
            "ticker": symbol.upper(),
            "etf_type": schema.label,
            "etf_type_key": schema.key,
            "date": (last_date + timedelta(days=band["day"])).isoformat(),
            "p10": round_value(band["p10"]),
            "p50": round_value(band["p50"]),
            "p90": round_value(band["p90"]),
            "regime": regime_for_day(band["day"]),
            "volatility_model": volatility_estimate.model,
            "expense_ratio": round_value(signals["expense_ratio"]),
            "dividend_yield": round_value(signals["dividend_yield"]),
            "nav_premium_discount": round_value(signals["nav_premium_discount"]),
            "aggregate_pe": round_value(signals["aggregate_pe"]),
            "last_updated": fetched_at,
            "source": "equicast",
        }
        for band in bands
    ]
