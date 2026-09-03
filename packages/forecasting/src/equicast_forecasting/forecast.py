"""Project a symbol's future dividend payouts from its actual payout history."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from equicast_datafeed import round_value
from equicast_dividends import dividend_frequency, median_payout_gap_days

#: Cadences worth projecting forward. `dividend_frequency()`'s other two labels
#: ("irregular", "not_applicable") mean there's no dependable cadence to extend -
#: a classification this uncertain about the *past* shouldn't be extrapolated
#: years into the future.
_FORECASTABLE_FREQUENCIES = frozenset({"weekly", "monthly", "quarterly", "half_yearly", "yearly"})

#: Look back at most this many full calendar years of history when computing
#: the trailing dividend growth rate - a longer window would let very old
#: history (a payer that behaved differently a decade ago) dominate the rate
#: used to project the next `years` years.
_GROWTH_LOOKBACK_YEARS = 5

#: The trailing growth rate is clamped to this range before being compounded
#: forward, so one outlier historical year (a special dividend inflating a
#: single year's total, or a one-off cut) doesn't produce an implausible
#: runaway compound over a long horizon.
_GROWTH_RATE_CLAMP = (-0.5, 0.5)


def _annual_totals(dates_amounts: list[tuple[date, float]], before_year: int) -> dict[int, float]:
    """Sum `dates_amounts` into one total per calendar year, for years strictly
    before `before_year` only - the current year may not be complete yet, so
    including it would understate that year's eventual total and skew the
    growth rate toward a false slowdown."""
    totals: dict[int, float] = {}
    for payout_date, amount in dates_amounts:
        if payout_date.year < before_year:
            totals[payout_date.year] = totals.get(payout_date.year, 0.0) + amount
    return totals


def _dividend_growth_rate(dates_amounts: list[tuple[date, float]], today: date) -> float:
    """Trailing annualized dividend growth rate, comparing the oldest to the
    newest of the most recent `_GROWTH_LOOKBACK_YEARS + 1` full calendar years
    of summed payouts.

    Returns `0.0` (flat - no growth or decline assumed) if there are fewer
    than 2 full years to compare, or if the older year's total is 0 (can't
    compute a meaningful ratio from it - e.g. payouts only started partway
    through that year). Otherwise clamped to `_GROWTH_RATE_CLAMP`.
    """
    totals = _annual_totals(dates_amounts, before_year=today.year)
    years = sorted(totals)[-(_GROWTH_LOOKBACK_YEARS + 1) :]
    if len(years) < 2:
        return 0.0

    oldest_year, newest_year = years[0], years[-1]
    oldest_total, newest_total = totals[oldest_year], totals[newest_year]
    if oldest_total <= 0:
        return 0.0

    rate = (newest_total / oldest_total) ** (1 / (newest_year - oldest_year)) - 1
    return max(_GROWTH_RATE_CLAMP[0], min(rate, _GROWTH_RATE_CLAMP[1]))


def dividends(records: list[dict[str, Any]], years: int = 10) -> list[dict[str, Any]]:
    """Project up to `years` years of future dividend payouts for a symbol from
    its actual ex-dividend-date history (`records`, shaped like
    `DividendsClient.dividends()`'s output).

    Returns `[]` when there isn't a dependable cadence to extend - the same
    `"irregular"`/`"not_applicable"` cases `dividend_frequency()` flags (a
    genuinely erratic payer, or fewer than 2 recorded payouts) aren't
    projected forward.

    Each projected payout continues the ticker's *actual* empirical cadence
    forward from its most recent real payout (`median_payout_gap_days()` -
    the same day-gap `dividend_frequency()` classifies, not a fixed
    per-label constant, so a payer whose real median gap is 84 days keeps
    stepping by 84, not by "quarterly"'s canonical ~91), out to `years` years
    from today. The amount compounds once per calendar year crossed (relative
    to the last actual payout) at a trailing growth rate derived from
    full-year payout totals - see `_dividend_growth_rate` - 0.0 ("flat",
    repeating the last actual amount) if there isn't enough full-year history
    to compute one.

    Each returned record is shaped like a real dividend record
    (`{ticker, currency, ex_dividend_date, price, last_updated, source}`)
    plus a `dividend_frequency` field naming the cadence assumption used, and
    `source: "equicast"` rather than `"yfinance"` - this is a computed
    projection, not observed data.
    """
    if not records:
        return []

    frequency = dividend_frequency(records)
    if frequency not in _FORECASTABLE_FREQUENCIES:
        return []

    gap_days = median_payout_gap_days(records)
    assert gap_days is not None  # frequency wouldn't be forecastable otherwise

    dates_amounts = sorted(
        (date.fromisoformat(record["ex_dividend_date"]), record["price"]) for record in records
    )
    last_date, last_amount = dates_amounts[-1]

    today = datetime.now(UTC).date()
    growth_rate = _dividend_growth_rate(dates_amounts, today)
    horizon_end = today + timedelta(days=365 * years)
    fetched_at = datetime.now(UTC).isoformat()
    ticker = records[0]["ticker"]
    currency = records[0]["currency"]

    forecasts = []
    next_date = last_date + timedelta(days=gap_days)
    while next_date <= horizon_end:
        years_ahead = next_date.year - last_date.year
        projected_amount = round_value(last_amount * (1 + growth_rate) ** years_ahead)
        forecasts.append(
            {
                "ticker": ticker,
                "currency": currency,
                "ex_dividend_date": next_date.isoformat(),
                "price": projected_amount,
                "dividend_frequency": frequency,
                "last_updated": fetched_at,
                "source": "equicast",
            }
        )
        next_date = next_date + timedelta(days=gap_days)
    return forecasts
