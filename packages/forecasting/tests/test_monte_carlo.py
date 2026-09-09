import numpy as np
import pytest
from equicast_forecasting.monte_carlo import block_bootstrap_log_returns, monte_carlo_bands


def _returns(n: int = 100, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0, 0.01, n)


def test_block_bootstrap_shape() -> None:
    rng = np.random.default_rng(1)
    result = block_bootstrap_log_returns(
        _returns(), num_days=50, num_paths=10, block_size=5, rng=rng
    )
    assert result.shape == (10, 50)


def test_block_bootstrap_raises_when_history_shorter_than_block_size() -> None:
    rng = np.random.default_rng(1)
    with pytest.raises(ValueError, match="at least 5"):
        block_bootstrap_log_returns(_returns(3), num_days=10, num_paths=5, block_size=5, rng=rng)


def test_block_bootstrap_reproducible_with_fixed_seed() -> None:
    result_a = block_bootstrap_log_returns(
        _returns(), num_days=30, num_paths=5, block_size=5, rng=np.random.default_rng(42)
    )
    result_b = block_bootstrap_log_returns(
        _returns(), num_days=30, num_paths=5, block_size=5, rng=np.random.default_rng(42)
    )
    np.testing.assert_array_equal(result_a, result_b)


def test_monte_carlo_bands_empty_for_zero_days() -> None:
    assert monte_carlo_bands(100.0, _returns(), num_days=0, seed=1) == []


def test_monte_carlo_bands_shape_and_ordering() -> None:
    bands = monte_carlo_bands(100.0, _returns(300), num_days=20, num_paths=200, seed=1)

    assert [b["day"] for b in bands] == list(range(1, 21))
    for band in bands:
        assert band["p10"] < band["p50"] < band["p90"]


def test_monte_carlo_bands_no_drift_stays_centered_near_last_price() -> None:
    bands = monte_carlo_bands(100.0, _returns(300), num_days=10, num_paths=3000, seed=1)
    # No drift and demeaned returns -> the median path shouldn't wander far
    # from the starting price over just 10 days.
    assert bands[-1]["p50"] == pytest.approx(100.0, rel=0.05)


def test_monte_carlo_bands_positive_drift_shifts_median_up() -> None:
    no_drift = monte_carlo_bands(100.0, _returns(300), num_days=60, num_paths=2000, seed=7)
    with_drift = monte_carlo_bands(
        100.0, _returns(300), num_days=60, daily_drift=lambda _day: 0.002, num_paths=2000, seed=7
    )

    assert with_drift[-1]["p50"] > no_drift[-1]["p50"]


def test_monte_carlo_bands_target_volatility_widens_band() -> None:
    quiet = monte_carlo_bands(
        100.0, _returns(300), num_days=30, target_daily_volatility=0.001, num_paths=2000, seed=3
    )
    loud = monte_carlo_bands(
        100.0, _returns(300), num_days=30, target_daily_volatility=0.05, num_paths=2000, seed=3
    )

    quiet_width = quiet[-1]["p90"] - quiet[-1]["p10"]
    loud_width = loud[-1]["p90"] - loud[-1]["p10"]
    assert loud_width > quiet_width


def test_monte_carlo_bands_reproducible_with_fixed_seed() -> None:
    a = monte_carlo_bands(100.0, _returns(200), num_days=15, num_paths=100, seed=99)
    b = monte_carlo_bands(100.0, _returns(200), num_days=15, num_paths=100, seed=99)
    assert a == b
