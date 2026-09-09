"""Generic block-bootstrap Monte Carlo probability-band construction -
asset-class-agnostic (only needs a historical daily log-return series, a
starting price, and an optional day-indexed drift function), so it's
reusable wherever a "simulate the future from resampled real history"
forecast is needed, not just stock (see stock_forecast.py, issue #66).

Complements bands.py's closed-form lognormal random walk rather than
replacing it: `bands.price_bands` assumes returns are i.i.d. normal with a
single constant volatility (fine for a short vol-forecast band); this
module instead resamples real historical return *blocks*, so the simulated
paths inherit whatever the real return distribution's actual shape is
(fat tails, skew, volatility clustering within a block) rather than
assuming normality.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

import numpy as np

#: Simulated paths per forecast - enough for stable 10th/90th-percentile
#: estimates (a small-sample percentile is noisy in the tails) without
#: making a 10-year daily simulation slow.
DEFAULT_NUM_PATHS = 2000

#: Contiguous trading-day block length resampled at a time - preserves
#: within-block volatility clustering/autocorrelation, unlike resampling
#: individual days independently. ~1 trading month.
DEFAULT_BLOCK_SIZE = 20

#: Percentiles returned per day - the same 10th/50th/90th set bands.py uses.
_PERCENTILES = {"p10": 10.0, "p50": 50.0, "p90": 90.0}


class PriceBand(TypedDict):
    day: int
    p10: float
    p50: float
    p90: float


def block_bootstrap_log_returns(
    daily_returns: np.ndarray,
    num_days: int,
    num_paths: int,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Simulate `num_paths` independent daily log-return paths of length
    `num_days`, each built by concatenating contiguous `block_size`-day
    blocks resampled (with replacement) from `daily_returns`. Returns a
    `(num_paths, num_days)` array of daily (not cumulative) log returns.

    Raises `ValueError` if `daily_returns` has fewer than `block_size`
    observations - there'd be no full block to draw.
    """
    if len(daily_returns) < block_size:
        raise ValueError(
            f"Need at least {block_size} historical daily returns to draw a block from, "
            f"got {len(daily_returns)}."
        )

    num_blocks_needed = -(-num_days // block_size)  # ceil division
    max_start = len(daily_returns) - block_size
    paths = np.empty((num_paths, num_blocks_needed * block_size), dtype=float)
    for path_index in range(num_paths):
        block_starts = rng.integers(0, max_start + 1, size=num_blocks_needed)
        paths[path_index] = np.concatenate(
            [daily_returns[start : start + block_size] for start in block_starts]
        )
    return paths[:, :num_days]


def monte_carlo_bands(
    last_price: float,
    historical_daily_returns: np.ndarray,
    num_days: int,
    daily_drift: Callable[[int], float] | None = None,
    target_daily_volatility: float | None = None,
    num_paths: int = DEFAULT_NUM_PATHS,
    block_size: int = DEFAULT_BLOCK_SIZE,
    seed: int | None = None,
) -> list[PriceBand]:
    """Return one `{day, p10, p50, p90}` record per day from 1 to
    `num_days`, built from `num_paths` simulated price paths: each day's
    return is resampled from real historical blocks (see
    `block_bootstrap_log_returns`), demeaned (so the resampled *shape* -
    volatility, fat tails - contributes without also leaking the sample
    window's own average return, which can be a fluke of *when* the lookback
    happens to start/end), then optionally rescaled to
    `target_daily_volatility` (e.g. a GARCH/EWMA forecast - see
    volatility.py - rather than trusting the resampled window's own
    historical volatility, which may not reflect current conditions) and
    shifted by `daily_drift(day)`'s running sum (0.0 for every day when
    omitted - a pure resampled random walk).

    `p10`/`p50`/`p90` are the 10th/50th/90th percentiles of the `num_paths`
    simulated price levels at each day - not a closed-form formula the way
    `bands.price_bands` is, so expect run-to-run sampling noise unless
    `seed` is fixed (tests should always fix it).
    """
    if num_days <= 0:
        return []

    rng = np.random.default_rng(seed)
    returns = np.asarray(historical_daily_returns, dtype=float)
    demeaned = returns - returns.mean()
    historical_volatility = float(demeaned.std())
    if target_daily_volatility is not None and historical_volatility > 0:
        demeaned = demeaned * (target_daily_volatility / historical_volatility)

    daily_log_returns = block_bootstrap_log_returns(demeaned, num_days, num_paths, block_size, rng)

    drift_fn = daily_drift if daily_drift is not None else (lambda _day: 0.0)
    cumulative_drift = np.cumsum([drift_fn(day) for day in range(1, num_days + 1)])

    cumulative_returns = np.cumsum(daily_log_returns, axis=1)
    price_paths = last_price * np.exp(cumulative_returns + cumulative_drift)

    percentiles = {
        quantile: np.percentile(price_paths, pct, axis=0) for quantile, pct in _PERCENTILES.items()
    }
    return [
        {
            "day": day + 1,
            "p10": float(percentiles["p10"][day]),
            "p50": float(percentiles["p50"][day]),
            "p90": float(percentiles["p90"][day]),
        }
        for day in range(num_days)
    ]
