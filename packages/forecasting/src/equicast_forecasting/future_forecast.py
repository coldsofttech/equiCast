"""Top-level futures forecast entry point (GitHub issue #143): routes a
future to one of 5 commodity-class schemas (commodity_registry.py), then
runs the same generic Monte Carlo engine (monte_carlo.py) stock/ETF/
benchmark forecasting (issues #66/#67/#68) already use into one daily
probability-band series, same output shape as stock/ETF/benchmark/FX
forecasting.

Horizon regimes (identical day-boundaries to FX/stock/ETF/benchmark - see
regimes.py):
  - 1w-1m ("short"): no directional drift. Volatility throughout the whole
    simulation is calibrated to a GARCH(1,1)-with-EWMA-fallback estimate
    (volatility.py) - same as every other equicast forecasting model, and
    exactly what the issue calls for ("GARCH+EWMA fallback (short)").
  - 6m-2y ("medium"): Monte Carlo bootstrap, no bias - 0.0 drift, per the
    issue's own "Same two-model skeleton" note.
  - 3y-10y ("long"): Monte Carlo bootstrap + a reversion bias - but per
    the issue's own explicit instruction, **not** a valuation multiple:
    "the long-horizon reversion target is curve-implied fair value /
    cost-of-carry, not a valuation multiple like stocks use. Don't reuse
    starting_pe_vs_history-style fields here; the schema needs its own
    reversion-anchor field (e.g. basis_vs_cost_of_carry)." `basis_vs_cost_
    of_carry` is that field: conceptually, how far the futures price sits
    from what the cost-of-carry model (spot + storage + financing costs,
    for a storable commodity) implies it "should" be - a positive value
    (futures rich vs. fair value) implies expected downward reversion,
    same z-score-reverts-toward-its-mean shape stock_forecast.py's own
    `_long_drift` uses for its valuation multiple (see
    `VALUATION_REVERSION_STRENGTH` there for the honest "heuristic scaling
    coefficient, not rigorously derived" caveat, which applies here
    identically).

    **No future gets a real bias today**: `basis_vs_cost_of_carry`
    defaults to `None` and every caller today leaves it that way. Per the
    issue's own explicitly-flagged data gap: "USDA WASDE, EIA inventory,
    and CFTC COT reports are not available via yfinance - yfinance gives
    OHLC futures price history only. This issue should ship with those
    fields defaulting to None/unavailable... with a follow-up issue for
    wiring real data sources." Spot commodity prices and storage/financing
    cost data (needed to compute a real cost-of-carry fair value) are
    equally unavailable today - `equicast_future.FutureClient.profile()`
    mirrors `BenchmarkClient`'s own shape exactly (no fundamentals field
    at all, verified live: yfinance's `.info` for GC=F/CL=F/NG=F/ZW=F
    reports no spot/storage/financing data any more than a raw index
    ticker does). `basis_vs_cost_of_carry` is kept as a real, explicit
    parameter (not inlined as a hardcoded 0.0) so a future real data
    source (a spot-price feed plus a storage/financing cost model) only
    needs to pass a value in here, exactly how FX forecasting's own
    `reer_deviation` (also always `None` today) is wired.

Continuous-contract-construction caveat (verified per the issue's own
"should be verified/documented before backtesting" instruction): checked
live 2-year daily return distributions for GC=F/CL=F/NG=F. GC=F (gold) is
comparatively clean - 4 of 504 trading days moved >5%. CL=F (WTI crude)
had 35 such days, and NG=F (natural gas) had 97 (~19% of trading days),
with a single-day move as large as 47%. The jump dates don't cluster on a
fixed day-of-month across contracts the way a purely mechanical,
un-back-adjusted monthly roll would (that would produce near-identical
calendar spacing every month) - more consistent with genuine commodity
event-driven volatility (natural gas is a famously volatile market) than
a systematic roll artifact, but yfinance doesn't publicly document its
"=F" continuous-contract construction methodology (back-adjusted vs.
raw-spliced), so this can't be fully ruled out either. Flagged here,
unresolved, exactly as the issue asks - the GARCH/EWMA volatility
estimate and Monte Carlo bootstrap both use this same price history
as-is, so if roll jumps ever turn out to be a real, still-present
contributor, they'd currently be feeding directly into both.

One Monte Carlo simulation spans the entire horizon, exactly as
stock_forecast.py's/etf_forecast.py's/benchmark_forecast.py's own
docstrings describe (resampled historical return blocks, rescaled to the
GARCH/EWMA volatility estimate, with the day-varying drift schedule
applied on top) - see those modules for the full reasoning, unchanged
here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from equicast_datafeed import round_value

from equicast_forecasting.commodity_registry import route_commodity_class
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
from equicast_forecasting.volatility import daily_log_returns, estimate_daily_volatility

#: Same scaling coefficient stock_forecast.py/benchmark_forecast.py use
#: for their own valuation-reversion biases - an explicitly heuristic
#: mapping, not a rigorously derived economic relationship (see those
#: modules' own docstrings for the full caveat, which applies identically
#: here). Shared in spirit rather than imported, since a fresh, futures-
#: specific coefficient may need its own tuning once real cost-of-carry
#: data exists - unlike the stock/benchmark cases, there's no shared
#: financial-statement-derived multiple family to keep in lockstep with.
BASIS_REVERSION_STRENGTH = 0.5


def _long_drift(basis_vs_cost_of_carry: float | None, reversion_years: float) -> float:
    """The cost-of-carry-reversion-implied daily log return - `0.0` when
    `basis_vs_cost_of_carry` is `None` (no real data source today - see
    module docstring) or there's no time left to revert over
    (`reversion_years <= 0`). Same formula shape as stock_forecast.py's
    own `_long_drift`/benchmark_forecast.py's own `_long_drift`."""
    if basis_vs_cost_of_carry is None or reversion_years <= 0:
        return 0.0
    return -basis_vs_cost_of_carry * BASIS_REVERSION_STRENGTH / reversion_years / DAYS_PER_YEAR


