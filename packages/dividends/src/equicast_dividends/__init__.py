"""equicast-dividends: generic dividend history for any yfinance equity-like symbol."""

from equicast_dividends.client import DividendsClient
from equicast_dividends.frequency import dividend_frequency

__version__ = "0.1.0"

__all__ = ["DividendsClient", "dividend_frequency"]
