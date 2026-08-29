from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_metrics.client import MetricsClient


def _history(prices: list[float], start: str = "2015-01-01") -> pd.DataFrame:
    index = pd.date_range(start=start, periods=len(prices), freq="D")
    return pd.DataFrame({"Close": prices}, index=index)


def _datafeed(info: dict, history: pd.DataFrame) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    datafeed.get_history.return_value = history
    return datafeed


def test_symbol_is_uppercased() -> None:
    client = MetricsClient("aapl", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.symbol == "AAPL"


def test_metrics_uses_yfinance_cagr_1y_when_present() -> None:
    info = {"fiftyTwoWeekChangePercent": 20.0}
    history = _history([100.0] * 4000)  # long flat history: 2/3/5/10y all computable

    metrics = MetricsClient("AAPL", datafeed=_datafeed(info, history)).metrics()

    assert metrics["cagr_1y"] == pytest.approx(0.20)
    assert metrics["source"] == "equicast"  # other fields are still computed


def test_metrics_calculates_cagr_1y_when_yfinance_field_missing() -> None:
    history = _history([100.0] * 400)
    metrics = MetricsClient("AAPL", datafeed=_datafeed({}, history)).metrics()

    assert metrics["cagr_1y"] is not None


def test_metrics_returns_none_for_windows_without_enough_history() -> None:
    history = _history([100.0] * 30)  # ~1 month: not enough for any CAGR window
    metrics = MetricsClient("AAPL", datafeed=_datafeed({}, history)).metrics()

    assert metrics["cagr_1y"] is None
    assert metrics["cagr_10y"] is None


def test_metrics_handles_empty_history() -> None:
    metrics = MetricsClient("AAPL", datafeed=_datafeed({}, pd.DataFrame())).metrics()

    assert metrics["volatility"] is None
    assert metrics["sharpe_ratio"] is None
    assert metrics["max_drawdown"] is None
    assert all(metrics[f"cagr_{y}y"] is None for y in (1, 2, 3, 5, 10))


def test_metrics_includes_last_updated_and_source() -> None:
    history = _history([100.0, 101.0, 99.0, 102.0])
    metrics = MetricsClient("AAPL", datafeed=_datafeed({}, history)).metrics()

    assert metrics["last_updated"]
    assert metrics["source"] == "equicast"


def test_metrics_works_for_fx_symbols_too() -> None:
    history = _history([1.30, 1.31, 1.29, 1.32])
    metrics = MetricsClient("GBPUSD=X", datafeed=_datafeed({}, history)).metrics()

    assert metrics["volatility"] is not None


def test_metrics_ignores_trailing_nan_close_from_an_incomplete_trading_day() -> None:
    # A still-forming "today" bar can come back with a NaN close; it should
    # be dropped rather than poisoning every downstream calculation via
    # the last row.
    history = _history([100.0] * 4000 + [float("nan")])

    metrics = MetricsClient("AAPL", datafeed=_datafeed({}, history)).metrics()

    for value in metrics.values():
        assert not (isinstance(value, float) and value != value)  # not NaN
