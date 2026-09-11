"""Class-based client for recent news headlines on any yfinance symbol."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from equicast_datafeed import DatafeedClient, warn_once

logger = logging.getLogger(__name__)

#: Shown once per process on the first NewsClient construction. Distinct
#: from equicast-datafeed's own YFINANCE_DATA_DISCLAIMER (rather than
#: reusing it) so it's always visible on its own, the same way
#: equicast-events'/equicast-dividends'/equicast-metrics' disclaimers are -
#: not deduped away just because DatafeedClient already logged theirs
#: earlier in the same process.
EQUICAST_NEWS_DISCLAIMER = (
    "equicast-news: recent news headlines via yfinance (Yahoo Finance), "
    "for educational purposes only - not financial advice."
)

#: Default lookback window - "only past one month, no historical data".
NEWS_DEFAULT_DAYS = 30

#: Articles fetched from yfinance per call - comfortably more than any
#: symbol publishes in a month, so the days-filter (not this count) is what
#: actually bounds the result.
NEWS_DEFAULT_COUNT = 50


class NewsClient:
    """Fetches recent news headlines for any yfinance symbol - generic
    across asset classes, mirroring `equicast-events`' `EventsClient` and
    `equicast-dividends`' `DividendsClient`: a small client built on
    `equicast-datafeed`, reusable by any asset-class package.

    Unlike those, there's no `full_load` option here - yfinance's
    `get_news` only ever returns its own recent-articles window, so there's
    no historical archive to opt into.
    """

    def __init__(self, symbol: str, datafeed: DatafeedClient | None = None) -> None:
        warn_once(logger, EQUICAST_NEWS_DISCLAIMER)
        self.symbol = symbol.upper()
        self._datafeed = datafeed or DatafeedClient()

    def news(
        self, days: int = NEWS_DEFAULT_DAYS, count: int = NEWS_DEFAULT_COUNT
    ) -> list[dict[str, Any]]:
        """Return one record per article published in the trailing `days`
        days, newest first: {ticker, id, title, summary, publisher, url,
        thumbnail_url, published_at, last_updated, source}.

        `url` prefers the article's `clickThroughUrl`, falling back to
        `canonicalUrl` when absent. `thumbnail_url` is the first available
        resolution, or `None` if yfinance reports no thumbnail.
        """
        fetched_at = datetime.now(UTC).isoformat()
        cutoff = datetime.now(UTC) - timedelta(days=days)

        articles = self._datafeed.get_news(self.symbol, count=count)
        records = [
            record
            for article in articles
            if (record := self._record(article, fetched_at)) is not None
            and record["published_at"] >= cutoff.isoformat()
        ]
        records.sort(key=lambda record: record["published_at"], reverse=True)
        return records

    def _record(self, article: dict[str, Any], fetched_at: str) -> dict[str, Any] | None:
        content = article.get("content") or {}
        published_at = content.get("pubDate")
        if not published_at:
            return None

        click_through = content.get("clickThroughUrl") or {}
        canonical = content.get("canonicalUrl") or {}
        url = click_through.get("url") or canonical.get("url")
        if not url:
            return None

        thumbnail = content.get("thumbnail") or {}
        resolutions = thumbnail.get("resolutions") or []
        thumbnail_url = resolutions[0].get("url") if resolutions else None

        provider = content.get("provider") or {}

        return {
            "ticker": self.symbol,
            "id": article.get("id"),
            "title": content.get("title"),
            "summary": content.get("summary") or content.get("description"),
            "publisher": provider.get("displayName"),
            "url": url,
            "thumbnail_url": thumbnail_url,
            "published_at": published_at,
            "last_updated": fetched_at,
            "source": "yfinance",
        }
