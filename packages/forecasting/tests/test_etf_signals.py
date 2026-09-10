from unittest.mock import MagicMock

import pytest
from equicast_forecasting.etf_signals import (
    aggregate_pe,
    compute_etf_signals,
    dividend_yield,
    expense_ratio,
    nav_premium_discount,
)


def test_expense_ratio_reads_net_expense_ratio() -> None:
    assert expense_ratio({"netExpenseRatio": 0.0003}) == pytest.approx(0.0003)


def test_expense_ratio_none_when_missing() -> None:
    assert expense_ratio({}) is None


def test_dividend_yield_reads_yield_field() -> None:
    assert dividend_yield({"yield": 0.013}) == pytest.approx(0.013)


def test_dividend_yield_none_when_missing() -> None:
    assert dividend_yield({}) is None


def test_nav_premium_discount_positive_when_trading_above_nav() -> None:
    info = {"navPrice": 100.0, "currentPrice": 101.0}
    assert nav_premium_discount(info) == pytest.approx(0.01)


def test_nav_premium_discount_negative_when_trading_below_nav() -> None:
    info = {"navPrice": 100.0, "regularMarketPrice": 99.0}
    assert nav_premium_discount(info) == pytest.approx(-0.01)


def test_nav_premium_discount_none_when_nav_missing() -> None:
    assert nav_premium_discount({"currentPrice": 101.0}) is None


def test_nav_premium_discount_none_when_price_missing() -> None:
    assert nav_premium_discount({"navPrice": 100.0}) is None


def test_nav_premium_discount_none_when_nav_zero() -> None:
    assert nav_premium_discount({"navPrice": 0.0, "currentPrice": 101.0}) is None


def test_aggregate_pe_reads_trailing_pe_when_reported() -> None:
    assert aggregate_pe({"trailingPE": 27.5}) == pytest.approx(27.5)


def test_aggregate_pe_none_when_not_reported() -> None:
    # No trailingPE, no trailingEps/currentPrice to compute a fallback
    # ratio from, and no financials (ETFs file none) - degrades to None
    # rather than raising.
    assert aggregate_pe({}) is None


def test_compute_etf_signals_combines_all_four_fields() -> None:
    datafeed = MagicMock()
    datafeed.get_info.return_value = {
        "netExpenseRatio": 0.0003,
        "yield": 0.013,
        "navPrice": 500.0,
        "currentPrice": 501.0,
        "trailingPE": 27.5,
    }

    signals = compute_etf_signals(datafeed, "VOO")

    assert signals == {
        "expense_ratio": pytest.approx(0.0003),
        "dividend_yield": pytest.approx(0.013),
        "nav_premium_discount": pytest.approx(0.002),
        "aggregate_pe": pytest.approx(27.5),
    }
    datafeed.get_info.assert_called_once_with("VOO")


def test_compute_etf_signals_all_none_when_info_sparse() -> None:
    datafeed = MagicMock()
    datafeed.get_info.return_value = {}

    signals = compute_etf_signals(datafeed, "VOO")

    assert signals == {
        "expense_ratio": None,
        "dividend_yield": None,
        "nav_premium_discount": None,
        "aggregate_pe": None,
    }
