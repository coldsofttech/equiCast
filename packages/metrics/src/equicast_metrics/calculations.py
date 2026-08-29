"""Pure functions for volatility, Sharpe ratio, max drawdown, and CAGR.

All take a `pandas.Series` of close prices indexed by date, and return `None`
when there isn't enough history to compute a meaningful result.
"""

from __future__ import annotations

import math

import pandas as pd
from equicast_datafeed import round_value

TRADING_DAYS_PER_YEAR = 252


def trailing_window(close: pd.Series, years: int = 1) -> pd.Series:
    """Slice `close` to the trailing `years`, by calendar date (not row count)."""
    if close.empty:
        return close
    cutoff = close.index[-1] - pd.DateOffset(years=years)
    return close[close.index > cutoff]


def annualized_volatility(close: pd.Series) -> float | None:
    """Annualized standard deviation of daily returns."""
    returns = close.pct_change().dropna()
    if len(returns) < 2:
        return None
    return round_value(float(returns.std() * math.sqrt(TRADING_DAYS_PER_YEAR)))


def sharpe_ratio(close: pd.Series, risk_free_rate: float = 0.0) -> float | None:
    """Annualized Sharpe ratio from daily returns; `risk_free_rate` is annual."""
    returns = close.pct_change().dropna()
    if len(returns) < 2 or returns.std() == 0:
        return None
    daily_risk_free = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_returns = returns - daily_risk_free
    return round_value(
        float((excess_returns.mean() / returns.std()) * math.sqrt(TRADING_DAYS_PER_YEAR))
    )


def max_drawdown(close: pd.Series) -> float | None:
    """Largest peak-to-trough decline, as a negative fraction (e.g. -0.25)."""
    if close.empty:
        return None
    running_max = close.cummax()
    drawdown = (close - running_max) / running_max
    return round_value(float(drawdown.min()))


def cagr(close: pd.Series, years: int) -> float | None:
    """Compound annual growth rate over the trailing `years`.

    Returns `None` if `close` doesn't have history reaching back that far.
    """
    if close.empty:
        return None

    end_date = close.index[-1]
    start_cutoff = end_date - pd.DateOffset(years=years)
    if close.index[0] > start_cutoff:
        return None

    window = close[close.index <= start_cutoff]
    if window.empty:
        return None

    start_price = float(window.iloc[-1])
    end_price = float(close.iloc[-1])
    if start_price <= 0:
        return None

    return round_value((end_price / start_price) ** (1 / years) - 1)
