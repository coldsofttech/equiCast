"""equicast-datafeed: resilient yfinance-backed market data client."""

from equicast_datafeed.client import DatafeedClient
from equicast_datafeed.exceptions import DatafeedError
from equicast_datafeed.rounding import DECIMAL_PRECISION, round_value

__version__ = "0.1.0"

__all__ = ["DatafeedClient", "DatafeedError", "DECIMAL_PRECISION", "round_value"]
