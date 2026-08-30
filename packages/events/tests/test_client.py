import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_datafeed import YFINANCE_DATA_DISCLAIMER, DatafeedClient
from equicast_datafeed.disclaimers import reset_warned
from equicast_events.client import (
    EARNINGS_DEFAULT_LIMIT,
    EARNINGS_FULL_LOAD_LIMIT,
    EQUICAST_EVENTS_DISCLAIMER,
    EventsClient,
)


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


def _earnings_df(rows: list[tuple[str, float | None, float | None, float | None]]) -> pd.DataFrame:
    index = pd.DatetimeIndex([date for date, *_ in rows]).tz_localize("America/New_York")
    return pd.DataFrame(
        {
            "EPS Estimate": [eps_estimate for _, eps_estimate, _, _ in rows],
            "Reported EPS": [reported_eps for _, _, reported_eps, _ in rows],
            "Surprise(%)": [surprise for _, _, _, surprise in rows],
        },
        index=index.rename("Earnings Date"),
    )


def _ratings_df(rows: list[tuple[str, str, str, str, str]]) -> pd.DataFrame:
    index = pd.DatetimeIndex([date for date, *_ in rows]).rename("GradeDate")
    return pd.DataFrame(
        {
            "Firm": [firm for _, firm, _, _, _ in rows],
            "ToGrade": [to_grade for _, _, to_grade, _, _ in rows],
            "FromGrade": [from_grade for _, _, _, from_grade, _ in rows],
            "Action": [action for _, _, _, _, action in rows],
        },
        index=index,
    )


def _splits_series(entries: list[tuple[str, float]]) -> pd.Series:
    index = pd.DatetimeIndex([date for date, _ in entries]).tz_localize("UTC")
    return pd.Series([ratio for _, ratio in entries], index=index)


def _datafeed(
    earnings: pd.DataFrame | None = None,
    ratings: pd.DataFrame | None = None,
    splits: pd.Series | None = None,
) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_earnings_dates.return_value = earnings if earnings is not None else pd.DataFrame()
    datafeed.get_upgrades_downgrades.return_value = (
        ratings if ratings is not None else pd.DataFrame()
    )
    datafeed.get_splits.return_value = splits if splits is not None else pd.Series(dtype=float)
    return datafeed


def test_symbol_is_uppercased() -> None:
    client = EventsClient("aapl", datafeed=_datafeed())
    assert client.symbol == "AAPL"


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        EventsClient("AAPL", datafeed=_datafeed())
        EventsClient("MSFT", datafeed=_datafeed())

    assert caplog.messages == [EQUICAST_EVENTS_DISCLAIMER]


def test_events_disclaimer_is_not_deduped_by_datafeeds_own_disclaimer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        DatafeedClient()
        EventsClient("AAPL", datafeed=_datafeed())

    assert YFINANCE_DATA_DISCLAIMER in caplog.messages
    assert EQUICAST_EVENTS_DISCLAIMER in caplog.messages


def test_events_empty_data_returns_no_records() -> None:
    client = EventsClient("TSLA", datafeed=_datafeed())
    assert client.events() == []


def test_events_handles_none_earnings_dates() -> None:
    datafeed = _datafeed()
    datafeed.get_earnings_dates.return_value = None
    client = EventsClient("DELISTED", datafeed=datafeed)
    assert client.events() == []


def test_events_earnings_records_include_past_and_future_rows() -> None:
    this_year = datetime.now(UTC).year
    earnings = _earnings_df(
        [
            (f"{this_year}-01-30", None, 2.18, -3.5),
            (f"{this_year}-04-30", 2.30, None, None),
        ]
    )
    client = EventsClient("AAPL", datafeed=_datafeed(earnings=earnings))

    records = client.events()

    assert records == [
        {
            "ticker": "AAPL",
            "event_type": "earnings",
            "date": f"{this_year}-01-30",
            "eps_estimate": None,
            "reported_eps": 2.18,
            "surprise_pct": -3.5,
            "firm": None,
            "from_grade": None,
            "to_grade": None,
            "action": None,
            "ratio": None,
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        },
        {
            "ticker": "AAPL",
            "event_type": "earnings",
            "date": f"{this_year}-04-30",
            "eps_estimate": 2.3,
            "reported_eps": None,
            "surprise_pct": None,
            "firm": None,
            "from_grade": None,
            "to_grade": None,
            "action": None,
            "ratio": None,
            "last_updated": records[1]["last_updated"],
            "source": "yfinance",
        },
    ]


