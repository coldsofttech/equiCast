"""Generic daily probability-band construction: a lognormal random-walk
(GBM-style) price path with i.i.d. daily volatility and an optional,
day-varying drift schedule - the "random walk + vol band" framework the
GitHub issue this package implements calls for at the short horizon, kept
here asset-class-agnostic (it only needs a starting price, a daily
volatility, and an optional drift function) so a future stock/etf price
forecast can reuse it with its own volatility estimate and drift model,
not just FX's interest-rate-parity/PPP one (see fx_forecast.py)."""

from __future__ import annotations

from collections.abc import Callable
from math import exp, sqrt
from typing import TypedDict

#: 10th/50th/90th percentile z-scores of the standard normal distribution -
#: the exact set the issue asks for ("probability bands (e.g. 10th/50th/
#: 90th percentile), not point forecasts").
_Z_SCORES = {"p10": -1.2815515655446004, "p50": 0.0, "p90": 1.2815515655446004}


class PriceBand(TypedDict):
    day: int
    p10: float
    p50: float
    p90: float


def price_bands(
    last_price: float,
    daily_volatility: float,
    num_days: int,
    daily_drift: Callable[[int], float] | None = None,
) -> list[PriceBand]:
    """Return one `{day, p10, p50, p90}` record per day from 1 to
    `num_days` (`day=1` is the first forecast day after `last_price`'s own
    date), built as a lognormal random walk:

        price_q(day) = last_price * exp(cumulative_drift(day) + z_q * daily_volatility * sqrt(day))

    `daily_drift(day)` returns that day's expected daily log return - 0.0
    for a pure random walk with no directional edge (the short-horizon
    GARCH/EWMA vol-band case the issue calls for: a volatility forecast
    paired with a random walk, explicitly "not a directional return
    forecast"). Its running sum up to `day` shifts the whole distribution,
    while volatility scales with `sqrt(day)`, the standard i.i.d.-daily-
    returns assumption. Defaults to a pure random walk (`daily_drift=None`)
    when the caller has no directional model to layer in.

    This assumes daily volatility is constant over the whole horizon
    (typical for a random-walk band) rather than itself decaying at long
    horizons the way a genuinely mean-reverting process's variance would -
    a known simplification callers should account for via their own
    `daily_drift` (a reversion-implied drift narrows the *median* path's
    distance from the current price without this function needing to also
    narrow the *band width*).
    """
    drift_fn = daily_drift if daily_drift is not None else (lambda _day: 0.0)

    bands: list[PriceBand] = []
    cumulative_drift = 0.0
    for day in range(1, num_days + 1):
        cumulative_drift += drift_fn(day)
        vol_term = daily_volatility * sqrt(day)
        bands.append(
            {
                "day": day,
                "p10": last_price * exp(cumulative_drift + _Z_SCORES["p10"] * vol_term),
                "p50": last_price * exp(cumulative_drift + _Z_SCORES["p50"] * vol_term),
                "p90": last_price * exp(cumulative_drift + _Z_SCORES["p90"] * vol_term),
            }
        )
    return bands
