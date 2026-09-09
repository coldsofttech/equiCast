"""Top-level stock forecast entry point (GitHub issue #66): routes a stock
to one of 16 sector/sub-sector schemas (sector_registry.py), then combines
the generic Monte Carlo engine (monte_carlo.py) with a real, per-sector
valuation-reversion bias (fundamentals_signals.py) into one daily
probability-band series - same output shape as FX forecasting's
`fx_price_bands()` (issue #65; see that module's docstring for why one row
per calendar day, not per named horizon).

Horizon regimes (identical day-boundaries to FX - see regimes.py):
  - 1w-1m ("short"): no directional drift. Volatility throughout the whole
    simulation is calibrated to a GARCH(1,1)-with-EWMA-fallback estimate
    (volatility.py) - literally what the issue calls for at this horizon.
  - 6m-2y ("medium"): Monte Carlo bootstrap, explicitly no valuation bias
    (per the issue's own notes) - 0.0 drift.
  - 3y-10y ("long"): Monte Carlo bootstrap + valuation-reversion bias, from
    a real starting-multiple z-score when this sector has one wired up
    (see `sector_registry.SectorSchema.valuation_multiple` /
    `fundamentals_signals.compute_valuation_signal`) - 0.0 drift otherwise
    (today: Healthcare - Pharma/Devices, Healthcare - Biotech, Real Estate
    - REIT (equity), and Energy have no real multiple source yet - see
    sector_schemas.yaml).

One Monte Carlo simulation spans the *entire* horizon (not three
separately-stitched model types): resampled historical return blocks,
rescaled to the GARCH/EWMA volatility estimate (so the short-horizon
behavior really does reflect "GARCH/EWMA," not just the sample's own
historical volatility), with the day-varying drift schedule
(`regimes.drift_schedule`) applied on top. This avoids an artificial seam
between structurally different model types at the regime boundaries, at
the cost of the short-horizon band being sampled (Monte Carlo) rather than
FX's closed-form lognormal formula (bands.py) - a deliberate
simplification, not an oversight; a large `num_paths` keeps the sampling
noise small.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from equicast_datafeed import DatafeedClient, round_value

from equicast_forecasting.fundamentals_signals import (
    compute_fundamental_signals,
    compute_valuation_signal,
)
from equicast_forecasting.monte_carlo import (
    DEFAULT_BLOCK_SIZE,
    DEFAULT_NUM_PATHS,
    monte_carlo_bands,
)
from equicast_forecasting.regimes import (
    DAYS_PER_YEAR,
    MEDIUM_REGIME_END_DAYS,
    drift_schedule,
    regime_for_day,
)
from equicast_forecasting.sector_registry import route_sector
from equicast_forecasting.volatility import daily_log_returns, estimate_daily_volatility

#: How much of the valuation z-score's implied gap the long-horizon median
#: path closes over the reversion window - a scaling coefficient mapping
#: "stdevs of multiple" onto "units of log-return", not a rigorously
#: derived economic relationship (that would need the multiple's own
#: volatility relative to price's, which the coarse annual-resolution
#: historical series in fundamentals_signals.py doesn't support estimating
#: reliably). Deliberately conservative - this is a gentle bias, not a
#: prediction that the multiple snaps back to its mean by a fixed date.
VALUATION_REVERSION_STRENGTH = 0.5


def _long_drift(zscore: float | None, reversion_years: float) -> float:
    """The valuation-reversion-implied daily log return: a positive
    z-score (today's multiple sits above its own historical average -
    "rich") implies expected price underperformance as the multiple
    reverts toward its mean, and vice versa for a negative (cheap) one -
    see `VALUATION_REVERSION_STRENGTH`'s docstring for the honest caveat
    about this mapping. Spread evenly (as a constant daily log return)
    over `reversion_years`.

    0.0 when `zscore` is `None` (no real multiple for this sector, or too
    little historical data to compute one) or there's no time left to
    revert over (`reversion_years <= 0`).
    """
    if zscore is None or reversion_years <= 0:
        return 0.0
    return -zscore * VALUATION_REVERSION_STRENGTH / reversion_years / DAYS_PER_YEAR


def stock_price_bands(
    prices: list[dict[str, Any]],
    symbol: str,
    sector: str | None,
    industry: str | None,
    datafeed: DatafeedClient | None = None,
    years: int = 10,
    num_paths: int = DEFAULT_NUM_PATHS,
) -> list[dict[str, Any]]:
    """Project `years` years of daily probability bands (p10/p50/p90) for
    `symbol`, from real price history (`prices`, each needing at least
    `date`/`close` keys, the shape `StockClient.prices()` already returns)
    plus whatever real fundamentals data is available for `sector`/
    `industry`'s routed schema (see fundamentals_signals.py).

    Each returned record: `{ticker, sector, sub_sector, date, p10, p50,
    p90, regime, volatility_model, valuation_multiple_family,
    valuation_multiple, valuation_zscore, revenue_cagr,
    profit_margin_trend, rd_to_revenue, short_interest_ratio,
    last_updated, source: "equicast"}` - `sector`/`sub_sector` are the
    routed schema's own `label`/`key` (see sector_registry.SectorSchema),
    not necessarily `sector`/`industry` verbatim. `valuation_multiple_
    family`/`valuation_multiple`/`valuation_zscore` are all `None`
    together when this sector has no real multiple wired up yet (see
    module docstring); the four fundamentals-signal fields (see
    fundamentals_signals.compute_fundamental_signals) are independently
    `None` whenever yfinance doesn't report the underlying line item for
    this ticker (e.g. `rd_to_revenue` for a non-R&D-reporting company).
    Every one of these nine fields is a per-ticker constant, repeated on
    every daily row rather than split into a separate file - simpler, and
    Parquet's own dictionary/RLE encoding compresses a repeated constant
    column to almost nothing.

    Raises `sector_registry.UnroutableSectorError` if `sector`/`industry`
    matches none of the 16 registered schemas - "fail loudly," per the
    issue, rather than ever guessing a generic template that doesn't fit.
    Raised *before* touching `prices` or fetching anything further, so an
    unroutable ticker fails fast.

    Returns `[]` for fewer than `DEFAULT_BLOCK_SIZE + 1` price records -
    not enough real history to draw even one resampled return block from,
    let alone estimate a meaningful GARCH/EWMA volatility.
    """
    schema = route_sector(sector, industry)

    if len(prices) < DEFAULT_BLOCK_SIZE + 1:
        return []

    sorted_prices = sorted(prices, key=lambda record: record["date"])
    closes = [record["close"] for record in sorted_prices]
    last_price = closes[-1]
    last_date = date.fromisoformat(sorted_prices[-1]["date"])

    volatility_estimate = estimate_daily_volatility(closes)
    historical_returns = daily_log_returns(closes)

    datafeed = datafeed or DatafeedClient()
    current_multiple, zscore = compute_valuation_signal(
        schema.valuation_multiple, datafeed, symbol, sorted_prices
    )
    fundamental_signals = compute_fundamental_signals(datafeed, symbol)

    num_days = years * DAYS_PER_YEAR
    reversion_years = (num_days - MEDIUM_REGIME_END_DAYS) / DAYS_PER_YEAR
    daily_drift = drift_schedule(medium_drift=0.0, long_drift=_long_drift(zscore, reversion_years))

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
            "sector": schema.label,
            "sub_sector": schema.key,
            "date": (last_date + timedelta(days=band["day"])).isoformat(),
            "p10": round_value(band["p10"]),
            "p50": round_value(band["p50"]),
            "p90": round_value(band["p90"]),
            "regime": regime_for_day(band["day"]),
            "volatility_model": volatility_estimate.model,
            "valuation_multiple_family": schema.valuation_multiple,
            "valuation_multiple": round_value(current_multiple),
            "valuation_zscore": round_value(zscore),
            "revenue_cagr": round_value(fundamental_signals["revenue_cagr"]),
            "profit_margin_trend": round_value(fundamental_signals["profit_margin_trend"]),
            "rd_to_revenue": round_value(fundamental_signals["rd_to_revenue"]),
            "short_interest_ratio": round_value(fundamental_signals["short_interest_ratio"]),
            "last_updated": fetched_at,
            "source": "equicast",
        }
        for band in bands
    ]
