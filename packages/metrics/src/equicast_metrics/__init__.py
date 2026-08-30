"""equicast-metrics: generic risk/performance metrics for any yfinance symbol."""

from equicast_metrics.client import MetricsClient
from equicast_metrics.exceptions import UnsupportedSymbolError

__version__ = "0.1.0"

__all__ = ["MetricsClient", "UnsupportedSymbolError"]
