import pandas as pd
import pytest
from equicast_metrics.fundamentals import compute_fundamentals, latest_statement_value, ratio


def _no_financials() -> pd.DataFrame | None:
    return None


def _no_balance_sheet() -> pd.DataFrame | None:
    return None


def test_ratio_returns_none_for_missing_or_zero_denominator() -> None:
    assert ratio(10, None) is None
    assert ratio(None, 10) is None
    assert ratio(10, 0) is None
    assert ratio(10, 4) == 2.5


def test_latest_statement_value_returns_none_for_empty_or_missing_statement() -> None:
    assert latest_statement_value(None, ("Total Assets",)) is None
    assert latest_statement_value(pd.DataFrame(), ("Total Assets",)) is None


def test_latest_statement_value_picks_first_matching_row_most_recent_column() -> None:
    statement = pd.DataFrame({"2026-12-31": [100.0], "2025-12-31": [90.0]}, index=["Total Assets"])
    assert latest_statement_value(statement, ("Total Assets",)) == 100.0


def test_latest_statement_value_tries_fallback_row_names_in_order() -> None:
    statement = pd.DataFrame({"2026-12-31": [50.0]}, index=["Total Liab"])
    row_names = ("Total Liabilities Net Minority Interest", "Total Liab")
    assert latest_statement_value(statement, row_names) == 50.0


def test_compute_fundamentals_uses_direct_info_fields_when_present() -> None:
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
        "freeCashflow": 90000000000,
        "sharesOutstanding": 15000000000,
    }

    values, used_fallback = compute_fundamentals(info, _no_financials, _no_balance_sheet)

    assert values["trailing_pe"] == 30.0
    assert values["forward_pe"] == 25.0
    assert values["trailing_eps"] == 6.0
    assert values["forward_eps"] == 7.2
    assert values["peg"] == 2.1
    assert values["price_to_book"] == 45.0
    assert values["price_to_sales"] == 8.0
    assert values["ev_ebitda"] == 20.0
    assert values["gross_margin"] == 0.45
    assert values["operating_margin"] == 0.3
    assert values["profit_margin"] == 0.25
    assert values["return_on_equity"] == 1.5
    assert values["return_on_assets"] == 0.28
    assert values["debt_to_equity"] == 150.0
    assert values["free_cash_flow_per_share"] == pytest.approx(6.0)
    # free_cash_flow_per_share has no direct yfinance field, so it always
    # counts as a fallback even though every input came straight from .info.
    assert used_fallback is True


def test_compute_fundamentals_falls_back_to_derived_ratios() -> None:
    info = {
        "currentPrice": 100.0,
        "trailingEps": 5.0,
        "marketCap": 1000.0,
        "totalRevenue": 500.0,
        "enterpriseValue": 1200.0,
        "ebitda": 100.0,
        "earningsGrowth": 0.15,
    }

    values, used_fallback = compute_fundamentals(info, _no_financials, _no_balance_sheet)

    assert values["trailing_pe"] == pytest.approx(20.0)  # currentPrice / trailingEps
    assert values["price_to_sales"] == pytest.approx(2.0)  # marketCap / totalRevenue
    assert values["ev_ebitda"] == pytest.approx(12.0)  # enterpriseValue / ebitda
    assert values["peg"] == pytest.approx(20.0 / 15.0)  # trailing_pe / (earningsGrowth * 100)
    assert used_fallback is True


def test_compute_fundamentals_falls_back_to_balance_sheet_and_financials() -> None:
    info = {"currentPrice": 100.0, "marketCap": 1000.0}
    financials = pd.DataFrame(
        {"2026-12-31": [500.0, 200.0, 150.0, 80.0, 4.0]},
        index=[
            "Total Revenue",
            "Gross Profit",
            "Operating Income",
            "Net Income",
            "Diluted EPS",
        ],
    )
    balance_sheet = pd.DataFrame(
        {"2026-12-31": [1000.0, 400.0, 600.0]},
        index=["Total Assets", "Total Liabilities Net Minority Interest", "Stockholders Equity"],
    )

    values, used_fallback = compute_fundamentals(info, lambda: financials, lambda: balance_sheet)

    assert values["trailing_eps"] == 4.0  # Diluted EPS row
    assert values["gross_margin"] == pytest.approx(200.0 / 500.0)
    assert values["operating_margin"] == pytest.approx(150.0 / 500.0)
    assert values["profit_margin"] == pytest.approx(80.0 / 500.0)
    assert values["return_on_equity"] == pytest.approx(80.0 / 600.0)
    assert values["return_on_assets"] == pytest.approx(80.0 / 1000.0)
    assert values["debt_to_equity"] == pytest.approx((400.0 / 600.0) * 100)
    assert used_fallback is True


def test_compute_fundamentals_fetches_statements_lazily_and_only_once() -> None:
    calls = {"financials": 0, "balance_sheet": 0}

    def get_financials() -> pd.DataFrame | None:
        calls["financials"] += 1
        return pd.DataFrame({"2026-12-31": [500.0]}, index=["Total Revenue"])

    def get_balance_sheet() -> pd.DataFrame | None:
        calls["balance_sheet"] += 1
        return pd.DataFrame({"2026-12-31": [1000.0]}, index=["Total Assets"])

    info: dict = {}  # everything missing -> every fallback tier gets exercised
    compute_fundamentals(info, get_financials, get_balance_sheet)

    assert calls["financials"] == 1
    assert calls["balance_sheet"] == 1


def test_compute_fundamentals_forward_eps_and_pe_have_no_statement_fallback() -> None:
    info = {"currentPrice": 100.0}
    values, _ = compute_fundamentals(info, _no_financials, _no_balance_sheet)

    assert values["forward_eps"] is None
    assert values["forward_pe"] is None


def test_compute_fundamentals_returns_none_when_nothing_available() -> None:
    values, used_fallback = compute_fundamentals({}, _no_financials, _no_balance_sheet)

    assert all(value is None for value in values.values())
    assert used_fallback is False


def test_compute_fundamentals_free_cash_flow_per_share_falls_back_to_cashflow_minus_capex() -> None:
    info = {
        "operatingCashflow": 100.0,
        "capitalExpenditures": -20.0,  # capex is reported negative by yfinance
        "sharesOutstanding": 40.0,
    }

    values, used_fallback = compute_fundamentals(info, _no_financials, _no_balance_sheet)

    assert values["free_cash_flow_per_share"] == pytest.approx((100.0 - 20.0) / 40.0)
    assert used_fallback is True
