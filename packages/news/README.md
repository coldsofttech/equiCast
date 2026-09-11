# equicast-news

Generic recent news headlines for any yfinance symbol — a stock, ETF, or
benchmark ticker, since the underlying data is shaped the same way
regardless of asset class. Mirrors `equicast-events`' `EventsClient` and
`equicast-dividends`' `DividendsClient` in spirit: a small, generic client
built on `equicast-datafeed`, reusable by any asset-class package rather
than living inside one.

Unlike those packages, there's no `full_load` option and no historical
archive — yfinance's `get_news` only ever returns its own recent-articles
window, and this package further trims that down to the trailing month by
design (see below).

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing a `NewsClient` logs this as a one-line warning the first time
it happens in a process. Like `equicast-events`/`equicast-dividends`, this
uses its own distinct message rather than reusing `equicast-datafeed`'s —
so it's always visible even when `DatafeedClient`'s disclaimer already
fired earlier in the same process (e.g. constructed first in a CLI's
`run()`).

## Usage

```python
from equicast_news import NewsClient

NewsClient("AAPL").news()
# [{"ticker": "AAPL", "id": "abc123", "title": "Apple beats estimates",
#   "summary": "Details here", "publisher": "Reuters",
#   "url": "https://example.com/click", "thumbnail_url": "https://example.com/thumb.jpg",
#   "published_at": "2026-08-30T09:00:00+00:00",
#   "last_updated": "2026-08-30T09:05:00+00:00", "source": "yfinance"}, ...]
```

`news()` returns one record per article published in the trailing 30 days
(`days=` is overridable), newest first — "only past one month entries, no
historical data" by design, not just a yfinance limitation. `url` prefers
the article's `clickThroughUrl`, falling back to `canonicalUrl` when
absent; an article with neither a URL nor a publish date is dropped
entirely, since both are required to safely link to and date-filter it.
`thumbnail_url` is the first resolution yfinance reports, or `None` when it
reports none.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src
```
