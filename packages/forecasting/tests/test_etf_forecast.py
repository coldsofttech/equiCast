from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from equicast_forecasting.etf_forecast import etf_price_bands
from equicast_forecasting.etf_type_registry import UnroutableEtfTypeError
from equicast_forecasting.monte_carlo import DEFAULT_BLOCK_SIZE
from equicast_forecasting.regimes import MEDIUM_REGIME_END_DAYS, SHORT_REGIME_END_DAYS

_NO_SIGNALS = {
    "expense_ratio": None,
    "dividend_yield": None,
    "nav_premium_discount": None,
    "aggregate_pe": None,
}


@pytest.fixture(autouse=True)
def _mock_signals():
    with patch(
        "equicast_forecasting.etf_forecast.compute_etf_signals", return_value=_NO_SIGNALS
    ) as mock:
        yield mock


def _prices(num_days: int = 300, start: float = 100.0, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    closes = start + rng.normal(0, 1, num_days).cumsum()
    today = date.today()
    return [
        {"date": (today - timedelta(days=num_days - i)).isoformat(), "close": float(close)}
        for i, close in enumerate(closes)
    ]


def test_etf_price_bands_raises_for_unroutable_category(_mock_signals: MagicMock) -> None:
    with pytest.raises(UnroutableEtfTypeError):
        etf_price_bands(_prices(), "XYZ", "Not A Real Category", years=1)
    _mock_signals.assert_not_called()  # fails fast, before touching signals


def test_etf_price_bands_empty_for_too_little_price_history() -> None:
    short_prices = _prices(num_days=DEFAULT_BLOCK_SIZE)
    assert etf_price_bands(short_prices, "VOO", "Large Blend", years=1) == []


def test_etf_price_bands_shape_and_horizon() -> None:
    prices = _prices()

    records = etf_price_bands(prices, "voo", "Large Blend", years=1)

    assert len(records) == 365
    first, last = records[0], records[-1]
    assert first["ticker"] == "VOO"
    assert first["etf_type"] == "Broad/S&P"
    assert first["etf_type_key"] == "broad_sp"
    assert first["source"] == "equicast"
    assert first["volatility_model"] in ("garch", "ewma")
    assert set(first.keys()) == {
        "ticker",
        "etf_type",
        "etf_type_key",
        "date",
        "p10",
        "p50",
        "p90",
        "regime",
        "volatility_model",
        "expense_ratio",
        "dividend_yield",
        "nav_premium_discount",
        "aggregate_pe",
        "last_updated",
        "source",
    }
    last_price_date = date.fromisoformat(prices[-1]["date"])
    assert first["date"] == (last_price_date + timedelta(days=1)).isoformat()
    assert last["date"] == (last_price_date + timedelta(days=365)).isoformat()


def test_etf_price_bands_reports_none_signals_when_unavailable() -> None:
    records = etf_price_bands(_prices(), "VOO", "Large Blend", years=1)

    assert all(r["expense_ratio"] is None for r in records)
    assert all(r["dividend_yield"] is None for r in records)
    assert all(r["nav_premium_discount"] is None for r in records)
    assert all(r["aggregate_pe"] is None for r in records)


def test_etf_price_bands_reports_real_signals(_mock_signals: MagicMock) -> None:
    _mock_signals.return_value = {
        "expense_ratio": 0.0003,
        "dividend_yield": 0.013,
        "nav_premium_discount": 0.001,
        "aggregate_pe": 27.5,
    }

    records = etf_price_bands(_prices(), "VOO", "Large Blend", years=1)

    assert all(r["expense_ratio"] == pytest.approx(0.0003) for r in records)
    assert all(r["dividend_yield"] == pytest.approx(0.013) for r in records)
    assert all(r["nav_premium_discount"] == pytest.approx(0.001) for r in records)
    assert all(r["aggregate_pe"] == pytest.approx(27.5) for r in records)


def test_etf_price_bands_ordered_ascending_by_date() -> None:
    records = etf_price_bands(_prices(), "VOO", "Large Blend", years=1)
    dates = [r["date"] for r in records]
    assert dates == sorted(dates)


def test_etf_price_bands_p10_lt_p50_lt_p90() -> None:
    records = etf_price_bands(_prices(), "VOO", "Large Blend", years=1)
    for record in records:
        assert record["p10"] < record["p50"] < record["p90"]


def test_etf_price_bands_regime_tags_match_day_boundaries() -> None:
    records = etf_price_bands(_prices(), "VOO", "Large Blend", years=2)

    regimes_by_day = {i + 1: r["regime"] for i, r in enumerate(records)}
    assert regimes_by_day[1] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS + 1] == "medium"
    assert regimes_by_day[MEDIUM_REGIME_END_DAYS] == "medium"


def test_etf_price_bands_real_expense_ratio_biases_long_horizon_downward(
    _mock_signals: MagicMock,
) -> None:
    prices = _prices()

    _mock_signals.return_value = _NO_SIGNALS
    unbiased = etf_price_bands(prices, "VOO", "Large Blend", years=10)

    _mock_signals.return_value = {**_NO_SIGNALS, "expense_ratio": 0.01}  # a real, sizable fee drag
    biased = etf_price_bands(prices, "VOO", "Large Blend", years=10)

    assert biased[-1]["p50"] < unbiased[-1]["p50"]


def test_etf_price_bands_passes_symbol_to_signals(_mock_signals: MagicMock) -> None:
    etf_price_bands(_prices(), "VOO", "Large Blend", years=1)
    args, _ = _mock_signals.call_args
    assert args[-1] == "VOO"
