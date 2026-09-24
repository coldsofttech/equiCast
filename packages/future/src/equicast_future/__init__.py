"""equicast-future: class-based futures contract data extraction."""

from equicast_future.client import FutureClient
from equicast_future.config import Future, load_futures, parse_futures_json

__version__ = "0.1.0"

__all__ = ["FutureClient", "Future", "load_futures", "parse_futures_json"]
