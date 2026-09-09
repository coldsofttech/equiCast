from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from equicast_forecasting.monte_carlo import DEFAULT_BLOCK_SIZE
from equicast_forecasting.regimes import MEDIUM_REGIME_END_DAYS, SHORT_REGIME_END_DAYS
from equicast_forecasting.sector_registry import UnroutableSectorError
from equicast_forecasting.stock_forecast import stock_price_bands

_NO_FUNDAMENTAL_SIGNALS = {
    "revenue_cagr": None,
    "profit_margin_trend": None,
    "rd_to_revenue": None,
    "short_interest_ratio": None,
}


@pytest.fixture(autouse=True)
def _mock_fundamental_signals():
    with patch(
        "equicast_forecasting.stock_forecast.compute_fundamental_signals",
        return_value=_NO_FUNDAMENTAL_SIGNALS,
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


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_raises_for_unroutable_sector(mock_signal: MagicMock) -> None:
    with pytest.raises(UnroutableSectorError):
        stock_price_bands(_prices(), "XYZ", "Not A Real Sector", "Whatever", years=1)
    mock_signal.assert_not_called()  # fails fast, before touching fundamentals


def test_stock_price_bands_empty_for_too_little_price_history() -> None:
    short_prices = _prices(num_days=DEFAULT_BLOCK_SIZE)
    assert stock_price_bands(short_prices, "AAPL", "Technology", "Semiconductors", years=1) == []


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_shape_and_horizon(mock_signal: MagicMock) -> None:
    prices = _prices()

    records = stock_price_bands(prices, "aapl", "Technology", "Semiconductors", years=1)

    assert len(records) == 365
    first, last = records[0], records[-1]
    assert first["ticker"] == "AAPL"
    assert first["sector"] == "Technology"
    assert first["sub_sector"] == "technology"
    assert first["source"] == "equicast"
    assert first["volatility_model"] in ("garch", "ewma")
    assert set(first.keys()) == {
        "ticker",
        "sector",
        "sub_sector",
        "date",
        "p10",
        "p50",
        "p90",
        "regime",
        "volatility_model",
        "valuation_multiple_family",
        "valuation_multiple",
        "valuation_zscore",
        "revenue_cagr",
        "profit_margin_trend",
        "rd_to_revenue",
        "short_interest_ratio",
        "last_updated",
        "source",
    }
    last_price_date = date.fromisoformat(prices[-1]["date"])
    assert first["date"] == (last_price_date + timedelta(days=1)).isoformat()
    assert last["date"] == (last_price_date + timedelta(days=365)).isoformat()


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_no_multiple_family_reports_none(mock_signal: MagicMock) -> None:
    records = stock_price_bands(
        _prices(), "PFE", "Healthcare", "Drug Manufacturers - General", years=1
    )

    assert all(r["valuation_multiple_family"] is None for r in records)
    assert all(r["valuation_multiple"] is None for r in records)
    assert all(r["valuation_zscore"] is None for r in records)


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(30.0, 1.5))
def test_stock_price_bands_reports_real_multiple_and_zscore(mock_signal: MagicMock) -> None:
    records = stock_price_bands(_prices(), "AAPL", "Technology", "Semiconductors", years=1)

    assert records[0]["valuation_multiple_family"] == "pe"
    assert all(r["valuation_multiple"] == pytest.approx(30.0) for r in records)
    assert all(r["valuation_zscore"] == pytest.approx(1.5) for r in records)


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_reports_real_fundamental_signals(
    mock_signal: MagicMock, _mock_fundamental_signals: MagicMock
) -> None:
    _mock_fundamental_signals.return_value = {
        "revenue_cagr": 0.1,
        "profit_margin_trend": 0.02,
        "rd_to_revenue": 0.08,
        "short_interest_ratio": 0.01,
    }

    records = stock_price_bands(_prices(), "AAPL", "Technology", "Semiconductors", years=1)

    assert all(r["revenue_cagr"] == pytest.approx(0.1) for r in records)
    assert all(r["profit_margin_trend"] == pytest.approx(0.02) for r in records)
    assert all(r["rd_to_revenue"] == pytest.approx(0.08) for r in records)
    assert all(r["short_interest_ratio"] == pytest.approx(0.01) for r in records)


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_ordered_ascending_by_date(mock_signal: MagicMock) -> None:
    records = stock_price_bands(_prices(), "AAPL", "Technology", "Semiconductors", years=1)
    dates = [r["date"] for r in records]
    assert dates == sorted(dates)


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_p10_lt_p50_lt_p90(mock_signal: MagicMock) -> None:
    records = stock_price_bands(_prices(), "AAPL", "Technology", "Semiconductors", years=1)
    for record in records:
        assert record["p10"] < record["p50"] < record["p90"]


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_regime_tags_match_day_boundaries(mock_signal: MagicMock) -> None:
    records = stock_price_bands(_prices(), "AAPL", "Technology", "Semiconductors", years=2)

    regimes_by_day = {i + 1: r["regime"] for i, r in enumerate(records)}
    assert regimes_by_day[1] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS + 1] == "medium"
    assert regimes_by_day[MEDIUM_REGIME_END_DAYS] == "medium"


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal")
def test_stock_price_bands_positive_zscore_biases_long_horizon_downward(
    mock_signal: MagicMock,
) -> None:
    prices = _prices()

    mock_signal.return_value = (None, None)
    unbiased = stock_price_bands(prices, "AAPL", "Technology", "Semiconductors", years=10)

    mock_signal.return_value = (50.0, 3.0)  # richly valued -> expect downward drift
    biased = stock_price_bands(prices, "AAPL", "Technology", "Semiconductors", years=10)

    assert biased[-1]["p50"] < unbiased[-1]["p50"]


@patch("equicast_forecasting.stock_forecast.compute_valuation_signal", return_value=(None, None))
def test_stock_price_bands_passes_sorted_prices_to_valuation_signal(mock_signal: MagicMock) -> None:
    prices = _prices()
    unsorted_prices = list(reversed(prices))

    stock_price_bands(unsorted_prices, "AAPL", "Technology", "Semiconductors", years=1)

    call_args = mock_signal.call_args
    passed_prices = call_args.args[-1] if call_args.args else call_args.kwargs["prices"]
    assert [p["date"] for p in passed_prices] == sorted(p["date"] for p in prices)
