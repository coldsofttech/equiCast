"""Top-level FX forecast entry point (GitHub issue #65): combines the
generic volatility/band engine (volatility.py, bands.py) with FX-specific
interest-rate-parity and PPP-reversion drift into one daily probability-
band series.

Horizon regimes, matching the issue's table:
  - 1w-1m ("short"):  GARCH/EWMA volatility, no directional drift - a pure
    random-walk band, exactly as the issue specifies ("pair with
    random-walk-plus-vol-band for actual price range, not a directional
    return forecast").
  - 6m-2y ("medium"): uncovered-interest-rate-parity drift, from a real
    `rate_diff` when available (see fx_rates.py - today, only pairs
    involving USD), 0.0 (no tilt) otherwise.
  - 3y-10y ("long"):  PPP mean-reversion drift, from `reer_deviation` when
    supplied - always `None` today (no real effective exchange rate data
    source is wired up yet), so this regime also has 0.0 drift in
    practice, same graceful degrade as `inflation_diff`/
    `current_account_balance`/`productivity_diff`/`terms_of_trade_trend`/
    `sovereign_debt_trend` in the issue's medium/long rows - none of which
    have a real data source in equicast today either, and are accepted as
    optional parameters here for exactly that reason (nothing currently
    supplies them, but the reversion math is ready for whenever something
    does, e.g. a future FRED-backed package).

Each regime's drift tapers linearly into the next over `REGIME_TAPER_DAYS`
rather than jumping discontinuously at the boundary - cosmetic only (keeps
the median path's slope from kinking sharply), it doesn't change either
regime's own eventual drift level.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from equicast_datafeed import DatafeedClient, round_value

from equicast_forecasting.bands import price_bands
from equicast_forecasting.fx_rates import long_term_rate_diff
from equicast_forecasting.volatility import estimate_daily_volatility

#: End of the short (pure random-walk) regime, in calendar days - the
#: issue's "1w-1m" horizon, rounded up to a clean month.
SHORT_REGIME_END_DAYS = 30

#: End of the medium (interest-rate-parity) regime - the issue's "6m-2y"
#: horizon's upper bound.
MEDIUM_REGIME_END_DAYS = 730

#: Days over which one regime's drift linearly tapers into the next,
#: straddling each boundary above.
REGIME_TAPER_DAYS = 90

#: Trading/calendar convention used to convert an annualized rate
#: differential or reversion rate into a daily one - act/365, matching how
#: the underlying treasury yields themselves are already annualized.
DAYS_PER_YEAR = 365


def regime_for_day(day: int) -> str:
    """Which horizon regime `day` (1-indexed calendar days out from the
    last known price) falls into - `"short"`/`"medium"`/`"long"`, matching
    the module docstring's horizon table."""
    if day <= SHORT_REGIME_END_DAYS:
        return "short"
    if day <= MEDIUM_REGIME_END_DAYS:
        return "medium"
    return "long"


def _taper(day: int, start: int, end: int, from_value: float, to_value: float) -> float:
    if day <= start:
        return from_value
    if day >= end:
        return to_value
    weight = (day - start) / (end - start)
    return from_value + weight * (to_value - from_value)


def _drift_schedule(medium_drift: float, long_drift: float) -> Callable[[int], float]:
    """A day-indexed drift function stepping (with a linear taper at each
    boundary) from 0.0 (short regime) to `medium_drift` to `long_drift` -
    see the module docstring for what each regime's drift represents."""
    medium_taper_end = SHORT_REGIME_END_DAYS + REGIME_TAPER_DAYS
    long_taper_end = MEDIUM_REGIME_END_DAYS + REGIME_TAPER_DAYS

    def daily_drift(day: int) -> float:
        if day <= SHORT_REGIME_END_DAYS:
            return 0.0
        if day <= medium_taper_end:
            return _taper(day, SHORT_REGIME_END_DAYS, medium_taper_end, 0.0, medium_drift)
        if day <= MEDIUM_REGIME_END_DAYS:
            return medium_drift
        if day <= long_taper_end:
            return _taper(day, MEDIUM_REGIME_END_DAYS, long_taper_end, medium_drift, long_drift)
        return long_drift

    return daily_drift


