"""equicast-forecasting: project future dividend payouts from actual
dividend history, daily FX price probability bands from actual price
history plus available macro/rate data (fx_forecast.py), daily
sector-routed stock price probability bands from actual price/
fundamentals data (stock_forecast.py), and daily ETF-type-routed price
probability bands from actual price/fund data (etf_forecast.py)."""

from equicast_forecasting.bands import price_bands
from equicast_forecasting.etf_forecast import etf_price_bands
from equicast_forecasting.etf_type_registry import UnroutableEtfTypeError, route_etf_type
from equicast_forecasting.forecast import dividends
from equicast_forecasting.fx_forecast import fx_price_bands
from equicast_forecasting.monte_carlo import monte_carlo_bands
from equicast_forecasting.sector_registry import UnroutableSectorError, route_sector
from equicast_forecasting.stock_forecast import stock_price_bands
from equicast_forecasting.volatility import estimate_daily_volatility

__version__ = "0.1.0"

__all__ = [
    "UnroutableEtfTypeError",
    "UnroutableSectorError",
    "dividends",
    "estimate_daily_volatility",
    "etf_price_bands",
    "fx_price_bands",
    "monte_carlo_bands",
    "price_bands",
    "route_etf_type",
    "route_sector",
    "stock_price_bands",
]
