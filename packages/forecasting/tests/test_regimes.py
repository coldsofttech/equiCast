import pytest
from equicast_forecasting.regimes import (
    MEDIUM_REGIME_END_DAYS,
    REGIME_TAPER_DAYS,
    SHORT_REGIME_END_DAYS,
    drift_schedule,
    regime_for_day,
)


def test_regime_for_day_boundaries() -> None:
    assert regime_for_day(1) == "short"
    assert regime_for_day(SHORT_REGIME_END_DAYS) == "short"
    assert regime_for_day(SHORT_REGIME_END_DAYS + 1) == "medium"
    assert regime_for_day(MEDIUM_REGIME_END_DAYS) == "medium"
    assert regime_for_day(MEDIUM_REGIME_END_DAYS + 1) == "long"


def test_drift_schedule_zero_through_short_regime() -> None:
    schedule = drift_schedule(medium_drift=0.01, long_drift=0.02)
    for day in range(1, SHORT_REGIME_END_DAYS + 1):
        assert schedule(day) == 0.0


def test_drift_schedule_reaches_medium_drift_after_taper() -> None:
    schedule = drift_schedule(medium_drift=0.01, long_drift=0.02)
    taper_end = SHORT_REGIME_END_DAYS + REGIME_TAPER_DAYS
    assert schedule(taper_end) == pytest.approx(0.01)
    assert schedule(MEDIUM_REGIME_END_DAYS) == pytest.approx(0.01)


def test_drift_schedule_tapers_linearly_between_regimes() -> None:
    schedule = drift_schedule(medium_drift=0.01, long_drift=0.02)
    midpoint = SHORT_REGIME_END_DAYS + REGIME_TAPER_DAYS // 2
    assert schedule(midpoint) == pytest.approx(0.005, abs=1e-6)


def test_drift_schedule_reaches_long_drift_after_second_taper() -> None:
    schedule = drift_schedule(medium_drift=0.01, long_drift=0.02)
    taper_end = MEDIUM_REGIME_END_DAYS + REGIME_TAPER_DAYS
    assert schedule(taper_end) == pytest.approx(0.02)
    assert schedule(taper_end + 100) == pytest.approx(0.02)


def test_drift_schedule_no_taper_when_medium_equals_long() -> None:
    schedule = drift_schedule(medium_drift=0.0, long_drift=0.0)
    for day in (1, SHORT_REGIME_END_DAYS, MEDIUM_REGIME_END_DAYS, MEDIUM_REGIME_END_DAYS + 1000):
        assert schedule(day) == 0.0
