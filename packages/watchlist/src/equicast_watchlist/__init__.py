"""equicast-watchlist: builds a system watchlist's entries fresh from
yfinance, on top of equicast-fx/-benchmark/-future."""

from equicast_watchlist.builder import build_entries, build_entry
from equicast_watchlist.config import WatchlistEntry, load_watchlist_entries

__version__ = "0.1.0"

__all__ = [
    "build_entries",
    "build_entry",
    "WatchlistEntry",
    "load_watchlist_entries",
]
