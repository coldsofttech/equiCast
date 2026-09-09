from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from equicast_forecasting.fx_forecast import (
    MEDIUM_REGIME_END_DAYS,
    SHORT_REGIME_END_DAYS,
    fx_price_bands,
    regime_for_day,
)


def _prices(num_days: int = 400, start: float = 1.30, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    closes = start + rng.normal(0, 0.002, num_days).cumsum()
    today = date.today()
    return [
        {"date": (today - timedelta(days=num_days - i)).isoformat(), "close": float(close)}
        for i, close in enumerate(closes)
    ]


def test_regime_for_day_boundaries() -> None:
    assert regime_for_day(1) == "short"
    assert regime_for_day(SHORT_REGIME_END_DAYS) == "short"
    assert regime_for_day(SHORT_REGIME_END_DAYS + 1) == "medium"
    assert regime_for_day(MEDIUM_REGIME_END_DAYS) == "medium"
    assert regime_for_day(MEDIUM_REGIME_END_DAYS + 1) == "long"


def test_fx_price_bands_empty_for_fewer_than_two_prices() -> None:
    assert fx_price_bands([{"date": "2026-01-01", "close": 1.3}], "GBP", "USD") == []
    assert fx_price_bands([], "GBP", "USD") == []


@patch("equicast_forecasting.fx_forecast.long_term_rate_diff", return_value=None)
def test_fx_price_bands_shape_and_horizon(mock_rate_diff: MagicMock) -> None:
    prices = _prices()

    records = fx_price_bands(prices, "gbp", "usd", years=1)

    assert len(records) == 365
    first, last = records[0], records[-1]
    assert first["from_currency"] == "GBP"
    assert first["to_currency"] == "USD"
    assert first["source"] == "equicast"
    assert first["volatility_model"] in ("garch", "ewma")
    assert set(records[0].keys()) == {
        "from_currency",
        "to_currency",
        "date",
        "p10",
        "p50",
        "p90",
        "regime",
        "volatility_model",
        "last_updated",
        "source",
    }
    last_price_date = date.fromisoformat(prices[-1]["date"])
    assert first["date"] == (last_price_date + timedelta(days=1)).isoformat()
    assert last["date"] == (last_price_date + timedelta(days=365)).isoformat()


@patch("equicast_forecasting.fx_forecast.long_term_rate_diff", return_value=None)
def test_fx_price_bands_ordered_ascending_by_date(mock_rate_diff: MagicMock) -> None:
    records = fx_price_bands(_prices(), "gbp", "usd", years=1)
    dates = [r["date"] for r in records]
    assert dates == sorted(dates)


@patch("equicast_forecasting.fx_forecast.long_term_rate_diff", return_value=None)
def test_fx_price_bands_p10_lt_p50_lt_p90(mock_rate_diff: MagicMock) -> None:
    records = fx_price_bands(_prices(), "gbp", "usd", years=1)
    for record in records:
        assert record["p10"] < record["p50"] < record["p90"]


@patch("equicast_forecasting.fx_forecast.long_term_rate_diff", return_value=None)
def test_fx_price_bands_short_regime_has_no_directional_drift(mock_rate_diff: MagicMock) -> None:
    prices = _prices()
    records = fx_price_bands(prices, "gbp", "usd", years=1)
    last_close = prices[-1]["close"]

    short_regime_records = [r for r in records if r["regime"] == "short"]
    assert len(short_regime_records) == SHORT_REGIME_END_DAYS
    for record in short_regime_records:
        assert record["p50"] == pytest.approx(last_close, rel=1e-6)


@patch("equicast_forecasting.fx_forecast.long_term_rate_diff")
def test_fx_price_bands_medium_regime_tilts_toward_positive_rate_diff(
    mock_rate_diff: MagicMock,
) -> None:
    # A positive rate_diff (to_currency yields more than from_currency)
    # means the from currency is expected to appreciate under UIP - see
    # fx_forecast.py's own docstring on the sign convention - so the
    # medium-regime median should end up above the last real close.
    mock_rate_diff.return_value = 0.05
    prices = _prices()
    last_close = prices[-1]["close"]

    records = fx_price_bands(prices, "gbp", "usd", years=2)

    medium_records = [r for r in records if r["regime"] == "medium"]
    assert medium_records[-1]["p50"] > last_close


@patch("equicast_forecasting.fx_forecast.long_term_rate_diff", return_value=None)
def test_fx_price_bands_long_regime_defaults_to_no_drift_when_reer_deviation_missing(
    mock_rate_diff: MagicMock,
) -> None:
    prices = _prices()
    records = fx_price_bands(prices, "gbp", "usd", years=10, reer_deviation=None)

    medium_records = [r for r in records if r["regime"] == "medium"]
    long_records = [r for r in records if r["regime"] == "long"]
    assert long_records  # 10-year horizon reaches the long regime
    # With no rate_diff and no reer_deviation, drift is 0.0 everywhere, so
    # the long regime's median should equal the medium regime's own
    # (flat) median rather than drifting further.
    assert long_records[-1]["p50"] == pytest.approx(medium_records[-1]["p50"], rel=1e-6)
