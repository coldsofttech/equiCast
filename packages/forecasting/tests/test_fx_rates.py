from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_forecasting import fx_rates
from equicast_forecasting.fx_rates import (
    LONG_TERM_YIELD_TICKERS,
    SHORT_TERM_YIELD_TICKERS,
    _latest_yield,
    long_term_rate_diff,
    short_term_rate_diff,
)


def _history(close: float) -> pd.DataFrame:
    return pd.DataFrame({"Close": [close]})


def _datafeed(by_ticker: dict[str, float]) -> MagicMock:
    datafeed = MagicMock()

    def get_history(ticker: str, period: str = "1y", interval: str = "1d"):
        if ticker in by_ticker:
            return _history(by_ticker[ticker])
        return pd.DataFrame()

    datafeed.get_history.side_effect = get_history
    return datafeed


def test_short_term_rate_diff_uses_mapped_tickers() -> None:
    usd_ticker = SHORT_TERM_YIELD_TICKERS["USD"]
    datafeed = _datafeed({usd_ticker: 5.0})

    # GBP isn't mapped (see fx_rates.py's module docstring), so a GBP/USD
    # pair still can't resolve a full two-leg differential today.
    assert short_term_rate_diff("GBP", "USD", datafeed) is None


def test_short_term_rate_diff_none_when_neither_currency_mapped() -> None:
    datafeed = _datafeed({})
    assert short_term_rate_diff("GBP", "EUR", datafeed) is None


def test_long_term_rate_diff_computes_to_minus_from_when_both_mapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Today only USD is really mapped (see fx_rates.py's module docstring)
    # - a fake second mapping exercises the actual to-minus-from
    # subtraction without depending on a second currency ever getting a
    # real yfinance ticker.
    monkeypatch.setitem(fx_rates.LONG_TERM_YIELD_TICKERS, "XYZ", "XYZ10Y")
    datafeed = _datafeed({LONG_TERM_YIELD_TICKERS["USD"]: 4.5, "XYZ10Y": 2.0})

    assert long_term_rate_diff("XYZ", "USD", datafeed) == pytest.approx(0.025)
    assert long_term_rate_diff("USD", "XYZ", datafeed) == pytest.approx(-0.025)


def test_long_term_rate_diff_converts_percent_to_fraction() -> None:
    ticker = LONG_TERM_YIELD_TICKERS["USD"]
    datafeed = _datafeed({ticker: 4.8})

    assert _latest_yield(LONG_TERM_YIELD_TICKERS, "USD", datafeed) == 0.048


def test_rate_diff_none_when_history_is_empty() -> None:
    datafeed = MagicMock()
    datafeed.get_history.return_value = pd.DataFrame()

    assert short_term_rate_diff("USD", "USD", datafeed) is None
