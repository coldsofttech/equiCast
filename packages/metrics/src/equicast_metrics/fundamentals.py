"""Pure functions for valuation/fundamental metrics on a stock ticker.

Each field prefers yfinance's `.info` dict directly, then a ratio built from
other `.info` fields, and only as a last resort a line item pulled from the
annual balance sheet / income statement (fetched lazily, at most once each,
since most tickers resolve every field from `.info` alone). yfinance's row
names for those two statements have varied across versions, so each lookup
tries a few candidate names.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

TOTAL_ASSETS_ROWS = ("Total Assets",)
TOTAL_LIABILITIES_ROWS = ("Total Liabilities Net Minority Interest", "Total Liab")
STOCKHOLDERS_EQUITY_ROWS = (
    "Stockholders Equity",
    "Total Stockholder Equity",
    "Common Stock Equity",
)
TOTAL_REVENUE_ROWS = ("Total Revenue",)
GROSS_PROFIT_ROWS = ("Gross Profit",)
OPERATING_INCOME_ROWS = ("Operating Income",)
NET_INCOME_ROWS = ("Net Income", "Net Income Common Stockholders")
DILUTED_EPS_ROWS = ("Diluted EPS",)


def latest_statement_value(
    statement: pd.DataFrame | None, row_names: tuple[str, ...]
) -> float | None:
    """Most-recent period's value for the first matching row name, or `None`."""
    if statement is None or statement.empty:
        return None
    for name in row_names:
        if name in statement.index:
            value = statement.loc[name].iloc[0]
            if pd.notna(value):
                return float(value)
    return None


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


class _Resolver:
    """Tries `.info` first, then each fallback in order; remembers whether
    any field ever needed one, for the caller's `source` field. Also caches
    `get_financials()`/`get_balance_sheet()` itself (regardless of whether
    the callables passed in already do), so a ticker needing several
    statement-derived fields still only fetches each statement once."""

    def __init__(
        self,
        get_financials: Callable[[], pd.DataFrame | None],
        get_balance_sheet: Callable[[], pd.DataFrame | None],
    ) -> None:
        self._get_financials = get_financials
        self._get_balance_sheet = get_balance_sheet
        self._financials: pd.DataFrame | None = None
        self._financials_fetched = False
        self._balance_sheet: pd.DataFrame | None = None
        self._balance_sheet_fetched = False
        self.used_fallback = False

    def resolve(self, direct: float | None, *fallbacks: Callable[[], float | None]) -> float | None:
        if direct is not None:
            return direct
        for fallback in fallbacks:
            value = fallback()
            if value is not None:
                self.used_fallback = True
                return value
        return None

    def financials_row(self, row_names: tuple[str, ...]) -> float | None:
        if not self._financials_fetched:
            self._financials_fetched = True
            self._financials = self._get_financials()
        return latest_statement_value(self._financials, row_names)

    def balance_sheet_row(self, row_names: tuple[str, ...]) -> float | None:
        if not self._balance_sheet_fetched:
            self._balance_sheet_fetched = True
            self._balance_sheet = self._get_balance_sheet()
        return latest_statement_value(self._balance_sheet, row_names)


