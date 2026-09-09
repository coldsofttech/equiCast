"""equicast-forecasting: project future dividend payouts from actual
dividend history, and (see fx_forecast.py) daily FX price probability
bands from actual price history plus available macro/rate data."""

from equicast_forecasting.bands import price_bands
from equicast_forecasting.forecast import dividends
from equicast_forecasting.fx_forecast import fx_price_bands
from equicast_forecasting.volatility import estimate_daily_volatility

__version__ = "0.1.0"

__all__ = ["dividends", "estimate_daily_volatility", "fx_price_bands", "price_bands"]
