"""Top-level benchmark (market index) forecast entry point (GitHub issue
#68): routes a benchmark to one of its per-index schemas
(benchmark_registry.py), then runs the same generic Monte Carlo engine
(monte_carlo.py) stock/ETF forecasting (issues #66/#67) already use into
one daily probability-band series, same output shape as stock/ETF/FX
forecasting.

Horizon regimes (identical day-boundaries to FX/stock/ETF - see
regimes.py):
  - 1w-1m ("short"): no directional drift. Volatility throughout the whole
    simulation is calibrated to a GARCH(1,1)-with-EWMA-fallback estimate
    (volatility.py) - same as every other equicast forecasting model.
  - 6m-2y ("medium"): Monte Carlo bootstrap, no bias - 0.0 drift, per the
    issue's own "Model split identical to stocks" note.
  - 3y-10y ("long"): Monte Carlo bootstrap + a CAPE/aggregate-PE
    valuation-reversion bias, per the issue's own table (`starting_cape`/
    `starting_pe_vs_own_longrun_avg` for every benchmark row) - same
    z-score-reverts-toward-its-mean shape as `stock_forecast.py`'s own
    `_long_drift` (see `VALUATION_REVERSION_STRENGTH` there for the honest
    "heuristic scaling coefficient, not rigorously derived" caveat, which
    applies here identically).

    Unlike stock (a real per-sector multiple z-score for 9/16 sectors) or
    even ETF (a real expense-ratio drag for every fund), **no benchmark
    gets a real bias today**: `cape_zscore` defaults to `None` and every
    caller today leaves it that way, because no real index-level
    valuation data source exists to compute one from - verified live
    against yfinance's `.info` for ^GSPC/^FTSE/^RUA/^N225/^GDAXI/^DJI/
    ^NDX, every one returns `None` for trailingPE/dividendYield/
    priceToBook/category. A raw index has no single issuer to report a
    P/E or CAPE for the way a stock or an ETF has. `cape_zscore` is kept
    as a real, explicit parameter (not inlined as a hardcoded 0.0) so a
    future real CAPE/aggregate-PE data source only needs to pass a value
    in here, exactly how FX forecasting's own `reer_deviation` (also
    always `None` today) is wired - see that module's docstring.

    `currency_drag_benefit` (the issue's own explicitly-required
    per-index, not-constant, FX-sensitivity parameter) is similarly
    unwired: each schema declares its own `currency_sensitivity`
    classification (benchmark_schemas.yaml - a real, per-index config
    value, satisfying the issue's own requirement), returned on every
    record, but with no real historical FX-correlation signal behind it
    yet to turn into an actual drift number.

One Monte Carlo simulation spans the entire horizon, exactly as
stock_forecast.py's/etf_forecast.py's own docstrings describe (resampled
historical return blocks, rescaled to the GARCH/EWMA volatility estimate,
with the day-varying drift schedule applied on top) - see those modules
for the full reasoning, unchanged here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from equicast_datafeed import round_value

from equicast_forecasting.benchmark_registry import route_benchmark
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

#: Same scaling coefficient stock_forecast.py uses for its own
#: valuation-reversion bias - an explicitly heuristic mapping of "stdevs
#: of multiple" onto "units of log-return", not a rigorously derived
#: economic relationship (see that module's own docstring for the full
#: caveat, which applies identically here). Shared rather than
#: re-declared so the two valuation-reversion models stay in lockstep if
#: this coefficient is ever tuned.
VALUATION_REVERSION_STRENGTH = 0.5


def _long_drift(cape_zscore: float | None, reversion_years: float) -> float:
    """The CAPE/aggregate-PE valuation-reversion-implied daily log
    return - `0.0` when `cape_zscore` is `None` (no real data source
    today - see module docstring) or there's no time left to revert over
    (`reversion_years <= 0`). Same formula as stock_forecast.py's own
    `_long_drift`."""
    if cape_zscore is None or reversion_years <= 0:
        return 0.0
    return -cape_zscore * VALUATION_REVERSION_STRENGTH / reversion_years / DAYS_PER_YEAR


def benchmark_price_bands(
    prices: list[dict[str, Any]],
    key: str,
    years: int = 10,
    num_paths: int = DEFAULT_NUM_PATHS,
    cape_zscore: float | None = None,
) -> list[dict[str, Any]]:
    """Project `years` years of daily probability bands (p10/p50/p90) for
    the benchmark identified by `key` (equicast_benchmark's own S3
    partition key, e.g. `"SP500"`), from real price history (`prices`,
    each needing at least `date`/`close` keys, the shape
    `BenchmarkClient.prices()` already returns).

    `cape_zscore` - a real CAPE/aggregate-PE z-score, once some future
    caller has a real data source to compute one from (see module
    docstring) - defaults to `None`, which degrades the long-horizon
    regime to a plain, unbiased Monte Carlo bootstrap.

    Each returned record: `{key, benchmark, currency_sensitivity, date,
    p10, p50, p90, regime, volatility_model, cape_zscore, last_updated,
    source: "equicast"}` - `benchmark`/`currency_sensitivity` are the
    routed schema's own `label`/`currency_sensitivity`
    (see benchmark_registry.BenchmarkSchema).

    Raises `benchmark_registry.UnroutableBenchmarkError` if `key` matches
    no registered benchmark - "fail loudly," per the issue (mirroring
    issues #66/#67's own routing requirement), rather than ever falling
    back to a generic template. Raised *before* touching `prices`, so an
    unroutable benchmark fails fast.

    Returns `[]` for fewer than `DEFAULT_BLOCK_SIZE + 1` price records -
    not enough real history to draw even one resampled return block from,
    let alone estimate a meaningful GARCH/EWMA volatility.
    """
    schema = route_benchmark(key)

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
    long_drift = _long_drift(cape_zscore, reversion_years)
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
            "key": schema.key,
            "benchmark": schema.label,
            "currency_sensitivity": schema.currency_sensitivity,
            "date": (last_date + timedelta(days=band["day"])).isoformat(),
            "p10": round_value(band["p10"]),
            "p50": round_value(band["p50"]),
            "p90": round_value(band["p90"]),
            "regime": regime_for_day(band["day"]),
            "volatility_model": volatility_estimate.model,
            "cape_zscore": round_value(cape_zscore),
            "last_updated": fetched_at,
            "source": "equicast",
        }
        for band in bands
    ]
