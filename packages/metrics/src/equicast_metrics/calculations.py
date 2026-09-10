"""Pure functions for volatility, Sharpe ratio, max drawdown, CAGR, and
buy/sell volume pressure.

Most of these take a `pandas.Series` of close prices indexed by date;
`buy_sell_volume_pressure` additionally needs high/low/volume, so it takes
those as separate Series sharing the same index instead. All return `None`
when there isn't enough history to compute a meaningful result.
"""

from __future__ import annotations

import math

import pandas as pd
from equicast_datafeed import round_value

TRADING_DAYS_PER_YEAR = 252


def trailing_window(data: pd.Series | pd.DataFrame, years: int = 1) -> pd.Series | pd.DataFrame:
    """Slice `data` (a close-price Series, or a full OHLCV DataFrame) to the
    trailing `years`, by calendar date (not row count) — the slicing only
    ever touches `data`'s own index, so a Series and a DataFrame work
    identically here."""
    if data.empty:
        return data
    cutoff = data.index[-1] - pd.DateOffset(years=years)
    return data[data.index > cutoff]


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


def buy_sell_volume_pressure(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series
) -> tuple[float | None, float | None]:
    """Buyers vs sellers volume pressure over the given window, as
    `(buyers_pct, sellers_pct)` fractions (e.g. 0.62/0.38) that always sum to
    1 — a technical proxy for order-flow sentiment derived from OHLCV data,
    not literal buy/sell order counts (yfinance/Yahoo has no real
    order-book data).

    Chaikin Money Flow's own money-flow-multiplier: for each bar, where the
    close landed within that bar's own high-low range (+1 at the high, all
    buying pressure; -1 at the low, all selling pressure; 0 mid-range),
    multiplied by that bar's volume to get "money flow volume", then summed
    separately for positive ("buying") and negative ("selling") flows across
    the whole window. Each side's share of the combined total is its pct. A
    flat bar (high == low, so the multiplier is undefined) contributes 0
    either way rather than raising - same as a bar with 0 volume would.

    Returns `(None, None)` when there's nothing to compute a meaningful
    split from - an empty window, or every bar's buying/selling volume
    landing at exactly 0 (e.g. no volume recorded at all) - same "not
    enough history" contract as this module's other functions.
    """
    if close.empty:
        return None, None

    range_hl = (high - low).replace(0, float("nan"))
    mf_multiplier = (((close - low) - (high - close)) / range_hl).fillna(0)
    mf_volume = mf_multiplier * volume

    buying_volume = float(mf_volume[mf_volume > 0].sum())
    selling_volume = float(-mf_volume[mf_volume < 0].sum())
    total = buying_volume + selling_volume
    if total <= 0:
        return None, None

    buyers_pct = buying_volume / total
    return round_value(buyers_pct), round_value(1 - buyers_pct)
