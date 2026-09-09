"""Best-effort interest-rate proxies per currency, sourced from yfinance's
own treasury-yield index tickers - used to derive `rate_diff` for the
interest-rate-parity model (see fx_forecast.py).

Checked live: US Treasury yields (^IRX 13-week, ^TNX 10-year) resolve
cleanly via yfinance; there is no reliable free yfinance ticker for UK
gilt, German bund, or ECB/BoE policy-rate yields (candidates tried -
GB10Y=X, DE10Y=X, ^BUND, FGBL=F, ^GDBR10, EURIBOR3M=X - all 404 or return
empty history). So today, only USD is mapped, and `rate_diff` resolves to
`None` for any pair that doesn't involve it - the same graceful "leave
genuinely None" degrade this model's other macro inputs (inflation_diff,
reer_deviation, current_account_balance, ...) already use until a real
macro data source (FRED is the natural choice - global coverage) is added
in a follow-up. The maps below are deliberately just plain dicts so adding
a currency once a reliable ticker is found is a one-line change.
"""

from __future__ import annotations

from equicast_datafeed import DatafeedClient

#: yfinance ticker for a *short-term* (~13-week) risk-free yield, per
#: currency - see module docstring for why only USD is mapped today.
SHORT_TERM_YIELD_TICKERS: dict[str, str] = {
    "USD": "^IRX",
}

#: yfinance ticker for a *long-term* (~10-year) benchmark yield, per
#: currency - same USD-only coverage as `SHORT_TERM_YIELD_TICKERS`.
LONG_TERM_YIELD_TICKERS: dict[str, str] = {
    "USD": "^TNX",
}


def _latest_yield(
    ticker_map: dict[str, str], currency: str, datafeed: DatafeedClient
) -> float | None:
    ticker = ticker_map.get(currency.upper())
    if ticker is None:
        return None

    history = datafeed.get_history(ticker, period="5d")
    if history.empty:
        return None
    # ^IRX/^TNX report their yield as a plain percentage (e.g. 4.84 == 4.84%
    # annualized), not a fraction - divided here so callers get a fraction
    # consistent with every other rate-like field equicast reports (e.g.
    # dividend_yield).
    return float(history["Close"].iloc[-1]) / 100


def short_term_rate_diff(
    from_currency: str, to_currency: str, datafeed: DatafeedClient
) -> float | None:
    """`to_currency`'s short-term risk-free rate minus `from_currency`'s
    (both from `SHORT_TERM_YIELD_TICKERS`) - `None` if either currency
    isn't mapped (today, that's every currency but USD, so this only
    resolves for a pair with USD on one side)."""
    from_rate = _latest_yield(SHORT_TERM_YIELD_TICKERS, from_currency, datafeed)
    to_rate = _latest_yield(SHORT_TERM_YIELD_TICKERS, to_currency, datafeed)
    if from_rate is None or to_rate is None:
        return None
    return to_rate - from_rate


def long_term_rate_diff(
    from_currency: str, to_currency: str, datafeed: DatafeedClient
) -> float | None:
    """Same as `short_term_rate_diff`, off `LONG_TERM_YIELD_TICKERS`
    instead - this is the medium/long-horizon interest-rate-parity model's
    own `rate_diff_forward` input."""
    from_rate = _latest_yield(LONG_TERM_YIELD_TICKERS, from_currency, datafeed)
    to_rate = _latest_yield(LONG_TERM_YIELD_TICKERS, to_currency, datafeed)
    if from_rate is None or to_rate is None:
        return None
    return to_rate - from_rate
