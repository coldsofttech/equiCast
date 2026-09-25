"""equicast-watchlist: builds a system watchlist's entries fresh from
yfinance, on top of equicast-fx/-benchmark/-future/-stock/-etf."""

from equicast_watchlist.builder import build_entries, build_entry
from equicast_watchlist.config import WatchlistEntry, load_watchlist_entries
from equicast_watchlist.movers import (
    TickerCagr,
    compute_cagr_rankings,
    load_rankings,
    select_top,
    write_rankings,
)

__version__ = "0.1.0"

__all__ = [
    "build_entries",
    "build_entry",
    "WatchlistEntry",
    "load_watchlist_entries",
    "TickerCagr",
    "compute_cagr_rankings",
    "load_rankings",
    "select_top",
    "write_rankings",
]
