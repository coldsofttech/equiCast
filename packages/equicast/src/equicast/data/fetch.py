"""Fetch market data from Yahoo Finance via yfinance."""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download historical OHLCV data for a single ticker."""
    data = yf.Ticker(ticker).history(period=period, interval=interval)
    data.index.name = "date"
    return data.reset_index()
