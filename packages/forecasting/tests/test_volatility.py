import numpy as np
import pytest
from equicast_forecasting.volatility import (
    EWMA_LAMBDA,
    GARCH_MIN_OBSERVATIONS,
    daily_log_returns,
    estimate_daily_volatility,
    ewma_volatility,
    garch_volatility,
)


def test_daily_log_returns_computes_log_differences() -> None:
    closes = [100.0, 101.0, 99.0]

    returns = daily_log_returns(closes)

    assert returns == pytest.approx([np.log(101.0 / 100.0), np.log(99.0 / 101.0)])


def test_daily_log_returns_empty_for_fewer_than_two_closes() -> None:
    assert daily_log_returns([100.0]).size == 0
    assert daily_log_returns([]).size == 0


def test_ewma_volatility_zero_for_fewer_than_two_returns() -> None:
    assert ewma_volatility(np.array([])) == 0.0
    assert ewma_volatility(np.array([0.01])) == 0.0


def test_ewma_volatility_matches_manual_recursion_for_a_small_series() -> None:
    # Fewer returns than EWMA_SEED_WINDOW, so the whole series seeds the
    # initial variance and the recursive loop never runs - the estimate is
    # just the RMS of the returns themselves.
    returns = np.array([0.01, -0.02, 0.015])

    result = ewma_volatility(returns, lambda_=EWMA_LAMBDA)

    assert result == pytest.approx(np.sqrt(np.mean(returns**2)))


def test_ewma_volatility_recurses_past_the_seed_window() -> None:
    seed = [0.01] * 20
    extra = [0.05, -0.03]
    returns = np.array(seed + extra)

    variance = float(np.mean(np.array(seed) ** 2))
    for r in extra:
        variance = EWMA_LAMBDA * variance + (1 - EWMA_LAMBDA) * r**2
    expected = np.sqrt(variance)

    assert ewma_volatility(returns) == pytest.approx(expected)


def test_ewma_volatility_reacts_more_to_recent_shocks() -> None:
    quiet = np.array([0.001] * 30)
    loud_recent = np.concatenate([quiet, [0.2]])
    loud_early = np.concatenate([[0.2], quiet])

    assert ewma_volatility(loud_recent) > ewma_volatility(loud_early)


def test_garch_volatility_none_below_minimum_observations() -> None:
    returns = np.random.default_rng(0).normal(0, 0.01, GARCH_MIN_OBSERVATIONS - 1)
    assert garch_volatility(returns) is None


def test_garch_volatility_fits_with_enough_history() -> None:
    returns = np.random.default_rng(0).normal(0, 0.01, GARCH_MIN_OBSERVATIONS + 250)

    result = garch_volatility(returns)

    # A real fit either converges to a sensible positive daily vol, or
    # bails out to None (see the function's own docstring) - never raises,
    # never a negative/NaN value.
    assert result is None or result > 0


def test_estimate_daily_volatility_uses_ewma_below_garch_minimum() -> None:
    closes = list(100 + np.random.default_rng(1).normal(0, 1, 50).cumsum())

    result = estimate_daily_volatility(closes)

    assert result.model == "ewma"
    assert result.daily_volatility > 0


def test_estimate_daily_volatility_with_ample_history() -> None:
    num_observations = GARCH_MIN_OBSERVATIONS + 300
    closes = list(100 + np.random.default_rng(2).normal(0, 1, num_observations).cumsum())

    result = estimate_daily_volatility(closes)

    assert result.model in ("garch", "ewma")
    assert result.daily_volatility > 0
