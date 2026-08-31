"""equicast-core: shared AWS storage clients for equicast (S3 market-data
reads, DynamoDB user-profile storage, S3 JSON user-owned data)."""

from equicast_core.accounts import (
    MAX_ACCOUNTS,
    AccountLimitExceededError,
    AccountNotFoundError,
    AccountsClient,
)
from equicast_core.client import MarketDataClient
from equicast_core.user_profiles import UserProfileClient

__version__ = "0.1.0"

__all__ = [
    "MAX_ACCOUNTS",
    "AccountLimitExceededError",
    "AccountNotFoundError",
    "AccountsClient",
    "MarketDataClient",
    "UserProfileClient",
]
