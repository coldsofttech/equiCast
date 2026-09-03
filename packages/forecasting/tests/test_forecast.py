from datetime import date, timedelta

from equicast_forecasting.forecast import dividends


def _record(ticker: str, ex_dividend_date: date, price: float, **overrides) -> dict:
    record = {
        "ticker": ticker,
        "currency": "USD",
        "ex_dividend_date": ex_dividend_date.isoformat(),
        "price": price,
        "last_updated": "2026-08-30T09:00:02+00:00",
        "source": "yfinance",
    }
    record.update(overrides)
    return record


def _quarterly_history(
    ticker: str, amount_for_year: float | list[float], num_years: int = 5
) -> list[dict]:
    """`num_years` full calendar years of quarterly payouts (Feb/May/Aug/Nov
    10th each year), ending with the most recently *completed* calendar
    year - calendar-aligned (not a fixed day-count gap from a start date) so
    each year gets exactly 4 payouts with no drift, keeping annual totals
    exact for the growth-rate tests below.

    `amount_for_year` is either one flat amount for every payout, or a list
    with one amount per year (oldest first) for a payer with a real,
    year-over-year growth trend.
    """
    amounts = (
        amount_for_year if isinstance(amount_for_year, list) else [amount_for_year] * num_years
    )
    end_year = date.today().year - 1  # most recently completed full year
    records = []
    for year_index in range(num_years):
        year = end_year - (num_years - 1) + year_index
        for month, day in ((2, 10), (5, 10), (8, 10), (11, 10)):
            records.append(_record(ticker, date(year, month, day), amounts[year_index]))
    return records


def test_no_records_returns_no_forecast() -> None:
    assert dividends([]) == []


def test_not_applicable_frequency_returns_no_forecast() -> None:
    # A single historical payout -> dividend_frequency() is "not_applicable".
    records = [_record("AAPL", date.today() - timedelta(days=30), 0.26)]
    assert dividends(records) == []


def test_irregular_frequency_returns_no_forecast() -> None:
    today = date.today()
    records = [
        _record("AAPL", today - timedelta(days=2000), 0.2),
        _record("AAPL", today - timedelta(days=1980), 0.2),
        _record("AAPL", today - timedelta(days=1200), 0.2),
        _record("AAPL", today - timedelta(days=600), 0.2),
    ]
    assert dividends(records) == []


def test_projects_forward_using_the_real_median_gap_not_a_canonical_one() -> None:
    # 5 payouts 84 days apart (still classified "quarterly", but not exactly
    # 91) - the forecast should keep stepping by the real 84-day gap.
    today = date.today()
    records = [_record("AAPL", today - timedelta(days=84 * i), 0.5) for i in range(5, 0, -1)]
    last_actual = date.fromisoformat(max(r["ex_dividend_date"] for r in records))

    forecast = dividends(records, years=1)

    assert forecast
    first_projected = date.fromisoformat(forecast[0]["ex_dividend_date"])
    assert first_projected == last_actual + timedelta(days=84)
    if len(forecast) > 1:
        second_projected = date.fromisoformat(forecast[1]["ex_dividend_date"])
        assert (second_projected - first_projected).days == 84


def test_flat_history_projects_flat_amounts() -> None:
    # Same amount every quarter, spanning several full years -> no growth
    # rate to detect, so every projected payout keeps the same amount.
    records = _quarterly_history("AAPL", 0.5, num_years=5)

    forecast = dividends(records, years=10)

    assert forecast
    assert all(row["price"] == 0.5 for row in forecast)
    assert all(row["dividend_frequency"] == "quarterly" for row in forecast)
    assert all(row["source"] == "equicast" for row in forecast)
    assert all(row["ticker"] == "AAPL" and row["currency"] == "USD" for row in forecast)


def test_growing_history_projects_increasing_amounts() -> None:
    # Doubling total per year for 5 full years - a payer with a real,
    # detectable growth trend.
    records = _quarterly_history("AAPL", [0.1 * (2**i) for i in range(5)], num_years=5)

    forecast = dividends(records, years=10)

    assert forecast
    # Amounts should trend upward across the forecast (not stay flat, not
    # oscillate) - the last projected payout should be worth noticeably more
    # than the first.
    assert forecast[-1]["price"] > forecast[0]["price"]
    # Monotonically non-decreasing: growth only compounds forward.
    prices = [row["price"] for row in forecast]
    assert prices == sorted(prices)


def test_extreme_historical_growth_is_clamped() -> None:
    # A 100x jump in total per year (a data anomaly, not a real sustainable
    # growth rate) shouldn't compound unchecked over a 10-year horizon.
    records = _quarterly_history("AAPL", [0.01, 0.01, 1.0, 1.0, 1.0], num_years=5)
    last_actual_year = date.today().year - 1  # matches _quarterly_history's end_year

    forecast = dividends(records, years=10)

    last_price = forecast[-1]["price"]
    max_years_ahead = date.fromisoformat(forecast[-1]["ex_dividend_date"]).year - last_actual_year
    # Clamped to +50%/year: last actual amount (1.0) compounded at exactly
    # the clamp ceiling for as many years as this forecast actually spans is
    # already an extreme upper bound - actual growth should never exceed it
    # even with a runaway historical ratio feeding in.
    assert last_price <= 1.0 * 1.5**max_years_ahead


def test_years_parameter_controls_horizon_length() -> None:
    records = _quarterly_history("AAPL", 0.5, num_years=5)

    short_forecast = dividends(records, years=1)
    long_forecast = dividends(records, years=10)

    assert len(short_forecast) < len(long_forecast)
    for row in long_forecast:
        assert date.fromisoformat(row["ex_dividend_date"]) <= date.today() + timedelta(days=3650)
