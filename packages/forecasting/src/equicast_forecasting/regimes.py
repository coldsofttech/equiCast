"""Generic day-indexed horizon-regime helpers: the short (1w-1m) / medium
(6m-2y) / long (3y-10y) split every equicast forecasting model (FX - see
fx_forecast.py - and stock - see stock_forecast.py) uses, plus a piecewise-
linear drift schedule stepping between a regime's own drift level and the
next rather than jumping discontinuously at the boundary. Pulled out of
fx_forecast.py once stock forecasting (issue #66) needed the exact same
day-boundary/tapering math for a completely different drift model
(interest-rate-parity/PPP for FX vs. Monte-Carlo valuation-reversion for
stock) - genuinely asset-class-agnostic, since it only operates on plain
day integers and drift *values*, never on what produced them.
"""

from __future__ import annotations

from collections.abc import Callable

#: End of the short (no-directional-drift) regime, in calendar days - the
#: "1w-1m" horizon, rounded up to a clean month.
SHORT_REGIME_END_DAYS = 30

#: End of the medium regime - the "6m-2y" horizon's upper bound.
MEDIUM_REGIME_END_DAYS = 730

#: Days over which one regime's drift linearly tapers into the next,
#: straddling each boundary above.
REGIME_TAPER_DAYS = 90

#: Trading/calendar convention used to convert an annualized rate into a
#: daily one - act/365.
DAYS_PER_YEAR = 365


def regime_for_day(day: int) -> str:
    """Which horizon regime `day` (1-indexed calendar days out from the
    last known price) falls into - `"short"`/`"medium"`/`"long"`."""
    if day <= SHORT_REGIME_END_DAYS:
        return "short"
    if day <= MEDIUM_REGIME_END_DAYS:
        return "medium"
    return "long"


def _taper(day: int, start: int, end: int, from_value: float, to_value: float) -> float:
    if day <= start:
        return from_value
    if day >= end:
        return to_value
    weight = (day - start) / (end - start)
    return from_value + weight * (to_value - from_value)


def drift_schedule(medium_drift: float, long_drift: float) -> Callable[[int], float]:
    """A day-indexed drift function stepping (with a linear taper at each
    boundary) from 0.0 (short regime - every equicast forecasting model
    treats this as a pure random walk, only ever a volatility forecast)
    to `medium_drift` to `long_drift`."""
    medium_taper_end = SHORT_REGIME_END_DAYS + REGIME_TAPER_DAYS
    long_taper_end = MEDIUM_REGIME_END_DAYS + REGIME_TAPER_DAYS

    def daily_drift(day: int) -> float:
        if day <= SHORT_REGIME_END_DAYS:
            return 0.0
        if day <= medium_taper_end:
            return _taper(day, SHORT_REGIME_END_DAYS, medium_taper_end, 0.0, medium_drift)
        if day <= MEDIUM_REGIME_END_DAYS:
            return medium_drift
        if day <= long_taper_end:
            return _taper(day, MEDIUM_REGIME_END_DAYS, long_taper_end, medium_drift, long_drift)
        return long_drift

    return daily_drift