def test_events_rating_records_include_all_fields() -> None:
    this_year = datetime.now(UTC).year
    ratings = _ratings_df(
        [(f"{this_year}-03-01", "Morgan Stanley", "Overweight", "Equal-Weight", "up")]
    )
    client = EventsClient("AAPL", datafeed=_datafeed(ratings=ratings))

    records = client.events()

    assert records == [
        {
            "ticker": "AAPL",
            "event_type": "rating",
            "date": f"{this_year}-03-01",
            "eps_estimate": None,
            "reported_eps": None,
            "surprise_pct": None,
            "firm": "Morgan Stanley",
            "from_grade": "Equal-Weight",
            "to_grade": "Overweight",
            "action": "up",
            "ratio": None,
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        }
    ]


def test_events_rating_record_treats_empty_from_grade_as_none() -> None:
    this_year = datetime.now(UTC).year
    ratings = _ratings_df([(f"{this_year}-03-01", "Morgan Stanley", "Overweight", "", "init")])
    client = EventsClient("AAPL", datafeed=_datafeed(ratings=ratings))

    records = client.events()

    assert records[0]["from_grade"] is None


def test_events_split_records() -> None:
    this_year = datetime.now(UTC).year
    splits = _splits_series([(f"{this_year}-06-09", 4.0)])
    client = EventsClient("AAPL", datafeed=_datafeed(splits=splits))

    records = client.events()

    assert records == [
        {
            "ticker": "AAPL",
            "event_type": "split",
            "date": f"{this_year}-06-09",
            "eps_estimate": None,
            "reported_eps": None,
            "surprise_pct": None,
            "firm": None,
            "from_grade": None,
            "to_grade": None,
            "action": None,
            "ratio": 4.0,
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        }
    ]


def test_events_defaults_to_current_year_only() -> None:
    this_year = datetime.now(UTC).year
    earnings = _earnings_df(
        [
            (f"{this_year - 1}-10-30", None, 1.5, 2.0),
            (f"{this_year}-01-30", None, 2.18, -3.5),
        ]
    )
    ratings = _ratings_df(
        [
            (f"{this_year - 1}-05-01", "Firm A", "Buy", "Hold", "up"),
            (f"{this_year}-03-01", "Firm B", "Overweight", "Equal-Weight", "up"),
        ]
    )
    splits = _splits_series([(f"{this_year - 1}-01-01", 2.0), (f"{this_year}-06-09", 4.0)])
    client = EventsClient(
        "AAPL", datafeed=_datafeed(earnings=earnings, ratings=ratings, splits=splits)
    )

    records = client.events()

    assert [(r["event_type"], r["date"]) for r in records] == [
        ("earnings", f"{this_year}-01-30"),
        ("rating", f"{this_year}-03-01"),
        ("split", f"{this_year}-06-09"),
    ]


def test_events_full_load_returns_every_year() -> None:
    this_year = datetime.now(UTC).year
    earnings = _earnings_df([(f"{this_year - 1}-10-30", None, 1.5, 2.0)])
    client = EventsClient("AAPL", datafeed=_datafeed(earnings=earnings))

    records = client.events(full_load=True)

    assert [r["date"] for r in records] == [f"{this_year - 1}-10-30"]


def test_events_default_uses_default_earnings_dates_limit() -> None:
    datafeed = _datafeed()
    client = EventsClient("AAPL", datafeed=datafeed)

    client.events()

    datafeed.get_earnings_dates.assert_called_once_with("AAPL", limit=EARNINGS_DEFAULT_LIMIT)


def test_events_full_load_uses_higher_earnings_dates_limit() -> None:
    datafeed = _datafeed()
    client = EventsClient("AAPL", datafeed=datafeed)

    client.events(full_load=True)

    datafeed.get_earnings_dates.assert_called_once_with("AAPL", limit=EARNINGS_FULL_LOAD_LIMIT)
