import pandas as pd
import pytest
from equicast_metrics.calculations import (
    annualized_volatility,
    buy_sell_volume_pressure,
    cagr,
    max_drawdown,
    sharpe_ratio,
    trailing_window,
)


def _series(values: list[float], start: str = "2020-01-01") -> pd.Series:
    index = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=index)


def test_annualized_volatility_of_constant_series_is_zero() -> None:
    assert annualized_volatility(_series([100.0] * 10)) == 0.0


def test_annualized_volatility_needs_at_least_two_returns() -> None:
    assert annualized_volatility(_series([100.0])) is None
    assert annualized_volatility(pd.Series(dtype=float)) is None


def test_sharpe_ratio_zero_volatility_is_none() -> None:
    assert sharpe_ratio(_series([100.0] * 10)) is None


def test_sharpe_ratio_needs_at_least_two_returns() -> None:
    assert sharpe_ratio(_series([100.0])) is None
    assert sharpe_ratio(pd.Series(dtype=float)) is None


def test_sharpe_ratio_positive_trend_is_positive() -> None:
    close = _series([100 + i for i in range(300)])
    assert sharpe_ratio(close) > 0


def test_max_drawdown_of_monotonically_increasing_series_is_zero() -> None:
    assert max_drawdown(_series([100, 110, 120, 130])) == 0.0


def test_max_drawdown_detects_peak_to_trough_decline() -> None:
    close = _series([100, 120, 90, 110])
    # peak 120 -> trough 90: (90 - 120) / 120 = -0.25
    assert max_drawdown(close) == pytest.approx(-0.25)


def test_max_drawdown_empty_series_is_none() -> None:
    assert max_drawdown(pd.Series(dtype=float)) is None


def test_cagr_exact_one_year_doubling() -> None:
    index = pd.date_range("2020-01-01", "2021-01-01", freq="D")
    close = pd.Series([100.0] * (len(index) - 1) + [200.0], index=index)

    assert cagr(close, years=1) == pytest.approx(1.0, rel=1e-2)


def test_cagr_returns_none_when_not_enough_history() -> None:
    close = _series([100, 101, 102], start="2025-01-01")
    assert cagr(close, years=5) is None


def test_cagr_empty_series_is_none() -> None:
    assert cagr(pd.Series(dtype=float), years=1) is None


def test_trailing_window_slices_by_calendar_date() -> None:
    close = _series(list(range(800)))
    window = trailing_window(close, years=1)

    assert window.index.min() > close.index[-1] - pd.DateOffset(years=1)
    assert window.index[-1] == close.index[-1]


def test_trailing_window_empty_series() -> None:
    assert trailing_window(pd.Series(dtype=float), years=1).empty


def test_trailing_window_slices_a_dataframe_the_same_way_as_a_series() -> None:
    close = _series(list(range(800)))
    df = pd.DataFrame({"Close": close})

    window = trailing_window(df, years=1)

    assert window.index.min() > close.index[-1] - pd.DateOffset(years=1)
    assert window.index[-1] == close.index[-1]


def test_buy_sell_volume_pressure_all_closes_at_high_is_all_buyers() -> None:
    high = pd.Series([100.0, 101.0, 102.0])
    low = pd.Series([90.0, 91.0, 92.0])
    close = high  # every bar closes at its own high
    volume = pd.Series([1000, 2000, 3000])

    buyers_pct, sellers_pct = buy_sell_volume_pressure(high, low, close, volume)

    assert buyers_pct == pytest.approx(1.0)
    assert sellers_pct == pytest.approx(0.0)


def test_buy_sell_volume_pressure_all_closes_at_low_is_all_sellers() -> None:
    high = pd.Series([100.0, 101.0, 102.0])
    low = pd.Series([90.0, 91.0, 92.0])
    close = low  # every bar closes at its own low
    volume = pd.Series([1000, 2000, 3000])

    buyers_pct, sellers_pct = buy_sell_volume_pressure(high, low, close, volume)

    assert buyers_pct == pytest.approx(0.0)
    assert sellers_pct == pytest.approx(1.0)


def test_buy_sell_volume_pressure_mid_range_close_splits_evenly() -> None:
    high = pd.Series([100.0])
    low = pd.Series([90.0])
    close = pd.Series([95.0])  # exact midpoint: multiplier is 0
    volume = pd.Series([1000])

    # A zero multiplier contributes to neither side, so total money-flow
    # volume is 0 - same "nothing meaningful to compute" case as no volume
    # at all.
    assert buy_sell_volume_pressure(high, low, close, volume) == (None, None)


def test_buy_sell_volume_pressure_flat_bar_does_not_raise() -> None:
    # high == low would otherwise divide by zero.
    high = pd.Series([100.0, 105.0])
    low = pd.Series([100.0, 95.0])
    close = pd.Series([100.0, 105.0])
    volume = pd.Series([1000, 500])

    buyers_pct, sellers_pct = buy_sell_volume_pressure(high, low, close, volume)

    assert buyers_pct == pytest.approx(1.0)  # the flat bar contributes nothing either way
    assert sellers_pct == pytest.approx(0.0)


def test_buy_sell_volume_pressure_empty_series_is_none() -> None:
    empty = pd.Series(dtype=float)
    assert buy_sell_volume_pressure(empty, empty, empty, empty) == (None, None)


def test_buy_sell_volume_pressure_no_volume_is_none() -> None:
    high = pd.Series([100.0, 101.0])
    low = pd.Series([90.0, 91.0])
    close = pd.Series([100.0, 101.0])
    volume = pd.Series([0, 0])

    assert buy_sell_volume_pressure(high, low, close, volume) == (None, None)
