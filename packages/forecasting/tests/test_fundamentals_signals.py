import pandas as pd
import pytest
from equicast_forecasting.fundamentals_signals import (
    compute_fundamental_signals,
    compute_valuation_signal,
    current_valuation_multiple,
    historical_multiple_series,
    profit_margin_trend,
    rd_to_revenue,
    revenue_cagr,
    short_interest_ratio,
    valuation_multiple_zscore,
)


def _annual_statement(row_values: dict[str, dict[str, float]]) -> pd.DataFrame:
    """`row_values` is `{row_name: {"YYYY-MM-DD": value, ...}}` - builds a
    DataFrame with real `pd.Timestamp` columns, matching yfinance's own
    financials/balance-sheet shape (not plain string column labels)."""
    all_dates = sorted({d for row in row_values.values() for d in row}, reverse=True)
    columns = [pd.Timestamp(d) for d in all_dates]
    data = {
        row_name: [values.get(d) for d in all_dates] for row_name, values in row_values.items()
    }
    return pd.DataFrame(data, index=all_dates).T.set_axis(columns, axis=1)


def _prices(prices_by_date: dict[str, float]) -> list[dict]:
    return [{"date": d, "close": close} for d, close in prices_by_date.items()]


def test_revenue_cagr_computes_oldest_to_newest_growth() -> None:
    financials = _annual_statement(
        {"Total Revenue": {"2022-12-31": 100.0, "2023-12-31": 110.0, "2024-12-31": 121.0}}
    )
    assert revenue_cagr(financials) == pytest.approx(0.1, rel=0.01)


def test_revenue_cagr_none_with_fewer_than_two_periods() -> None:
    financials = _annual_statement({"Total Revenue": {"2024-12-31": 100.0}})
    assert revenue_cagr(financials) is None
    assert revenue_cagr(None) is None
    assert revenue_cagr(pd.DataFrame()) is None


def test_revenue_cagr_none_for_non_positive_oldest_value() -> None:
    financials = _annual_statement({"Total Revenue": {"2023-12-31": 0.0, "2024-12-31": 100.0}})
    assert revenue_cagr(financials) is None


def test_profit_margin_trend_computes_percentage_point_change() -> None:
    financials = _annual_statement(
        {
            "Total Revenue": {"2023-12-31": 100.0, "2024-12-31": 100.0},
            "Net Income": {"2023-12-31": 10.0, "2024-12-31": 20.0},
        }
    )
    assert profit_margin_trend(financials) == pytest.approx(0.10)


def test_profit_margin_trend_none_when_a_period_is_missing_either_figure() -> None:
    financials = _annual_statement({"Total Revenue": {"2024-12-31": 100.0}})
    assert profit_margin_trend(financials) is None


def test_rd_to_revenue_computes_fraction() -> None:
    financials = _annual_statement(
        {
            "Total Revenue": {"2024-12-31": 200.0},
            "Research And Development": {"2024-12-31": 20.0},
        }
    )
    assert rd_to_revenue(financials) == pytest.approx(0.1)


def test_rd_to_revenue_none_when_no_rd_line_item() -> None:
    financials = _annual_statement({"Total Revenue": {"2024-12-31": 200.0}})
    assert rd_to_revenue(financials) is None


def test_short_interest_ratio_reads_info_field() -> None:
    assert short_interest_ratio({"shortPercentOfFloat": 0.02}) == 0.02
    assert short_interest_ratio({}) is None


def test_current_valuation_multiple_pe_reads_fundamentals() -> None:
    assert current_valuation_multiple("pe", {}, {"trailing_pe": 25.0}, None) == 25.0


def test_current_valuation_multiple_price_to_book_and_book_value_are_the_same_field() -> None:
    fundamentals = {"price_to_book": 4.0}
    assert current_valuation_multiple("price_to_book", {}, fundamentals, None) == 4.0
    assert current_valuation_multiple("book_value", {}, fundamentals, None) == 4.0


def test_current_valuation_multiple_pe_tangible_book_computes_from_balance_sheet() -> None:
    info = {"currentPrice": 50.0, "sharesOutstanding": 10.0}
    balance_sheet = _annual_statement({"Tangible Book Value": {"2024-12-31": 100.0}})
    # tangible book/share = 100/10 = 10; multiple = 50/10 = 5
    assert current_valuation_multiple("pe_tangible_book", info, {}, balance_sheet) == 5.0


def test_current_valuation_multiple_pe_tangible_book_none_when_missing_data() -> None:
    assert current_valuation_multiple("pe_tangible_book", {}, {}, None) is None


def test_current_valuation_multiple_raises_for_unknown_family() -> None:
    with pytest.raises(ValueError, match="Unknown valuation multiple family"):
        current_valuation_multiple("not_a_family", {}, {}, None)


def test_historical_multiple_series_pe_pairs_eps_with_nearest_price() -> None:
    financials = _annual_statement(
        {"Diluted EPS": {"2022-12-31": 2.0, "2023-12-31": 2.5, "2024-12-31": 3.0}}
    )
    prices = _prices({"2022-12-31": 40.0, "2023-12-31": 50.0, "2024-12-31": 60.0})

    series = historical_multiple_series("pe", financials, None, prices)

    assert series == pytest.approx([20.0, 20.0, 20.0])