def future_price_bands(
    prices: list[dict[str, Any]],
    key: str,
    years: int = 10,
    num_paths: int = DEFAULT_NUM_PATHS,
    basis_vs_cost_of_carry: float | None = None,
) -> list[dict[str, Any]]:
    """Project `years` years of daily probability bands (p10/p50/p90) for
    the future identified by `key` (equicast_future's own S3 partition
    key, e.g. `"GOLD"`), from real price history (`prices`, each needing
    at least `date`/`close` keys, the shape `FutureClient.prices()`
    already returns).

    `basis_vs_cost_of_carry` - a real curve-implied fair-value gap, once
    some future caller has a real data source to compute one from (see
    module docstring) - defaults to `None`, which degrades the long-
    horizon regime to a plain, unbiased Monte Carlo bootstrap.

    Each returned record: `{key, commodity_class, date, p10, p50, p90,
    regime, volatility_model, basis_vs_cost_of_carry, last_updated,
    source: "equicast"}` - `commodity_class` is the routed schema's own
    `label` (see commodity_registry.CommodityClassSchema).

    Raises `commodity_registry.UnroutableCommodityError` if `key` matches
    no registered commodity class - "fail loudly," per the issue
    (mirroring issues #66/#67/#68's own routing requirement), rather than
    ever falling back to a generic template. Raised *before* touching
    `prices`, so an unroutable future fails fast.

    Returns `[]` for fewer than `DEFAULT_BLOCK_SIZE + 1` price records -
    not enough real history to draw even one resampled return block from,
    let alone estimate a meaningful GARCH/EWMA volatility.
    """
    schema = route_commodity_class(key)

    if len(prices) < DEFAULT_BLOCK_SIZE + 1:
        return []

    sorted_prices = sorted(prices, key=lambda record: record["date"])
    closes = [record["close"] for record in sorted_prices]
    last_price = closes[-1]
    last_date = date.fromisoformat(sorted_prices[-1]["date"])

    volatility_estimate = estimate_daily_volatility(closes)
    historical_returns = daily_log_returns(closes)

    num_days = years * DAYS_PER_YEAR
    reversion_years = (num_days - MEDIUM_REGIME_END_DAYS) / DAYS_PER_YEAR
    long_drift = _long_drift(basis_vs_cost_of_carry, reversion_years)
    daily_drift = drift_schedule(medium_drift=0.0, long_drift=long_drift)

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
            "key": key.upper(),
            "commodity_class": schema.label,
            "date": (last_date + timedelta(days=band["day"])).isoformat(),
            "p10": round_value(band["p10"]),
            "p50": round_value(band["p50"]),
            "p90": round_value(band["p90"]),
            "regime": regime_for_day(band["day"]),
            "volatility_model": volatility_estimate.model,
            "basis_vs_cost_of_carry": round_value(basis_vs_cost_of_carry),
            "last_updated": fetched_at,
            "source": "equicast",
        }
        for band in bands
    ]