def _medium_drift(rate_diff: float | None) -> float:
    """The interest-rate-parity-implied daily log return of the FROM
    currency (see fx_forecast's own from/to convention below) - 0.0 (no
    tilt) when `rate_diff` isn't available for this pair.

    Sign convention: `FXClient`'s own price is "how much `to_currency` 1
    unit of `from_currency` is worth" (e.g. GBPUSD=X quotes USD per 1 GBP -
    same convention `equicast_core.client`'s FX docstrings use throughout).
    Under uncovered interest rate parity, that price's expected log return
    ~= to_currency's rate minus from_currency's rate - `rate_diff` is
    already computed that way (see `fx_rates.long_term_rate_diff`), so a
    positive `rate_diff` means the FROM currency (the lower-yielding side)
    is expected to appreciate, compensating for its lower yield.
    """
    if rate_diff is None:
        return 0.0
    return rate_diff / DAYS_PER_YEAR


def _long_drift(reer_deviation: float | None, reversion_years: float) -> float:
    """The PPP-implied daily log return: a positive `reer_deviation` (the
    FROM currency overvalued relative to its long-run real effective
    exchange rate) implies expected depreciation, spread evenly over
    `reversion_years` - 0.0 when `reer_deviation` isn't available (always
    true today - see module docstring) or there's no time left to revert
    over (`reversion_years <= 0`, i.e. `years` is shorter than
    `MEDIUM_REGIME_END_DAYS`).
    """
    if reer_deviation is None or reversion_years <= 0:
        return 0.0
    return -reer_deviation / reversion_years / DAYS_PER_YEAR


def fx_price_bands(
    prices: list[dict[str, Any]],
    from_currency: str,
    to_currency: str,
    datafeed: DatafeedClient | None = None,
    reer_deviation: float | None = None,
    years: int = 10,
) -> list[dict[str, Any]]:
    """Project `years` years of daily probability bands (p10/p50/p90) for
    `from_currency`/`to_currency`, from real price history (`prices`, each
    needing at least `date`/`close` keys, the shape `FXClient.prices()`
    already returns) plus whatever real interest-rate data is available
    (see fx_rates.py).

    Each returned record: `{from_currency, to_currency, date, p10, p50,
    p90, regime, volatility_model, last_updated, source: "equicast"}` - one
    row per calendar day (not just trading days, unlike real price history:
    this is a smooth theoretical band meant to extend a price chart
    forward, not observed data, so there's no reason to gap it over
    weekends). `regime` names which horizon regime that day falls in
    (`"short"`/`"medium"`/`"long"` - see module docstring); `volatility_model`
    names which one actually produced the volatility estimate used
    throughout (`"garch"`/`"ewma"` - see volatility.py), the same for every
    row since volatility is estimated once from the full history, not
    per-day.

    `reer_deviation` (the long-run PPP input) has no real data source
    wired up yet - see module docstring - so it defaults to `None` and,
    unless a caller supplies a real value from elsewhere, the long-horizon
    regime ends up with 0.0 drift (a continued random walk, wider bands
    only from accumulating volatility, no directional pull).

    Returns `[]` for fewer than 2 price records (nothing to estimate
    volatility or a last price from).
    """
    if len(prices) < 2:
        return []

    sorted_prices = sorted(prices, key=lambda record: record["date"])
    closes = [record["close"] for record in sorted_prices]
    last_price = closes[-1]
    last_date = date.fromisoformat(sorted_prices[-1]["date"])

    volatility_estimate = estimate_daily_volatility(closes)

    datafeed = datafeed or DatafeedClient()
    rate_diff = long_term_rate_diff(from_currency, to_currency, datafeed)
    medium_drift = _medium_drift(rate_diff)

    num_days = years * DAYS_PER_YEAR
    reversion_years = (num_days - MEDIUM_REGIME_END_DAYS) / DAYS_PER_YEAR
    long_drift = _long_drift(reer_deviation, reversion_years)

    daily_drift = _drift_schedule(medium_drift, long_drift)
    bands = price_bands(last_price, volatility_estimate.daily_volatility, num_days, daily_drift)

    fetched_at = datetime.now(UTC).isoformat()
    return [
        {
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "date": (last_date + timedelta(days=band["day"])).isoformat(),
            "p10": round_value(band["p10"]),
            "p50": round_value(band["p50"]),
            "p90": round_value(band["p90"]),
            "regime": regime_for_day(band["day"]),
            "volatility_model": volatility_estimate.model,
            "last_updated": fetched_at,
            "source": "equicast",
        }
        for band in bands
    ]
