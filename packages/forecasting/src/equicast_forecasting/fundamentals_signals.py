"""Stock-specific fundamental signal derivation from real financial-
statement/price/short-interest data - feeds stock_forecast.py's
valuation-reversion bias (see sector_registry.py's `valuation_multiple`
per sector) plus a handful of the additional real signals GitHub issue
#66's tables name directly (`revenue_cagr`, `margin_trend`, `rd_to_revenue`,
`short_interest`).

Genuinely stock-specific (financial statements, short interest - none of
this generalizes to FX or any other asset class), unlike volatility.py/
bands.py/monte_carlo.py/regimes.py. Reuses `equicast_metrics.fundamentals`'
own `.info`-first/statement-fallback logic and row-name constants for the
*current* snapshot (`trailing_pe`, `price_to_book`) rather than
re-deriving them - only the *historical* series behind a valuation
z-score, and the few signals `equicast_metrics` doesn't compute at all,
are new here.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any

import pandas as pd
from equicast_datafeed import DatafeedClient
from equicast_metrics.fundamentals import (
    DILUTED_EPS_ROWS,
    NET_INCOME_ROWS,
    STOCKHOLDERS_EQUITY_ROWS,
    TOTAL_REVENUE_ROWS,
    compute_fundamentals,
    latest_statement_value,
)

#: Not in equicast_metrics.fundamentals - only needed here, for the
#: pe_tangible_book multiple family (Banks) and its historical series.
TANGIBLE_BOOK_VALUE_ROWS = ("Tangible Book Value",)
SHARES_OUTSTANDING_ROWS = ("Ordinary Shares Number", "Share Issued")
RESEARCH_AND_DEVELOPMENT_ROWS = ("Research And Development",)

#: Multiple families `compute_valuation_signal` knows how to compute a
#: current value and historical series for - matches sector_schemas.yaml's
#: own `valuation_multiple` values (`null` there means "no family wired up
#: yet," never one of these names).
VALUATION_MULTIPLE_FAMILIES = ("pe", "pe_tangible_book", "price_to_book", "book_value")

#: Minimum historical multiple data points needed to compute a z-score -
#: yfinance's annual financials/balance sheet typically report ~4-5 years,
#: so this is deliberately low (2, the bare minimum a stdev needs), not a
#: "large enough sample" threshold - see `valuation_multiple_zscore`'s
#: docstring for the honest caveat about what a 2-5-point z-score actually
#: means.
MIN_HISTORY_POINTS_FOR_ZSCORE = 2


def _annual_row_values(
    statement: pd.DataFrame | None, row_names: tuple[str, ...]
) -> list[tuple[date, float]]:
    """Every non-null `(period_end_date, value)` pair for the first
    matching row name in `row_names` - `[]` if `statement` is empty/`None`
    or has none of those rows."""
    if statement is None or statement.empty:
        return []
    for name in row_names:
        if name not in statement.index:
            continue
        row = statement.loc[name]
        return [(column.date(), float(value)) for column, value in row.items() if pd.notna(value)]
    return []


def _per_share_series(
    statement: pd.DataFrame | None, value_rows: tuple[str, ...]
) -> list[tuple[date, float]]:
    """`_annual_row_values(statement, value_rows)` divided by that same
    period's `SHARES_OUTSTANDING_ROWS` value - skips a period missing
    either side."""
    values = dict(_annual_row_values(statement, value_rows))
    shares = dict(_annual_row_values(statement, SHARES_OUTSTANDING_ROWS))
    return [
        (period_date, value / shares[period_date])
        for period_date, value in values.items()
        if shares.get(period_date)
    ]


def _nearest_price(prices: list[dict[str, Any]], target: date) -> float | None:
    """Real closing price on the nearest trading day on/before `target` -
    `None` if `prices` has nothing that far back yet."""
    candidates = [record for record in prices if date.fromisoformat(record["date"]) <= target]
    if not candidates:
        return None
    return float(max(candidates, key=lambda record: record["date"])["close"])


def revenue_cagr(financials: pd.DataFrame | None) -> float | None:
    """Annualized revenue growth rate between the oldest and newest
    available annual `Total Revenue` figures - same oldest-vs-newest CAGR
    shape `equicast_forecasting.forecast`'s own dividend growth rate uses.
    `None` with fewer than 2 annual periods, a non-positive oldest value
    (can't compute a meaningful ratio from it), or the two periods sharing
    the same date (shouldn't happen, guards a division by zero)."""
    values = _annual_row_values(financials, TOTAL_REVENUE_ROWS)
    if len(values) < 2:
        return None
    values.sort()
    oldest_date, oldest = values[0]
    newest_date, newest = values[-1]
    if oldest <= 0:
        return None
    years = (newest_date - oldest_date).days / 365
    if years <= 0:
        return None
    return (newest / oldest) ** (1 / years) - 1


def profit_margin_trend(financials: pd.DataFrame | None) -> float | None:
    """Change in profit margin (Net Income / Total Revenue), in percentage
    points, between the oldest and newest available annual periods with
    both figures known - a plain difference rather than a compound growth
    rate (unlike `revenue_cagr`), since a margin can be negative or
    near-zero, where a CAGR-style ratio breaks down. `None` with fewer
    than 2 such periods."""
    revenues = dict(_annual_row_values(financials, TOTAL_REVENUE_ROWS))
    net_incomes = dict(_annual_row_values(financials, NET_INCOME_ROWS))
    dates = sorted(d for d in revenues if d in net_incomes and revenues[d])
    if len(dates) < 2:
        return None
    oldest_margin = net_incomes[dates[0]] / revenues[dates[0]]
    newest_margin = net_incomes[dates[-1]] / revenues[dates[-1]]
    return newest_margin - oldest_margin


def rd_to_revenue(financials: pd.DataFrame | None) -> float | None:
    """Most recent annual Research And Development expense as a fraction
    of Total Revenue - `None` if either is missing (most non-Technology
    tickers report no R&D line item at all)."""
    rd = latest_statement_value(financials, RESEARCH_AND_DEVELOPMENT_ROWS)
    revenue = latest_statement_value(financials, TOTAL_REVENUE_ROWS)
    if rd is None or revenue is None or revenue == 0:
        return None
    return rd / revenue


def short_interest_ratio(info: dict[str, Any]) -> float | None:
    """The fraction of a stock's float currently sold short
    (`shortPercentOfFloat`) - `None` if yfinance doesn't report it."""
    value = info.get("shortPercentOfFloat")
    return float(value) if value is not None else None


def current_valuation_multiple(
    family: str,
    info: dict[str, Any],
    fundamentals: dict[str, float | None],
    balance_sheet: pd.DataFrame | None,
) -> float | None:
    """Today's value of `family`'s own multiple. `"pe"`/`"price_to_book"`/
    `"book_value"` read straight off `fundamentals` (`trailing_pe`/
    `price_to_book` - see `equicast_metrics.fundamentals.
    compute_fundamentals`; `"book_value"` is the same computation as
    `"price_to_book"` under a different name - both sector schemas mean
    "price relative to book value per share," see sector_schemas.yaml).
    `"pe_tangible_book"` is computed fresh here, since `equicast_metrics`
    has no tangible-book-value field at all.

    Raises `ValueError` for any other `family` - a programming error (bad
    sector_schemas.yaml entry), not a data-availability one.
    """
    if family in ("price_to_book", "book_value"):
        return fundamentals.get("price_to_book")
    if family == "pe":
        return fundamentals.get("trailing_pe")
    if family == "pe_tangible_book":
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding")
        tangible_book_value = latest_statement_value(balance_sheet, TANGIBLE_BOOK_VALUE_ROWS)
        if current_price is None or not shares or tangible_book_value is None:
            return None
        tangible_book_per_share = tangible_book_value / shares
        if tangible_book_per_share == 0:
            return None
        return current_price / tangible_book_per_share
    raise ValueError(f"Unknown valuation multiple family: {family!r}")


def historical_multiple_series(
    family: str,
    financials: pd.DataFrame | None,
    balance_sheet: pd.DataFrame | None,
    prices: list[dict[str, Any]],
) -> list[float]:
    """Reconstruct `family`'s own historical values, oldest first, by
    pairing each available annual financial-statement period's per-share
    fundamental (Diluted EPS for `"pe"`/`"pe_tangible_book"`'s numerator's
    counterpart... - tangible/plain book value per share for the
    book-value families) with the real closing price nearest that
    period's end date.

    This is a coarse, *annual*-resolution series (typically ~4-5 points -
    as many years as yfinance's financials/balance sheet report), not a
    true daily-resolution historical multiple - a real z-score would want
    far more observations than this to be statistically meaningful; treat
    it as a rough "cheap/rich relative to its last few years" signal, not
    a precise statistical one.

    Raises `ValueError` for any `family` not in `VALUATION_MULTIPLE_FAMILIES`.
    """
    if family not in VALUATION_MULTIPLE_FAMILIES:
        raise ValueError(f"Unknown valuation multiple family: {family!r}")

    if family == "pe":
        per_share_series = _annual_row_values(financials, DILUTED_EPS_ROWS)
    elif family == "pe_tangible_book":
        per_share_series = _per_share_series(balance_sheet, TANGIBLE_BOOK_VALUE_ROWS)
    else:  # "price_to_book" / "book_value"
        per_share_series = _per_share_series(balance_sheet, STOCKHOLDERS_EQUITY_ROWS)

    multiples = []
    for period_date, per_share in sorted(per_share_series):
        if per_share == 0:
            continue
        price = _nearest_price(prices, period_date)
        if price is None:
            continue
        multiples.append(price / per_share)
    return multiples


def valuation_multiple_zscore(
    family: str,
    current_multiple: float | None,
    financials: pd.DataFrame | None,
    balance_sheet: pd.DataFrame | None,
    prices: list[dict[str, Any]],
) -> float | None:
    """`current_multiple`'s z-score against `family`'s own historical
    series (see `historical_multiple_series`) - how many standard
    deviations today's multiple sits from its own (coarse, annual-
    resolution) historical average. `None` when `current_multiple` is
    `None`, fewer than `MIN_HISTORY_POINTS_FOR_ZSCORE` historical points
    are reconstructable, or the historical series has zero variance (every
    point identical - can't divide by a zero stdev)."""
    if current_multiple is None:
        return None
    history = historical_multiple_series(family, financials, balance_sheet, prices)
    if len(history) < MIN_HISTORY_POINTS_FOR_ZSCORE:
        return None
    stdev = statistics.pstdev(history)
    if stdev == 0:
        return None
    return (current_multiple - statistics.fmean(history)) / stdev


def compute_valuation_signal(
    family: str | None, datafeed: DatafeedClient, symbol: str, prices: list[dict[str, Any]]
) -> tuple[float | None, float | None]:
    """`(current_multiple, zscore)` for `family` (see sector_schemas.yaml's
    `valuation_multiple`) - `(None, None)` when `family` is `None` (this
    sector has no real multiple wired up yet - see
    `sector_registry.SectorSchema`)."""
    if family is None:
        return None, None

    info = datafeed.get_info(symbol)
    financials = datafeed.get_financials(symbol)
    balance_sheet = datafeed.get_balance_sheet(symbol)
    fundamentals, _ = compute_fundamentals(info, lambda: financials, lambda: balance_sheet)

    current = current_valuation_multiple(family, info, fundamentals, balance_sheet)
    zscore = valuation_multiple_zscore(family, current, financials, balance_sheet, prices)
    return current, zscore


def compute_fundamental_signals(datafeed: DatafeedClient, symbol: str) -> dict[str, float | None]:
    """The extra real signals from issue #66's tables equicast can compute
    today, independent of sector - every sector's schema either names one
    of these directly (e.g. Technology's `revenue_cagr`/`rd_to_revenue`),
    or a close analogue (e.g. Consumer Cyclical's `margin_trend`,
    Biotech's `short_interest`)."""
    info = datafeed.get_info(symbol)
    financials = datafeed.get_financials(symbol)
    return {
        "revenue_cagr": revenue_cagr(financials),
        "profit_margin_trend": profit_margin_trend(financials),
        "rd_to_revenue": rd_to_revenue(financials),
        "short_interest_ratio": short_interest_ratio(info),
    }
