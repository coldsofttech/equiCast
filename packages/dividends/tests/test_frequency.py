from datetime import date, timedelta

from equicast_dividends.frequency import dividend_frequency, median_payout_gap_days


def _records(dates: list[date]) -> list[dict]:
    return [{"ex_dividend_date": d.isoformat()} for d in dates]


def _spaced(start: date, gap_days: int, count: int) -> list[date]:
    return [start + timedelta(days=gap_days * i) for i in range(count)]


def test_no_payouts_is_not_applicable() -> None:
    assert dividend_frequency([]) == "not_applicable"


def test_single_payout_is_not_applicable() -> None:
    assert dividend_frequency(_records([date(2026, 1, 15)])) == "not_applicable"


def test_weekly_cadence() -> None:
    dates = _spaced(date(2025, 1, 1), 7, 6)
    assert dividend_frequency(_records(dates)) == "weekly"


def test_monthly_cadence() -> None:
    dates = _spaced(date(2025, 1, 1), 30, 8)
    assert dividend_frequency(_records(dates)) == "monthly"


def test_quarterly_cadence() -> None:
    dates = _spaced(date(2024, 1, 1), 91, 8)
    assert dividend_frequency(_records(dates)) == "quarterly"


def test_half_yearly_cadence() -> None:
    dates = _spaced(date(2022, 1, 1), 182, 6)
    assert dividend_frequency(_records(dates)) == "half_yearly"


def test_yearly_cadence() -> None:
    dates = _spaced(date(2016, 1, 1), 365, 10)
    assert dividend_frequency(_records(dates)) == "yearly"


def test_erratic_gaps_are_irregular() -> None:
    dates = [date(2020, 1, 1), date(2020, 1, 20), date(2022, 6, 1), date(2023, 12, 1)]
    assert dividend_frequency(_records(dates)) == "irregular"


def test_one_outlier_gap_does_not_flip_an_otherwise_quarterly_cadence() -> None:
    # 4 clean quarterly gaps plus one skipped/late payout (491 days after the
    # previous one) - the median of [91, 91, 91, 91, 491] is still 91, so one
    # outlier doesn't flip the whole ticker to "irregular".
    dates = _spaced(date(2024, 1, 1), 91, 5)
    dates.append(dates[-1] + timedelta(days=400))
    assert dividend_frequency(_records(dates)) == "quarterly"


def test_only_the_most_recent_ten_payouts_are_considered() -> None:
    # An erratic start to the payout history shouldn't outvote 10 clean recent
    # quarterly payouts - only the most recent 10 records feed the median.
    old_erratic = [date(2000, 1, 1), date(2000, 3, 1), date(2005, 1, 1)]
    recent_quarterly = _spaced(date(2023, 1, 1), 91, 10)
    assert dividend_frequency(_records(old_erratic + recent_quarterly)) == "quarterly"


def test_records_do_not_need_to_be_pre_sorted() -> None:
    dates = _spaced(date(2025, 1, 1), 30, 6)
    shuffled = [dates[3], dates[0], dates[5], dates[1], dates[4], dates[2]]
    assert dividend_frequency(_records(shuffled)) == "monthly"


def test_median_payout_gap_days_returns_none_below_the_minimum() -> None:
    assert median_payout_gap_days([]) is None
    assert median_payout_gap_days(_records([date(2026, 1, 15)])) is None


def test_median_payout_gap_days_returns_the_raw_median() -> None:
    dates = _spaced(date(2024, 1, 1), 91, 5)
    dates.append(dates[-1] + timedelta(days=400))
    # Same fixture as the "one outlier gap" dividend_frequency test above -
    # the raw median gap is 91, not a canonical/rounded value.
    assert median_payout_gap_days(_records(dates)) == 91
