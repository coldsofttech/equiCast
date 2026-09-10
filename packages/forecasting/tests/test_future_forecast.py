from datetime import date, timedelta

import numpy as np
import pytest
from equicast_forecasting.commodity_registry import UnroutableCommodityError
from equicast_forecasting.future_forecast import future_price_bands
from equicast_forecasting.monte_carlo import DEFAULT_BLOCK_SIZE
from equicast_forecasting.regimes import MEDIUM_REGIME_END_DAYS, SHORT_REGIME_END_DAYS


def _prices(num_days: int = 300, start: float = 1900.0, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    closes = start + rng.normal(0, 10, num_days).cumsum()
    today = date.today()
    return [
        {"date": (today - timedelta(days=num_days - i)).isoformat(), "close": float(close)}
        for i, close in enumerate(closes)
    ]


def test_future_price_bands_raises_for_unroutable_key() -> None:
    with pytest.raises(UnroutableCommodityError):
        future_price_bands(_prices(), "NOT_A_REAL_FUTURE", years=1)


def test_future_price_bands_empty_for_too_little_price_history() -> None:
    short_prices = _prices(num_days=DEFAULT_BLOCK_SIZE)
    assert future_price_bands(short_prices, "GOLD", years=1) == []


def test_future_price_bands_shape_and_horizon() -> None:
    prices = _prices()

    records = future_price_bands(prices, "gold", years=1)

    assert len(records) == 365
    first, last = records[0], records[-1]
    assert first["key"] == "GOLD"
    assert first["commodity_class"] == "Precious Metals"
    assert first["source"] == "equicast"
    assert first["volatility_model"] in ("garch", "ewma")
    assert set(first.keys()) == {
        "key",
        "commodity_class",
        "date",
        "p10",
        "p50",
        "p90",
        "regime",
        "volatility_model",
        "basis_vs_cost_of_carry",
        "last_updated",
        "source",
    }
    last_price_date = date.fromisoformat(prices[-1]["date"])
    assert first["date"] == (last_price_date + timedelta(days=1)).isoformat()
    assert last["date"] == (last_price_date + timedelta(days=365)).isoformat()


def test_future_price_bands_reports_none_basis_by_default() -> None:
    records = future_price_bands(_prices(), "GOLD", years=1)
    assert all(r["basis_vs_cost_of_carry"] is None for r in records)


def test_future_price_bands_ordered_ascending_by_date() -> None:
    records = future_price_bands(_prices(), "GOLD", years=1)
    dates = [r["date"] for r in records]
    assert dates == sorted(dates)


def test_future_price_bands_p10_lt_p50_lt_p90() -> None:
    records = future_price_bands(_prices(), "GOLD", years=1)
    for record in records:
        assert record["p10"] < record["p50"] < record["p90"]


def test_future_price_bands_regime_tags_match_day_boundaries() -> None:
    records = future_price_bands(_prices(), "GOLD", years=2)

    regimes_by_day = {i + 1: r["regime"] for i, r in enumerate(records)}
    assert regimes_by_day[1] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS] == "short"
    assert regimes_by_day[SHORT_REGIME_END_DAYS + 1] == "medium"
    assert regimes_by_day[MEDIUM_REGIME_END_DAYS] == "medium"


def test_future_price_bands_positive_basis_biases_long_horizon_downward() -> None:
    prices = _prices()

    unbiased = future_price_bands(prices, "GOLD", years=10, basis_vs_cost_of_carry=None)
    biased = future_price_bands(prices, "GOLD", years=10, basis_vs_cost_of_carry=3.0)

    assert biased[-1]["p50"] < unbiased[-1]["p50"]
    assert all(r["basis_vs_cost_of_carry"] == pytest.approx(3.0) for r in biased)


def test_future_price_bands_reports_routed_schema_fields() -> None:
    records = future_price_bands(_prices(), "NATURAL_GAS", years=1)
    assert all(r["key"] == "NATURAL_GAS" for r in records)
    assert all(r["commodity_class"] == "Energy" for r in records)


def test_future_price_bands_routes_every_configured_commodity_class() -> None:
    # One representative future per class - confirms the whole 16-symbol
    # -> 5-class registry is actually reachable through the top-level
    # entry point, not just commodity_registry.py in isolation.
    for key, expected_class in [
        ("GOLD", "Precious Metals"),
        ("CRUDE_OIL_WTI", "Energy"),
        ("COPPER", "Industrial Metals"),
        ("WHEAT", "Grains"),
        ("COFFEE", "Softs"),
    ]:
        records = future_price_bands(_prices(), key, years=1)
        assert records[0]["commodity_class"] == expected_class
