import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_datafeed.disclaimers import reset_warned
from equicast_datafeed.exceptions import DatafeedError
from equicast_metrics.client import EQUICAST_METRICS_DISCLAIMER, MetricsClient
from equicast_metrics.exceptions import UnsupportedSymbolError


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


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


def test_constructing_client_shows_equicast_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        MetricsClient("AAPL", datafeed=_datafeed({}, pd.DataFrame()))
        MetricsClient("GBPUSD=X", datafeed=_datafeed({}, pd.DataFrame()))

    assert caplog.messages == [EQUICAST_METRICS_DISCLAIMER]


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


def test_fundamentals_raises_for_fx_symbol() -> None:
    client = MetricsClient("GBPUSD=X", datafeed=_datafeed({}, pd.DataFrame()))

    with pytest.raises(UnsupportedSymbolError):
        client.fundamentals()


def test_fundamentals_uses_direct_info_fields_and_reports_yfinance_source() -> None:
    info = {
        "trailingPE": 30.0,
        "forwardPE": 25.0,
        "trailingEps": 6.0,
        "forwardEps": 7.2,
        "trailingPegRatio": 2.1,
        "priceToBook": 45.0,
        "priceToSalesTrailing12Months": 8.0,
        "enterpriseToEbitda": 20.0,
        "grossMargins": 0.45,
        "operatingMargins": 0.3,
        "profitMargins": 0.25,
        "returnOnEquity": 1.5,
        "returnOnAssets": 0.28,
        "debtToEquity": 150.0,
    }
    fundamentals = MetricsClient("AAPL", datafeed=_datafeed(info, pd.DataFrame())).fundamentals()

    assert fundamentals["trailing_pe"] == 30.0
    assert fundamentals["peg"] == 2.1
    # free_cash_flow_per_share has no direct yfinance field, so it's always
    # a fallback (and None here, with neither freeCashflow nor
    # operatingCashflow/capitalExpenditures in info) - "source" still comes
    # out "equicast" as a result.
    assert fundamentals["free_cash_flow_per_share"] is None
    assert fundamentals["source"] == "yfinance"


def test_fundamentals_falls_back_to_balance_sheet_and_financials() -> None:
    datafeed = _datafeed({"currentPrice": 100.0, "marketCap": 1000.0}, pd.DataFrame())
    datafeed.get_financials.return_value = pd.DataFrame(
        {"2026-12-31": [500.0, 80.0]}, index=["Total Revenue", "Net Income"]
    )
    datafeed.get_balance_sheet.return_value = pd.DataFrame(
        {"2026-12-31": [1000.0, 600.0]}, index=["Total Assets", "Stockholders Equity"]
    )

    fundamentals = MetricsClient("AAPL", datafeed=datafeed).fundamentals()

    assert fundamentals["profit_margin"] == pytest.approx(80.0 / 500.0)
    assert fundamentals["return_on_assets"] == pytest.approx(80.0 / 1000.0)
    assert fundamentals["source"] == "equicast"


def test_fundamentals_treats_statement_fetch_failure_as_unavailable() -> None:
    datafeed = _datafeed({}, pd.DataFrame())
    datafeed.get_financials.side_effect = DatafeedError("boom")
    datafeed.get_balance_sheet.side_effect = DatafeedError("boom")

    fundamentals = MetricsClient("AAPL", datafeed=datafeed).fundamentals()

    assert fundamentals["gross_margin"] is None
    assert fundamentals["return_on_equity"] is None


def test_fundamentals_fetches_statements_at_most_once_each() -> None:
    datafeed = _datafeed({}, pd.DataFrame())
    datafeed.get_financials.return_value = pd.DataFrame(
        {"2026-12-31": [500.0, 200.0, 150.0, 80.0]},
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
    )
    datafeed.get_balance_sheet.return_value = pd.DataFrame(
        {"2026-12-31": [1000.0, 400.0, 600.0]},
        index=["Total Assets", "Total Liabilities Net Minority Interest", "Stockholders Equity"],
    )

    MetricsClient("AAPL", datafeed=datafeed).fundamentals()

    datafeed.get_financials.assert_called_once_with("AAPL")
    datafeed.get_balance_sheet.assert_called_once_with("AAPL")


def test_fundamentals_includes_last_updated() -> None:
    fundamentals = MetricsClient("AAPL", datafeed=_datafeed({}, pd.DataFrame())).fundamentals()
    assert fundamentals["last_updated"]