def test_historical_multiple_series_uses_nearest_price_on_or_before() -> None:
    financials = _annual_statement({"Diluted EPS": {"2024-06-15": 2.0}})
    # No exact price on 2024-06-15 - should use the closest prior date.
    prices = _prices({"2024-06-01": 40.0, "2024-06-10": 44.0, "2024-07-01": 100.0})

    series = historical_multiple_series("pe", financials, None, prices)

    assert series == pytest.approx([22.0])  # 44 / 2.0


def test_historical_multiple_series_skips_periods_with_no_price_history() -> None:
    financials = _annual_statement({"Diluted EPS": {"2020-12-31": 1.0, "2024-12-31": 2.0}})
    prices = _prices({"2024-12-31": 40.0})  # nothing as far back as 2020

    series = historical_multiple_series("pe", financials, None, prices)

    assert series == pytest.approx([20.0])


def test_historical_multiple_series_tangible_book_uses_balance_sheet_and_shares() -> None:
    balance_sheet = _annual_statement(
        {
            "Tangible Book Value": {"2023-12-31": 100.0, "2024-12-31": 120.0},
            "Ordinary Shares Number": {"2023-12-31": 10.0, "2024-12-31": 10.0},
        }
    )
    prices = _prices({"2023-12-31": 30.0, "2024-12-31": 36.0})

    series = historical_multiple_series("pe_tangible_book", None, balance_sheet, prices)

    assert series == pytest.approx([3.0, 3.0])


def test_historical_multiple_series_raises_for_unknown_family() -> None:
    with pytest.raises(ValueError, match="Unknown valuation multiple family"):
        historical_multiple_series("not_a_family", None, None, [])


def test_valuation_multiple_zscore_none_when_current_is_none() -> None:
    assert valuation_multiple_zscore("pe", None, None, None, []) is None


def test_valuation_multiple_zscore_none_with_fewer_than_two_history_points() -> None:
    financials = _annual_statement({"Diluted EPS": {"2024-12-31": 2.0}})
    prices = _prices({"2024-12-31": 40.0})
    assert valuation_multiple_zscore("pe", 20.0, financials, None, prices) is None


def test_valuation_multiple_zscore_none_when_history_has_zero_variance() -> None:
    financials = _annual_statement(
        {"Diluted EPS": {"2023-12-31": 2.0, "2024-12-31": 2.0}}
    )
    prices = _prices({"2023-12-31": 40.0, "2024-12-31": 40.0})
    assert valuation_multiple_zscore("pe", 20.0, financials, None, prices) is None


def test_valuation_multiple_zscore_computes_standard_score() -> None:
    financials = _annual_statement(
        {"Diluted EPS": {"2022-12-31": 2.0, "2023-12-31": 2.0, "2024-12-31": 2.0}}
    )
    # historical PEs: 40/2=20, 50/2=25, 60/2=30 -> mean 25, pstdev ~4.0825
    prices = _prices({"2022-12-31": 40.0, "2023-12-31": 50.0, "2024-12-31": 60.0})

    zscore = valuation_multiple_zscore("pe", 30.0, financials, None, prices)

    assert zscore == pytest.approx((30.0 - 25.0) / 4.0824829, rel=1e-4)


def test_compute_valuation_signal_returns_none_none_when_family_is_none() -> None:
    from unittest.mock import MagicMock

    datafeed = MagicMock()
    assert compute_valuation_signal(None, datafeed, "AAPL", []) == (None, None)
    datafeed.get_info.assert_not_called()


def test_compute_valuation_signal_integrates_current_and_zscore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock

    financials = _annual_statement(
        {"Diluted EPS": {"2023-12-31": 2.0, "2024-12-31": 2.0}, "Total Revenue": {}}
    )
    datafeed = MagicMock()
    datafeed.get_info.return_value = {"trailingEps": 2.0, "currentPrice": 60.0}
    datafeed.get_financials.return_value = financials
    datafeed.get_balance_sheet.return_value = None
    prices = _prices({"2023-12-31": 40.0, "2024-12-31": 50.0})

    current, zscore = compute_valuation_signal("pe", datafeed, "AAPL", prices)

    assert current == pytest.approx(30.0)  # 60 / 2.0 trailing EPS
    assert zscore is not None


def test_compute_fundamental_signals_bundles_all_four() -> None:
    from unittest.mock import MagicMock

    datafeed = MagicMock()
    datafeed.get_info.return_value = {"shortPercentOfFloat": 0.03}
    datafeed.get_financials.return_value = _annual_statement(
        {
            "Total Revenue": {"2023-12-31": 100.0, "2024-12-31": 110.0},
            "Net Income": {"2023-12-31": 10.0, "2024-12-31": 12.0},
            "Research And Development": {"2024-12-31": 5.0},
        }
    )

    result = compute_fundamental_signals(datafeed, "AAPL")

    assert result["revenue_cagr"] == pytest.approx(0.1, rel=0.01)
    assert result["profit_margin_trend"] == pytest.approx(12 / 110 - 10 / 100)
    assert result["rd_to_revenue"] == pytest.approx(5 / 110)
    assert result["short_interest_ratio"] == 0.03