def compute_fundamentals(
    info: dict[str, Any],
    get_financials: Callable[[], pd.DataFrame | None],
    get_balance_sheet: Callable[[], pd.DataFrame | None],
) -> tuple[dict[str, float | None], bool]:
    """Compute the 15 valuation/fundamental fields for one stock ticker.

    Returns `(values, used_fallback)` with unrounded raw numbers — the
    caller (`MetricsClient.fundamentals`) applies `round_value()` and adds
    `last_updated`/`source`.
    """
    r = _Resolver(get_financials, get_balance_sheet)

    market_cap = info.get("marketCap")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    shares_outstanding = info.get("sharesOutstanding")

    total_revenue = r.resolve(
        info.get("totalRevenue"), lambda: r.financials_row(TOTAL_REVENUE_ROWS)
    )
    net_income = r.resolve(info.get("netIncomeToCommon"), lambda: r.financials_row(NET_INCOME_ROWS))
    total_assets = r.resolve(None, lambda: r.balance_sheet_row(TOTAL_ASSETS_ROWS))
    total_liabilities = r.resolve(None, lambda: r.balance_sheet_row(TOTAL_LIABILITIES_ROWS))
    stockholders_equity = r.resolve(None, lambda: r.balance_sheet_row(STOCKHOLDERS_EQUITY_ROWS))

    # yfinance's `.info` doesn't carry forward-looking earnings estimates
    # anywhere but `forwardEps`/`forwardPE` themselves, so those two have no
    # statement-based fallback - historical financials can't predict them.
    trailing_eps = r.resolve(
        info.get("trailingEps"),
        lambda: r.financials_row(DILUTED_EPS_ROWS),
        lambda: ratio(net_income, shares_outstanding),
    )
    forward_eps = info.get("forwardEps")

    trailing_pe = r.resolve(info.get("trailingPE"), lambda: ratio(current_price, trailing_eps))
    forward_pe = r.resolve(info.get("forwardPE"), lambda: ratio(current_price, forward_eps))

    peg = info.get("trailingPegRatio") or info.get("pegRatio")
    if peg is None:
        earnings_growth = info.get("earningsGrowth")
        if trailing_pe is not None and earnings_growth:
            peg = trailing_pe / (earnings_growth * 100)
            r.used_fallback = True

    price_to_book = r.resolve(
        info.get("priceToBook"), lambda: ratio(market_cap, stockholders_equity)
    )
    price_to_sales = r.resolve(
        info.get("priceToSalesTrailing12Months"), lambda: ratio(market_cap, total_revenue)
    )
    ev_ebitda = r.resolve(
        info.get("enterpriseToEbitda"),
        lambda: ratio(info.get("enterpriseValue"), info.get("ebitda")),
    )

    gross_margin = r.resolve(
        info.get("grossMargins"), lambda: ratio(r.financials_row(GROSS_PROFIT_ROWS), total_revenue)
    )
    operating_margin = r.resolve(
        info.get("operatingMargins"),
        lambda: ratio(r.financials_row(OPERATING_INCOME_ROWS), total_revenue),
    )
    profit_margin = r.resolve(info.get("profitMargins"), lambda: ratio(net_income, total_revenue))

    return_on_equity = r.resolve(
        info.get("returnOnEquity"), lambda: ratio(net_income, stockholders_equity)
    )
    return_on_assets = r.resolve(
        info.get("returnOnAssets"), lambda: ratio(net_income, total_assets)
    )

    def _debt_to_equity_from_statements() -> float | None:
        # yfinance's own `debtToEquity` is a percentage (e.g. 150.0 == 150%),
        # so the statement-derived ratio is scaled to match.
        value = ratio(total_liabilities, stockholders_equity)
        return value * 100 if value is not None else None

    debt_to_equity = r.resolve(info.get("debtToEquity"), _debt_to_equity_from_statements)

    # No balance sheet/income statement line item is "free cash flow per
    # share" - it's always built, first from yfinance's own freeCashflow
    # total, falling back to operatingCashflow + capitalExpenditures
    # (capex is reported negative, so this subtracts it).
    free_cash_flow = info.get("freeCashflow")
    if free_cash_flow is None:
        operating_cashflow = info.get("operatingCashflow")
        capital_expenditures = info.get("capitalExpenditures")
        if operating_cashflow is not None and capital_expenditures is not None:
            free_cash_flow = operating_cashflow + capital_expenditures
    free_cash_flow_per_share = ratio(free_cash_flow, shares_outstanding)
    if free_cash_flow_per_share is not None:
        r.used_fallback = True

    values = {
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "trailing_eps": trailing_eps,
        "forward_eps": forward_eps,
        "peg": peg,
        "price_to_book": price_to_book,
        "price_to_sales": price_to_sales,
        "ev_ebitda": ev_ebitda,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "profit_margin": profit_margin,
        "return_on_equity": return_on_equity,
        "return_on_assets": return_on_assets,
        "debt_to_equity": debt_to_equity,
        "free_cash_flow_per_share": free_cash_flow_per_share,
    }
    return values, r.used_fallback
