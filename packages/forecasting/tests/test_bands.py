from math import exp, log, sqrt

import pytest
from equicast_forecasting.bands import price_bands


def test_price_bands_pure_random_walk_widens_with_sqrt_time() -> None:
    bands = price_bands(last_price=100.0, daily_volatility=0.01, num_days=4)

    assert [b["day"] for b in bands] == [1, 2, 3, 4]
    for band in bands:
        assert band["p50"] == pytest.approx(100.0)
        # Band half-width (in log terms) grows with sqrt(day), not day itself.
        expected_half_width = 1.2815515655446004 * 0.01 * sqrt(band["day"])
        assert log(band["p90"] / 100.0) == pytest.approx(expected_half_width)
        assert log(band["p10"] / 100.0) == pytest.approx(-expected_half_width)


def test_price_bands_p10_lt_p50_lt_p90() -> None:
    bands = price_bands(last_price=1.30, daily_volatility=0.005, num_days=10)

    for band in bands:
        assert band["p10"] < band["p50"] < band["p90"]


def test_price_bands_zero_volatility_collapses_the_band() -> None:
    bands = price_bands(last_price=50.0, daily_volatility=0.0, num_days=3)

    for band in bands:
        assert band["p10"] == band["p50"] == band["p90"]


def test_price_bands_applies_cumulative_drift() -> None:
    daily_drift = 0.001
    bands = price_bands(
        last_price=100.0, daily_volatility=0.0, num_days=3, daily_drift=lambda _day: daily_drift
    )

    for band in bands:
        expected = 100.0 * exp(daily_drift * band["day"])
        assert band["p50"] == pytest.approx(expected)


def test_price_bands_drift_can_vary_by_day() -> None:
    # 0.0 drift on day 1, 0.01 from day 2 on - median should only move
    # starting day 2, and the day-2 move should be exactly 0.01 (not
    # 2 * 0.01, confirming cumulative drift sums the *daily* increments).
    def drift(day: int) -> float:
        return 0.0 if day == 1 else 0.01

    bands = price_bands(last_price=100.0, daily_volatility=0.0, num_days=3, daily_drift=drift)

    assert bands[0]["p50"] == pytest.approx(100.0)
    assert bands[1]["p50"] == pytest.approx(100.0 * exp(0.01))
    assert bands[2]["p50"] == pytest.approx(100.0 * exp(0.02))


def test_price_bands_empty_for_zero_days() -> None:
    assert price_bands(last_price=100.0, daily_volatility=0.01, num_days=0) == []
