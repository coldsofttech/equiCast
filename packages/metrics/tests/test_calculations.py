import pandas as pd
import pytest
from equicast_metrics.calculations import (
    annualized_volatility,
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
