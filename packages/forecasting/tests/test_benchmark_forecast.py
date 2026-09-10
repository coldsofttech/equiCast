from datetime import date, timedelta

import numpy as np
import pytest
from equicast_forecasting.benchmark_forecast import benchmark_price_bands
from equicast_forecasting.benchmark_registry import UnroutableBenchmarkError
from equicast_forecasting.monte_carlo import DEFAULT_BLOCK_SIZE
from equicast_forecasting.regimes import MEDIUM_REGIME_END_DAYS, SHORT_REGIME_END_DAYS


def _prices(num_days: int = 300, start: float = 4500.0, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    closes = start + rng.normal(0, 5, num_days).cumsum()
    today = date.today()
    return [
        {"date": (today - timedelta(days=num_days - i)).isoformat(), "close": float(close)}
        for i, close in enumerate(closes)
    ]


def test_benchmark_price_bands_raises_for_unroutable_key() -> None:
    with pytest.raises(UnroutableBenchmarkError):
        benchmark_price_bands(_prices(), "NOT_A_REAL_BENCHMARK", years=1)


def test_benchmark_price_bands_empty_for_too_little_price_history() -> None:
    short_prices = _prices(num_days=DEFAULT_BLOCK_SIZE)
    assert benchmark_price_bands(short_prices, "SP500", years=1) == []


def test_benchmark_price_bands_shape_and_horizon() -> None:
    prices = _prices()

    records = benchmark_price_bands(prices, "sp500", years=1)

    assert len(records) == 365
    first, last = records[0], records[-1]
    assert first["key"] == "SP500"
    assert first["benchmark"] == "S&P 500"
    assert first["currency_sensitivity"] == "low"
    assert first["source"] == "equicast"
    assert first["volatility_model"] in ("garch", "ewma")
    assert set(first.keys()) == {
        "key",
        "benchmark",
        "currency_sensitivity",
        "date",
        "p10",
        "p50",
        "p90",
        "regime",
        "volatility_model",
        "cape_zscore",
        "last_updated",
        "source",
    }
    last_price_date = date.fromisoformat(prices[-1]["date"])
    assert first["date"] == (last_price_date + timedelta(days=1)).isoformat()
    assert last["date"] == (last_price_date + timedelta(days=365)).isoformat()


def test_benchmark_price_bands_reports_none_cape_zscore_by_default() -> None:
    records = benchmark_price_bands(_prices(), "SP500", years=1)
    assert all(r["cape_zscore"] is None for r in records)


def test_benchmark_price_bands_ordered_ascending_by_date() -> None:
    records = benchmark_price_bands(_prices(), "SP500", years=1)
    dates = [r["date"] for r in records]
    assert dates == sorted(dates)


def test_benchmark_price_bands_p10_lt_p50_lt_p90() -> None:
    records = benchmark_price_bands(_prices(), "SP500", years=1)
    for record in records:
        assert record["p10"] < record["p50"] < record["p90"]


def test_benchmark_price_bands_regime_tags_match_day_boundaries() -> None:
    records = benchmark_price_bands(_prices(), "SP500", years=2)

    regimes_by_day = {i + 1: r["regime"] for i, r in enumerate(records)}
    assert regimes_by_day[1] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS + 1] == "medium"
    assert regimes_by_day[MEDIUM_REGIME_END_DAYS] == "medium"


def test_benchmark_price_bands_positive_cape_zscore_biases_long_horizon_downward() -> None:
    prices = _prices()

    unbiased = benchmark_price_bands(prices, "SP500", years=10, cape_zscore=None)
    biased = benchmark_price_bands(prices, "SP500", years=10, cape_zscore=3.0)

    assert biased[-1]["p50"] < unbiased[-1]["p50"]
    assert all(r["cape_zscore"] == pytest.approx(3.0) for r in biased)


def test_benchmark_price_bands_reports_routed_schema_fields() -> None:
    records = benchmark_price_bands(_prices(), "FTSE100", years=1)
    assert all(r["key"] == "FTSE100" for r in records)
    assert all(r["benchmark"] == "FTSE 100" for r in records)
    assert all(r["currency_sensitivity"] == "high" for r in records)
