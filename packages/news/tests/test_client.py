import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from equicast_datafeed import YFINANCE_DATA_DISCLAIMER, DatafeedClient
from equicast_datafeed.disclaimers import reset_warned
from equicast_news.client import (
    EQUICAST_NEWS_DISCLAIMER,
    NEWS_DEFAULT_COUNT,
    NEWS_DEFAULT_DAYS,
    NewsClient,
)


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


def _article(
    id_: str = "abc123",
    title: str = "Some headline",
    summary: str | None = "Some summary",
    publisher: str | None = "Reuters",
    click_through_url: str | None = "https://example.com/click",
    canonical_url: str | None = "https://example.com/canonical",
    thumbnail_url: str | None = "https://example.com/thumb.jpg",
    pub_date: str | None = None,
) -> dict:
    content: dict = {
        "title": title,
        "summary": summary,
        "pubDate": pub_date or datetime.now(UTC).isoformat(),
        "provider": {"displayName": publisher} if publisher else {},
    }
    if click_through_url is not None:
        content["clickThroughUrl"] = {"url": click_through_url}
    if canonical_url is not None:
        content["canonicalUrl"] = {"url": canonical_url}
    if thumbnail_url is not None:
        content["thumbnail"] = {"resolutions": [{"url": thumbnail_url}]}
    return {"id": id_, "content": content}


def _datafeed(articles: list[dict] | None = None) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_news.return_value = articles if articles is not None else []
    return datafeed


def test_symbol_is_uppercased() -> None:
    client = NewsClient("aapl", datafeed=_datafeed())
    assert client.symbol == "AAPL"


def test_constructing_client_shows_disclaimer_once(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        NewsClient("AAPL", datafeed=_datafeed())
        NewsClient("MSFT", datafeed=_datafeed())

    assert caplog.messages == [EQUICAST_NEWS_DISCLAIMER]


def test_news_disclaimer_is_not_deduped_by_datafeeds_own_disclaimer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        DatafeedClient()
        NewsClient("AAPL", datafeed=_datafeed())

    assert YFINANCE_DATA_DISCLAIMER in caplog.messages
    assert EQUICAST_NEWS_DISCLAIMER in caplog.messages


def test_news_empty_returns_no_records() -> None:
    client = NewsClient("TSLA", datafeed=_datafeed())
    assert client.news() == []


def test_news_maps_article_fields() -> None:
    pub_date = datetime.now(UTC).isoformat()
    article = _article(
        id_="abc123",
        title="Apple beats estimates",
        summary="Details here",
        publisher="Reuters",
        click_through_url="https://example.com/click",
        canonical_url="https://example.com/canonical",
        thumbnail_url="https://example.com/thumb.jpg",
        pub_date=pub_date,
    )
    client = NewsClient("AAPL", datafeed=_datafeed([article]))

    records = client.news()

    assert records == [
        {
            "ticker": "AAPL",
            "id": "abc123",
            "title": "Apple beats estimates",
            "summary": "Details here",
            "publisher": "Reuters",
            "url": "https://example.com/click",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "published_at": pub_date,
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        }
    ]


def test_news_url_falls_back_to_canonical_when_no_click_through() -> None:
    article = _article(click_through_url=None, canonical_url="https://example.com/canonical")
    client = NewsClient("AAPL", datafeed=_datafeed([article]))

    records = client.news()

    assert records[0]["url"] == "https://example.com/canonical"


def test_news_skips_article_with_no_url() -> None:
    article = _article(click_through_url=None, canonical_url=None)
    client = NewsClient("AAPL", datafeed=_datafeed([article]))

    assert client.news() == []


def test_news_skips_article_with_no_pub_date() -> None:
    article = _article()
    article["content"]["pubDate"] = None
    client = NewsClient("AAPL", datafeed=_datafeed([article]))

    assert client.news() == []


def test_news_thumbnail_url_none_when_no_thumbnail() -> None:
    article = _article(thumbnail_url=None)
    client = NewsClient("AAPL", datafeed=_datafeed([article]))

    records = client.news()

    assert records[0]["thumbnail_url"] is None


def test_news_excludes_articles_older_than_default_window() -> None:
    stale_date = (datetime.now(UTC) - timedelta(days=NEWS_DEFAULT_DAYS + 1)).isoformat()
    fresh_date = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    articles = [
        _article(id_="stale", pub_date=stale_date),
        _article(id_="fresh", pub_date=fresh_date),
    ]
    client = NewsClient("AAPL", datafeed=_datafeed(articles))

    records = client.news()

    assert [record["id"] for record in records] == ["fresh"]


def test_news_respects_custom_days_window() -> None:
    old_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    article = _article(id_="old", pub_date=old_date)
    client = NewsClient("AAPL", datafeed=_datafeed([article]))

    assert client.news(days=5) == []
    assert [record["id"] for record in client.news(days=15)] == ["old"]


def test_news_sorted_newest_first() -> None:
    older = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    newer = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    articles = [
        _article(id_="older", pub_date=older),
        _article(id_="newer", pub_date=newer),
    ]
    client = NewsClient("AAPL", datafeed=_datafeed(articles))

    records = client.news()

    assert [record["id"] for record in records] == ["newer", "older"]


def test_news_passes_count_through_to_datafeed() -> None:
    datafeed = _datafeed()
    client = NewsClient("AAPL", datafeed=datafeed)

    client.news(count=10)

    datafeed.get_news.assert_called_once_with("AAPL", count=10)


def test_news_uses_default_count() -> None:
    datafeed = _datafeed()
    client = NewsClient("AAPL", datafeed=datafeed)

    client.news()

    datafeed.get_news.assert_called_once_with("AAPL", count=NEWS_DEFAULT_COUNT)
