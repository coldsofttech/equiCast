"""equicast-core: shared AWS storage clients for equicast (S3 market-data
reads, DynamoDB user-profile storage)."""

from equicast_core.client import MarketDataClient
from equicast_core.user_profiles import UserProfileClient

__version__ = "0.1.0"

__all__ = ["MarketDataClient", "UserProfileClient"]
