"""equicast-news: recent news headlines (trailing ~30 days, no historical
archive) for any yfinance symbol."""

from equicast_news.client import NewsClient

__version__ = "0.1.0"

__all__ = ["NewsClient"]
