"""equicast-datafeed: resilient yfinance-backed market data client."""

from equicast_datafeed.client import DatafeedClient
from equicast_datafeed.exceptions import DatafeedError

__version__ = "0.1.0"

__all__ = ["DatafeedClient", "DatafeedError"]
