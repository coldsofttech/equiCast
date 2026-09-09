"""Generic daily-volatility estimation from a price series - GARCH(1,1)
with an EWMA fallback. Asset-class-agnostic: only needs a chronological
list of closing prices, nothing FX/stock/etf-specific, so it's reusable
wherever a "vol-band around a price" forecast is needed (see bands.py for
the band-construction side of that)."""

from __future__ import annotations

import logging
from typing import NamedTuple

import numpy as np

logger = logging.getLogger(__name__)

#: RiskMetrics' own standard EWMA decay factor for daily volatility - the
#: most recent squared return is weighted `(1 - lambda_)`, decaying by
#: `lambda_` per day further back.
EWMA_LAMBDA = 0.94

#: How many of the earliest returns seed `ewma_volatility`'s initial
#: variance (a plain mean of squared returns) before the exponential decay
#: takes over - avoids the estimate being dominated by whichever single
#: return happens to come first.
EWMA_SEED_WINDOW = 20

#: Daily returns needed before a GARCH(1,1) fit is even attempted - fewer
#: than this and the MLE is unreliable/prone to non-convergence, so
#: `estimate_daily_volatility` skips straight to EWMA rather than wasting a
#: fit attempt likely to fail anyway.
GARCH_MIN_OBSERVATIONS = 250


class VolatilityEstimate(NamedTuple):
    daily_volatility: float
    model: str  # "garch" | "ewma"


def daily_log_returns(closes: list[float]) -> np.ndarray:
    """Daily log returns from a chronological list of closing prices -
    `len(closes) - 1` values, empty if `closes` has fewer than 2 prices."""
    if len(closes) < 2:
        return np.array([])
    prices = np.asarray(closes, dtype=float)
    return np.diff(np.log(prices))


def ewma_volatility(returns: np.ndarray, lambda_: float = EWMA_LAMBDA) -> float:
    """RiskMetrics-style exponentially-weighted daily volatility: seeds the
    variance from the mean squared return of the first `EWMA_SEED_WINDOW`
    observations (or all of them, if fewer), then recurses `variance =
    lambda_ * variance + (1 - lambda_) * return**2` forward through the
    rest - a simple, closed-form estimate needing no fitting, used as
    GARCH's fallback (too little history, or a non-converging fit).

    Returns 0.0 for fewer than 2 returns (nothing to estimate from).
    """
    if len(returns) < 2:
        return 0.0

    seed_window = min(EWMA_SEED_WINDOW, len(returns))
    variance = float(np.mean(returns[:seed_window] ** 2))
    for daily_return in returns[seed_window:]:
        variance = lambda_ * variance + (1 - lambda_) * daily_return**2
    return float(np.sqrt(variance))


def garch_volatility(returns: np.ndarray) -> float | None:
    """Fit a zero-mean GARCH(1,1) model to `returns` (daily FX/asset
    returns have no reliably estimable drift, so the mean is fixed at 0
    rather than fit) and forecast the next day's volatility.

    Returns `None` (never raises) for fewer than `GARCH_MIN_OBSERVATIONS`
    returns or a non-converging/erroring fit, so callers fall back to
    `ewma_volatility` instead of failing outright - GARCH fitting is
    numerically finicky on short or unusually quiet series.
    """
    if len(returns) < GARCH_MIN_OBSERVATIONS:
        return None

    try:
        from arch import arch_model  # imported lazily - only needed on this path

        # `arch`'s MLE optimizer is tuned for percentage-point-scale
        # returns and can fail to converge on raw (tiny, e.g. ~0.001)
        # fractional daily returns - scaling up by 100 and back down after
        # is `arch`'s own documented workaround, not a modeling choice.
        scaled_returns = returns * 100
        model = arch_model(scaled_returns, vol="GARCH", p=1, q=1, mean="Zero", rescale=False)
        result = model.fit(disp="off", show_warning=False)
        forecast = result.forecast(horizon=1, reindex=False)
        forecast_variance = float(forecast.variance.values[-1, 0])
        return float(np.sqrt(forecast_variance)) / 100
    except Exception:
        logger.warning("GARCH(1,1) fit failed; falling back to EWMA", exc_info=True)
        return None


def estimate_daily_volatility(closes: list[float]) -> VolatilityEstimate:
    """The best available daily volatility estimate for a price series: a
    real GARCH(1,1) fit when there's enough history for one to converge
    (see `garch_volatility`), EWMA otherwise (see `ewma_volatility`).
    """
    returns = daily_log_returns(closes)
    garch_estimate = garch_volatility(returns)
    if garch_estimate is not None:
        return VolatilityEstimate(garch_estimate, "garch")
    return VolatilityEstimate(ewma_volatility(returns), "ewma")
